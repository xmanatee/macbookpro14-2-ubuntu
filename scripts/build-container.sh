#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p .work
# QEMU targets amd64; its userspace runs natively on the Docker engine architecture.
docker build --build-arg BUILDER_UID="$(id -u)" -t macbook-t1-builder .
docker run --rm --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$PWD,dst=/kit,readonly" \
    --mount "type=bind,src=$PWD/.work,dst=/work" \
    --security-opt no-new-privileges --cap-drop ALL macbook-t1-builder "$@"
