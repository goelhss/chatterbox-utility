#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
for command_name in curl git; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Missing %s. Install it first, then rerun.\n' "$command_name" >&2
    exit 1
  fi
done
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv_bin="$(command -v uv || true)"
uv_bin="${uv_bin:-$HOME/.local/bin/uv}"
"$uv_bin" python install 3.11
if [ ! -x .venv/bin/python ]; then "$uv_bin" venv --python 3.11 .venv; fi
if [ ! -f tools/chatterbox/pyproject.toml ]; then
  git clone https://github.com/resemble-ai/chatterbox.git tools/chatterbox
  git -C tools/chatterbox checkout 5de7a54aa4e5e2baadb0182dde554908b48b85c2
fi
"$uv_bin" pip install --python .venv/bin/python -e ./tools/chatterbox -r requirements-app.txt
mkdir -p models recordings books output logs tools/tmp tools/numba-cache
.venv/bin/python tools/download_model.py
printf '\nReady. Start with: scripts/mac/start.sh\n'
