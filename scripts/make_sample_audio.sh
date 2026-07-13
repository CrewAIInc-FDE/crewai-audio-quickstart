#!/usr/bin/env bash
# Generate a small spoken-question WAV so you can test with zero assets.
#
#   ./scripts/make_sample_audio.sh                          # default question
#   ./scripts/make_sample_audio.sh "Why is the sky blue?"   # your own
#   ./scripts/make_sample_audio.sh "..." out.wav            # custom path
set -euo pipefail

TEXT="${1:-What are three interesting facts about the Moon?}"
OUT="${2:-samples/question.wav}"
mkdir -p "$(dirname "$OUT")"

if command -v say >/dev/null 2>&1; then
  # macOS: built-in TTS, then convert to 16 kHz mono WAV
  TMP="$(mktemp -t sample).aiff"
  say -o "$TMP" "$TEXT"
  afconvert -f WAVE -d LEI16@16000 -c 1 "$TMP" "$OUT"
  rm -f "$TMP"
elif command -v espeak >/dev/null 2>&1 && command -v ffmpeg >/dev/null 2>&1; then
  # Linux: espeak + ffmpeg
  espeak "$TEXT" --stdout | ffmpeg -y -loglevel error -i - -ar 16000 -ac 1 "$OUT"
else
  echo "Need macOS 'say' or Linux 'espeak'+'ffmpeg' to synthesize audio." >&2
  echo "Any wav/mp3/m4a recording works too — record one and pass its path." >&2
  exit 1
fi

echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
