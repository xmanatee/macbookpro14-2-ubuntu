# Provenance and third-party licenses

`sources.lock.json` is the download authority. Community dependencies are small and necessarily less supported than the distribution kernel. A pin records reviewed/tested code; it is not a vendor endorsement or proof of absence of vulnerabilities.

| Resource | Use / trust boundary |
|---|---|
| [Canonical Ubuntu cloud images](https://cloud-images.ubuntu.com/releases/resolute/release-20260927/) | Official dated amd64 base; SHA-256 and signed manifest verified with Ubuntu's packaged cloud-image keyring |
| [Ubuntu packages](https://archive.ubuntu.com/ubuntu/) | Kernel, matching source/headers, dracut, stock hardware drivers, NetworkManager, BlueZ, UPower and media tools; apt signature verification |
| [AJ-dev-i60/t1-touchbar](https://github.com/AJ-dev-i60/t1-touchbar/tree/20d65c7b0fe6d05ea9734f869b27384a62de5109) | Kernel-7-compatible `apple-ib-drv`; upstream Linux kernel driver licensing applies; original roadrunner2 community work credited upstream |
| [davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro/tree/89b22ff90b86468b186706861dd18663562defa7) | Optional CS8409 audio module; Linux kernel GPL licensing; Ubuntu source/header ABI must match |
| [moerdowo/appletbdrm-t1](https://github.com/moerdowo/appletbdrm-t1/tree/186c32ee8828eb7d65fcd52c0ef49e737185461b) | Optional GPL-2.0 DRM driver; kept as downloaded DKMS source, not relicensed by this project |
| [moerdowo/MacLinux-Touchbar](https://github.com/moerdowo/MacLinux-Touchbar/tree/ac4d4157a3568593539a2fcca242dcae7f829e0e) | Only the pinned MIT `dfrdrm.py` adapter and its LICENSE are installed; upstream launcher/plugins are not used |
| [nohzafk/omarchy-macbookpro-t1](https://github.com/nohzafk/omarchy-macbookpro-t1/blob/8e479f0af82d16f47de811bef6e1a5cfd7d8c5f8/firmware/brcmfmac43602-pcie.txt) | Board-specific community calibration reference; target MAC substituted; inspect upstream provenance and applicable firmware terms before redistribution |
| [Docker](https://docs.docker.com/engine/install/ubuntu/), [Tailscale](https://pkgs.tailscale.com/stable/) | Explicit optional vendor packages; official signed apt repositories and pinned signing-key downloads |
| [niconistal/t1-revive](https://github.com/niconistal/t1-revive) | Expert recovery reference only; not downloaded or run automatically; review independently before any firmware reset |

This repository distributes **its own source code and documentation only**. Downloads occur locally at build time. Preserve upstream licenses/notices with downloaded sources; the renderer's LICENSE is installed beside the adapter. Ubuntu's proprietary firmware and Apple device-personalized files are not relicensed under this repository's MIT license. No ready-made image or factory/identity record is published.
