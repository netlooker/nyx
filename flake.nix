{
  description = "Nyx — Nix-backed container environment for OpenClaw";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    bombon.url = "github:nikstur/bombon";
  };

  outputs = { self, nixpkgs, bombon }:
    let
      lib = nixpkgs.lib;
      systems = [ "aarch64-linux" "aarch64-darwin" "x86_64-linux" "x86_64-darwin" ];
      forAllSystems = lib.genAttrs systems;
    in
    {
      # ---------------------------------------------------------------------------
      # Base Docker image — built by Nix for precise, auditable toolchain control.
      # Build this on the target Linux arch (aarch64-linux on Apple Silicon).
      # Workflow: `just build-base` → loads nyx-base-image into Docker.
      # ---------------------------------------------------------------------------
      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          # Synapse — semantic retrieval / discovery engine, pinned by git rev.
          # Bumped via `just update-synapse` which rewrites rev + hash in place.
          # Upstream `pydantic-ai` isn't packaged in nixpkgs; we rewrite the
          # dependency to `pydantic-ai-slim` which is what an MCP server needs.
          # `sqlite-vec` version constraint is relaxed to match nixpkgs' pin.
          synapse = pkgs.python3Packages.buildPythonApplication {
            pname = "netlooker-synapse";
            version = "0-unstable-2026-04-07";
            pyproject = true;

            src = pkgs.fetchFromGitHub {
              owner = "netlooker";
              repo = "synapse";
              rev = "a3b4dc869c2b2c21e5bd671b755c5191c8bcc09c";
              hash = "sha256-k2FpFUnR4u/u5wSh7ePEq8Lwp5QGG+tgW8n0HiohKUI=";
            };

            postPatch = ''
              substituteInPlace "pyproject.toml" \
                --replace-fail "pydantic-ai" "pydantic-ai-slim"
            '';

            build-system = with pkgs.python3Packages; [
              uv-build
              setuptools
            ];

            pythonRelaxDeps = [ "sqlite-vec" ];

            # `mcp` is promoted from an optional extra to a core dependency so
            # `synapse-mcp` works out of the box — Nyx always needs the MCP
            # entrypoint, never the bare CLI-only build.
            dependencies = with pkgs.python3Packages; [
              anyio
              mcp
              numpy
              ollama
              pydantic-ai-slim
              sqlite-vec
            ];

            pythonImportsCheck = [ "synapse" ];
          };

          # Every tool that must exist inside the container.
          # Pinned by the flake.lock — no version drift, no surprises.
          basePaths = with pkgs; [
            # --- Core runtime ---
            bashInteractive
            coreutils
            cacert
            stdenv.cc.cc.lib   # exposes libstdc++.so.6 to pip-installed binary wheels

            # --- Version control ---
            git
            gh                 # GitHub CLI — issues, PRs, comments, push

            # --- Languages & package managers ---
            python3
            python3Packages.pip
            python3Packages.virtualenv
            uv                 # fast Python package manager
            nodejs  # bundles npm in its own bin/

            # --- Native build tools ---
            cmake
            gcc
            pkg-config
            gnumake

            # --- Archive & compression ---
            gnutar
            gzip
            unzip
            zip

            # --- Text processing & search ---
            jq
            yq-go              # jq but for YAML/TOML
            ripgrep
            fd
            gnused
            gawk
            diffutils

            # --- File & system utilities ---
            coreutils
            findutils
            tree
            file
            less
            which

            # --- Network ---
            curl
            wget
            openssh            # ssh, scp, ssh-keygen

            # --- Database ---
            sqlite

            # --- Security & crypto ---
            gnupg
            openssl

            # --- Terminal quality-of-life ---
            bat
            eza
            htop
            rtk                # token optimizer — reduces LLM token consumption

            # --- Content tools ---
            hugo               # static site generator
            pandoc             # document conversion
          ] ++ lib.optionals pkgs.stdenv.isLinux [
            pkgs.calibre       # ebook conversion (Linux only)
          ] ++ [
            # --- Netlooker apps (pinned by rev+hash, bumped via just update-synapse) ---
            synapse            # semantic retrieval engine
          ];

          # Merge all paths into one derivation so dockerTools sees a flat tree
          baseContent = pkgs.symlinkJoin {
            name = "nyx-base-content";
            paths = basePaths;
          };

          # Cryptographic SBOM — proves exactly what's in the base layer
          baseSbom = bombon.lib.${system}.buildBom baseContent {};

          sbomDir = pkgs.runCommand "sbom-dir" {} ''
            mkdir -p $out/app
            cp ${baseSbom} $out/app/sbom-base.json
          '';

          # Pure Nix images lack /bin/sh and /usr/bin/env — Node.js child_process
          # and shebang lines need these to exist.
          fhsCompat = pkgs.runCommand "fhs-compat" {} ''
            mkdir -p $out/bin $out/usr/bin
            ln -s ${pkgs.bashInteractive}/bin/bash $out/bin/sh
            ln -s ${pkgs.coreutils}/bin/env $out/usr/bin/env
          '';

        in {
          # Used by the multi-stage Dockerfile (container/Dockerfile stage 1).
          # Produces a single directory with symlinks into the Nix store —
          # Docker copies /nix/store + this directory into the final image.
          base-content = baseContent;

          # Exposed so `just update-synapse` can nix-build it in isolation
          # and the justfile can nix-eval its version string for the image label.
          inherit synapse;

          # Optional SBOM artifact — kept out of the default Docker build path
          # because bombon pulls a large Rust dependency graph.
          sbom-dir = sbomDir;

          # Standalone Docker image tar — useful for CI or manual inspection.
          # Load with: nix build .#base-image && docker load < result
          base-image = pkgs.dockerTools.buildLayeredImage {
            name = "nyx-base-image";
            tag = "latest";
            contents = [ baseContent fhsCompat pkgs.coreutils ];
            config = {
              Cmd = [ (lib.getExe pkgs.bashInteractive) ];
              Env = [
                "PATH=${baseContent}/bin:/bin"
                "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
                "HOME=/root"
              ];
            };
          };

          # Opt-in SBOM variant for compliance-focused builds.
          base-image-sbom = pkgs.dockerTools.buildLayeredImage {
            name = "nyx-base-image";
            tag = "latest-sbom";
            contents = [ baseContent sbomDir fhsCompat pkgs.coreutils ];
            config = {
              Cmd = [ (lib.getExe pkgs.bashInteractive) ];
              Env = [
                "PATH=${baseContent}/bin:/bin"
                "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
                "HOME=/root"
              ];
            };
          };
        }
      );

      # ---------------------------------------------------------------------------
      # Dev shell — local development on Mac without building the Docker image.
      # `cd nyx && direnv allow` drops you here automatically.
      # ---------------------------------------------------------------------------
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          sandboxTools = pkgs.lib.optionals pkgs.stdenv.isLinux [ pkgs.bubblewrap ];
        in
        {
          default = pkgs.mkShell {
            name = "nyx";
            buildInputs = with pkgs; [
              git
              python3
              python3Packages.pip
              nodejs  # bundles npm in its own bin/
              just
              age
              rtk
            ] ++ sandboxTools;

            shellHook = ''
              echo "nyx dev shell (${system})"
              if [ ! -f "$PWD/secrets/openclaw.json5" ]; then
                echo "warning: secrets/openclaw.json5 not found — cp container/openclaw.json5.example secrets/openclaw.json5"
              fi
            '';
          };
        }
      );
    };
}
