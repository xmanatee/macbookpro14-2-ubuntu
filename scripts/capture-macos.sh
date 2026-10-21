#!/usr/bin/env bash
# Read-only capture from this target Mac. Mount its EFI partition before running.
set -euo pipefail
umask 077
[[ "$(uname -s)" == Darwin ]] || { echo 'Run on the target Mac while macOS still works.' >&2; exit 1; }
model="$(sysctl -n hw.model)"
[[ "$model" == MacBookPro14,2 ]] || { echo 'Only MacBookPro14,2 is qualified.' >&2; exit 1; }
[[ $# == 1 ]] || { echo 'Usage: capture-macos.sh /Volumes/EFI/EFI/APPLE/EMBEDDEDOS' >&2; exit 1; }
[[ ! -e .private/EMBEDDEDOS ]] || { echo 'Private capture already exists; refusing to overwrite it.' >&2; exit 1; }
for name in combined.memboot FDRData version.plist; do
    [[ -s "$1/$name" ]] || { echo "Missing $name; stop and read docs/recovery.md." >&2; exit 1; }
done
mkdir -p .private/EMBEDDEDOS
chmod 700 .private .private/EMBEDDEDOS
for name in combined.memboot FDRData version.plist; do
    cp "$1/$name" ".private/EMBEDDEDOS/$name"
    chmod 600 ".private/EMBEDDEDOS/$name"
done
printf 'Saved only the target Mac three T1 files into .private/EMBEDDEDOS. Keep an encrypted backup.\n'
