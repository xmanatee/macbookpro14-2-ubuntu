#!/usr/bin/env python3
"""Materialize one target's Wi-Fi profile inside the image guest."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from common import validate


def apply(profile, calibration):
    validate(profile)
    text = Path(calibration).read_text()
    for field in ["devid=0x43ba", "rssi_delta_5gml=", "mcsbw805ghpo=", "txchain=7"]:
        if field not in text:
            raise ValueError("Incomplete BCM43602 calibration")
    text, count = re.subn(
        r"^macaddr=.*$", "macaddr=" + profile["wifi_mac"], text, flags=re.M
    )
    if count != 1:
        raise ValueError("Expected exactly one calibration MAC")
    firmware = Path("/usr/lib/firmware/brcm")
    firmware.mkdir(parents=True, exist_ok=True)
    (firmware / "brcmfmac43602-pcie.txt").write_text(text)
    specific = firmware / "brcmfmac43602-pcie.Apple Inc.-MacBookPro14,2.txt"
    specific.unlink(missing_ok=True)
    specific.symlink_to("brcmfmac43602-pcie.txt")
    networks = Path("/etc/NetworkManager/system-connections")
    networks.mkdir(mode=0o700, parents=True, exist_ok=True)
    for index, item in enumerate(profile["wifi"]):
        result = subprocess.run(
            [
                "nmcli",
                "--offline",
                "connection",
                "add",
                "type",
                "wifi",
                "con-name",
                f"macbook-wifi-{index + 1}",
                "ssid",
                item["ssid"],
                "connection.autoconnect",
                "yes",
                "connection.autoconnect-priority",
                str(100 - index),
                "802-11-wireless.cloned-mac-address",
                "permanent",
                "802-11-wireless.powersave",
                "2",
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                item["psk"],
            ],
            check=True,
            capture_output=True,
        )
        path = networks / f"macbook-wifi-{index + 1}.nmconnection"
        path.write_bytes(result.stdout)
        path.chmod(0o600)
    # cloud-init created this image's temporary VM interface; only NM owns the final network.
    for path in Path("/etc/netplan").glob("*.yaml"):
        path.unlink()
    path = Path("/etc/netplan/01-network-manager.yaml")
    path.write_text("network:\n  version: 2\n  renderer: NetworkManager\n")
    path.chmod(0o600)
    Path("/etc/systemd/system/macbook-radio.service").write_text(
        """[Unit]
Description=Set the local wireless regulatory domain
ConditionVirtualization=false
Before=NetworkManager.service
[Service]
Type=oneshot
ExecStartPre=/usr/sbin/modprobe cfg80211
ExecStart=/usr/sbin/iw reg set """
        + profile["country"]
        + """
[Install]
WantedBy=multi-user.target
"""
    )


if __name__ == "__main__":
    os.umask(0o077)
    apply(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
