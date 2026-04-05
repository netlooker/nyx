{
  perSystem =
    { pkgs, system, ... }:
    {
      devShells = {
        default = pkgs.mkShell {
          name = "nyx";
          buildInputs =
            with pkgs;
            [
              git
              python3
              python3Packages.pip
              nodejs # bundles npm in its own bin/
              just
              age
              rtk
            ]
            ++ lib.optionals pkgs.stdenv.isLinux [ pkgs.bubblewrap ];

          shellHook = ''
            echo "nyx dev shell (${system})"
            if [ ! -f "$PWD/secrets/openclaw.json5" ]; then
              echo "warning: secrets/openclaw.json5 not found — cp container/openclaw.json5.example secrets/openclaw.json5"
            fi
          '';
        };
      };
    };
}
