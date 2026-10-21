import base64
import copy
import gzip
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import validate, fetch

spec = importlib.util.spec_from_file_location("writer", ROOT / "scripts/write-image.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


def profile():
    blob = (
        struct.pack(">I", 11)
        + b"ssh-ed25519"
        + struct.pack(">I", 32)
        + bytes(range(32))
    )
    return {
        "hostname": "macbook-lab",
        "username": "macadmin",
        "ssh_public_key": "ssh-ed25519 " + base64.b64encode(blob).decode(),
        "wifi_mac": "00:11:22:33:44:55",
        "country": "GB",
        "wifi": [{"ssid": "Example home", "psk": "ExampleOnly123"}],
        "headless": True,
        "audio": False,
        "display": False,
        "docker": False,
        "tailscale": False,
    }


class InputBoundary(unittest.TestCase):
    def test_valid_profile_and_literal_punctuation(self):
        p = profile()
        p["wifi"][0] = {
            "ssid": "A; literal's % network",
            "psk": "Example<3;not-a-shell",
        }
        self.assertEqual(validate(p), p)

    def test_reject_command_injection_and_unsafe_identities(self):
        for key, value in [
            ("hostname", "host; reboot"),
            ("username", "root"),
            ("username", "ubuntu"),
            ("username", "operator"),
            ("country", "GB\nExecStart=/bin/false"),
            ("wifi_mac", "02:11:22:33:44:55"),
            ("ssh_public_key", "-----BEGIN OPENSSH PRIVATE KEY-----"),
            ("display", "true"),
        ]:
            p = profile()
            p[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate(p)

    def test_reject_malformed_public_key_and_duplicate_networks(self):
        p = profile()
        p["ssh_public_key"] = "ssh-ed25519 QUJD"
        with self.assertRaises(ValueError):
            validate(p)
        p = profile()
        p["wifi"] *= 2
        with self.assertRaises(ValueError):
            validate(p)

    def test_reject_invalid_ssid_and_password_boundaries(self):
        for ssid, psk in [
            ("", "ExampleOnly123"),
            ("x" * 33, "ExampleOnly123"),
            ("line\nbreak", "ExampleOnly123"),
            ("Example", "short"),
            ("Example", "a" * 65),
        ]:
            p = profile()
            p["wifi"] = [{"ssid": ssid, "psk": psk}]
            with self.subTest(ssid=ssid), self.assertRaises(ValueError):
                validate(p)

    def test_corrupt_cached_source_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "file").write_text("corrupt")
            with self.assertRaises(ValueError):
                fetch(
                    {
                        "filename": "file",
                        "url": "https://invalid.example/file",
                        "sha256": "0" * 64,
                    },
                    directory,
                )


class DiskBoundary(unittest.TestCase):
    def setUp(self):
        self.disk = {
            "WholeDisk": True,
            "Internal": False,
            "VirtualOrPhysical": "Physical",
            "BusProtocol": "USB",
            "TotalSize": 64 * 1024**3,
            "Writable": True,
            "DeviceBlockSize": 512,
            "RegistryEntryID": 1234,
            "DeviceIdentifier": "disk9",
            "DeviceTreePath": "example-usb-path",
            "MediaName": "Example external disk",
        }

    def test_external_whole_disk_is_accepted(self):
        writer.validate_disk("/dev/disk9", self.disk, ["disk9"], set(), 32 * 1024**3)

    def test_internal_partition_virtual_readonly_or_small_disk_is_rejected(self):
        for key, value in [
            ("WholeDisk", False),
            ("Internal", True),
            ("Internal", None),
            ("DeviceBlockSize", 4096),
            ("RegistryEntryID", None),
            ("BusProtocol", "Disk Image"),
            ("Writable", False),
            ("TotalSize", 1024),
        ]:
            disk = copy.deepcopy(self.disk)
            disk[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                writer.validate_disk("/dev/disk9", disk, ["disk9"], set(), 32 * 1024**3)

    def test_missing_identity_metadata_is_not_treated_as_safe(self):
        with self.assertRaises(ValueError):
            writer.validate_disk("/dev/disk9", {}, ["disk9"], set(), 32 * 1024**3)

    def test_system_or_image_backing_disk_is_rejected(self):
        with self.assertRaises(ValueError):
            writer.validate_disk(
                "/dev/disk9", self.disk, ["disk9"], {"disk9"}, 32 * 1024**3
            )
        with self.assertRaises(ValueError):
            writer.validate_disk("/dev/disk9", self.disk, [], set(), 32 * 1024**3)

    def test_reconnection_changes_authorization_identity(self):
        before = writer.disk_identity(self.disk)
        self.disk["RegistryEntryID"] += 1
        self.assertNotEqual(before, writer.disk_identity(self.disk))


class ImageTransfer(unittest.TestCase):
    def test_written_image_is_read_back_and_matches_original(self):
        data = bytes(range(256)) * 1000
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.gz"
            image.write_bytes(gzip.compress(data))
            manifest = {
                "raw_bytes": len(data),
                "raw_sha256": hashlib.sha256(data).hexdigest(),
            }
            with (
                tempfile.TemporaryFile() as target,
                patch.object(writer.fcntl, "ioctl"),
            ):
                writer.write_image(image, target, manifest)
                target.seek(0)
                self.assertEqual(target.read(), data)

    def test_wrong_decompressed_length_or_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.gz"
            image.write_bytes(gzip.compress(b"example image"))
            for size, digest in [(2, "0" * 64), (13, "0" * 64)]:
                with (
                    tempfile.TemporaryFile() as target,
                    patch.object(writer.fcntl, "ioctl"),
                    self.assertRaises(ValueError),
                ):
                    writer.write_image(
                        image, target, {"raw_bytes": size, "raw_sha256": digest}
                    )


if __name__ == "__main__":
    unittest.main()
