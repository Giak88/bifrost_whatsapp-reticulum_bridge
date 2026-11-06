#!/usr/bin/env bash
# Bifrost - guided setup / installazione guidata (English / Italiano)
#
#   ./setup.sh                 first install, or a menu if Bifrost is already installed
#   ./setup.sh --lang it       choose the language (en | it) without asking
#   ./setup.sh --yes --owner <32-hex LXMF address> [--pair none|qr|code --phone 39333...]
#                              unattended install (no questions)
#   ./setup.sh --uninstall     remove the services (asks before touching your data)
#
# Environment (advanced): BIFROST_HOME (data folder, default ~/.bifrost),
# BIFROST_UNIT_DIR (default /etc/systemd/system), BIFROST_VENV_FLAGS (e.g. --system-site-packages).
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${BIFROST_HOME:-$HOME/.bifrost}"
UNIT_DIR="${BIFROST_UNIT_DIR:-/etc/systemd/system}"
VENV="$DATA/venv"
CFG="$DATA/config.ini"
VERSION="$(cat "$DIR/VERSION" 2>/dev/null || echo '?')"

LANGSEL="" ; YES=0 ; OWNER="" ; PAIR="" ; PHONE="" ; ACTION="" ; SKIP_TESTS=0

# ------------------------------------------------------------------ messages
declare -A M
m() { M["en.$1"]="$2"; M["it.$1"]="$3"; }

