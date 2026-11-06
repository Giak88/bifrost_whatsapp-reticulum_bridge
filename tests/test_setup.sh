#!/usr/bin/env bash
# Tests setup.sh with stubbed sudo/systemctl/apt-get/npm and a fake pairing, in a throwaway HOME.
# Usage: tests/test_setup.sh [wheel_dir]
#   wheel_dir: folder holding rns and lxmf wheels for an offline pip (default: use the network)
# Needs ffmpeg with libcodec2+libopus and python3 with Pillow (system-site-packages venv when offline).
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
WHEELS="${1:-}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home" "$T/units"
REAL_NODE="$(command -v node)"

cat > "$T/bin/sudo" <<'STUB'
#!/usr/bin/env bash
exec "$@"
STUB
cat > "$T/bin/systemctl" <<'STUB'
#!/usr/bin/env bash
echo "systemctl $*" >> "$STUB_LOG"
case "$1" in is-active) exit 0 ;; list-unit-files) echo "rnsd.service enabled" ;; esac
exit 0
STUB
cat > "$T/bin/npm" <<'STUB'
#!/usr/bin/env bash
echo "npm $*" >> "$STUB_LOG"; mkdir -p node_modules; exit 0
STUB
cat > "$T/bin/node" <<'STUB'
#!/usr/bin/env bash
# fake node: version queries go to the real one; the sidecar in pairing mode "pairs" instantly
for a in "$@"; do
  if [ "$a" = index.mjs ]; then
    echo "fake sidecar: pair-only=$BIFROST_PAIR_ONLY phone=${WA_PHONE:-} lang=$BIFROST_LANG" >> "$STUB_LOG"
    mkdir -p "$BIFROST_DIR/wa-auth"; echo '{"registered": true}' > "$BIFROST_DIR/wa-auth/creds.json"; exit 0
  fi
done
exec REAL_NODE_PATH "$@"
STUB
sed -i "s#REAL_NODE_PATH#$REAL_NODE#" "$T/bin/node"
chmod +x "$T/bin/"*

