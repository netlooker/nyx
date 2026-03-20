{
  description = "Pragmatic NyxClaw (OpenClaw) Environment";

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
      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          # The isolated toolchains required for OpenClaw
          nyxclawPaths = with pkgs; [
            bashInteractive
            coreutils
            cacert
            python3
            python3Packages.pip
            python3Packages.virtualenv
            nodejs
            nodePackages.pnpm
            cmake
            gcc
            pkg-config
            gnumake
            syft
          ];

          # Combine the paths cleanly
          sbomContent = pkgs.symlinkJoin {
            name = "nyxclaw-base-content";
            paths = nyxclawPaths;
          };

          # Generate the cryptographically pure SBOM using Bombon
          baseSbom = bombon.lib.${system}.buildBom sbomContent {};

        in {
          base-image = pkgs.dockerTools.buildLayeredImage {
            name = "nyxclaw-base-image";
            tag = "latest";
            contents = [ sbomContent baseSbom pkgs.coreutils ]; # Include coreutils for /usr/bin/env compatibility
            config = {
              Cmd = [ "/bin/bash" ];
              Env = [
                "PATH=${sbomContent}/bin:/bin"
                "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
              ];
            };
          };
        }
      );

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            name = "nyxclaw-env";
            
            buildInputs = with pkgs; [
              # 1. Python Toolchain
              python3
              python3Packages.pip
              python3Packages.virtualenv

              # 2. Node Toolchain (Pure binary, dirty project)
              nodejs # Latest native version
              nodePackages.pnpm
              
              # 3. Base compilation systems required for native Node bindings (node-gyp, sqlite, websockets)
              cmake
              gcc
              pkg-config
              gnumake

              # 4. Security Scanning
              syft
            ];

            shellHook = ''
              echo "==========================================================="
              echo " 🤖 Welcome to the NyxClaw Agent Environment (''${system})"
              echo " Python: $(python3 --version)"
              echo " Node: $(node --version)"
              echo "==========================================================="
              echo "💡 Tip: You can run standard 'npm install' and 'pip install' here without fighting Nix!"
              
              # Declarative out-of-band secret configuration
              export OPENCLAW_CONFIG_PATH="$PWD/secrets/openclaw.json5"
              
              if [ ! -f "$OPENCLAW_CONFIG_PATH" ]; then
                echo "🔑 First time setup: Bootstrapping generic config into secrets/"
                mkdir -p secrets
                cp openclaw.example.json5 secrets/openclaw.json5
              fi
            '';
          };
        }
      );
    };
}
