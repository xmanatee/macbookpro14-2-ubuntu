#!/usr/bin/env python3
"""Build privately in QEMU, then boot again without the provisioning seed."""

import argparse
from datetime import datetime, timezone
import gzip
import grp
import pwd
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
from common import ROOT, fetch, load_profile, run, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / ".private/profile.json")
    parser.add_argument("--work", type=Path, default=Path("/work"))
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run the full guest build and cold-boot checks without exporting a disk image",
    )
    args = parser.parse_args()
    os.umask(0o077)
    profile = load_profile(args.profile)
    # The builder and target share Ubuntu's base account namespace. A username
    # colliding with an existing system group makes cloud-init useradd fail.
    for database in (pwd.getpwall(), grp.getgrall()):
        if any(entry[0] == profile["username"] for entry in database):
            raise ValueError(
                "Choose a new username; that account/group is reserved by Ubuntu"
            )
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    cache = work / "sources"
    cache.mkdir(exist_ok=True)
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    print("Checking pinned source downloads.", flush=True)
    for item in lock["artifacts"].values():
        fetch(item, cache)
    run(
        "gpgv",
        "--keyring",
        "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
        str(cache / "SHA256SUMS.gpg"),
        str(cache / "SHA256SUMS"),
    )
    image = lock["artifacts"]["ubuntu"]
    name = image["url"].rsplit("/", 1)[1]
    entries = [line.split() for line in (cache / "SHA256SUMS").read_text().splitlines()]
    if [image["sha256"], "*" + name] not in entries and [
        image["sha256"],
        name,
    ] not in entries:
        raise ValueError("Exact image name/digest absent from signed Ubuntu manifest")
    build = work / "build"
    if build.exists():
        raise SystemExit(
            "Build state exists. Reuse its completed image, or archive/remove .work/build deliberately before rebuilding."
        )
    build.mkdir()
    (work / "image/manifest.json").unlink(missing_ok=True)
    (build / "input").mkdir()
    (build / "output").mkdir()
    run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(build / "build-key"))
    build_key = (build / "build-key.pub").read_text().strip()

    def root_owned(member):
        if "__pycache__" in Path(member.name).parts or member.name.endswith(".pyc"):
            return None
        member.uid = member.gid = 0
        member.uname = member.gname = "root"
        member.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
        return member

    with tarfile.open(build / "input/payload.tgz", "w:gz") as archive:
        for path in ["scripts", "rootfs", "touchbar", "sources.lock.json"]:
            archive.add(ROOT / path, arcname=path, filter=root_owned)
        for item in lock["artifacts"].values():
            if item["filename"] not in ["ubuntu.qcow2", "SHA256SUMS", "SHA256SUMS.gpg"]:
                archive.add(
                    cache / item["filename"], arcname="sources/" + item["filename"]
                )
        # Fixed allowlist: never recursively archive .private or an EFI partition.
        firmware = ROOT / ".private/EMBEDDEDOS"
        if firmware.exists():
            for name in ["combined.memboot", "FDRData", "version.plist"]:
                path = firmware / name
                if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
                    raise ValueError("Incomplete private T1 capture")
                archive.add(path, arcname="firmware/EMBEDDEDOS/" + name)
        profile_bytes = (json.dumps(profile) + "\n").encode()
        entry = tarfile.TarInfo("profile.json")
        entry.size, entry.mode = len(profile_bytes), 0o600
        archive.addfile(entry, io.BytesIO(profile_bytes))
    config = {
        "hostname": profile["hostname"],
        "manage_etc_hosts": True,
        "disable_root": True,
        "ssh_pwauth": False,
        "users": [
            {
                "name": profile["username"],
                "shell": "/bin/bash",
                "groups": ["sudo"],
                "lock_passwd": True,
                "sudo": ["ALL=(ALL) NOPASSWD:ALL"],
                "ssh_authorized_keys": [profile["ssh_public_key"], build_key],
            }
        ],
        "runcmd": [
            [
                "bash",
                "-c",
                "set -euo pipefail; trap 'echo MACBOOK_BUILD_FAILED > /dev/ttyS0' ERR; "
                "mkdir -m 700 /root/macbook-kit; mkdir /mnt/kit-input; "
                "mount -t 9p -o trans=virtio,version=9p2000.L,ro kit-input /mnt/kit-input; "
                "tar -xzf /mnt/kit-input/payload.tgz -C /root/macbook-kit; "
                "bash /root/macbook-kit/scripts/configure.sh",
            ]
        ],
    }
    (build / "user-data").write_text("#cloud-config\n" + json.dumps(config))
    (build / "meta-data").write_text(
        json.dumps({"instance-id": "macbook-" + os.urandom(12).hex()})
    )
    run(
        "cloud-localds",
        str(build / "seed.img"),
        str(build / "user-data"),
        str(build / "meta-data"),
    )
    run(
        "qemu-img",
        "create",
        "-f",
        "qcow2",
        "-F",
        "qcow2",
        "-b",
        str(cache / "ubuntu.qcow2"),
        str(build / "disk.qcow2"),
        "32G",
    )

    def guest(seed):
        shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", build / "vars.fd")
        argv = [
            "qemu-system-x86_64",
            "-machine",
            "q35",
            "-accel",
            "tcg,thread=multi",
            "-cpu",
            "Skylake-Client-v3",
            "-smp",
            "2",
            "-m",
            "4096",
            "-display",
            "none",
            "-monitor",
            "none",
            "-no-reboot",
            "-drive",
            "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
            "-drive",
            f"if=pflash,format=raw,file={build}/vars.fd",
            "-drive",
            (
                f"if=virtio,format=qcow2,discard=unmap,file={build}/disk.qcow2"
                if seed
                else f"if=none,id=system,format=qcow2,discard=unmap,file={build}/disk.qcow2"
            ),
            "-netdev",
            "user,id=net,hostfwd=tcp:127.0.0.1:2222-:22",
            "-device",
            "virtio-net-pci,netdev=net",
            "-object",
            "rng-random,id=rng,filename=/dev/urandom",
            "-device",
            "virtio-rng-pci,rng=rng",
            "-virtfs",
            f"local,path={build}/output,mount_tag=kit-output,security_model=none",
            "-chardev",
            f"file,id=serial,path={build}/serial.log,append=on",
            "-serial",
            "chardev:serial",
        ]
        if not seed:
            index = argv.index("-netdev")
            argv[index:index] = ["-device", "nvme,drive=system,serial=MACBOOKKIT"]
        if seed:
            argv += [
                "-drive",
                f"if=virtio,format=raw,readonly=on,file={build}/seed.img",
                "-virtfs",
                f"local,path={build}/input,mount_tag=kit-input,security_model=none,readonly=on",
            ]
        with (build / "qemu.log").open("ab") as log:
            return subprocess.Popen(argv, stdout=log, stderr=log)

    def wait(process, predicate, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            serial = build / "serial.log"
            if (build / "output/failed").exists() or (
                serial.exists()
                and "MACBOOK_BUILD_FAILED"
                in serial.read_text(errors="replace").splitlines()
            ):
                raise RuntimeError("Provisioning failed; inspect private serial.log")
            if predicate():
                return
            if process.poll() is not None:
                raise RuntimeError(
                    "Guest stopped; inspect private qemu.log and serial.log"
                )
            time.sleep(3)
        raise TimeoutError("Guest deadline exceeded; inspect .work/build logs")

    def ssh(command, required=True, **kwargs):
        result = subprocess.run(
            [
                "ssh",
                "-i",
                str(build / "build-key"),
                "-p",
                "2222",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=60",
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "UserKnownHostsFile=" + str(build / "known_hosts"),
                profile["username"] + "@127.0.0.1",
                command,
            ],
            capture_output=True,
            timeout=kwargs.pop("timeout", 300),
            **kwargs,
        )
        if required and result.returncode:
            (build / "guest-command.log").write_bytes(result.stdout + result.stderr)
            raise RuntimeError(
                "Guest command failed; inspect private guest-command.log"
            )
        return result

    process = guest(True)
    try:
        print(
            "Installing packages and compiling drivers; private progress: .work/build/serial.log",
            flush=True,
        )
        wait(process, lambda: (build / "output/provisioned.json").exists(), 7200)
        report = json.loads((build / "output/provisioned.json").read_text())
        (build / "known_hosts").write_text(
            "[127.0.0.1]:2222 " + report["ssh_host_key"] + "\n"
        )
        wait(process, lambda: ssh("true", False).returncode == 0, 600)
        # Cloud-init has finished before the image's network handoff is finalized.
        ssh("sudo -n cloud-init status --wait", timeout=600)
        ssh("sudo -n touch /etc/cloud/cloud-init.disabled")
        ssh(
            "sudo -n env DEBIAN_FRONTEND=noninteractive apt-get purge -y "
            "cloud-init cloud-init-base snapd open-iscsi multipath-tools open-vm-tools "
            "lxd-agent-loader cloud-initramfs-copymods cloud-initramfs-dyn-netconf "
            "linux-virtual linux-image-virtual linux-headers-virtual rsyslog networkd-dispatcher",
            timeout=1800,  # Package hooks rebuild initramfs under CPU emulation.
        )
        ssh(
            "sudo -n rm -rf /root/macbook-kit /etc/cloud /var/lib/cloud /var/log/cloud-init.log /var/log/cloud-init-output.log"
        )
        ssh("sudo -n apt-get clean")
        ssh("sudo -n systemctl poweroff")
        process.wait(timeout=120)
        print("Cold-booting with fresh UEFI variables and no seed disk.", flush=True)
        process = guest(False)
        wait(process, lambda: ssh("true", False).returncode == 0, 900)
        if (
            not ssh("findmnt -nro SOURCE /")
            .stdout.decode()
            .strip()
            .startswith("/dev/nvme")
        ):
            raise RuntimeError("Cold boot did not use the emulated NVMe root disk")
        result = ssh(
            "sudo -n python3 /usr/local/lib/macbook-t1/verify.py --vm", timeout=600
        )
        (build / "output/verified-boot.json").write_bytes(result.stdout)
        (build / "output/packages.tsv").write_bytes(
            ssh("dpkg-query -W -f='${binary:Package}\\t${Version}\\n'").stdout
        )
        # Restore scheduled updates for the physical boot, without starting jobs now.
        ssh("sudo -n systemctl unmask apt-daily.timer apt-daily-upgrade.timer")
        ssh("sudo -n systemctl enable apt-daily.timer apt-daily-upgrade.timer")
        # Remove only the ephemeral builder key, preserving exactly the supplied owner key.
        ssh(
            "python3 -",
            input=(
                "from pathlib import Path\np=Path.home()/'.ssh/authorized_keys'\np.write_text("
                + repr(profile["ssh_public_key"] + "\n")
                + ")\np.chmod(0o600)\nimport subprocess\nsubprocess.run(['sudo','-n','systemctl','poweroff'],check=True)\n"
            ).encode(),
            required=False,
        )
        process.wait(timeout=120)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=30)
    if args.validate_only:
        print("Cold boot passed; export skipped by --validate-only.", flush=True)
        return
    export_image(work, lock, report, profile_bytes)


