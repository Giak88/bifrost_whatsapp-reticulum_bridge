#!/usr/bin/env bash
# End-to-end test with no network and no WhatsApp: a private rnsd, the real bridge,
# a fake sidecar and a fake "owner" LXMF client. Usage: tests/e2e.sh [python] [en|it]
# Needs rns + lxmf importable by the python given (or on PYTHONPATH), ffmpeg, Pillow.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${1:-python3}"; LANG_="${2:-en}"
W="$(mktemp -d)"; PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$W"; }
trap cleanup EXIT
mkdir -p "$W/rns" "$W/data/spool" "$W/media"

PORT=$((37000 + RANDOM % 2000))
cat > "$W/rns/config" <<CFG
[reticulum]
  enable_transport = No
  share_instance = Yes
  shared_instance_port = $PORT
  instance_control_port = $((PORT + 1))
[logging]
  loglevel = 3
[interfaces]
CFG
"$PY" tests/make_media.py "$W/media"
"$PY" - "$W" <<'PYEOF'
import sys, io, RNS
from PIL import Image
w = sys.argv[1]
i = RNS.Identity(); i.to_file(f"{w}/owner.id")
open(f"{w}/owner.hash", "w").write(RNS.Destination.hash(i, "lxmf", "delivery").hex())
b = io.BytesIO(); Image.new("RGB", (320, 240), (10, 120, 200)).save(b, "webp", quality=22)
open(f"{w}/img.webp", "wb").write(b.getvalue())
PYEOF
cat > "$W/config.ini" <<CFG
[bridge]
owner = $(cat "$W/owner.hash")
language = $LANG_
dir = $W/data
rns_config = $W/rns
announce_min = 1
CFG

"$PY" -m RNS.Utilities.rnsd --config "$W/rns" > "$W/rnsd.log" 2>&1 & PIDS+=($!)
sleep 3
"$PY" tests/e2e_fake_sidecar.py "$W/data/ipc.sock" "$W/data/spool" "$W/media" > "$W/sidecar.log" 2>&1 & PIDS+=($!)
sleep 1
"$PY" bridge/bifrost.py "$W/config.ini" > "$W/bridge.log" 2>&1 & PIDS+=($!)
for _ in $(seq 1 30); do [ -s "$W/data/address.txt" ] && break; sleep 1; done
[ -s "$W/data/address.txt" ] || { echo "FAILED: the bridge never wrote address.txt"; cat "$W/bridge.log"; exit 1; }
BRIDGE="$(cat "$W/data/address.txt")"
echo "bridge address: $BRIDGE"

WAIT=14 "$PY" tests/e2e_owner.py "$W/rns" "$W" "$BRIDGE" > "$W/owner.log" 2>&1
sleep 2
echo "--- owner received:"; grep RECEIVED "$W/owner.log"
echo "--- sidecar commands:"; grep "SIDECAR CMD" "$W/sidecar.log"

fail=0
need() { grep -q -- "$2" "$1" || { echo "FAILED: $3"; fail=1; }; }
need "$W/owner.log" "#1 Mario: hello from WhatsApp" "text from WhatsApp did not arrive"
need "$W/owner.log" "(6: *)\?.*webp\|'webp'" "image did not arrive"
need "$W/sidecar.log" "SIDECAR CMD: text .* 'hello from the LoRa'" "text to WhatsApp did not reach the sidecar"
need "$W/sidecar.log" "SIDECAR CMD: image" "image to WhatsApp did not reach the sidecar"
need "$W/bridge.log" "Delivered to the owner\|Consegnato al proprietario" "no delivery log line"
[ "$fail" = 0 ] && echo "E2E PASSED ($LANG_)" || { echo "--- bridge log:"; tail -25 "$W/bridge.log"; exit 1; }
