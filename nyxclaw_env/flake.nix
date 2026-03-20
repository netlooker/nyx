{
  description = "Pragmatic NyxClaw (OpenClaw) Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-linux" "aarch64-darwin" "x86_64-linux" "x86_64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
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
              
              # 3. Base compilation systems required for native ARM AI compilation (llama.cpp / bindings)
              cmake
              gcc
              pkg-config
              # gnumake is not required as make is available, but added if needed. On Darwin, use gnumake.
              gnumake
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
