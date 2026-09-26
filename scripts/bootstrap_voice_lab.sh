#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os
MODEL_ROOT=/srv/empire_os/runtime/models/voice_lab
TTS_DIR="$MODEL_ROOT/kokoro-en-v0_19"
STT_DIR="$MODEL_ROOT/sherpa-onnx-whisper-tiny.en"
STREAM_STT_DIR="$MODEL_ROOT/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"

echo "=== EMPIRE VOICE LAB BOOTSTRAP ==="
echo "Python: $(./.venv/bin/python --version)"

mkdir -p "$MODEL_ROOT"

./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e '.[voice]'

download_extract() {
  local url="$1"
  local expected_dir="$2"
  local archive="$3"
  if [ -d "$expected_dir" ]; then
    echo "Model already present: $expected_dir"
    return 0
  fi
  echo "Downloading: $url"
  curl -fL --retry 4 --retry-delay 3 -o "$archive" "$url"
  tar -xjf "$archive" -C "$MODEL_ROOT"
  rm -f "$archive"
}

download_extract   "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-en-v0_19.tar.bz2"   "$TTS_DIR"   "$MODEL_ROOT/kokoro-en-v0_19.tar.bz2"

download_extract   "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-tiny.en.tar.bz2"   "$STT_DIR"   "$MODEL_ROOT/sherpa-onnx-whisper-tiny.en.tar.bz2"

download_extract   "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17.tar.bz2"   "$STREAM_STT_DIR"   "$MODEL_ROOT/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17.tar.bz2"

echo "=== READINESS ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python - <<'PY'
from empire_os.voice_lab import EmpireVoiceLab, VoiceLabConfig, MODEL_ROOT
from pathlib import Path
import json

deps = EmpireVoiceLab.dependency_readiness()
models = EmpireVoiceLab.model_readiness(VoiceLabConfig.from_env())
stream_dir = Path(MODEL_ROOT) / "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"
streaming_stt = {
    "encoder": (stream_dir / "encoder-epoch-99-avg-1.int8.onnx").is_file(),
    "decoder": (stream_dir / "decoder-epoch-99-avg-1.onnx").is_file(),
    "joiner": (stream_dir / "joiner-epoch-99-avg-1.int8.onnx").is_file(),
    "tokens": (stream_dir / "tokens.txt").is_file(),
}
print(json.dumps({
    "dependencies": deps,
    "models": models,
    "streaming_stt": streaming_stt,
}, indent=2, sort_keys=True))
if (
    not all(deps.values())
    or not all(models.values())
    or not all(streaming_stt.values())
):
    raise SystemExit("Voice Lab runtime/model readiness incomplete")
PY

echo "=== VOICE LAB BOOTSTRAP COMPLETE ==="
