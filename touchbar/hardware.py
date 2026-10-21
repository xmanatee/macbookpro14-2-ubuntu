"""T1 USB configuration, DRM output and digitizer; no ACPI power calls."""

import ctypes
import errno
import fcntl
import os
from pathlib import Path
import struct
import subprocess
import sys

WIDTH, HEIGHT = 2170, 60


def run(*argv):
    return subprocess.run(
        argv, check=True, capture_output=True, text=True, timeout=15
    ).stdout


def usb_device():
    devices = [
        path
        for path in Path("/sys/bus/usb/devices").glob("*")
        if (path / "idVendor").exists()
        and (path / "idProduct").exists()
        and (path / "idVendor").read_text().strip() == "05ac"
        and (path / "idProduct").read_text().strip() == "8600"
    ]
    if len(devices) != 1:
        raise RuntimeError("Expected exactly one T1 iBridge")
    return devices[0]


def drain(device):
    """Consume bounded stale DFR replies before the kernel claims interface 3."""
    bus, number = (int((device / name).read_text()) for name in ("busnum", "devnum"))
    fd = os.open(f"/dev/bus/usb/{bus:03d}/{number:03d}", os.O_RDWR | os.O_CLOEXEC)
    try:
        fcntl.ioctl(
            fd, 0x8004550F, bytearray(struct.pack("I", 3))
        )  # USBDEVFS_CLAIMINTERFACE
        for _ in range(32):
            buffer = ctypes.create_string_buffer(512)
            request = bytearray(
                struct.pack("IIIxxxxQ", 0x85, 512, 200, ctypes.addressof(buffer))
            )
            try:
                fcntl.ioctl(fd, 0xC0185502, request)  # USBDEVFS_BULK, x86_64
            except OSError as error:
                if error.errno == errno.ETIMEDOUT:
                    return
                raise
        raise RuntimeError("T1 reply queue did not drain")
    finally:
        os.close(fd)  # Also releases the USB interface.


def configure(mode):
    device = usb_device()
    if mode == "keyboard":
        run("modprobe", "-r", "appletbdrm")
        (device / "bConfigurationValue").write_text("1")
        run("modprobe", "apple_ibridge", "skip_acpi_power=1")
        run("modprobe", "apple_touchbar")
        return
    if mode != "display":
        raise ValueError("Unknown T1 mode")
    if "/updates/dkms/" not in run("modinfo", "-n", "appletbdrm"):
        raise RuntimeError("The qualified T1 DRM module is not installed")
    run("modprobe", "-r", "apple_touchbar", "apple_ibridge", "appletbdrm")
    (device / "bConfigurationValue").write_text("2")
    drain(device)
    run("modprobe", "appletbdrm")
    run("modprobe", "uinput")
    run("udevadm", "settle", "--timeout=10")


def digitizer_path():
    devices = []
    for path in Path("/sys/class/hidraw").glob("hidraw*"):
        device = path / "device"
        fields = dict(
            line.split("=", 1) for line in (device / "uevent").read_text().splitlines()
        )
        identity = fields.get("HID_ID", "").split(":")
        if len(identity) != 3 or [int(value, 16) for value in identity[1:]] != [
            0x05AC,
            0x8600,
        ]:
            continue
        if (
            (device / "report_descriptor")
            .read_bytes()
            .startswith(bytes.fromhex("05 0d 09 05 a1 01"))
        ):
            devices.append("/dev/" + path.name)
    if len(devices) != 1:
        raise RuntimeError("T1 digitizer is unavailable or ambiguous")
    return devices[0]


def contacts(data):
    if not 40 <= len(data) <= 256:
        raise ValueError("Invalid T1 digitizer report length")
    points = []
    for offset in range(0, 40, 4):
        flags, x, y = struct.unpack_from("<BHB", data, offset)
        if flags & 0x10:
            if x > 32767 or y > 127:
                raise ValueError("Invalid T1 touch coordinates")
            points.append((flags & 15, x * WIDTH / 32767, y * HEIGHT / 127))
    if len({point[0] for point in points}) != len(points):
        raise ValueError("Duplicate T1 contacts")
    return points


class Hardware:
    def __init__(self):
        # Only the reviewed, pinned KMS adapter is installed from MacLinux-Touchbar.
        sys.path.insert(0, str(Path(__file__).parent / "vendor"))
        from dfrdrm import TouchBar
        from evdev import UInput, ecodes

        cards = [
            path
            for path in Path("/sys/class/drm").glob("card[0-9]*")
            if (path / "device/driver").resolve().name == "appletbdrm"
        ]
        if len(cards) != 1:
            raise RuntimeError("T1 DRM output is unavailable or ambiguous")
        self.bar = TouchBar("/dev/dri/" + cards[0].name)
        self.keyboard = UInput(
            {ecodes.EV_KEY: [ecodes.KEY_ESC]}, name="MacBook Touch Bar Escape"
        )
        self.fd = os.open(digitizer_path(), os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        if (self.bar.width, self.bar.height) != (WIDTH, HEIGHT):
            raise RuntimeError("Unexpected Touch Bar dimensions")

    def read(self):
        try:
            data = os.read(self.fd, 256)
        except BlockingIOError:
            return None
        if not data:
            raise RuntimeError("T1 digitizer disconnected")
        return contacts(data)

    def escape(self):
        from evdev import ecodes

        for value in (1, 0):
            self.keyboard.write(ecodes.EV_KEY, ecodes.KEY_ESC, value)
            self.keyboard.syn()

    def close(self):
        os.close(self.fd)
        self.keyboard.close()
        self.bar.close()


if __name__ == "__main__":
    configure(sys.argv[1])
