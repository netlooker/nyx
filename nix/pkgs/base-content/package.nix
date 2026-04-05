{
  lib,
  symlinkJoin,
  bashInteractive,
  cacert,
  stdenv,
  gitMinimal,
  gh,
  python3,
  python3Packages,
  uv,
  nodejs,
  cmake,
  gcc,
  pkg-config,
  gnumake,
  gnutar,
  gzip,
  unzip,
  zip,
  jq,
  yq-go,
  ripgrep,
  fd,
  gnused,
  gawk,
  diffutils,
  coreutils,
  findutils,
  tree,
  file,
  less,
  which,
  curl,
  wget,
  openssh,
  sqlite,
  gnupg,
  openssl,
  bat,
  eza,
  htop,
  rtk,
  hugo,
  pandoc,
  calibre,
  netlooker,
}:
symlinkJoin {
  name = "nyx-base-content";
  paths = [
    # --- Core runtime ---
    bashInteractive
    coreutils
    cacert
    stdenv.cc.cc.lib # exposes libstdc++.so.6 to pip-installed binary wheels

    # --- Version control ---
    gitMinimal
    gh # GitHub CLI — issues, PRs, comments, push

    # --- Languages & package managers ---
    python3
    python3Packages.pip
    python3Packages.virtualenv
    uv # fast Python package manager
    nodejs # bundles npm in its own bin/

    # --- Native build tools ---
    cmake
    gcc
    pkg-config
    gnumake

    # --- Archive & compression ---
    gnutar
    gzip
    unzip
    zip

    # --- Text processing & search ---
    jq
    yq-go # jq but for YAML/TOML
    ripgrep
    fd
    gnused
    gawk
    diffutils

    # --- File & system utilities ---
    coreutils
    findutils
    tree
    file
    less
    which

    # --- Network ---
    curl
    wget
    openssh # ssh, scp, ssh-keygen

    # --- Database ---
    sqlite

    # --- Security & crypto ---
    gnupg
    openssl

    # --- Terminal quality-of-life ---
    bat
    eza
    htop
    rtk # token optimizer — reduces LLM token consumption

    # --- Content tools ---
    hugo # static site generator
    pandoc # document conversion
  ]
  ++ lib.optionals stdenv.isLinux [
    calibre # ebook conversion (Linux only)
  ]
  ++ [
    # --- Netlooker apps (pinned by rev+hash, bumped via just update-synapse) ---
    netlooker.synapse # semantic retrieval engine
  ];
}
