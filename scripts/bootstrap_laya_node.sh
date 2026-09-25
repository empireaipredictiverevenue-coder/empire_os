#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/srv/empire_os}"
SIDE="${ROOT}/tools/laya_node"
CACHE="${ROOT}/runtime/laya/cache"

echo "=== LAYA NODE/ONNX RESOURCE GATE ==="
mem_kb="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
disk_kb="$(df -Pk "${ROOT}" | awk 'NR==2 {print $4}')"
echo "MemAvailable_kB=${mem_kb:-0}"
echo "DiskAvailable_kB=${disk_kb:-0}"

if [[ "${mem_kb:-0}" -lt 2800000 ]]; then
  echo "BLOCKED: need at least ~2.8 GB available RAM for first Laya benchmark" >&2
  exit 2
fi
if [[ "${disk_kb:-0}" -lt 4000000 ]]; then
  echo "BLOCKED: need at least ~4 GB free disk for package/cache headroom" >&2
  exit 2
fi

echo
echo "=== INSTALL PINNED NODE SIDECAR ==="
npm --prefix "${SIDE}" install --omit=dev --no-audit --no-fund

echo
echo "=== PRELOAD MODEL TO LOCAL CACHE ==="
mkdir -p "${CACHE}"
LAYA_CACHE="${CACHE}" LAYA_THREADS="${LAYA_THREADS:-4}" node "${SIDE}/preload.mjs"

echo
echo "=== COMPLETE ==="
