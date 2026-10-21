"""Local read-only T1 display. No remote endpoints, application credentials or agents."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import socket
import subprocess
import time
from hardware import Hardware, WIDTH


def notify(message):
    address = os.environ.get("NOTIFY_SOCKET")
    if address:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect("\0" + address[1:] if address.startswith("@") else address)
            sock.sendall(message.encode())


def readings():
    def command(*args):
        return subprocess.check_output(
            args, text=True, stderr=subprocess.DEVNULL, timeout=3
        ).strip()

    try:
        network = command("nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show").replace(
            "IP4.ADDRESS[1]:", ""
        )
        network = (
            "  ".join(
                line for line in network.splitlines() if line and not line.endswith(":")
            )
            or "No IPv4 address"
        )
    except (subprocess.SubprocessError, OSError):
        network = "Network unknown"
    temperatures = []
    for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
        if (zone / "type").read_text().strip() == "x86_pkg_temp":
            temperatures.append(int((zone / "temp").read_text()) / 1000)
    temperature = f"{max(temperatures):.0f} C" if temperatures else "Temp unknown"
    storage = os.statvfs("/")
    free = f"{storage.f_bavail * storage.f_frsize / 1024**3:.0f} GiB free"
    try:
        failed = command("systemctl", "--failed", "--no-legend", "--plain")
        health = failed.splitlines()[0][:70] if failed else "No failed systemd units"
    except (subprocess.SubprocessError, OSError):
        health = "Service state unknown"
    return [health, network, temperature + " | " + free], time.monotonic()


def main():
    import cairo

    hardware = Hardware()
    executor = ThreadPoolExecutor(max_workers=1)
    pending = None
    last_refresh = 0
    values = ["Starting diagnostics…"]
    sampled = 0
    page = 0
    touched = False
    wake_only = False
    last_touch = time.monotonic()
    notify("READY=1")
    try:
        while True:
            now = time.monotonic()
            notify("WATCHDOG=1")
            if pending is None and now - last_refresh > 5:
                pending = executor.submit(readings)
                last_refresh = now
            if pending is not None and pending.done():
                # Collector failures stay visible instead of leaving old green text.
                try:
                    values, sampled = pending.result()
                except Exception as error:
                    print(
                        f"Local diagnostics failed: {type(error).__name__}: {error}",
                        flush=True,
                    )
                    values, sampled = ["Diagnostics unavailable"], 0
                pending = None
            contacts = hardware.read()
            if contacts is not None:
                active = bool(contacts)
                if active and not touched:
                    wake_only = now - last_touch >= 30
                    if not wake_only:
                        if len(contacts) == 1 and contacts[0][1] < 180:
                            hardware.escape()
                        elif len(contacts) == 1:
                            page = (page + 1) % len(values)
                    last_touch = now
                touched = active
            stale = now - sampled > 15
            dimmed = now - last_touch >= 30
            context = hardware.bar.ctx
            context.set_source_rgb(0.025, 0.025, 0.025)
            context.paint()
            factor = 0.2 if dimmed else 1
            context.set_source_rgb(
                factor, factor * 0.85, factor * 0.6 if stale else factor
            )
            context.select_font_face(
                "DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            context.set_font_size(27)
            context.move_to(25, 40)
            context.show_text("Esc")
            context.move_to(200, 40)
            context.show_text(
                "Status unknown / stale" if stale else values[page % len(values)][:120]
            )
            context.move_to(WIDTH - 300, 40)
            context.show_text("Tap for next")
            hardware.bar.flush()
            time.sleep(0.05)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
        hardware.close()


if __name__ == "__main__":
    main()
