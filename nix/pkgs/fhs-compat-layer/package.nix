{
  runCommand,
  bashInteractive,
  coreutils,
}:
runCommand "fhs-compat" { } ''
  mkdir -p $out/bin $out/usr/bin
  ln -s ${bashInteractive}/bin/bash $out/bin/sh
  ln -s ${coreutils}/bin/env $out/usr/bin/env
''
