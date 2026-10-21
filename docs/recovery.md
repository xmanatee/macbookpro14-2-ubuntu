# Recovery and Apple T1 identity

## Before erasing macOS

Update Apple's firmware through supported macOS while you still can. A Linux package update is not an Apple Boot ROM update. Keep recovery media and a tested backup. Apple documents [Intel startup-key combinations](https://support.apple.com/en-us/102603), [external startup disks](https://support.apple.com/en-ie/111336) and the [Intel boot process](https://support.apple.com/guide/security/boot-process-sec5d0fab7c6/web).

macOS `bless --nextonly` is not universally available for arbitrary external EFI selection: SIP/firmware configuration may reject it. VNC and ordinary SSH stop at reboot and cannot control Recovery, FileVault unlock or the firmware picker. Holding Command-R does not itself restart a running Mac. Do not disable SIP blindly or describe an untested key sequence as guaranteed.

A kernel panic can trigger `panic=60`. That does **not** restart a hung firmware picker, a kernel stuck before its panic path, an absent network driver or a machine waiting in macOS Recovery. A systemd watchdog operates only once Linux and that service are running. There is no promised automatic return to macOS in this kit.

## Preserve this Mac's embeddedOS files

The T1 has its own embeddedOS. A kernel driver can enumerate without a functional T1 firmware state. These device-personalized files matter:

```text
EFI/APPLE/EMBEDDEDOS/combined.memboot
EFI/APPLE/EMBEDDEDOS/FDRData
EFI/APPLE/EMBEDDEDOS/version.plist
```

They may already be staged on the target's EFI System Partition; **not every macOS installation has all three there**. Inspect `diskutil list`, identify the target's EFI partition, mount it with `sudo diskutil mount PARTITION`, then use its actual mount path:

```sh
./scripts/capture-macos.sh /Volumes/EFI/EFI/APPLE/EMBEDDEDOS
```

Run this on the target Mac in macOS. It copies exactly three non-empty files into `.private/EMBEDDEDOS`, refusing to overwrite an existing capture. The builder includes that fixed allowlist in the private image. Keep a separately encrypted backup; an image stored only on the disk you erase is not a backup.

These files are **not public driver dependencies**. Never attach them to issues, distribute them in images, use another Mac's FDRData or replace device identity records with a downloaded donor set. Their presence/size alone does not prove they are valid for a different Mac.

## Dark or non-booting T1

First check USB enumeration, configuration and driver state. Do not start a firmware reset because a DKMS module is missing:

```sh
lsusb -d 05ac:8600
dkms status
journalctl -b -k | grep -Ei 'ibridge|touchbar|appletb|firmware'
cat /etc/modprobe.d/apple-touchbar.conf
```

The safe bridge option is `skip_acpi_power=1`. Never call `ASOC.SOCW(1)`. For preset mode, USB configuration 1 and the `apple_ibridge` / `apple_touchbar` modules are expected. A custom DRM display instead uses configuration 2 and `appletbdrm`; they are mutually exclusive owners.

If the optional display fails, `sudo systemctl stop macbook-touchbar` restores preset mode through `ExecStopPost`; inspect `journalctl -u macbook-touchbar` for the actual failure. Repeated start failures are rate-limited rather than causing endless device resets. Do not run competing Touch Bar renderers or generic installers on top.

If the T1 actually lacks valid personalized firmware, treat it as **attended expert recovery**. The physical migration required regenerating/staging this Mac's own files using [niconistal/t1-revive](https://github.com/niconistal/t1-revive). That is a small, evolving community project that performs device recovery; it is not part of automatic image provisioning. Review its current prerequisites, pinned source, tests, USB ownership and exact ACPI path before running it. Keep AC power and known-good backups. It can need Apple signing/network services and original factory records; availability is not guaranteed.

Do not copy an old private recovery transcript into a generic installer. If files are missing and you cannot validate a device-specific recovery path, retain macOS and stop before erasing it. Touch ID requires additional software and is not configured here.

## Network / update failure

- With local access: `nmcli device`, `nmcli connection show`, `journalctl -u NetworkManager -b`; explicitly activate a known profile. A connected network without internet may remain connected.
- With a previous kernel: select its GRUB advanced entry using a display, inspect the failed DKMS build and rebuild against matching headers/source. Do not delete the working kernel first.
- With a bad bootloader or dead network: boot known-good external recovery media. Mount and back up the intended internal filesystems before changing them. Do not overwrite the EFI/APPLE tree while repairing GRUB.
- With a frozen machine: physical power-button recovery may be required. Avoid it during disk writes; no ordinary remote tool can guarantee recovery from every firmware/kernel failure.