m title        "Bifrost %s - WhatsApp <-> Reticulum/LXMF bridge" "Bifrost %s - ponte WhatsApp <-> Reticulum/LXMF"
m root         "Do not run this as root: Bifrost must run as your normal user (it asks for sudo when needed)." "Non eseguirlo come root: Bifrost deve girare con il tuo utente normale (chiede sudo quando serve)."
m nosudo       "sudo is not available: services cannot be installed. Install sudo or run as a user who has it." "sudo non è disponibile: non posso installare i service. Installa sudo o usa un utente che lo abbia."
m nosystemd    "systemd not found: dependencies and config will be set up, but you must start the bridge yourself (see README)." "systemd non trovato: preparo dipendenze e configurazione, ma dovrai avviare il bridge a mano (vedi README)."
m step_deps    "Checking dependencies" "Controllo delle dipendenze"
m miss_pkgs    "Missing: %s" "Mancano: %s"
m ask_apt      "Install them now with apt-get?" "Li installo ora con apt-get?"
m no_apt       "No apt-get here: install them with your package manager and run ./setup.sh again." "Qui non c'è apt-get: installali con il tuo gestore di pacchetti e rilancia ./setup.sh."
m node_old     "Node.js >= 20 is required, you have %s. Debian 13 ships Node 20; on older systems use https://github.com/nodesource/distributions or nvm, then run ./setup.sh again." "Serve Node.js >= 20, hai %s. Debian 13 ha Node 20; su sistemi più vecchi usa https://github.com/nodesource/distributions oppure nvm, poi rilancia ./setup.sh."
m no_codec2    "Your ffmpeg has no libcodec2 (needed for LoRa voice notes). On Debian/Ubuntu the stock 'ffmpeg' package has it: sudo apt install ffmpeg" "Il tuo ffmpeg non ha libcodec2 (serve per i vocali LoRa). Su Debian/Ubuntu il pacchetto 'ffmpeg' standard ce l'ha: sudo apt install ffmpeg"
m no_opus      "Your ffmpeg has no libopus. Install a full ffmpeg build." "Il tuo ffmpeg non ha libopus. Installa una build completa di ffmpeg."
m deps_ok      "Dependencies OK (node %s, ffmpeg with codec2+opus)" "Dipendenze OK (node %s, ffmpeg con codec2+opus)"
m rnsd_ok      "Reticulum daemon (rnsd) is running" "Il demone Reticulum (rnsd) è attivo"
m rnsd_missing "rnsd is NOT running. Bifrost needs a running Reticulum instance to talk to your radio/network (it never opens the radio itself). Install and start it first: https://reticulum.network/manual/gettingstartedfast.html" "rnsd NON è attivo. Bifrost ha bisogno di un'istanza Reticulum attiva per parlare con la tua radio/rete (non apre mai la radio da solo). Installalo e avvialo prima: https://reticulum.network/manual/gettingstartedfast.html"
m ask_cont     "Continue anyway?" "Continuo comunque?"
m step_py      "Python environment" "Ambiente Python"
m step_node    "WhatsApp sidecar (npm)" "Sidecar WhatsApp (npm)"
m step_tests   "Self-test" "Autotest"
m tests_ok     "Self-test passed" "Autotest superato"
m tests_bad    "The self-test FAILED (output above). Installation continues, but voice/image conversion may not work." "L'autotest è FALLITO (output sopra). L'installazione prosegue, ma la conversione di vocali/immagini potrebbe non funzionare."
m step_cfg     "Configuration" "Configurazione"
m ask_owner    "Your LXMF address (32 hex characters; in Sideband: the 'LXMF address' shown in Connectivity/Settings)" "Il tuo indirizzo LXMF (32 caratteri esadecimali; in Sideband: l'\"indirizzo LXMF\" mostrato in Connettività/Impostazioni)"
m bad_owner    "That is not a valid address (32 hex characters expected)." "Indirizzo non valido (servono 32 caratteri esadecimali)."
m owner_hint   "Careful: use the client's LXMF *delivery* address, not its identity hash." "Attenzione: usa l'indirizzo LXMF *di consegna* del client, non l'hash dell'identità."
m cfg_created  "Config written: %s" "Configurazione scritta: %s"
m cfg_kept     "Existing config kept: %s" "Configurazione esistente mantenuta: %s"
m cfg_migrated "Config from an earlier version updated to the current key names." "Configurazione di una versione precedente aggiornata ai nomi attuali."
m owner_needed "No owner address: run ./setup.sh --owner <address> or edit %s" "Nessun indirizzo owner: lancia ./setup.sh --owner <indirizzo> oppure modifica %s"
m step_svc     "Services" "Servizi"
m svc_written  "Service files installed in %s" "File dei service installati in %s"
m step_pair    "WhatsApp pairing" "Abbinamento WhatsApp"
m paired_yes   "WhatsApp is already paired (session in %s)." "WhatsApp è già abbinato (sessione in %s)."
m pair_intro   "Bifrost links to WhatsApp like WhatsApp Web (an extra 'linked device'). It uses an unofficial library: WhatsApp may ban numbers that use it. A dedicated number is the prudent choice." "Bifrost si collega a WhatsApp come WhatsApp Web (un 'dispositivo collegato' in più). Usa una libreria non ufficiale: WhatsApp può bannare i numeri che la usano. Un numero dedicato è la scelta prudente."
m pair_ask     "How do you want to pair?" "Come vuoi abbinare?"
m pair_opt_qr  "1) scan a QR code with the phone" "1) scansiono un QR con il telefono"
m pair_opt_code "2) type an 8-character code on the phone" "2) digito un codice di 8 caratteri sul telefono"
m pair_opt_skip "3) later" "3) più tardi"
m pair_phone   "Phone number of the WhatsApp account, with country code, digits only (e.g. 393331234567)" "Numero di telefono dell'account WhatsApp, con prefisso internazionale, solo cifre (es. 393331234567)"
m pair_qr_how  "On the phone: WhatsApp > Settings > Linked devices > Link a device, then scan the QR below." "Sul telefono: WhatsApp > Impostazioni > Dispositivi collegati > Collega un dispositivo, poi scansiona il QR qui sotto."
m pair_code_how "On the phone: WhatsApp > Settings > Linked devices > Link a device > 'Link with phone number instead', then type the code that appears below." "Sul telefono: WhatsApp > Impostazioni > Dispositivi collegati > Collega un dispositivo > 'Collega con numero di telefono', poi digita il codice che compare qui sotto."
m pair_ok      "Pairing complete." "Abbinamento completato."
m pair_bad     "Pairing did not complete. Run ./setup.sh again and choose 'Re-pair WhatsApp'." "Abbinamento non completato. Rilancia ./setup.sh e scegli 'Abbina di nuovo WhatsApp'."
m pair_skipped "Pairing skipped. Do it later with ./setup.sh (menu: re-pair WhatsApp)." "Abbinamento rimandato. Fallo dopo con ./setup.sh (menu: abbina di nuovo WhatsApp)."
m step_start   "Starting" "Avvio"
m wait_addr    "Waiting for the bridge to publish its address..." "Attendo che il bridge pubblichi il suo indirizzo..."
m done_title   "Done." "Fatto."
m done_addr    "Bridge LXMF address: %s" "Indirizzo LXMF del bridge: %s"
m done_next    "Now, from Sideband/MeshChatX: open a conversation with that address (announce/add it) and send /status. /help lists the commands." "Ora, da Sideband/MeshChatX: apri una conversazione con quell'indirizzo (annuncio/aggiungi) e invia /stato. /aiuto elenca i comandi."
m done_noaddr  "The bridge has not published its address yet. Look at: sudo journalctl -u bifrost -f" "Il bridge non ha ancora pubblicato il suo indirizzo. Guarda: sudo journalctl -u bifrost -f"
m done_nostart "Services installed but not started (WhatsApp not paired). After pairing: sudo systemctl enable --now bifrost-sidecar bifrost" "Service installati ma non avviati (WhatsApp non abbinato). Dopo l'abbinamento: sudo systemctl enable --now bifrost-sidecar bifrost"
m menu_title   "Bifrost %s is installed. What do you want to do?" "Bifrost %s è installato. Cosa vuoi fare?"
m menu_1       "1) Show status" "1) Mostra lo stato"
m menu_2       "2) Show the log (Ctrl+C to leave)" "2) Mostra il log (Ctrl+C per uscire)"
m menu_3       "3) Restart the services" "3) Riavvia i servizi"
m menu_4       "4) Re-pair WhatsApp" "4) Abbina di nuovo WhatsApp"
m menu_5       "5) Change the owner address" "5) Cambia l'indirizzo owner"
m menu_6       "6) Change the language" "6) Cambia la lingua"
m menu_7       "7) Update (dependencies, config, services) from this folder" "7) Aggiorna (dipendenze, configurazione, service) da questa cartella"
m menu_8       "8) Uninstall" "8) Disinstalla"
m menu_0       "0) Quit" "0) Esci"
m menu_ask     "Choice" "Scelta"
m lang_set     "Language set to %s." "Lingua impostata su %s."
m owner_set    "Owner address updated." "Indirizzo owner aggiornato."
m ask_unin     "Remove the Bifrost services?" "Rimuovo i service di Bifrost?"
m ask_data     "Also delete %s? It holds your WhatsApp session and the bridge identity (its LXMF address)." "Cancello anche %s? Contiene la sessione WhatsApp e l'identità del bridge (il suo indirizzo LXMF)."
m unin_done    "Uninstalled. The program folder (%s) was left alone: delete it yourself if you want." "Disinstallato. La cartella del programma (%s) non è stata toccata: cancellala tu se vuoi."
m ask_lang     "Language / Lingua [en/it]" "Language / Lingua [en/it]"
m yes_hint     "[y/N]" "[s/N]"
m unknown_opt  "Unknown option: %s" "Opzione sconosciuta: %s"
m yes_needs    "--yes needs --owner <address> on a first install." "--yes richiede --owner <indirizzo> alla prima installazione."
m svc_status   "Services:" "Servizi:"

