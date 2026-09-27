#!/usr/bin/env bash
# Gate fixture: lines listed in expected.json trip one pattern each.
set -euo pipefail
apt-get install -y sox || true
command -v uv 2>/dev/null
rm -rf build 2> /dev/null
echo "TODO: finish"
