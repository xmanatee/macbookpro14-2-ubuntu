#!/usr/bin/env python3
"""Create a private profile without putting passwords into shell history."""

import getpass
import json
import os
import sys
from pathlib import Path
from common import validate


def main():
    if not sys.stdin.isatty():
        raise SystemExit(
            "Run this command in an interactive terminal for hidden password entry."
        )
    os.umask(0o077)
    target = Path(".private/profile.json")
    if target.exists():
        raise SystemExit("Profile already exists; edit the private file intentionally.")
    profile = {
        "hostname": input("Hostname: ").strip(),
        "username": input(
            "Login username (e.g. macadmin; not root/ubuntu/operator): "
        ).strip(),
        "ssh_public_key": Path(input("Ed25519 PUBLIC key file: ").strip())
        .expanduser()
        .read_text()
        .strip(),
        "wifi_mac": input("Target Mac original Wi-Fi MAC: ").strip().lower(),
        "country": input("Actual two-letter country: ").strip().upper(),
        "wifi": [],
    }
    while ssid := input("Wi-Fi SSID, preferred first (empty to finish): "):
        profile["wifi"].append(
            {"ssid": ssid, "psk": getpass.getpass("Wi-Fi password: ")}
        )
    for option in ["headless", "audio", "display", "docker", "tailscale"]:
        profile[option] = input(option + "? [y/N]: ").strip().lower() == "y"
    validate(profile)
    target.parent.mkdir(mode=0o700, exist_ok=True)
    target.write_text(json.dumps(profile, indent=2) + "\n")
    target.chmod(0o600)
    print(
        "Saved private profile. Keep .private and .work out of Git and shared storage."
    )


if __name__ == "__main__":
    main()
