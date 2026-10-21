"""Input and download boundaries shared by the image tools."""

import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate(profile):
    expected = {
        "hostname",
        "username",
        "ssh_public_key",
        "wifi_mac",
        "country",
        "wifi",
        "headless",
        "audio",
        "display",
        "docker",
        "tailscale",
    }
    if set(profile) != expected:
        raise ValueError("Profile fields must match scripts/profile.py exactly")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", profile["hostname"]):
        raise ValueError("Invalid hostname")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,30}", profile["username"]) or profile[
        "username"
    ] in {"root", "ubuntu", "operator"}:
        raise ValueError(
            "Choose a non-reserved username (not root, ubuntu or operator)"
        )
    key = profile["ssh_public_key"]
    if (
        not isinstance(key, str)
        or "\n" in key
        or not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]+={0,2}(?: [^\r\n]+)?", key)
    ):
        raise ValueError("Supply one Ed25519 public key, never a private key")
    import base64, struct

    blob = base64.b64decode(key.split()[1], validate=True)
    if len(blob) != 51 or blob[:19] != struct.pack(
        ">I", 11
    ) + b"ssh-ed25519" + struct.pack(">I", 32):
        raise ValueError("Malformed Ed25519 public key")
    if (
        not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", profile["wifi_mac"])
        or int(profile["wifi_mac"][:2], 16) & 3
    ):
        raise ValueError(
            "Use this target Mac's original, globally assigned unicast Wi-Fi MAC"
        )
    if not re.fullmatch(r"[A-Z]{2}", profile["country"]):
        raise ValueError("Country must be the actual two-letter regulatory country")
    if not isinstance(profile["wifi"], list) or not 1 <= len(profile["wifi"]) <= 20:
        raise ValueError("Supply 1–20 WPA2 personal networks in preferred order")
    seen = set()
    for item in profile["wifi"]:
        if set(item) != {"ssid", "psk"} or not all(
            isinstance(v, str) for v in item.values()
        ):
            raise ValueError("Each Wi-Fi entry needs an SSID and PSK")
        ssid, psk = item["ssid"], item["psk"]
        if (
            not 1 <= len(ssid.encode()) <= 32
            or any(c in ssid for c in "\r\n\0")
            or ssid in seen
        ):
            raise ValueError("Invalid or duplicate SSID")
        if not (
            8 <= len(psk) <= 63
            and all(32 <= ord(c) <= 126 for c in psk)
            or re.fullmatch(r"[a-fA-F0-9]{64}", psk)
        ):
            raise ValueError(
                "PSK must be 8–63 printable ASCII characters or 64 hexadecimal digits"
            )
        seen.add(ssid)
    for field in ["headless", "audio", "display", "docker", "tailscale"]:
        if type(profile[field]) is not bool:
            raise ValueError("Options must be booleans")
    return profile


def fetch(item, directory):
    target = Path(directory) / item["filename"]
    if not target.exists():
        partial = target.with_suffix(".partial")
        with (
            urllib.request.urlopen(item["url"], timeout=120) as response,
            partial.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        if sha256(partial) != item["sha256"]:
            raise ValueError("Download checksum mismatch: " + target.name)
        partial.replace(target)
    if sha256(target) != item["sha256"]:
        raise ValueError("Cache checksum mismatch: " + target.name)
    return target


def load_profile(path):
    return validate(json.loads(Path(path).read_text()))