say()  { local fmt="${M[$LANGSEL.$1]:-$1}"; shift; printf "$fmt\n" "$@"; }
step() { local fmt="${M[$LANGSEL.$1]}"; shift; printf "\n== $fmt\n" "$@"; }
warn() { local fmt="${M[$LANGSEL.$1]:-$1}"; shift; printf "!! $fmt\n" "$@" >&2; }
die()  { warn "$@"; exit 1; }

# yes/no question; with --yes it is answered yes
confirm() {
  local ans
  [ "$YES" = 1 ] && return 0
  read -r -p "$(say "$1" "${@:2}") $(say yes_hint) " ans
  case "${ans,,}" in y|yes|s|si|sì) return 0 ;; *) return 1 ;; esac
}

# ------------------------------------------------------------------ args
while [ $# -gt 0 ]; do
  case "$1" in
    --lang)   LANGSEL="${2:-}"; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    --owner)  OWNER="${2:-}"; shift 2 ;;
    --pair)   PAIR="${2:-}"; shift 2 ;;
    --phone)  PHONE="${2:-}"; shift 2 ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --uninstall) ACTION=uninstall; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) LANGSEL="${LANGSEL:-en}"; warn unknown_opt "$1"; exit 2 ;;
  esac
done

# language: flag > existing config > ask > $LANG
if [ -z "$LANGSEL" ] && [ -f "$CFG" ]; then
  LANGSEL="$(python3 "$DIR/tools/cfgtool.py" get "$CFG" bridge language 2>/dev/null | tr -d '[:space:]')"
