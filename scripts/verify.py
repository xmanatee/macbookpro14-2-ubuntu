#!/usr/bin/env python3
"""Read-only baseline checks. Physical tests still require an operator."""

import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm", action="store_true")
    args = parser.parse_args()

    def output(*argv, timeout=180):
        return subprocess.check_output(
            argv, text=True, stderr=subprocess.STDOUT, timeout=timeout
        ).strip()

    lock = json.loads((Path(__file__).parent / "sources.lock.json").read_text())
    checks = {}

    def check(name, condition):
        checks[name] = bool(condition)

    check("kernel", output("uname", "-r") == lock["kernel"])
    check(
        "root_ownership",
        all(
            Path(path).stat().st_uid == 0 and not Path(path).stat().st_mode & 0o022
            for path in ["/", "/etc", "/etc/ssh", "/etc/modprobe.d"]
        ),
    )
    dkms = output("dkms", "status")
    check(
        "T1_DKMS", "apple-ib-drv/0.1, " + lock["kernel"] + ", x86_64: installed" in dkms
    )
    for name, version in [("snd_hda_macbookpro", "0.1"), ("appletbdrm-t1", "1.1")]:
        if Path("/usr/src/" + name + "-" + version).exists():
            check(
                name + "_DKMS",
                name + "/" + version + ", " + lock["kernel"] + ", x86_64: installed"
                in dkms,
            )
    check("UEFI_loader", Path("/boot/efi/EFI/BOOT/BOOTX64.EFI").is_file())
    check("SSH_service", output("systemctl", "is-active", "ssh") == "active")
    check(
        "NetworkManager", output("systemctl", "is-active", "NetworkManager") == "active"
    )
    sshd = dict(
        line.split(" ", 1) for line in output("/usr/sbin/sshd", "-T").splitlines()
    )
    check(
        "SSH_key_only",
        sshd["passwordauthentication"] == "no"
        and sshd["permitrootlogin"] == "no"
        and sshd["kbdinteractiveauthentication"] == "no",
    )
    check(
        "no_failed_units", not output("systemctl", "--failed", "--no-legend", "--plain")
    )
    for module in [
        "applespi",
        "brcmfmac",
        "hci_uart",
        "i915",
        "applesmc",
        "uvcvideo",
        "apple_ibridge",
        "apple_touchbar",
    ]:
        output("modinfo", "-k", lock["kernel"], module)
    if not args.vm:
        check(
            "exact_model",
            Path("/sys/devices/virtual/dmi/id/product_name").read_text().strip()
            == "MacBookPro14,2",
        )
        check(
            "T1_safe_power",
            "skip_acpi_power=1"
            in Path("/etc/modprobe.d/apple-touchbar.conf").read_text(),
        )
        check(
            "T1_personalized_files",
            all(
                (Path("/boot/efi/EFI/APPLE/EMBEDDEDOS") / name).is_file()
                for name in ["combined.memboot", "FDRData", "version.plist"]
            ),
        )
    print(
        json.dumps(
            {
                "passed": all(checks.values()),
                "checks": checks,
                "scope": "VM"
                if args.vm
                else "physical baseline; not a peripheral acceptance test",
            },
            indent=2,
        )
    )
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
