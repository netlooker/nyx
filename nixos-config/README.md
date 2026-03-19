# Declarative NemoClaw NixOS Agent

This repository contains the pure Nix Flake configuration for the `aarch64` NemoClaw AI Agent environment optimized for VMware Fusion on Apple Silicon.

## Phase 1: Bootstrapping the VM (Manual Steps)

Because NixOS needs bare-metal partitions mounted before a Flake can be installed, the following steps must be executed manually on any brand-new VM before applying this repository.

### 1. VM Provisioning
1. Download the [NixOS Minimal `aarch64` ISO](https://nixos.org/download/).
2. Create a new VMware Virtual Machine:
   - **Guest OS:** Other Linux 6.x kernel 64-bit Arm
   - **Firmware:** UEFI
   - **Specs:** 4 vCPUs, 4GB RAM, 16GB NVMe (adjust based on inference needs).
   - **Network:** Share with my Mac (NAT).
3. Boot into the live ISO.

### 2. Disk Partitioning
Once at the root shell (`sudo su -`), identify your disk (e.g., `/dev/nvme0n1`) and run:
```bash
# Create partition table and layout
parted /dev/nvme0n1 -s -- mklabel gpt
parted /dev/nvme0n1 -s -- mkpart root ext4 512MB -2GB
parted /dev/nvme0n1 -s -- mkpart swap linux-swap -2GB 100%
parted /dev/nvme0n1 -s -- mkpart ESP fat32 1MB 512MB
parted /dev/nvme0n1 -s -- set 3 esp on
```

### 3. Formatting and Mounting
```bash
# Format partitions
mkfs.ext4 -F -L nixos /dev/nvme0n1p1
mkswap -L swap /dev/nvme0n1p2
mkfs.fat -F 32 -n boot /dev/nvme0n1p3

# Mount for installation
swapon /dev/nvme0n1p2
mount /dev/disk/by-label/nixos /mnt
mkdir -p /mnt/boot
mount /dev/disk/by-label/boot /mnt/boot
```

### 4. Hardware Configuration
Generate the initial hardware mounts specific to this VM:
```bash
nixos-generate-config --root /mnt
```
*Note: Any new `hardware-configuration.nix` generated here should be copied into this Git repository if the underlying VM hardware changes significantly.*

---

## Phase 2: Declarative Installation (Flake)

Once the raw VM is partitioned and mounted, this repository's Flake completely takes over. The deployment is entirely declarative, leveraging exactly two foundational files to define the OS:

1. `flake.nix`: Targets the `aarch64-linux` architecture and explicitly tracks the `nixos-unstable` branch to ensure we have access to the absolute latest ML/AI tooling required by NemoClaw.
2. `configuration.nix`: Declares the inner OS rules, including bridging VMware Fusion tools seamlessly, configuring user permissions, pre-baking developer CLI utilities, and natively importing the host Mac's SSH keys for passwordless remote administration.

### Managing Secrets (Out-of-Band)
To ensure that repository forks and open-sourcing never expose sensitive data (SSH Public Host IDs or API Tokens), this configuration strictly loads authorization data dynamically from a `.gitignore`'d folder.

**Before applying this configuration on a new machine:**
You MUST manually create `secrets/authorized_keys` alongside `configuration.nix` inside `/etc/nixos/` prior to building. The Flake expects these files to be present on the raw disk.

### Executing the Initial Install
To bootstrap the newly partitioned drive using this repository:
```bash
# From the mac host, initialize the git repository (Flakes require git)
git init && git add .

# Push the configuration to the live USB
scp *.nix root@<VM_IP>:/mnt/etc/nixos/

# Run the flake-based installer inside the VM
nixos-install --flake /mnt/etc/nixos#nixos
```

### Applying Future Updates
After the system completes installation and reboots into its final state, you never need to use `nixos-install` again. To apply any declarative changes made to `configuration.nix` or NemoClaw configurations in the future, simply run:
```bash
sudo nixos-rebuild switch --flake /etc/nixos#nixos
```

---

## Phase 3: The NemoClaw AI Agent Environment

To keep the base NixOS installation totally pristine, the agent dependencies are isolated inside a standard Nix `devShell` located in the `nemoclaw_env/` directory.

### The Hybrid Architecture
Because the Node.js `npm` ecosystem can be incredibly hostile to pure declarative Nix evaluation, we adopted a pragmatic "hybrid" approach:

1. **Pure Toolchains:** `flake.nix` forcefully injects exact, reproducible versions of Python 3.11, NodeJS LTS, and the C++ compiling toolchain (`cmake`, `gcc`, `pkg-config`) into your path.
2. **Impure Dependencies:** The shell intentionally avoids package manager abstractions like `poetry2nix`. You can run `npm install` or `pip install` entirely natively. Any C++ bindings (like `llama.cpp`) will build perfectly against the Nix-sandboxed C++ compilers natively on your `aarch64` M4 Pro hardware.
3. **Direnv Integration:** The provided `.envrc` uses `layout python3` to automatically invoke a local Python `.venv` the moment you enter the directory.

### Initialization & Usage
```bash
cd nemoclaw_env/

# If direnv is installed, authorize it once:
direnv allow

# The environment is now perfectly isolated!
npm install
pip install "nemoclaw>=1.0.0"
```
