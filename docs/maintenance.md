# Maintenance

## One update boundary

Ubuntu security userspace updates run automatically without automatic reboots. During image construction and its qualification boot, the apt timers are masked and any existing scheduler job is allowed to finish. The builder unmasks/enables those timers without starting them before the final shutdown; scheduled updates resume on the installed system. See [systemctl unit semantics](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html). Kernel, headers/modules/source, firmware, DKMS, GRUB/shim, dracut and microcode need **attended qualification**. The apt blacklist affects unattended upgrades, not an explicit `apt full-upgrade`.

Before changing that boundary:

1. Back up data, EFI and the current boot configuration; retain a working previous kernel and a local recovery route.
2. Install candidate kernel headers **and the matching Ubuntu kernel source package version** before the audio DKMS build. The audio hook refuses mismatched versions; substituting an unrelated upstream source tree is not a fix.
3. Require `dkms status` to show each enabled driver installed for the candidate kernel, run `depmod`, rebuild the candidate dracut image and inspect it with `lsinitrd` for NVMe/USB/SPI/network drivers.
4. Regenerate GRUB, boot the candidate with local recovery available, and repeat physical acceptance. Check `journalctl -b -p warning`, actual network access and the functions you use. Only then make it the default or remove the previous kernel.

The lock records a **qualified reference**, not a promise that this kernel stays secure forever. Compare current Ubuntu security advisories and upstream driver changes before adopting or updating it. The reference kernel reports **Gather Data Sampling as vulnerable**. This older Intel CPU has hardware/security-support limits: Intel lists the i7-7567U's end of servicing as 2024. A new operating system cannot guarantee elimination of all CPU vulnerabilities. See [Intel specifications](https://www.intel.com/content/www/us/en/products/sku/97541/intel-core-i77567u-processor-4m-cache-up-to-4-00-ghz/specifications.html).

The dated cloud image, signing manifest and community artifacts are pinned by SHA-256 in `sources.lock.json`. Ubuntu's signed manifest authenticates the **exact base filename and digest**. Ubuntu apt metadata/packages and optional vendor repositories have their own signature validation. Installed userspace versions vary with repository updates; this is not a bit-for-bit reproducible distro snapshot. Builds keep a package inventory privately. If an artifact disappears or a hash changes, the build fails rather than silently switching sources.

## Diagnostics

```sh
sudo python3 /usr/local/lib/macbook-t1/verify.py
systemctl --failed
journalctl -b -p warning
nmcli device
sudo iw dev
bluetoothctl show
rfkill list
vainfo
dkms status
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
```

Use the physical checklist in [install.md](install.md). `verify.py` is a baseline check, not a synthetic claim that every hardware function is healthy. Logs can contain addresses/SSIDs/identifiers; redact before sharing.

## Power and storage

The image removes cloud provisioning, Snap, unused hypervisor/iSCSI/multipath helpers, virtual-kernel metapackages and duplicate logging/network-dispatch daemons. It keeps the native generic kernel, NetworkManager and journald. No graphical desktop is installed. The `headless` option explicitly ignores the lid, disables suspend/hibernate and enables UPower critical-battery shutdown (20% low, 10% critical, action at 5%). These percentages do not repair an aged battery. Keep ventilation clear; a closed laptop under sustained load still needs cooling.

The physical reference server used a conservative Intel package power policy (23 W sustained / 28 W burst). This is a workload/thermal tradeoff, not a mandatory driver. It is intentionally not applied to every image. For this exact CPU, a scoped udev rule can set `intel-rapl:0`, `name=package-0`, `constraint_0_name=long_term`, `constraint_1_name=short_term`, limits `23000000` and `28000000` µW. Confirm the reported constraints and measure temperatures/performance before persisting a limit; do not write guessed constraint numbers on another model.

Journald retains up to 256 MiB persistently, 64 MiB in runtime storage and 14 days. SSD TRIM should be checked with `systemctl status fstrim.timer`. An image restored to a larger disk needs the explicit GPT/root expansion in the installation guide. A connected external disk is not automatically backup storage; design and test your own encrypted backup/restore workflow.

## Optional Docker and Tailscale

Docker is installed from [Docker's official apt repository](https://docs.docker.com/engine/install/ubuntu/). No application stack, registry credential or personal GitHub session is included. The login user is **not** added to the root-equivalent Docker group; use deliberate sudo administration. New containers use Docker's bounded `local` log driver. Published container ports can bypass ordinary UFW rules; [read Docker's firewall limitations](https://docs.docker.com/engine/install/ubuntu/#firewall-limitations) before exposing anything.

Tailscale is installed from its signed official repository but **not enrolled during the build**. Run `sudo tailscale up --ssh=false` after physical boot and complete the displayed login flow. Native OpenSSH remains the SSH mechanism. The systemd environment sets `TS_NO_LOGS_NO_SUPPORT=true` before first daemon start; this opts out of client log submission and affects support diagnostics. It does not hide device registration or network metadata inherent to a coordination service. Avoid reusable enrollment keys in images. Manage package updates through apt, and inspect your tailnet's access/key-expiry settings separately. See [Tailscale logging controls](https://tailscale.com/kb/1011/log-mesh-traffic).

## Privacy boundaries

No analytics, session recording, vendor feedback or application agents are added by this project. Crash/popularity upload packages and Ubuntu connectivity/news probes are disabled where installed. No public diagnostic upload is performed. Distribution/vendor package downloads, time synchronization and an explicitly enabled VPN necessarily contact their respective services. Do not claim an internet-connected OS transmits no metadata.

No desktop is installed. If you add one, audit that desktop's privacy, indexing, crash and application telemetry independently. A generic kit cannot permanently govern software installed later. Firmware updates and T1 recovery remain attended actions; there is no self-updating firmware script.

For a short synthetic hardware-encode check on this model (no personal media):

```sh
ffmpeg -hide_banner -loglevel warning \
  -vaapi_device /dev/dri/by-path/pci-0000:00:02.0-render \
  -f lavfi -i testsrc2=size=1280x720:rate=30 -t 3 \
  -vf 'format=nv12,hwupload' -c:v h264_vaapi -f null -
```

Run as an account with render-device access. A successful H.264 encode does not establish every HEVC profile, decode path or application workload.


## Additional settings retained from the physical setup

[`extras/`](../extras/) contains the exact optional 23/28 W RAPL rule and GNOME privacy policy, separate from the minimal server image. They are reference configurations rather than additional default daemons. Read its application instructions before using them.

For an unenrolled Ubuntu Pro client, disable subscription polling with `sudo systemctl disable --now ua-timer.timer` after checking that `/var/lib/ubuntu-advantage/private/machine-token.json` is absent. Do not disable an enrolled support service without understanding its purpose. The image disables login MOTD news via `/etc/default/motd-news`; on a system with the timer installed, also mask `motd-news.timer`.

To match the reference machine's local crash-dump policy, use an `/etc/sysctl.d/` drop-in with `kernel.core_pattern =` and `kernel.core_uses_pid = 0`, then apply that specific file with `sudo sysctl --load FILE`. This removes local core-dump material and reduces debugging options; it is separate from disabling remote crash uploads.
