#!/usr/bin/env bash
set -euo pipefail

ROOT="${EMPIRE_VOICE_MODEL_ROOT:-/srv/empire_os/runtime/models/voice_lab}"
BASE="https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models"

mkdir -p "$ROOT"
cd "$ROOT"

install_archive() {
  local name="$1"
  local required="$2"
  if [[ -f "$ROOT/$name/$required" ]]; then
    echo "[tts-candidates] ready: $name"
    return
  fi

  echo "[tts-candidates] downloading: $name"
  local archive="$name.tar.bz2"
  curl -fL --retry 3 --retry-delay 2     "$BASE/$archive"     -o "$archive"

  echo "[tts-candidates] extracting: $name"
  tar xjf "$archive"
  rm -f "$archive"

  if [[ ! -f "$ROOT/$name/$required" ]]; then
    echo "[tts-candidates] missing expected artifact: $name/$required" >&2
    exit 1
  fi
}

install_archive "kokoro-int8-en-v0_19" "model.int8.onnx"
install_archive "kitten-nano-en-v0_8-int8" "model.int8.onnx"

echo
echo "=== TTS CANDIDATES READY ==="
du -sh   "$ROOT/kokoro-en-v0_19"   "$ROOT/kokoro-int8-en-v0_19"   "$ROOT/kitten-nano-en-v0_8-int8"   2>/dev/null || true

echo
echo "No production TTS configuration was changed."
