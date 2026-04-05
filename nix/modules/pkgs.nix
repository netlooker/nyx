{
  inputs,
  lib,
  ...
}:
{
  imports = [
    inputs.pkgs-by-name-for-flake-parts.flakeModule
  ];

  systems = lib.systems.flakeExposed;

  perSystem =
    { system, ... }:
    {
      pkgsDirectory = ../pkgs;
      _module.args.pkgs = import inputs.nixpkgs {
        inherit system;
        overlays = [ inputs.ec-lib.overlays.default ];
      };
    };
}
