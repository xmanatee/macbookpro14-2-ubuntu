# Installation

## 1. Keep a recovery route

Make and test a backup of macOS, data and this Mac's T1 files. Keep a macOS installer/recovery route and a working display. Turn off FileVault only if your own backup/migration plan requires it; this kit does not change SIP, disk encryption, firmware passwords or Apple security settings.

Build on a separate computer with the README commands. Inspect `.work/build/output/verified-boot.json`: it must pass. A VM boot proves an amd64 UEFI image and driver builds, **not Mac firmware, radio reception or physical input**.

The image is a 32 GiB raw disk with an ext4 root and the Ubuntu cloud image's boot partitions. A small EFI System Partition is necessary; one ordinary filesystem partition cannot replace it. The cloud image also retains its separate Linux /boot and tiny BIOS-compatibility partitions. There is no encrypted root or boot-time passphrase. Someone with the disk can read its contents and Wi-Fi credentials.

## 2. Write an external disk from macOS

The disk's existing partition layout and volumes will be replaced. This is image installation, not secure erasure of every old sector. It must be directly connected by USB and larger than 32 GiB (a 64 GB or larger drive is recommended). Run:

```sh
diskutil list external physical
python3 scripts/write-image.py /dev/diskN
```

Replace `/dev/diskN` with the **whole external disk**, not a partition. The second command only prints the disk's identity, size and an authorization token. Compare those with the actual drive, then run the exact command it suggests:

```sh
sudo python3 scripts/write-image.py /dev/diskN --erase-id TOKEN_FROM_INSPECTION
```

The writer refuses internal/virtual/system/source disks and 4Kn-only media, checks the compressed image, unmounts the target, rechecks its identity, writes, reads back **every image byte**, checks SHA-256 and ejects. A failure means the disk is not qualified; do not guess that the partial write is usable. The manifest protects integrity against accidental corruption, not against a malicious person able to replace both image and manifest.

## 3. First physical boot

1. Connect the prepared disk to the target Mac, attach AC and keep the lid open initially. Enable a configured Wi-Fi network or hotspot.
2. Start the Intel Mac holding **Option (⌥)** and select the external **EFI Boot** entry using a working display. Firmware may show several EFI entries. Do not assume a fixed number of arrow presses.
3. GRUB starts the selected Ubuntu kernel; Linux then initializes hardware, NetworkManager, SSH and optional services. No installer questions are expected after Linux starts. Tailscale enrollment is a separate action after login.
4. Find the address in your router's DHCP leases, on the optional Touch Bar example, or locally with `ip -br address`. Connect using the profile's username and your SSH key:

   ```sh
   ssh USERNAME@ADDRESS
   ```

   Before accepting the key, compare its full public key/fingerprint with `ssh_host_key` in the private manifest. You can write that line to a temporary `.pub` file and run `ssh-keygen -lf FILE.pub`.
5. Run `sudo python3 /usr/local/lib/macbook-t1/verify.py`. Complete the checklist below before erasing macOS.

Do not boot two copies of the same personalized image simultaneously. They share filesystem UUIDs, machine identity and SSH host keys. Keep the external copy disconnected when booting an installed copy.

## 4. Physical acceptance

| Test | What success actually means |
|---|---|
| Cold boot twice | Boot works from power-off, not just a warm reboot |
| Wi-Fi / fallback hotspot | Real DNS and HTTPS requests work on each configured network; check 5 GHz with `iw dev`; test an unavailable preferred network |
| SSH | Your owner key logs in; password and root logins are rejected; reconnect after reboot |
| T1 | Preset keys or custom display work after cold boot; touch mapping correct; webcam still captures in the selected mode |
| Input | Type locally; verify Escape/Fn, trackpad buttons and required gestures |
| Bluetooth | Pair a real device and exercise its actual function; discovery alone is insufficient |
| GPU | `vainfo` plus an actual required FFmpeg encode/decode workload succeeds |
| Audio | Start at low volume; test both speakers, headphone routing and microphone if needed |
| Ports | Exercise each required USB-C cable, storage device, display adapter and charger |
| Power | Check battery/AC and thermal readings, fan behavior, lid policy and a sustained workload |
| Recovery | Stop SSH locally then recover it from a terminal; understand how to power off and return to macOS |

Never deliberately cut power during a write or deep-discharge an old battery to test recovery.

## 5. Replacing macOS / using the full SSD

**The external trial never installs itself onto the internal SSD.** Internal installation is a separate destructive step after physical acceptance and tested backups. This repository deliberately does not select or erase your internal disk automatically.

A clean installation can restore the same **original 32 GiB built image** to the internal SSD from another booted Linux environment. Use a disk-image restoration tool you understand, verify the target by model/serial/size and ensure it is unmounted and is neither the running root nor the image's source storage. Verify the written bytes against `raw_sha256`. Preserve the target's own T1 files in the image **before** doing this. Restoring a larger, already-expanded trial disk is not equivalent to restoring the original image.

For a concrete GUI route, use a separate Ubuntu live session with a display and [GNOME Disks](https://apps.gnome.org/DiskUtility/). Decompress the original image with `gzip -dk macbook.img.gz` (allow another 32 GiB of source storage), compare `sha256sum macbook.img` with the manifest, select the **whole internal SSD** by model/serial/size, and use **Restore Disk Image…**. This replaces the entire selected disk, including its partition table. Restore the whole image rather than only its root partition. The source image must be on a different disk.

After restoring, shut down, disconnect the external clone and boot the internal SSD. Firmware selection may still need local intervention; changing partition identities can invalidate an existing boot entry. Keep recovery media until internal cold boots and all acceptance checks pass.

Once booted from the intended disk, expand the GPT/root filesystem with standard Ubuntu tools. Inspect first:

```sh
findmnt -no SOURCE,FSTYPE /
lsblk -o NAME,PATH,SIZE,TYPE,FSTYPE,MOUNTPOINTS
```

For an **ext4 partition directly on a plain disk**, use the actual parent disk and root partition number from that output:

```sh
sudo sgdisk -e /dev/PARENT_DISK
sudo growpart /dev/PARENT_DISK ROOT_PARTITION_NUMBER
sudo resize2fs /dev/ROOT_PARTITION
```

These are placeholders, not commands to paste unchanged. Do not apply them to APFS, LVM, encrypted roots or a disk you have not identified. Confirm `findmnt` and `df -h /` afterward. The boot EFI partition remains separate; the expanded root uses the remaining space.

This installs the operating system and optional tools. Application data is restored separately from your own verified backups; the hardware kit has no knowledge of a personal service inventory.
