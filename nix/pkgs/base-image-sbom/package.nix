
{
  dockerTools,
  base-image,
  sbom-dir,
  ...
}:
dockerTools.buildLayeredImage {
  name = "nyx-base-image";
  tag = "latest";
  fromImage = base-image;
  contents = [
    sbom-dir
  ];
}
