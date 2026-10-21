FROM ubuntu:26.04@sha256:f144425ff09be612d6d9ad965196e9cdc23dae1f42110a8a11a3e9a8198759f7
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates cloud-image-utils gpgv openssh-client ovmf python3 qemu-system-x86 qemu-utils \
    && rm -rf /var/lib/apt/lists/*
ARG BUILDER_UID=1000
RUN usermod --uid "$BUILDER_UID" ubuntu
WORKDIR /kit
ENTRYPOINT ["python3", "/kit/scripts/build.py"]