export PATH="$T/bin:$PATH" HOME="$T/home" STUB_LOG="$T/stub.log" BIFROST_UNIT_DIR="$T/units"
export BIFROST_HOME="$T/home/.bifrost" BIFROST_ALLOW_ROOT=1 BIFROST_ADDR_WAIT=1
[ -n "$WHEELS" ] && export PIP_NO_INDEX=1 PIP_FIND_LINKS="$WHEELS" PIP_NO_DEPS=1 BIFROST_VENV_FLAGS=--system-site-packages
: > "$STUB_LOG"
fail=0
ok()   { echo "ok   $1"; }
bad()  { echo "FAIL $1"; fail=1; }
chk()  { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

OWNER=0123456789abcdef0123456789abcdef
for L in en it; do
  rm -rf "$T/home/.bifrost" "$T/units"/* ; : > "$STUB_LOG"
  echo "== unattended install, language $L"
  if ! ./setup.sh --lang "$L" --yes --owner "<$OWNER>" --pair code --phone "+39 333 1234567" > "$T/out.$L" 2>&1; then
    bad "setup.sh exit code ($L)"; tail -20 "$T/out.$L"
  fi
  CFG="$T/home/.bifrost/config.ini"
  chk "[$L] config has owner and language" "grep -q '^owner = $OWNER' $CFG && grep -q '^language = $L' $CFG"
  chk "[$L] config is the $L example" "grep -q '$( [ $L = it ] && echo Configurazione || echo 'Bifrost configuration')' $CFG"
  chk "[$L] unit files rendered" "grep -q \"^User=$(id -un)\" $T/units/bifrost.service && grep -q 'WorkingDirectory=$REPO/bridge' $T/units/bifrost.service && ! grep -q '@[A-Z_]*@' $T/units/*.service"
  chk "[$L] bridge unit points at the venv and config" "grep -q 'ExecStart=$T/home/.bifrost/venv/bin/python bifrost.py $T/home/.bifrost/config.ini' $T/units/bifrost.service"
  chk "[$L] sidecar unit carries language" "grep -q 'BIFROST_LANG=$L' $T/units/bifrost-sidecar.service"
  chk "[$L] rnsd dependency added" "grep -q 'Requires=rnsd.service' $T/units/bifrost.service"
  chk "[$L] pairing ran with the phone digits" "grep -q 'pair-only=1 phone=393331234567 lang=$L' $STUB_LOG"
  chk "[$L] services enabled and restarted" "grep -q 'systemctl enable bifrost-sidecar bifrost' $STUB_LOG && grep -q 'systemctl restart bifrost-sidecar bifrost' $STUB_LOG"
  chk "[$L] npm install ran in the sidecar" "grep -q 'npm install' $STUB_LOG"
  chk "[$L] self-test passed" "grep -qi '$( [ $L = it ] && echo 'Autotest superato' || echo 'Self-test passed')' $T/out.$L"
  chk "[$L] output is in $L" "grep -q '$( [ $L = it ] && echo 'Dipendenze OK' || echo 'Dependencies OK')' $T/out.$L"
  chk "[$L] reports missing address.txt politely (no bridge in this test)" "grep -q '$( [ $L = it ] && echo 'non ha ancora pubblicato' || echo 'not published its address')' $T/out.$L"
done

echo "== re-run keeps the config (upgrade path)"
./setup.sh --lang en --yes --pair none > "$T/out.up" 2>&1
chk "existing config kept" "grep -q 'Existing config kept' $T/out.up && grep -q '^owner = $OWNER' $T/home/.bifrost/config.ini"
chk "already paired is detected" "grep -q 'already paired' $T/out.up"

echo "== alpha0.2 config (Italian keys) is migrated"
rm -rf "$T/home/.bifrost/venv"   # force the full path again
cat > "$T/home/.bifrost/config.ini" <<CFG
[bridge]
proprietario = $OWNER
nome = Bifrost alpha0.2
annuncio_min = 15
max_invio_mb = 30
[limiti]
soglia_conferma_kb = 32
qualita_img = medio
qualita_audio = basso
gruppi = seguiti
CFG
./setup.sh --lang it --yes --pair none > "$T/out.mig" 2>&1
C="$T/home/.bifrost/config.ini"
chk "keys renamed" "grep -q '^owner = $OWNER' $C && grep -q '^\[limits\]' $C && grep -q '^quality_img = medium' $C && grep -q '^groups = followed' $C"
chk "pinned name removed, backup made" "! grep -q '^nome' $C && [ -f $C.bak ]"
chk "language added" "grep -q '^language = it' $C"

echo "== bad inputs"
rm -rf "$T/home/.bifrost"
chk "invalid owner refused" "! ./setup.sh --lang en --yes --owner nothex --pair none > $T/out.bad 2>&1 && grep -q 'not a valid address' $T/out.bad"
chk "--yes without owner refused" "! ./setup.sh --lang en --yes --pair none > $T/out.bad2 2>&1 && grep -q -- '--yes needs --owner' $T/out.bad2"
chk "unknown option refused" "! ./setup.sh --bogus > $T/out.bad3 2>&1"

echo "== uninstall"
./setup.sh --lang en --yes --owner "$OWNER" --pair none --skip-tests > /dev/null 2>&1
./setup.sh --lang en --yes --uninstall > "$T/out.un" 2>&1
chk "unit files removed" "[ ! -e $T/units/bifrost.service ] && [ ! -e $T/units/bifrost-sidecar.service ]"
chk "data kept in unattended mode" "[ -f $T/home/.bifrost/config.ini ]"

[ "$fail" = 0 ] && echo "SETUP TESTS PASSED" || { echo "SETUP TESTS FAILED"; exit 1; }
