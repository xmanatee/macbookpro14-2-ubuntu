# Ubuntu on the 2017 13-inch Touch Bar MacBook Pro

A source-only preparation kit and field guide for turning **MacBookPro14,2 (A1706, Intel, Apple T1)** into an Ubuntu server. It documents a real migration, including the Wi-Fi calibration, kernel/DKMS dependencies and T1 firmware problem that generic installation guides miss.

**Reference system:** Ubuntu 26.04 LTS, kernel `7.0.0-38-generic`, i7-7567U, Iris Plus 650, BCM43602. Other models, newer kernels and T2 Macs are **not qualified by this project**. This is a community recipe, not an Apple or Canonical supported hardware configuration.

```text
Ubuntu signed cloud image + pinned driver sources
                       │
Your private profile ──┤  Wi-Fi, SSH public key, target MAC, optional own T1 files
                       ▼
                 QEMU image build
                       │
                Cold-boot checks
                       ▼
               Private external disk
                       │
             Physical hardware acceptance
                       ▼
              Optional full-SSD install
```

## Start here

1. Read the [hardware evidence and limitations](docs/hardware.md). Have a verified backup, macOS recovery route and a working display available for the first boot. **A broken screen does not make firmware selection remotely controllable.**
2. While macOS still works, preserve the target's original Wi-Fi MAC and any available [T1 identity files](docs/recovery.md). Do not erase macOS before resolving missing T1 files if you need the Touch Bar.
3. Install Python 3.10+, Git and a working Docker engine on the build computer. On Apple Silicon, QEMU runs natively in the Linux container and emulates the Intel target; no privileged host-device container is needed. Review the scripts before running them.
4. Clone and create a private profile:

   ```sh
   git clone https://github.com/xmanatee/macbookpro14-2-ubuntu.git
   cd macbookpro14-2-ubuntu
   python3 scripts/profile.py
   ```

   Enter WPA2 personal networks in preferred order. Password entry is hidden. The key must be an **Ed25519 public key**. Enable `headless` for an always-on server; audio, a small Touch Bar display, Docker and Tailscale are explicit options.
5. Build once:

   ```sh
   ./scripts/build-container.sh
   ```

   Allow several GB of downloads, **at least 25 GiB free workspace** and potentially hours under x86 emulation. The VM installs packages, builds DKMS modules, installs removable-path UEFI GRUB, then cold-boots through an emulated NVMe controller without its provisioning disk. Progress and receipts are in `.work/build/`. It does not enroll Tailscale or touch a physical disk.
6. [Inspect, write and verify an external disk](docs/install.md), then complete the physical acceptance checklist. Only then consider replacing macOS.

**Never publish `.private/`, `.work/`, captured EFI files, build logs or generated images.** The image contains Wi-Fi passwords, a unique SSH host identity and a key-authorized administrator. One image belongs to one physical target. Git ignores these directories; they are also excluded from the Docker build context.

## What is automated

| Area | Mechanism |
|---|---|
| Image | Signed Ubuntu base; SHA-256 pinned community sources; unprivileged QEMU guest |
| Wi-Fi | NetworkManager profiles, ordered autoconnect priorities, permanent target MAC, BCM43602 calibration, user-selected country |
| SSH | Key-only login; root/password/keyboard-interactive login disabled |
| Hardware | Stock Intel/SPI/NVMe/USB drivers; pinned T1 DKMS; optional matched-source audio DKMS |
| Touch Bar | Preset control strip, or optional local read-only DRM status example with Escape |
| Headless policy | Lid ignored; suspend/hibernate disabled; UPower critical-battery shutdown |
| Updates | Automatic distribution security userspace updates; attended kernel/firmware/boot changes |
| Privacy | No reporting agent added; crash/popularity upload packages removed; connectivity/news probes disabled |
| Optional tools | Docker from its signed official repository; Tailscale from its signed official repository, client logging opted out before first start |

The generated administrator has a locked password and passwordless sudo. Root is locked. This is intentional for key-managed headless access: possession of the administrator's SSH private key grants root access. Set a local administrator password with `sudo passwd USERNAME` after boot if you need console login. No default or shared password is generated.

## Read next

- [Installation and physical acceptance](docs/install.md)
- [Hardware: what works, what was only detected, what remains unproven](docs/hardware.md)
- [Recovery, T1 identity and boot limitations](docs/recovery.md)
- [Updates, diagnostics, power and optional tools](docs/maintenance.md)
- [Source provenance and licenses](THIRD_PARTY.md)

## Validation and contributions

```sh
python3 -m unittest discover -s tests -v
shellcheck scripts/*.sh
python3 -m compileall -q scripts touchbar
```

`./scripts/build-container.sh --validate-only` exercises the full guest installation and cold boot without exporting the image. It is an explicit, expensive local check; CI runs input/disk safety tests and syntax checks only. An existing `.work/build` is never silently reused or rebuilt. Keep the completed image; archive/remove that build directory intentionally when changing a recipe or profile.

[Validation record](docs/validation.md) separates the original physical deployment from the extracted public kit. Contributions should state the exact model, distro, kernel and physical checks performed. Do not attach identities, full system dumps or personalized firmware.

MIT for this project's scripts and documentation. Third-party drivers and firmware keep their own licenses; no third-party binaries or proprietary device credentials are distributed here.
