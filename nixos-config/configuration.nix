{ config, pkgs, lib, ... }:

{
  imports = [ ];

  # Bootloader.
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "nixos-agent";
  networking.networkmanager.enable = true;
  networking.useDHCP = lib.mkDefault true;

  time.timeZone = "UTC";
  i18n.defaultLocale = "en_US.UTF-8";

  # Enable the OpenSSH daemon.
  services.openssh.enable = true;
  services.openssh.settings.PermitRootLogin = "prohibit-password";
  services.openssh.settings.PasswordAuthentication = true;

  # VMware guest additions for seamless host integration
  virtualisation.vmware.guest.enable = true;

  # Sub-agent sandboxing engine for NemoClaw/OpenShell
  virtualisation.docker.enable = true;

  # Ensure the primary user has sudo and network setup
  users.users.agent = {
    isNormalUser = true;
    description = "NemoClaw Agent Primary User";
    extraGroups = [ "networkmanager" "wheel" "docker" ];
    initialPassword = "123"; # Temporary password, change immediately!
  };

  # Authorize the Mac host SSH key out-of-band to protect host identity from git
  users.users.root.openssh.authorizedKeys.keyFiles = [
    "/etc/nixos/secrets/authorized_keys"
  ];
  users.users.agent.openssh.authorizedKeys.keyFiles = [
    "/etc/nixos/secrets/authorized_keys"
  ];

  # Allow unfree packages since AI often uses NVIDIA driver/closed sources dependencies
  nixpkgs.config.allowUnfree = true;

  # Enable Flakes natively
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Essential developer and system utilities
  environment.systemPackages = with pkgs; [
    git
    vim
    wget
    curl
    direnv
    htop
    parted
    jq
  ];

  # Protect state version
  system.stateVersion = "24.11"; 
}
