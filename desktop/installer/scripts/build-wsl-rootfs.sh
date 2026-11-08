#!/usr/bin/env bash
# Builds assets/wsl/studentide-rootfs.tar.gz (the WSL distro setup imports on Windows).
# Needs Docker or Podman. Usage: scripts/build-wsl-rootfs.sh [docker|podman]
set -euo pipefail
cd "$(dirname "$0")/../assets/wsl"
ENGINE="${1:-docker}"
"$ENGINE" build --platform linux/amd64 -t studentide-wsl-rootfs -f Containerfile .
id=$("$ENGINE" create --platform linux/amd64 studentide-wsl-rootfs)
trap '"$ENGINE" rm -f "$id" >/dev/null' EXIT
"$ENGINE" export "$id" | gzip -9 > studentide-rootfs.tar.gz
ls -lh studentide-rootfs.tar.gz
