#!/usr/bin/env bash
# Runs only inside the disposable amd64 image guest. Never formats a block device.
set -euo pipefail
[[ "$(uname -m)" == x86_64 && "$(systemd-detect-virt --vm)" == qemu ]] || {
    echo 'Provisioning is restricted to the disposable amd64 QEMU image guest.' >&2
    exit 1
}
export DEBIAN_FRONTEND=noninteractive
cd /root/macbook-kit
install -d /mnt/kit-output
mount -t 9p -o trans=virtio,version=9p2000.L kit-output /mnt/kit-output
trap 'touch /mnt/kit-output/failed' ERR
# No background package transactions during provisioning or the qualification boot.
systemctl stop apt-daily.timer apt-daily-upgrade.timer
systemctl mask apt-daily.timer apt-daily-upgrade.timer
timeout 900 python3 - <<'WAIT_APT'
import subprocess, time
while True:
    states = subprocess.check_output([
        'systemctl', 'show', '--property=ActiveState', '--value',
        'apt-daily.service', 'apt-daily-upgrade.service',
    ], text=True).split()
    if len(states) != 2:
        raise RuntimeError('Cannot determine package scheduler state')
    if all(state in ('inactive', 'failed') for state in states):
        break
    time.sleep(3)
WAIT_APT
read -r kernel version < <(python3 -c 'import json; d=json.load(open("sources.lock.json")); print(d["kernel"],d["kernel_package"])')
printf '%s\n' 'grub-efi-amd64 grub2/update_nvram boolean false' | debconf-set-selections
# Privacy policy precedes any optional daemon's first start.
install -d /etc/systemd/system/tailscaled.service.d
printf '[Service]\nEnvironment=TS_NO_LOGS_NO_SUPPORT=true\n' > /etc/systemd/system/tailscaled.service.d/privacy.conf
apt-get update
apt-get dist-upgrade -y
apt-get install -y --no-install-recommends \
    "linux-generic=$version" "linux-headers-$kernel=$version" linux-firmware intel-microcode \
    dkms build-essential patch wget dracut cloud-guest-utils gdisk grub-efi-amd64 grub-pc- grub-pc-bin- \
    network-manager bluez libinput-tools libmtp-runtime alsa-utils v4l-utils iw smartmontools \
    unattended-upgrades upower intel-media-va-driver-non-free vainfo ffmpeg rfkill
# Hardware groups become available only after their packages are installed.
groupadd --system --force bluetooth
owner="$(python3 -c 'import json; print(json.load(open("profile.json"))["username"])')"
usermod -aG audio,video,render,netdev,bluetooth "$owner"
install -d /usr/src/apple-ib-drv-0.1
tar -xzf sources/touchbar.tar.gz --strip-components=2 --wildcards \
    -C /usr/src/apple-ib-drv-0.1 '*/apple-ib-drv/*'
dkms add apple-ib-drv/0.1
dkms install apple-ib-drv/0.1 -k "$kernel"
if python3 -c 'import json,sys; sys.exit(not json.load(open("profile.json"))["audio"])'; then
    apt-get install -y --no-install-recommends "linux-source-${kernel%%-*}=$version"
    install -d /usr/src/snd_hda_macbookpro-0.1
    tar -xzf sources/audio.tar.gz --strip-components=1 -C /usr/src/snd_hda_macbookpro-0.1
    install -m 0755 scripts/audio-pre-build.sh /usr/src/snd_hda_macbookpro-0.1/audio-pre-build.sh
    python3 - <<'PY'
from pathlib import Path
p=Path('/usr/src/snd_hda_macbookpro-0.1/dkms.conf')
s=p.read_text(); assert sum(line.startswith('PRE_BUILD=') for line in s.splitlines())==1
p.write_text('\n'.join('PRE_BUILD="audio-pre-build.sh $kernelver"' if line.startswith('PRE_BUILD=') else line for line in s.splitlines())+'\n')
PY
    dkms add snd_hda_macbookpro/0.1
    dkms install snd_hda_macbookpro/0.1 -k "$kernel"
fi
if python3 -c 'import json,sys; sys.exit(not json.load(open("profile.json"))["display"])'; then
    apt-get install -y --no-install-recommends python3-cairo python3-evdev fonts-dejavu-core
    install -d /usr/src/appletbdrm-t1-1.1 /opt/macbook-touchbar/vendor
    tar -xzf sources/display.tar.gz --strip-components=1 -C /usr/src/appletbdrm-t1-1.1
    dkms add appletbdrm-t1/1.1
    dkms install appletbdrm-t1/1.1 -k "$kernel"
    install -m 0644 sources/dfrdrm.py sources/LICENSE /opt/macbook-touchbar/vendor/
    install -m 0644 touchbar/hardware.py touchbar/panel.py /opt/macbook-touchbar/
    install -m 0644 touchbar/macbook-touchbar.service /etc/systemd/system/
    printf 'blacklist appletbdrm\n' > /etc/modprobe.d/macbook-display.conf
    systemctl enable macbook-touchbar.service