fi
case "$LANGSEL" in en|it) ;; *)
  LANGSEL=en; case "${LANG:-}" in it*) LANGSEL=it ;; esac
  if [ "$YES" = 0 ] && [ -t 0 ]; then
    read -r -p "$(say ask_lang) " a; a="${a,,}"; [ "$a" = en ] || [ "$a" = it ] && LANGSEL="$a"
  fi ;;
esac

# ------------------------------------------------------------------ helpers
HAVE_SYSTEMD=0; command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system -o -n "${BIFROST_UNIT_DIR:-}" ] && HAVE_SYSTEMD=1
SUDO=""; [ "$(id -u)" != 0 ] && SUDO="sudo"
cfg_get() { python3 "$DIR/tools/cfgtool.py" get "$CFG" "$1" "$2"; }
cfg_set() { python3 "$DIR/tools/cfgtool.py" set "$CFG" "$1" "$2" "$3"; }
valid_addr() { [[ "$1" =~ ^[0-9a-fA-F]{32}$ ]]; }
clean_addr() { local a="${1//[<>[:space:]]/}"; echo "${a,,}"; }
is_paired() { [ -f "$DATA/wa-auth/creds.json" ] && grep -q '"registered": *true' "$DATA/wa-auth/creds.json" 2>/dev/null; }
is_installed() { [ -f "$CFG" ] && [ -x "$VENV/bin/python" ]; }
sysd() { $SUDO systemctl "$@"; }

