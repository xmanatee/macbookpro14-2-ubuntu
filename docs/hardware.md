# Hardware evidence

Reference: **MacBookPro14,2**, 2017 13-inch Touch Bar/T1; Ubuntu 26.04, kernel `7.0.0-38-generic`. The statements below describe the physical reference machine, not a compatibility guarantee for every A1706. Kernel module presence and VM boots cannot prove a physical peripheral works.

| Component | Evidence on the reference Mac | Boundary / remaining check |
|---|---|---|
| Internal SSD | Ubuntu boots from the full internal NVMe SSD | Back up before repartitioning; firmware selection may require a display |
| Wi-Fi BCM43602 (`14e4:43ba`) | Internet access on 2.4 and 5 GHz using brcmfmac and the locked calibration file | WPA2 personal tested; WPA3, enterprise, roaming and all regulatory channels unqualified |
| Bluetooth | Stock BlueZ/hci_uart controller enumerated and discovered nearby devices | Missing-patch/baud warnings observed; pairing, long transfers and Bluetooth audio not physically accepted |
| CPU / thermals | Intel pstate and SMC sensors active; real workloads ran | Sustained stress can throttle; clean cooling and verify fan behavior. No guaranteed performance uplift |
| GPU / media | Stock i915; actual containerized H.264 / HEVC Main10 hardware media tests passed | Not proof of every codec, HDR path, external display or application pipeline |
| Keyboard / trackpad | Stock applespi and input devices enumerate; internal-keyboard libinput quirk supplied | Complete physical key map, gestures and palm rejection require local testing |
| Touch Bar preset keys | Pinned bridge/control-strip modules built and bound with safe power option | Requires working T1 embeddedOS and this Mac's own staged identity files |
| Touch Bar custom display | DRM rendering and digitizer alignment physically confirmed; watchdog recovery exercised in the original panel | Public minimal example is newly extracted; validate it locally. It cannot draw in Apple firmware or a frozen kernel |
| Audio | Pinned CS8409 driver built against matching Ubuntu source/headers and loaded | Speaker output, microphone, jack routing and safe listening levels not physically qualified |
| Webcam | T1 configuration 1 exposes the camera via stock uvcvideo | Enumeration is not an image-quality/capture acceptance test; custom-display mode must be checked separately |
| USB / Thunderbolt | USB 2/3 controllers and an external storage device work | Cable/hub/dock dependent; not every port mode, display adapter or USB-C charging path tested |
| Battery | Charge, capacity, AC state and UPower policy visible | Battery health/capacity not certified; no charge-limit support claimed; test emergency shutdown locally |
| Sleep / hibernate | Disabled in the headless profile | Reliable suspend/resume is not established; do not treat disabling sleep as fixing it |
| Internal / external display | Stock graphics driver present | Broken reference display prevented full panel, backlight, hotplug and firmware-menu qualification |
| Touch ID | Not configured | This kit does not install or promise biometric authentication |

## Wi-Fi details that matter

The firmware binary comes from Ubuntu's `linux-firmware`. The extra **BCM43602 calibration/NVRAM text** is a pinned community-sourced board configuration, not vendor-certified for every laptop. Its original MAC is replaced by the target Mac's original globally assigned address. The DMI-specific filename points to that same file. Do not use random donor MACs or generic incomplete calibration snippets.

On macOS, identify the Wi-Fi hardware port with `networksetup -listallhardwareports`, then use `networksetup -getmacaddress DEVICE`. Use the hardware address, not a per-network private/random address. Set the actual two-letter country in the profile; this is not a technique for bypassing channel restrictions.

Wi-Fi power saving is disabled. NetworkManager autoconnect priority helps choose between **available disconnected profiles**; it does not continuously leave a connected captive portal or internet-broken router for a lower-priority hotspot. There is deliberately no home-grown network-flapping watchdog. Keep a local recovery route, test your hotspot and explicitly switch with `nmcli connection up macbook-wifi-N` when necessary.

Audio reports for this exact model include both [working speakers/headphones](https://github.com/davidjo/snd_hda_macbookpro/issues/206) and [missing speaker channels/digital noise](https://github.com/davidjo/snd_hda_macbookpro/issues/211). They concern different environments and do not establish full speaker correctness for this recipe. Test at low volume; do not add guessed codec quirks to make an enumeration check pass.

## T1, not T2

This model uses Apple T1 USB `05ac:8600`; T2 `apple-bce`, T2 kernels and `tiny-dfr` instructions are not interchangeable with it. The bridge is configured with **`skip_acpi_power=1`**. Calling `ASOC.SOCW(1)` was associated with a hard freeze; never set `skip_acpi_power=0` to light a dark bar.

The optional custom display uses USB configuration 2 with bridge modules unloaded, drains bounded stale DFR replies, then loads `appletbdrm`. Stopping it restores configuration 1 and the preset bridge driver. The adapter implements the T1 digitizer protocol and a virtual Escape key. No X11/Wayland session or network listener is required. The example shows local service state, IPv4 addresses, temperature and free space; first touch after dimming wakes it. Personal application/alert dashboards are outside this repository.

## Sources

- [Kernel-7 T1 bridge and freeze-safe option](https://github.com/AJ-dev-i60/t1-touchbar/tree/20d65c7b0fe6d05ea9734f869b27384a62de5109)
- [T1 DRM driver](https://github.com/moerdowo/appletbdrm-t1/tree/186c32ee8828eb7d65fcd52c0ef49e737185461b), [DRM userspace renderer](https://github.com/moerdowo/MacLinux-Touchbar/tree/ac4d4157a3568593539a2fcca242dcae7f829e0e)
- [CS8409 audio driver and model-specific reports](https://github.com/davidjo/snd_hda_macbookpro/tree/89b22ff90b86468b186706861dd18663562defa7)
- [Exact community calibration source](https://github.com/nohzafk/omarchy-macbookpro-t1/blob/8e479f0af82d16f47de811bef6e1a5cfd7d8c5f8/firmware/brcmfmac43602-pcie.txt)
- [NetworkManager autoconnect semantics](https://networkmanager.dev/docs/api/latest/settings-connection.html)
