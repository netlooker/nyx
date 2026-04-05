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

  perSystem = {
    pkgsDirectory = ../pkgs;
  };
}
