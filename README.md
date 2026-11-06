# Bifrost

**English** · [Italiano](README.it.md)

A bridge between **WhatsApp** and **Reticulum / LXMF**. Your WhatsApp chats show up as LXMF messages in Sideband or MeshChatX, and you answer from there — over LoRa, TCP, or whatever your Reticulum network is made of. Photos, voice notes, videos and files go both ways, squeezed to fit a radio link.

> **Status: alpha (`alpha0.3`).** Tested end to end against a real `rnsd` and used live on a Debian 13 home server with a Heltec V4 RNode. Expect rough edges: see [Known limits](#known-limits).

```
WhatsApp ── Baileys (Node sidecar) ──Unix socket── bridge (Python) ── rnsd (shared instance) ── RNode / TCP / ...
```

The bridge **never opens your radio**. It is a client of the `rnsd` shared instance, exactly like Sideband or MeshChatX, so they can run at the same time on the same node. It has its own LXMF identity (its own address) stored in `~/.bifrost/identity`.

## Features

- Text, photos, voice notes, videos and documents, both directions
- **Media compression for LoRa**: photos become WebP (Sideband's low/medium/high presets), voice notes become Codec2 or Opus
- **Confirmation for big media**: anything over a threshold (32 KB by default) is announced with its size and estimated airtime; you fetch it with `/download N`
- **Quality switchable from the chat** (`/quality`), separately for photos and voice notes
- Chat management by command: pick the active chat, write to another one with `#N text`, reply to the last one with `/r`
- WhatsApp groups are off by default; follow the ones you want with `/follow N`
- Commands work in **English and Italian** (`/download` = `/scarica`, ...); bot replies and logs follow the configured language
- Delivery to you is logged and retried; optional propagation-node fallback
- Guided installer (`setup.sh`) in English or Italian, with a menu for later maintenance

## Requirements

- A Linux box with **systemd** (developed on Debian 13)
- **Reticulum** (`rnsd`) already installed and running, with your radio/network configured. Bifrost does not set Reticulum up for you
- Node.js **≥ 20**, npm, **ffmpeg built with libcodec2 and libopus** (the stock Debian/Ubuntu `ffmpeg` has both), Python 3 with `venv`
- A WhatsApp account. **A dedicated number is the prudent choice**: Bifrost uses [Baileys](https://github.com/WhiskeySockets/Baileys), an *unofficial* WhatsApp Web library, and WhatsApp can ban numbers that use unofficial clients
- An LXMF client (Sideband, MeshChatX, ...) and its **LXMF address**

`setup.sh` checks all of this and offers to `apt-get install` what is missing.

## Quick start

```bash
git clone https://github.com/Giak88/bifrost-whatsapp-reticulum.git
cd bifrost-whatsapp-reticulum
./setup.sh                 # asks for the language, then walks you through everything
# or:  ./setup.sh --lang en
```

The installer:

1. checks the dependencies (and offers to install them)
2. checks that `rnsd` is running
3. creates the Python environment in `~/.bifrost/venv` and installs the sidecar's npm packages
4. runs a quick self-test of the conversions
5. asks for **your LXMF address** (32 hex characters) and writes `~/.bifrost/config.ini`
6. installs the two systemd services (`bifrost-sidecar`, `bifrost`)
7. pairs WhatsApp (QR code, or an 8-character code typed on the phone)
8. starts everything and prints **the bridge's LXMF address**

Then, in Sideband/MeshChatX, open a conversation with that address and send `/status`.

> Use your client's **LXMF delivery address** as the owner, not its identity hash. If the bridge ignores you, the log says `Ignoring message from <...>`: that `<...>` is the address to use.

Run `./setup.sh` again at any time for a menu: status, logs, restart, re-pair WhatsApp, change owner, change language, update, uninstall.

Unattended: `./setup.sh --lang en --yes --owner <32-hex> [--pair code --phone 15551234567]`.

## Commands

Send these from your LXMF client. Every message from WhatsApp starts with `#N Name:` (groups: `#N Group/Sender:`).

| Command | What it does |
|---|---|
| plain text | goes to the active chat |
| `#N text` | goes to chat N without changing the active one |
| `/r text` | replies to the last chat that wrote to you |
| `/to N`, `/to +15551234567` | sets the active chat (by number or phone number) |
| `/chat [n]` | last chats with their numbers |
| `/download N`, `/cancel N`, `/pending` | media waiting for confirmation |
| `/follow N`, `/unfollow N` | forward a WhatsApp group (none by default) |
| `/quality`, `/quality img medium`, `/quality audio medium` | quality of the photos and voice notes you *receive* |
| `/status`, `/help` | version, WhatsApp state, active chat / command list |

Italian aliases: `/scarica`, `/annulla`, `/pendenti`, `/segui`, `/ignora`, `/qualita`, `/stato`, `/aiuto`. Levels can be written `low|medium|high|original` or `basso|medio|alto|originale`.

Attachments (photo, voice note, file) sent from your client go to the active chat.

## Media

**What you receive** (WhatsApp → LXMF). Defaults: `low` for both; the choice made with `/quality` is saved.

| Level | Photos | Voice notes |
|---|---|---|
| `low` | 320 px, WebP q22 (Sideband "low") | Codec2 2400, ~0.3 KB/s |
| `medium` | 640 px, WebP q66 | Opus 12 kbps, ~1.5 KB/s |
| `high` | 1280 px, WebP q75 | Opus 24 kbps, ~3 KB/s |
| `original` | file unchanged | WhatsApp's Opus, unchanged |

If a result is bigger than `max_file_mb`, Bifrost steps down a level on its own (`[reduced to low: too large]`). Videos and documents arrive unchanged.

Whatever is still bigger than `confirm_threshold_kb` *after* conversion is held: you get a notice with the size and the estimated time over LoRa, and receive it with `/download N`. Held media expire after 24 h. Above `max_file_mb` (0.9) it cannot be delivered at all: a stock LXMF router refuses deliveries over 1000 KB.

**What you send** (LXMF → WhatsApp) is compressed by *your* client (pick the level in Sideband when sending); Bifrost forwards it without degrading it.

| From your client | On WhatsApp |
|---|---|
| image | JPEG |
| audio (Codec2 or Opus) | voice note |
| file | a **video** if it is `.mp4`/`.mov`/... up to `max_video_wa_mb` (16 MB), otherwise a document |

**Big files.** Bifrost's LXMF router accepts up to `max_send_mb` (30 by default; stock LXMF stops at 1 MB). If a send exceeds it, you get `⚠️ Send rejected`. On a fast link (TCP, Tailscale) 12 MB takes seconds; over LoRa it takes hours and hogs the channel, so don't.

## Configuration

`~/.bifrost/config.ini` (documented template: [`config.example.ini`](config.example.ini)). After editing: `sudo systemctl restart bifrost`.

| Key | Default | Meaning |
|---|---|---|
| `[bridge] owner` | – | your LXMF address(es), comma-separated |
| `language` | `en` | `en` or `it`: bot replies and logs |
| `max_send_mb` | 30 | biggest file you can send to WhatsApp |
| `propagation_node` | – | optional fallback for deferred delivery |
| `[limits] confirm_threshold_kb` | 32 | above this, ask before sending the media |
| `max_file_mb` | 0.9 | above this, never deliver |
| `quality_img`, `quality_audio` | `low` | defaults of `/quality` |
| `codec2_mode` | 2400 | Codec2 mode of the `low` voice level |
| `link_kbps` | 1.2 | your real link speed, only for the time estimate |
| `max_video_wa_mb` | 16 | videos up to this size go to WhatsApp as videos |
| `pending_ttl_h` | 24 | hours before unfetched media are discarded |
| `groups` | `followed` | `none`, `followed` or `all` |

Configs from `alpha0.1`/`alpha0.2` (Italian key names such as `proprietario`, `[limiti]`) are still read, and `setup.sh` renames them for you.

## Running alongside Sideband / MeshChatX

They all talk to the same `rnsd` shared instance, so they can be connected to the same radio at once. Only `rnsd` touches the serial port. Bifrost logs a warning if it finds no shared instance and starts its own Reticulum instead; if you see it, check that `rnsd` is running.

## Logs

```bash
sudo journalctl -u bifrost -f            # the LXMF side: deliveries, retries, the bridge address
sudo journalctl -u bifrost-sidecar -f    # the WhatsApp side
```

The bridge address is also in `~/.bifrost/address.txt`. The logs never contain message text.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/status` gets no answer | the owner address is the identity hash instead of the delivery address; look for `Ignoring message from` in the log |
| WhatsApp messages never arrive | check `journalctl -u bifrost-sidecar`; look at the `upsert` lines; `msg=NULL` means WhatsApp could not be decrypted |
| Sidecar stops with exit code 2 | the phone unlinked the device: `./setup.sh` → re-pair WhatsApp |
| Journal full of `Pathing` lines | `loglevel` in `~/.reticulum/config` is too high (use 4) |
| `Your ffmpeg has no libcodec2` during setup | install the stock `ffmpeg` package; some builds omit Codec2 |
| `Delivery failed (attempt n/4)` | the owner node is not reachable right now; it retries every 30 s, then gives up (or uses the propagation node if configured) |

## Known limits

- **Delivery to you is retried up to 4 times, 30 s apart.** After that, if no `propagation_node` is set, the message is logged as lost (`Delivery failed for good`). The propagation fallback is implemented but not field-tested.
- Ignored: reactions, replies/quotes, edits and deletions, polls, status updates. Locations arrive as text.
- A WhatsApp message that cannot be decrypted is dropped.
- Receiving a video above ~1000 KB is impossible over LXMF (the client's router limit): videos you *receive* in that range come as a notice only.
- Several owners are supported but lightly tested.
- Messages from unfollowed groups are dropped without trace (apart from their entry in `/chat`).

## Security notes

- WhatsApp's end-to-end encryption ends on the machine running Bifrost. `~/.bifrost/wa-auth` is your WhatsApp session: treat it like a password.
- Only LXMF addresses listed in `owner` can control the bridge; anything else is ignored.
- Reticulum/LXMF encrypts the radio leg, but the bridge host sees everything in clear.

## Development

```bash
tests/run_tests.sh              # catalogue, config, core (EN and IT); needs rns + lxmf + Pillow + ffmpeg
tests/e2e.sh python3 en         # end to end with a private rnsd, the real bridge and a fake sidecar
tests/test_setup.sh             # setup.sh against stubbed sudo/systemctl/npm
```

Layout: `bridge/` (core logic, LXMF side, transcoding, messages), `sidecar/` (Baileys), `systemd/` (unit templates), `tools/` (config editor), `tests/`.

Adding a language: add its code to `LANGS` in `bridge/i18n.py`, fill every message (`tests/test_i18n.py` fails on missing ones), add its command aliases in `bridge/core.py`, and translate `setup.sh` and the example config.

## Credits

Idea and field testing by [Giak88](https://github.com/Giak88). Designed and written with Claude (Anthropic).

Built on [Reticulum](https://reticulum.network) and [LXMF](https://github.com/markqvist/LXMF) by Mark Qvist, [Sideband](https://github.com/markqvist/Sideband)'s message and media conventions, and [Baileys](https://github.com/WhiskeySockets/Baileys). Not affiliated with or endorsed by WhatsApp/Meta.

## License

MIT, see [LICENSE](LICENSE).
