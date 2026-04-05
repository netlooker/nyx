{
  lib,
  dockerTools,
  bashInteractive,
  base-content,
  fhs-compat-layer,
  coreutils,
  cacert,
  ...
}:
dockerTools.buildLayeredImage {
  name = "nyx-base-image";
  tag = "latest";
  contents = [
    base-content
    fhs-compat-layer
    coreutils
  ];
  config = {
    Cmd = [ (lib.getExe bashInteractive) ];
    Env = [
      "PATH=${base-content}/bin:/bin"
      "SSL_CERT_FILE=${cacert}/etc/ssl/certs/ca-bundle.crt"
      "HOME=/root"
    ];
  };
}
