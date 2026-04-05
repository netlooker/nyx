{
  runCommand,
  inputs,
  base-content,
  stdenv,
  ...
}:
let
  baseSbom = inputs.bombon.lib.${stdenv.hostPlatform.system}.buildBom base-content { };
in
runCommand "sbom-dir" { } ''
  mkdir -p $out/app
  cp ${baseSbom} $out/app/sbom-base.json
''
