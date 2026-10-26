#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec caffeinate -i "$root/.venv/bin/python" "$root/tools/narrate.py" "$@"
