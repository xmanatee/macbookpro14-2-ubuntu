#!/usr/bin/env python3
"""Inspect, explicitly authorize, write and read-verify one external macOS USB disk."""

import argparse
import ctypes
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
from common import sha256

# macOS sys/disk.h: _IOW('d', 22, dk_synchronize_t), 24-byte request.
DKIOCSYNCHRONIZE = 0x80186416


def disk_info(device):
    info = plistlib.loads(
        subprocess.check_output(["diskutil", "info", "-plist", device])
    )
    if info.get("WholeDisk") is True:
        # IOKit assigns a new identity on reconnect, even for identical SSDs at one port.
        kit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        kit.IOBSDNameMatching.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_char_p]
        kit.IOBSDNameMatching.restype = ctypes.c_void_p
        kit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        kit.IOServiceGetMatchingService.restype = ctypes.c_uint
        kit.IORegistryEntryGetRegistryEntryID.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint64),
        ]
        kit.IOObjectRelease.argtypes = [ctypes.c_uint]
        matching = kit.IOBSDNameMatching(0, 0, info["DeviceIdentifier"].encode())
        if not matching:
            raise ValueError("Cannot create the disk identity query")
        service = kit.IOServiceGetMatchingService(0, matching)
        if not service:
            raise ValueError("Cannot identify this disk connection in IOKit")
        try:
            identity = ctypes.c_uint64()
            if kit.IORegistryEntryGetRegistryEntryID(service, ctypes.byref(identity)):
                raise ValueError("Cannot pin this disk connection in IOKit")
            info["RegistryEntryID"] = identity.value
        finally:
            kit.IOObjectRelease(service)
    return info


def image_disk(path):
    filesystem = (
        subprocess.check_output(["df", "-P", str(path)], text=True)
        .splitlines()[-1]
        .split()[0]
    )
    if not filesystem.startswith("/dev/disk"):
        raise ValueError("Keep the image on a local Mac volume for SSD preparation")
    return disk_info(filesystem)


def root_disks(info):
    stores = [p["APFSPhysicalStore"] for p in info.get("APFSPhysicalStores", [])]
    if info.get("ParentWholeDisk"):
        stores.append(info["ParentWholeDisk"])
    if info.get("WholeDisk") is True:
        stores.append(info["DeviceIdentifier"])
    if not stores:
        raise ValueError(
            "Cannot identify the physical disk backing the system or image"
        )
    return {re.sub(r"s\d+$", "", p) for p in stores}


def validate_disk(device, info, external_disks, protected_disks, image_bytes):
    if not re.fullmatch(r"/dev/disk[0-9]+", device):
        raise ValueError("Select a whole disk using /dev/diskN")
    identifier = device.removeprefix("/dev/")
    if identifier not in external_disks or identifier in protected_disks:
        raise ValueError(
            "Target must be an external physical disk outside the running system"
        )
    if info.get("Internal") is not False or info.get("WholeDisk") is not True:
        raise ValueError("Refusing an internal disk, partition or unclassified device")
    if info.get("DeviceIdentifier") != identifier or not info.get("Writable"):
        raise ValueError("Disk identity or writeability check failed")
    if info.get("BusProtocol") != "USB" or not info.get("DeviceTreePath"):
        raise ValueError(
            "Use a directly connected USB drive; Thunderbolt-only boot storage is not qualified"
        )
    if type(info.get("RegistryEntryID")) is not int or info["RegistryEntryID"] <= 0:
        raise ValueError("Disk connection identity is missing")
    if info.get("DeviceBlockSize") != 512:
        raise ValueError(
            "This image requires a USB drive exposing 512-byte logical sectors"
        )
    if info.get("TotalSize", 0) <= max(image_bytes, 32 * 1024**3):
        raise ValueError(
            "USB drive must be larger than the 32 GiB image; use a 64 GB or larger drive"
        )


def disk_identity(info):
    fields = [
        "DeviceTreePath",
        "MediaName",
        "TotalSize",
        "DeviceBlockSize",
        "Internal",
        "DeviceIdentifier",
        "BusProtocol",
        "RegistryEntryID",
    ]
    return hashlib.sha256(
        json.dumps({k: info.get(k) for k in fields}, sort_keys=True).encode()
    ).hexdigest()