def export_image(work, lock, report, profile_bytes):
    """Convert only a stopped, qualified guest disk and publish its receipt atomically."""
    build = work / "build"
    print(
        "Cold boot passed. Exporting a private image for ONE physical target.",
        flush=True,
    )
    raw = build / "disk.raw"
    run(
        "qemu-img",
        "convert",
        "-O",
        "raw",
        "-S",
        "4k",
        str(build / "disk.qcow2"),
        str(raw),
    )
    output = work / "image"
    output.mkdir(exist_ok=True)
    target = output / "macbook.img.gz"
    partial = output / "macbook.img.gz.partial"
    digest = hashlib.sha256()
    with raw.open("rb") as source, partial.open("wb") as destination:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=destination, compresslevel=1, mtime=0
        ) as compressed:
            while chunk := source.read(8 * 1024 * 1024):
                digest.update(chunk)
                compressed.write(chunk)
    partial.replace(target)
    manifest = {
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "vm_cold_boot": True,
        "physical_hardware_tested": False,
        "kernel": lock["kernel"],
        "profile_sha256": hashlib.sha256(profile_bytes).hexdigest(),
        "payload_sha256": sha256(build / "input/payload.tgz"),
        "compressed_sha256": sha256(target),
        "raw_sha256": digest.hexdigest(),
        "raw_bytes": raw.stat().st_size,
        "ssh_host_key": report["ssh_host_key"],
    }
    marker = output / "manifest.partial"
    marker.write_text(json.dumps(manifest, indent=2) + "\n")
    marker.replace(output / "manifest.json")
    raw.unlink()
    print(
        "Ready: .work/image/macbook.img.gz and manifest.json. Never publish .work or .private.",
        flush=True,
    )


if __name__ == "__main__":
    main()
