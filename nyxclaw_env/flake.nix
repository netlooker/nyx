{
  description = "Pragmatic NyxClaw (OpenClaw) Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "aarch64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        name = "nyxclaw-env";
        
        buildInputs = with pkgs; [
          # 1. Python Toolchain
          python311
          python311Packages.pip
          python311Packages.virtualenv

          # 2. Node Toolchain (Pure binary, dirty project)
          nodejs # Latest native version
          
          # 3. Base compilation systems required for native ARM AI compilation (llama.cpp / bindings)
          cmake
          gcc
          gnumake
          pkg-config
        ];

        shellHook = ''
          echo "==========================================================="
          echo " 🤖 Welcome to the NyxClaw Agent Environment "
          echo " Python: $(python3 --version)"
          echo " Node: $(node --version)"
          echo "==========================================================="
          echo "💡 Tip: You can run standard 'npm install' and 'pip install' here without fighting Nix!"
        '';
      };
    };
}