check_deps() {
  step step_deps
  local miss=() pkgs=()
  command -v node >/dev/null   || { miss+=(node);   pkgs+=(nodejs); }
  command -v npm >/dev/null    || { miss+=(npm);    pkgs+=(npm); }
  command -v ffmpeg >/dev/null || { miss+=(ffmpeg); pkgs+=(ffmpeg); }
  command -v python3 >/dev/null || { miss+=(python3); pkgs+=(python3); }
  python3 -c 'import venv, ensurepip' 2>/dev/null || { miss+=(python3-venv); pkgs+=(python3-venv); }
  if [ ${#miss[@]} -gt 0 ]; then
    say miss_pkgs "${miss[*]}"
    if command -v apt-get >/dev/null; then
      confirm ask_apt || die no_apt
      $SUDO apt-get update && $SUDO apt-get install -y "${pkgs[@]}" || die miss_pkgs "${miss[*]}"
    else
      die no_apt
    fi
  fi
  local nv; nv="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  [ "$nv" -ge 20 ] 2>/dev/null || die node_old "$(node -v 2>/dev/null || echo '?')"
  local enc; enc="$(ffmpeg -hide_banner -encoders 2>/dev/null || true)"   # captured: 'grep -q' on a pipe breaks under pipefail
  grep -q libcodec2 <<<"$enc" || die no_codec2
  grep -q libopus <<<"$enc" || die no_opus
  say deps_ok "$(node -v)"

  if { [ "$HAVE_SYSTEMD" = 1 ] && systemctl is-active --quiet rnsd 2>/dev/null; } || pgrep -f 'rnsd' >/dev/null 2>&1; then
    say rnsd_ok
  else
    warn rnsd_missing
    confirm ask_cont || exit 1
  fi
}

setup_python() {
  step step_py
  mkdir -p "$DATA" && chmod 700 "$DATA"
  # shellcheck disable=SC2086
  [ -x "$VENV/bin/python" ] || python3 -m venv ${BIFROST_VENV_FLAGS:-} "$VENV" || die step_py
  "$VENV/bin/python" -m pip install -q --upgrade pip >/dev/null 2>&1 || true
  "$VENV/bin/python" -m pip install -q -r "$DIR/requirements.txt" || die step_py
  "$VENV/bin/python" -c 'import RNS, LXMF; print("RNS", RNS.__version__, "- LXMF", LXMF.__version__)' || die step_py
}

setup_node() {
  step step_node
  (cd "$DIR/sidecar" && npm install --omit=dev --no-audit --no-fund) || die step_node
}

run_selftest() {
  [ "$SKIP_TESTS" = 1 ] && return 0
  step step_tests
  local d; d="$(mktemp -d)"
  if "$VENV/bin/python" "$DIR/tests/make_media.py" "$d" \
     && "$VENV/bin/python" "$DIR/tests/test_i18n.py" \
     && "$VENV/bin/python" "$DIR/tests/test_core.py" "$d" "$LANGSEL" | tail -1; then
    say tests_ok
  else
    warn tests_bad
  fi
  rm -rf "$d"
}

owner_is_set() {
  local o; o="$(cfg_get bridge owner)"
  [ -n "$o" ] && ! grep -q 'REPLACE_WITH\|SOSTITUISCI' <<<"$o"
}

# sets OWNER_VAL (from --owner or by asking); dies on an invalid one or on --yes without --owner
get_owner() {
  local a="$OWNER"
  if [ -n "$a" ]; then
    a="$(clean_addr "$a")"; valid_addr "$a" || die bad_owner
  elif [ "$YES" = 1 ]; then
    die yes_needs
  else
    say owner_hint
    while :; do
      read -r -p "$(say ask_owner): " a; a="$(clean_addr "$a")"
      valid_addr "$a" && break
      say bad_owner
    done
  fi
  OWNER_VAL="$a"
}

setup_config() {
  step step_cfg
  local example="$DIR/config.example.ini"; [ "$LANGSEL" = it ] && example="$DIR/config.example.it.ini"
  if [ ! -f "$CFG" ]; then
    get_owner                       # asked first: a refused answer must not leave a half-made config behind
    cp "$example" "$CFG"; chmod 600 "$CFG"
    cfg_set bridge owner "$OWNER_VAL"
    cfg_set bridge language "$LANGSEL"
    say cfg_created "$CFG"
  else
    # alpha0.1/0.2 used Italian key names: rename them, keep the user's values and comments
    if grep -q '^\(proprietario\|\[limiti\]\)' "$CFG"; then
      cp "$CFG" "$CFG.bak"; python3 "$DIR/tools/cfgtool.py" migrate "$CFG" "$LANGSEL"; say cfg_migrated
    fi
    [ -n "$(cfg_get bridge language)" ] || cfg_set bridge language "$LANGSEL"
    if [ -n "$OWNER" ]; then
      OWNER="$(clean_addr "$OWNER")"; valid_addr "$OWNER" || die bad_owner
      cfg_set bridge owner "$OWNER"
    elif ! owner_is_set; then
      get_owner; cfg_set bridge owner "$OWNER_VAL"
    fi
    say cfg_kept "$CFG"
  fi
}

install_services() {
  step step_svc
  [ "$HAVE_SYSTEMD" = 1 ] || { warn nosystemd; return 0; }
  [ -z "$SUDO" ] || command -v sudo >/dev/null || die nosudo
  local node_bin rnsd_unit="network-online.target" rnsd_req=""
  node_bin="$(command -v node)"
  if systemctl list-unit-files rnsd.service 2>/dev/null | grep -q '^rnsd\.service' || [ -f "$UNIT_DIR/rnsd.service" ]; then
    rnsd_unit="rnsd.service"; rnsd_req="Requires=rnsd.service"
  fi
  local f
  for f in bifrost-sidecar bifrost; do
    sed -e "s#@USER@#$(id -un)#g" -e "s#@DIR@#$DIR#g" -e "s#@DATA@#$DATA#g" -e "s#@LANG@#$LANGSEL#g" \
        -e "s#@NODE@#$node_bin#g" -e "s#@RNSD_UNIT@#$rnsd_unit#g" -e "s#@RNSD_REQUIRES@#$rnsd_req#g" \
        "$DIR/systemd/$f.service.in" | $SUDO tee "$UNIT_DIR/$f.service" >/dev/null || die step_svc
  done
  sysd daemon-reload
  say svc_written "$UNIT_DIR"
}

pair_whatsapp() {
  step step_pair
  if is_paired && [ "${1:-}" != force ]; then say paired_yes "$DATA/wa-auth"; return 0; fi
  say pair_intro
  local choice="$PAIR"
  if [ -z "$choice" ]; then
    if [ "$YES" = 1 ]; then choice=none; else
      say pair_ask; say pair_opt_qr; say pair_opt_code; say pair_opt_skip
      read -r -p "> " c; case "$c" in 1) choice=qr ;; 2) choice=code ;; *) choice=none ;; esac
    fi
  fi
  case "$choice" in
    none) say pair_skipped; return 1 ;;
    code)
      local ph="${PHONE//[^0-9]/}"
      while [ -z "$ph" ] && [ "$YES" = 0 ]; do read -r -p "$(say pair_phone): " ph; ph="${ph//[^0-9]/}"; done
      [ -n "$ph" ] || { say pair_skipped; return 1; }
      say pair_code_how
      [ "${1:-}" = force ] && rm -rf "$DATA/wa-auth"
      (cd "$DIR/sidecar" && BIFROST_DIR="$DATA" BIFROST_LANG="$LANGSEL" BIFROST_PAIR_ONLY=1 WA_PHONE="$ph" timeout --foreground 600 node index.mjs) ;;
    *)
      say pair_qr_how
      [ "${1:-}" = force ] && rm -rf "$DATA/wa-auth"
      (cd "$DIR/sidecar" && BIFROST_DIR="$DATA" BIFROST_LANG="$LANGSEL" BIFROST_PAIR_ONLY=1 timeout --foreground 600 node index.mjs) ;;
  esac
  if is_paired; then say pair_ok; return 0; fi
  warn pair_bad; return 1
}

