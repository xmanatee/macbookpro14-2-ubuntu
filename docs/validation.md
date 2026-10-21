# Validation record

Recorded on **2026-10-21**. Evidence has two distinct scopes:

| Check | Result / scope |
|---|---|
| Physical reference hardware | MacBookPro14,2 on Ubuntu 26.04 / `7.0.0-38-generic`; the observations and remaining physical checks are in [hardware.md](hardware.md) |
| Public input/disk/transfer tests | 12 tests passed: profile validation, corrupt cache rejection, system/source/4Kn disk rejection, reconnect identity changes, actual gzip-to-file transfer/readback and corrupt-stream rejection |
| Source authenticity | All locked downloads matched SHA-256; Ubuntu base matched its exact filename in the signed manifest; `gpgv` accepted Canonical's packaged trust key |
| macOS discovery | Actual IOKit connection identity and APFS system/image backing-disk identification passed read-only checks |
| macOS build UID | Container account mapping, Ed25519 generation and OpenSSH configuration lookup passed under UID 501 |
| Static checks | ShellCheck, Python compilation and unused-name checks passed |
| Publication audit | Gitleaks found no secrets; explicit tracked-file review excluded private identities, profiles, logs, images and firmware records; repository starts with fresh history |
| Guest installation / cold boot | Fresh signed base installed with every optional feature; all three DKMS drivers built. After cleanup, a fresh-UEFI NVMe boot without the seed or input share passed every baseline check; owner key accepted, temporary builder key rejected |
| Docker behavior | Two containers shared a real persistent volume; container DNS and HTTPS requests succeeded; Compose available |
| Build guard / update settings | Provisioning refused macOS; QEMU detection confirmed. Both apt timers enabled in the final guest |
| Image export | Sparse raw conversion, gzip export and full 32 GiB decompression/readback matched the recorded byte count and SHA-256 |

The public source was extracted and generalized from a physical migration. Installation, cleanup and export were exercised in stages on the same disposable guest, rather than recompiling drivers after every refinement. The reference machine was **not erased or reinstalled again** to test publication. The minimal public Touch Bar example is not the original personal application dashboard; its hardware adapter shares the physically exercised protocol, while the new example still needs its own local display/touch acceptance.

No VM result certifies Bluetooth pairing, audio output, gestures, suspend, thermal endurance, display adapters or Apple firmware recovery. No generated personal image, factory record or raw machine log is published. The public macOS writer reuses the original migration's disk safeguards; this extraction was checked through input/transfer tests and read-only hardware discovery, without erasing another physical disk.
