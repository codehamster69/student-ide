#!/usr/bin/env bash
# Downloads the engine pieces bundled into the app, pinned by version and SHA-256.
# Usage: scripts/fetch-assets.sh mac|linux|win   (win builds the WSL rootfs; needs Docker)
set -euo pipefail
cd "$(dirname "$0")/.."
LIMA=1.0.7
PODMAN=5.3.1

fetch() { # url sha256 out
  curl -fsSL --retry 3 -o "$3" "$1"
  echo "$2  $3" | sha256sum -c - >/dev/null || { echo "checksum mismatch for $1" >&2; rm -f "$3"; exit 1; }
}

case "${1:?mac|linux|win}" in
  mac)
    for pair in "arm64 arm64 fa3836128e19920ca7113bbcc9908399c56f0665b4b04f294dd76aa02ef38905" \
                "x64 x86_64 1fa5211968d5a3f895fa2ddc9a36695ac287a3f6526b83147c62582d837055cc"; do
      set -- $pair
      mkdir -p "assets/lima/$1"
      fetch "https://github.com/lima-vm/lima/releases/download/v$LIMA/lima-$LIMA-Darwin-$2.tar.gz" "$3" /tmp/lima.tgz
      # limactl, the guest agent for this arch (VM arch = host arch) and Lima's licence (Apache-2.0).
      guest=$([ "$1" = arm64 ] && echo aarch64 || echo x86_64)
      tar -xzf /tmp/lima.tgz -C "assets/lima/$1" ./bin/limactl "./share/lima/lima-guestagent.Linux-$guest.gz" \
        ./share/doc/lima/LICENSE 2>/dev/null \
        || tar -xzf /tmp/lima.tgz -C "assets/lima/$1" ./bin/limactl "./share/lima/lima-guestagent.Linux-$guest" ./share/doc/lima/LICENSE
      rm -f /tmp/lima.tgz
    done ;;
  linux)
    mkdir -p assets/podman-static
    fetch "https://github.com/mgoltzsche/podman-static/releases/download/v$PODMAN/podman-linux-amd64.tar.gz" \
      5d4b5042097b4dcf6d4b20c00a23bac3640b47513d8b2eda876a52f64f811419 assets/podman-static/podman-linux-amd64.tar.gz ;;
  win)
    scripts/build-wsl-rootfs.sh docker ;;
esac