start_services() {
  step step_start
  [ "$HAVE_SYSTEMD" = 1 ] || return 0
  sysd enable bifrost-sidecar bifrost >/dev/null 2>&1
  sysd restart bifrost-sidecar bifrost
}

final_summary() {
  local started="$1" addr="" i
  echo
  if [ "$started" = 1 ]; then
    say wait_addr
    for i in $(seq 1 "${BIFROST_ADDR_WAIT:-40}"); do [ -s "$DATA/address.txt" ] && break; sleep 1; done
    addr="$(cat "$DATA/address.txt" 2>/dev/null || true)"
  fi
  say done_title
  if [ -n "$addr" ]; then say done_addr "$addr"; say done_next
  elif [ "$started" = 1 ]; then say done_noaddr
  else say done_nostart; fi
}

do_install() {
  check_deps
  setup_python
  setup_node
  run_selftest
  setup_config
  owner_is_set || die owner_needed "$CFG"
  install_services
  local started=0
  if pair_whatsapp; then start_services && started=1; fi
  final_summary "$started"
}

do_update() {
  check_deps; setup_python; setup_node; run_selftest; setup_config; install_services
  if is_paired; then start_services; final_summary 1; else final_summary 0; fi
}

do_uninstall() {
  confirm ask_unin || exit 0
  if [ "$HAVE_SYSTEMD" = 1 ]; then
    sysd disable --now bifrost bifrost-sidecar 2>/dev/null
    $SUDO rm -f "$UNIT_DIR/bifrost.service" "$UNIT_DIR/bifrost-sidecar.service"
    sysd daemon-reload
  fi
  if [ "$YES" = 0 ] && confirm ask_data "$DATA"; then rm -rf "$DATA"; fi
  say unin_done "$DIR"
}

menu() {
  while :; do
    echo; say menu_title "$VERSION"
    say menu_1; say menu_2; say menu_3; say menu_4; say menu_5; say menu_6; say menu_7; say menu_8; say menu_0
    read -r -p "$(say menu_ask): " c
    case "$c" in
      1) say svc_status; sysd --no-pager status bifrost bifrost-sidecar 2>&1 | sed -n '1,14p'
         [ -s "$DATA/address.txt" ] && say done_addr "$(cat "$DATA/address.txt")"
         is_paired && say paired_yes "$DATA/wa-auth" ;;
      2) $SUDO journalctl -u bifrost -u bifrost-sidecar -f -n 40 ;;
      3) sysd restart bifrost-sidecar bifrost ;;
      4) sysd stop bifrost-sidecar bifrost; if pair_whatsapp force; then sysd start bifrost-sidecar bifrost; fi ;;
      5) local a
         while :; do read -r -p "$(say ask_owner): " a; a="$(clean_addr "$a")"; valid_addr "$a" && break; say bad_owner; done
         cfg_set bridge owner "$a"; sysd restart bifrost; say owner_set ;;
      6) local l; read -r -p "$(say ask_lang) " l; l="${l,,}"
         if [ "$l" = en ] || [ "$l" = it ]; then
           LANGSEL="$l"; cfg_set bridge language "$l"; install_services; sysd restart bifrost-sidecar bifrost; say lang_set "$l"
         fi ;;
      7) do_update; ;;
      8) do_uninstall; return ;;
      0|q|"") return ;;
    esac
  done
}

# ------------------------------------------------------------------ main
say title "$VERSION"
[ "$(id -u)" != 0 ] || [ -n "${BIFROST_ALLOW_ROOT:-}" ] || die root

case "$ACTION" in
  uninstall) do_uninstall; exit 0 ;;
esac

if is_installed && [ "$YES" = 0 ] && [ -z "$OWNER" ] && [ -t 0 ]; then
  menu
else
  do_install
fi
