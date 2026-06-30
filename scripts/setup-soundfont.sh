#!/usr/bin/env bash
# Provision the optional "soundfont" engine (Stage 2): sample-based realism via
# FluidSynth + a General MIDI soundfont. The core synth engines need none of
# this — run it only when a track uses "engine": "soundfont".
#
# Installs:
#   - fluidsynth (system library + CLI), which also drops FluidR3_GM.sf2 into
#     /usr/share/sounds/sf2/ on Debian/Ubuntu
#   - pyfluidsynth (the Python binding)
#
# Override the soundfont with the VIBETRACKS_SOUNDFONT environment variable.
set -euo pipefail

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq || true
  sudo apt-get install -y fluidsynth fluid-soundfont-gm
elif command -v brew >/dev/null 2>&1; then
  brew install fluid-synth
  echo "note: install a GM soundfont (e.g. FluidR3_GM.sf2) and point"
  echo "      VIBETRACKS_SOUNDFONT at it."
else
  echo "unsupported package manager — install FluidSynth + a GM .sf2 manually." >&2
  exit 1
fi

pip install "pyfluidsynth>=1.3.0"

python - <<'PY'
from vibetracks import soundfont
print("soundfont engine available:", soundfont.available())
if soundfont.available():
    print("using:", soundfont.find_soundfont())
PY