fi
for feature in docker tailscale; do
    if ! python3 -c "import json,sys; sys.exit(not json.load(open('profile.json'))['$feature'])"; then continue; fi
    install -d /etc/apt/keyrings
    if [[ "$feature" == docker ]]; then
        install -m 0644 sources/docker.asc /etc/apt/keyrings/docker.asc
        printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu resolute stable\n' > /etc/apt/sources.list.d/docker.list
        packages=(docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin)
    else
        install -m 0644 sources/tailscale.gpg /etc/apt/keyrings/tailscale.gpg
        printf 'deb [signed-by=/etc/apt/keyrings/tailscale.gpg] https://pkgs.tailscale.com/stable/ubuntu resolute main\n' > /etc/apt/sources.list.d/tailscale.list
        packages=(tailscale)
    fi
    apt-get update
    apt-get install -y --no-install-recommends "${packages[@]}"
    if [[ "$feature" == docker ]]; then
        install -d /etc/docker
        printf '{"log-driver":"local","log-opts":{"max-size":"10m","max-file":"3"}}\n' > /etc/docker/daemon.json
    fi
    systemctl enable "$([[ "$feature" == docker ]] && echo docker || echo tailscaled)"
done
python3 scripts/personalize.py profile.json sources/brcmfmac43602-pcie.txt
# Kernel package hooks run earlier: install the boot profile only after its
# calibration file and out-of-tree modules exist.
cp -a rootfs/. /
if python3 -c 'import json,sys; sys.exit(not json.load(open("profile.json"))["headless"])'; then
    install -d /etc/systemd/logind.conf.d /etc/systemd/sleep.conf.d /etc/UPower
    printf '[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nIdleAction=ignore\n' > /etc/systemd/logind.conf.d/macbook.conf
    printf '[Sleep]\nAllowSuspend=no\nAllowHibernation=no\nAllowHybridSleep=no\nAllowSuspendThenHibernate=no\n' > /etc/systemd/sleep.conf.d/macbook.conf
    printf '[UPower]\nUsePercentageForPolicy=true\nPercentageLow=20\nPercentageCritical=10\nPercentageAction=5\nCriticalPowerAction=PowerOff\n' > /etc/UPower/UPower.conf
    systemctl add-wants multi-user.target upower.service
fi
# Do not retain crash submission, popularity reporting or vendor news polling.
remove=()
for pkg in apport whoopsie ubuntu-report popularity-contest ubuntu-insights; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then remove+=("$pkg"); fi
done
if (( ${#remove[@]} )); then apt-get purge -y "${remove[@]}"; fi
install -d /etc/NetworkManager/conf.d /etc/systemd/journald.conf.d
printf '[connectivity]\nenabled=false\nuri=\ninterval=0\n' > /etc/NetworkManager/conf.d/90-privacy.conf
printf '[Journal]\nStorage=persistent\nSystemMaxUse=256M\nRuntimeMaxUse=64M\nMaxRetentionSec=14day\n' > /etc/systemd/journald.conf.d/limits.conf
if [[ -e /etc/default/motd-news ]]; then printf 'ENABLED=0\n' > /etc/default/motd-news; fi
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' > /etc/apt/apt.conf.d/20auto-upgrades
printf 'Unattended-Upgrade::Automatic-Reboot "false";\n' >> /etc/apt/apt.conf.d/90-macbook-t1
# Firmware identity files, when available, come only from this target's private capture.
if [[ -d firmware/EMBEDDEDOS ]]; then
    install -d /boot/efi/EFI/APPLE/EMBEDDEDOS
    cp -a firmware/EMBEDDEDOS/. /boot/efi/EFI/APPLE/EMBEDDEDOS/
fi
rm -f /etc/default/grub.d/50-cloudimg-settings.cfg
systemctl enable ssh bluetooth NetworkManager macbook-radio.service
systemctl set-default multi-user.target
# The VM needs its DHCP interface during the build. NM takes over after cold boot.
netplan generate
systemctl mask systemd-networkd.service systemd-networkd.socket systemd-networkd-resolve-hook.socket systemd-networkd-varlink.socket systemd-networkd-wait-online.service
depmod "$kernel"
dracut --force /boot/initrd.img-"$kernel" "$kernel"
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=ubuntu --removable --no-nvram --no-uefi-secure-boot
update-grub
root_uuid="$(findmnt -nro UUID /)"
grub-set-default "gnulinux-advanced-$root_uuid>gnulinux-$kernel-advanced-$root_uuid"
install -d /usr/local/lib/macbook-t1
install -m 0644 scripts/verify.py sources.lock.json /usr/local/lib/macbook-t1/
python3 - <<'DONE'
import json
from pathlib import Path
Path('/mnt/kit-output/provisioned.json').write_text(json.dumps({'ssh_host_key':Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().strip()}))
DONE