def write_image(image, target, manifest):
    digest, total = hashlib.sha256(), 0
    with gzip.open(image, "rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            if total + len(chunk) > manifest["raw_bytes"]:
                raise ValueError("Image exceeds declared length; do not boot this SSD")
            view = memoryview(chunk)
            while view:
                written = target.write(view)
                if not written:
                    raise ValueError("SSD write stopped early; do not boot it")
                view = view[written:]
            digest.update(chunk)
            total += len(chunk)
    if total != manifest["raw_bytes"] or digest.hexdigest() != manifest["raw_sha256"]:
        raise ValueError("Image stream checksum mismatch; do not boot this SSD")
    fcntl.ioctl(target.fileno(), DKIOCSYNCHRONIZE, bytes(24))
    print("Device cache flushed. Reading the SSD back for verification.", flush=True)
    target.seek(0)
    digest, remaining = hashlib.sha256(), total
    while remaining:
        chunk = target.read(min(4 * 1024 * 1024, remaining))
        if not chunk:
            raise ValueError("SSD read-back ended early; do not boot it")
        digest.update(chunk)
        remaining -= len(chunk)
    if digest.hexdigest() != manifest["raw_sha256"]:
        raise ValueError("SSD read-back checksum mismatch; do not boot it")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disk", help="Whole external USB disk, e.g. /dev/disk4")
    parser.add_argument(
        "--image", type=Path, default=Path(".work/image/macbook.img.gz")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path(".work/image/manifest.json")
    )
    parser.add_argument(
        "--erase-id", help="Exact connection-identity token from read-only inspection"
    )
    args = parser.parse_args()
    if sys.platform != "darwin" or not re.fullmatch(r"/dev/disk[0-9]+", args.disk):
        parser.error("This writer requires macOS and a whole /dev/diskN device")
    manifest = json.loads(args.manifest.read_text())
    if (
        manifest.get("vm_cold_boot") is not True
        or not 8 * 1024**3 <= manifest["raw_bytes"] <= 128 * 1024**3
    ):
        raise ValueError("A successful build/cold-boot manifest is required")
    protected = root_disks(disk_info("/")) | root_disks(image_disk(args.image))

    def inspect():
        listing = plistlib.loads(
            subprocess.check_output(
                ["diskutil", "list", "-plist", "external", "physical"]
            )
        )
        external = [
            item["DeviceIdentifier"] for item in listing["AllDisksAndPartitions"]
        ]
        info = disk_info(args.disk)
        validate_disk(args.disk, info, external, protected, manifest["raw_bytes"])
        return info

    info = inspect()
    identity = disk_identity(info)
    print(
        json.dumps(
            {
                "disk": {
                    key: info.get(key)
                    for key in [
                        "DeviceIdentifier",
                        "MediaName",
                        "TotalSize",
                        "BusProtocol",
                        "DeviceBlockSize",
                    ]
                },
                "erase_id": identity,
            },
            indent=2,
        ),
        flush=True,
    )
    if args.erase_id is None:
        print(
            "Read-only inspection. To ERASE this disk, rerun with sudo and --erase-id "
            + identity
        )
        return
    if args.erase_id != identity:
        raise ValueError("Disk connection changed or authorization token is wrong")
    if os.geteuid() != 0:
        raise PermissionError(
            "Writing requires sudo; inspect and confirm the disk first"
        )
    if sha256(args.image) != manifest["compressed_sha256"]:
        raise ValueError("Compressed image checksum mismatch")
    subprocess.run(["diskutil", "unmountDisk", args.disk], check=True)
    raw = args.disk.replace("/dev/disk", "/dev/rdisk")
    # Hold one descriptor throughout: never reopen a potentially reassigned diskN.
    with open(raw, "r+b", buffering=0) as target:
        if disk_identity(inspect()) != identity:
            raise ValueError("Disk connection changed; no image bytes written")
        write_image(args.image, target, manifest)
    subprocess.run(["diskutil", "eject", args.disk], check=True)
    print("Written, device-cache flushed, fully read back and ejected.")


if __name__ == "__main__":
    main()
