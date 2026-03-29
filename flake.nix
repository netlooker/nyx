{
  description = "Nyx — reproducible cortex environment for OpenClaw";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    bombon.url = "github:nikstur/bombon";
  };

  outputs = { self, nixpkgs, bombon }:
    let
      systems = [ "aarch64-linux" "aarch64-darwin" "x86_64-linux" "x86_64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
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

          # Every tool that must exist inside the container.
          # Pinned by the flake.lock — no version drift, no surprises.
          basePaths = with pkgs; [
            bashInteractive
            coreutils
            cacert
            git
            stdenv.cc.cc.lib   # exposes libstdc++.so.6 to pip-installed binary wheels
            python3
            python3Packages.pip
            python3Packages.virtualenv
            nodejs
            nodePackages.npm
            # Native build tools — needed by openclaw and agent npm packages
            cmake
            gcc
            pkg-config
            gnumake
            gnutar
            gzip
            # Utilities — text processing, search, file management
            jq
            ripgrep
            fd
            unzip
            zip
            # Terminal quality-of-life
            bat
            eza
            htop
            # GitHub CLI — agent can open issues, PRs, comment, push
            gh
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
          # Used by the multi-stage Dockerfile (cortex/Dockerfile stage 1).
          # Produces a single directory with symlinks into the Nix store —
          # Docker copies /nix/store + this directory into the final image.
          base-content = baseContent;

          # Standalone Docker image tar — useful for CI or manual inspection.
          # Load with: nix build .#base-image && docker load < result
          base-image = pkgs.dockerTools.buildLayeredImage {
            name = "nyx-base-image";
            tag = "latest";
            contents = [ baseContent sbomDir fhsCompat pkgs.coreutils ];
            config = {
              Cmd = [ "/bin/bash" ];
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
              nodejs
              nodePackages.npm
              just
              age
            ] ++ sandboxTools;

            shellHook = ''
              echo "nyx dev shell (${system})"
              if [ ! -f "$PWD/secrets/openclaw.json5" ]; then
                echo "warning: secrets/openclaw.json5 not found"
              fi
            '';
          };
        }
      );
    };
}
