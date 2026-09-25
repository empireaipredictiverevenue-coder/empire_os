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
echo "Install timeout: ${LAYA_NPM_TIMEOUT:-180}s"
set +e
timeout --foreground "${LAYA_NPM_TIMEOUT:-180}s"   npm --prefix "${SIDE}" install     --omit=dev --no-audit --no-fund --no-package-lock     --loglevel=notice
npm_rc=$?
set -e
if [[ "${npm_rc}" -eq 124 ]]; then
  echo "SKIPPED: Laya npm install exceeded timeout; Empire continues without Laya." >&2
  exit 3
fi
if [[ "${npm_rc}" -ne 0 ]]; then
  echo "SKIPPED: Laya npm install failed rc=${npm_rc}; Empire continues without Laya." >&2
  exit "${npm_rc}"
fi

echo
echo "=== PRELOAD MODEL TO LOCAL CACHE ==="
echo "Model bundle is ~1.7 GB; progress will print below."
echo "Preload timeout: ${LAYA_PRELOAD_TIMEOUT:-1200}s"
mkdir -p "${CACHE}"
set +e
LAYA_CACHE="${CACHE}" LAYA_THREADS="${LAYA_THREADS:-4}" timeout --foreground "${LAYA_PRELOAD_TIMEOUT:-1200}s"   node "${SIDE}/preload.mjs"
preload_rc=$?
set -e
if [[ "${preload_rc}" -eq 124 ]]; then
  echo "SKIPPED: Laya model preload exceeded timeout; Empire continues without Laya." >&2
  exit 4
fi
if [[ "${preload_rc}" -ne 0 ]]; then
  echo "SKIPPED: Laya model preload failed rc=${preload_rc}; Empire continues without Laya." >&2
  exit "${preload_rc}"
fi

echo
echo "=== COMPLETE ==="
