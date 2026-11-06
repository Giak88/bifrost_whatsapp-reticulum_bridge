# Changelog

## alpha0.4

- **`/repeat N` (`/ripeti N`)**: the bridge keeps every message it sent you (`history_h`, default 48 h, up to `history_max`, default 100; photos and voice notes included) and sends the last N again on request, oldest first, marked `↻ HH:MM`. Useful after being out of LoRa coverage. The number is required: `/repeat` alone replies with the usage.
- New `[limits]` keys `history_h` and `history_max` (`history_max = 0` turns the history off).

## alpha0.3

- **English and Italian.** One catalogue (`bridge/i18n.py`) drives every bot reply, log line and sidecar message; the language is the `language` key of the config. Commands exist in both languages (`/download` = `/scarica`, `/quality` = `/qualita`, ...), and level words too (`low` = `basso`, ...).
- **Guided installer** `setup.sh` (English/Italian): dependency check with optional `apt-get`, venv, npm, self-test, owner address, systemd units rendered for the real user and path (the project folder can live anywhere), WhatsApp pairing by QR or code, start, a maintenance menu (status, logs, start, stop, restart, re-pair, change owner/language, update, uninstall) and `./setup.sh start|stop|restart|status|logs`.
- Config keys are now English (`owner`, `[limits]`, `quality_img`, `groups = none|followed|all`, ...). Files from `alpha0.1`/`alpha0.2` keep working; `setup.sh` migrates them (keeping a `.bak`).
- The state file written by `alpha0.2` (Italian level names) is read and converted.
- The bridge writes its LXMF address to `~/.bifrost/address.txt` and validates the owner address at start.
- Sidecar: `BIFROST_PAIR_ONLY` mode (pair, then exit) used by the installer.
- Tests: catalogue completeness, config compatibility, core in both languages, setup script against stubs, end-to-end in both languages.
- MIT licence, READMEs in both languages.

## alpha0.2

- `/quality` (`/qualita`): quality of received photos and voice notes (low/medium/high/original) changeable from the chat, with automatic step-down if the result is too big.
- Sends up to 30 MB (`max_send_mb`), with a notice when a send is rejected; videos sent as files arrive on WhatsApp as videos.
- The sidecar deletes spool files after sending; delivery to the owner is logged and retried (4 tries, 30 s apart, propagation fallback if configured).

## alpha0.1

- First version: text, photos, voice notes, files, chat commands, `/download` confirmation for big media.
