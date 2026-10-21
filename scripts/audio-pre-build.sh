#!/usr/bin/env bash
set -euo pipefail
kernel="${1:?DKMS must provide the target kernel}"
base="${kernel%%-*}"
header_version="$(dpkg-query -W -f='${Version}' "linux-headers-$kernel")"
source_version="$(dpkg-query -W -f='${Version}' "linux-source-$base")"
if [[ "$header_version" != "$source_version" ]]; then
    echo "Audio build refused: kernel headers and distribution source must have identical package versions." >&2
    exit 1
fi
test -r "/usr/src/linux-source-$base.tar.bz2"
exec bash ./install.cirrus.driver.sh -k "$kernel" --dkms
