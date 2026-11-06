# Bifrost

[English](README.md) · **Italiano**

Un ponte tra **WhatsApp** e **Reticulum / LXMF**. Le tue chat WhatsApp arrivano come messaggi LXMF in Sideband o MeshChatX e rispondi da lì, via LoRa, TCP o qualunque cosa compone la tua rete Reticulum. Foto, vocali, video e file viaggiano in entrambe le direzioni, compressi per stare in un link radio.

> **Stato: alpha (`alpha0.3`).** Provato end to end contro un vero `rnsd` e usato dal vivo su un server domestico Debian 13 con un RNode Heltec V4. Aspettati qualche spigolo: vedi [Limiti noti](#limiti-noti).

```
WhatsApp ── Baileys (sidecar Node) ──socket Unix── bridge (Python) ── rnsd (shared instance) ── RNode / TCP / ...
```

Il bridge **non apre mai la tua radio**. È un client della shared instance di `rnsd`, esattamente come Sideband o MeshChatX, quindi possono girare insieme sullo stesso nodo. Ha una sua identità LXMF (un suo indirizzo) in `~/.bifrost/identity`.

## Funzioni

- Testo, foto, vocali, video e documenti, in entrambe le direzioni
- **Compressione dei media per il LoRa**: le foto diventano WebP (preset basso/medio/alto di Sideband), i vocali Codec2 oppure Opus
- **Conferma per i media grossi**: sopra una soglia (32 KB di default) arriva un avviso con dimensione e tempo stimato; lo scarichi con `/scarica N`
- **Qualità cambiabile da chat** (`/qualita`), separata per foto e vocali
- Gestione delle chat a comandi: scegli la chat attiva, scrivi a un'altra con `#N testo`, rispondi all'ultima con `/r`
- I gruppi WhatsApp sono disattivati di default; segui quelli che vuoi con `/segui N`
- I comandi funzionano in **italiano e in inglese** (`/scarica` = `/download`, ...); le risposte del bot e i log seguono la lingua configurata
- La consegna verso di te è registrata nel log e ritentata; fallback opzionale via propagation node
- Installer guidato (`setup.sh`) in italiano o inglese, con un menu per la manutenzione successiva

## Requisiti

- Una macchina Linux con **systemd** (sviluppato su Debian 13)
- **Reticulum** (`rnsd`) già installato e attivo, con radio/rete configurate. Bifrost non configura Reticulum al posto tuo
- Node.js **≥ 20**, npm, **ffmpeg compilato con libcodec2 e libopus** (il pacchetto `ffmpeg` standard di Debian/Ubuntu li ha entrambi), Python 3 con `venv`
- Un account WhatsApp. **Un numero dedicato è la scelta prudente**: Bifrost usa [Baileys](https://github.com/WhiskeySockets/Baileys), una libreria WhatsApp Web *non ufficiale*, e WhatsApp può bannare i numeri che usano client non ufficiali
- Un client LXMF (Sideband, MeshChatX, ...) e il suo **indirizzo LXMF**

`setup.sh` controlla tutto questo e propone di installare con `apt-get` ciò che manca.

## Avvio rapido

```bash
git clone https://github.com/Giak88/bifrost-whatsapp-reticulum.git
cd bifrost-whatsapp-reticulum
./setup.sh                 # chiede la lingua, poi ti guida in tutto
# oppure:  ./setup.sh --lang it
```

L'installer:

1. controlla le dipendenze (e propone di installarle)
2. controlla che `rnsd` sia attivo
3. crea l'ambiente Python in `~/.bifrost/venv` e installa i pacchetti npm del sidecar
4. esegue un rapido autotest delle conversioni
5. chiede **il tuo indirizzo LXMF** (32 caratteri esadecimali) e scrive `~/.bifrost/config.ini`
6. installa i due service systemd (`bifrost-sidecar`, `bifrost`)
7. abbina WhatsApp (QR, oppure un codice di 8 caratteri da digitare sul telefono)
8. avvia tutto e stampa **l'indirizzo LXMF del bridge**

Poi, in Sideband/MeshChatX, apri una conversazione con quell'indirizzo e invia `/stato`.

> Come owner usa l'**indirizzo LXMF di consegna** del client, non l'hash della sua identità. Se il bridge ti ignora, il log dice `Ignoro messaggio da <...>`: quel `<...>` è l'indirizzo da usare.

Rilancia `./setup.sh` quando vuoi per un menu: stato, log, avvio, arresto, riavvio, nuovo abbinamento WhatsApp, cambio owner, cambio lingua, aggiornamento, disinstallazione.

Non interattivo: `./setup.sh --lang it --yes --owner <32-hex> [--pair code --phone 393331234567]`.

## Comandi

Mandali dal tuo client LXMF. Ogni messaggio da WhatsApp inizia con `#N Nome:` (gruppi: `#N Gruppo/Mittente:`).

| Comando | Cosa fa |
|---|---|
| testo semplice | va alla chat attiva |
| `#N testo` | va alla chat N senza cambiare quella attiva |
| `/r testo` | risponde all'ultima chat che ti ha scritto |
| `/to N`, `/to +39333...` | imposta la chat attiva (per numero o numero di telefono) |
| `/chat [n]` | ultime chat con il loro numero |
| `/scarica N`, `/annulla N`, `/pendenti` | media in attesa di conferma |
| `/segui N`, `/ignora N` | inoltra un gruppo WhatsApp (di default nessuno) |
| `/qualita`, `/qualita img medio`, `/qualita audio medio` | qualità di foto e vocali che *ricevi* |
| `/stato`, `/aiuto` | versione, stato di WhatsApp, chat attiva / elenco comandi |

Alias inglesi: `/download`, `/cancel`, `/pending`, `/follow`, `/unfollow`, `/quality`, `/status`, `/help`. I livelli si scrivono `basso|medio|alto|originale` oppure `low|medium|high|original`.

Gli allegati (foto, vocale, file) mandati dal tuo client vanno alla chat attiva.

## Media

**Quello che ricevi** (WhatsApp → LXMF). Default: `basso` per entrambi; la scelta fatta con `/qualita` resta salvata.

| Livello | Foto | Vocali |
|---|---|---|
| `basso` | 320 px, WebP q22 ("low" di Sideband) | Codec2 2400, ~0,3 KB/s |
| `medio` | 640 px, WebP q66 | Opus 12 kbps, ~1,5 KB/s |
| `alto` | 1280 px, WebP q75 | Opus 24 kbps, ~3 KB/s |
| `originale` | file invariato | Opus di WhatsApp invariato |

Se il risultato supera `max_file_mb`, Bifrost scende da solo di livello (`[ridotta a basso: troppo grande]`). Video e documenti arrivano invariati.

Ciò che, *dopo* la conversione, resta sopra `confirm_threshold_kb` viene trattenuto: arriva un avviso con dimensione e tempo stimato su LoRa, e lo ricevi con `/scarica N`. I media trattenuti scadono dopo 24 h. Sopra `max_file_mb` (0,9) non si può consegnare affatto: un router LXMF di serie rifiuta consegne oltre 1000 KB.

**Quello che invii** (LXMF → WhatsApp) lo comprime *il tuo* client (scegli il livello in Sideband all'invio); Bifrost lo inoltra senza degradarlo.

| Dal tuo client | Su WhatsApp |
|---|---|
| immagine | JPEG |
| audio (Codec2 o Opus) | nota vocale |
| file | **video** se è `.mp4`/`.mov`/... fino a `max_video_wa_mb` (16 MB), altrimenti documento |

**File grandi.** Il router LXMF di Bifrost accetta fino a `max_send_mb` (30 di default; LXMF di serie si ferma a 1 MB). Se un invio lo supera ricevi `⚠️ Invio rifiutato`. Su un link veloce (TCP, Tailscale) 12 MB sono questione di secondi; su LoRa sono ore e occupano il canale, quindi non farlo.

## Configurazione

`~/.bifrost/config.ini` (modello commentato: [`config.example.it.ini`](config.example.it.ini)). Dopo ogni modifica: `sudo systemctl restart bifrost`.

| Chiave | Default | Significato |
|---|---|---|
| `[bridge] owner` | – | il tuo/i tuoi indirizzi LXMF, separati da virgola |
| `language` | `en` | `en` o `it`: risposte del bot e log |
| `max_send_mb` | 30 | file più grande che puoi mandare a WhatsApp |
| `propagation_node` | – | fallback facoltativo per la consegna differita |
| `[limits] confirm_threshold_kb` | 32 | sopra, chiede conferma prima di mandare il media |
| `max_file_mb` | 0.9 | sopra, non consegna mai |
| `quality_img`, `quality_audio` | `low` | default di `/qualita` |
| `codec2_mode` | 2400 | modo Codec2 del livello `low` dei vocali |
| `link_kbps` | 1.2 | velocità reale del tuo link, solo per il tempo stimato |
| `max_video_wa_mb` | 16 | i video fino a questa dimensione vanno a WhatsApp come video |
| `pending_ttl_h` | 24 | ore prima che i media non scaricati vengano scartati |
| `groups` | `followed` | `none`, `followed` o `all` |

Le configurazioni di `alpha0.1`/`alpha0.2` (chiavi in italiano come `proprietario`, `[limiti]`) vengono ancora lette, e `setup.sh` le rinomina per te.

## Insieme a Sideband / MeshChatX

Parlano tutti con la stessa shared instance di `rnsd`, quindi possono essere collegati alla stessa radio contemporaneamente. Solo `rnsd` tocca la porta seriale. Se non trova la shared instance Bifrost scrive un avviso e avvia un'istanza Reticulum propria; se lo vedi, controlla che `rnsd` sia attivo.

## Avviare, fermare, riavviare

Il bridge gira con due service systemd: `bifrost` (lato LXMF) e `bifrost-sidecar` (lato WhatsApp). Partono all'avvio del sistema. Dalla cartella del progetto:

```bash
./setup.sh start        # (ri)avvia entrambi
./setup.sh stop         # ferma entrambi
./setup.sh restart      # riavvia entrambi (dopo aver modificato config.ini)
./setup.sh status       # stato dei service, indirizzo del bridge, stato dell'abbinamento
./setup.sh logs         # segue i log (Ctrl+C per uscire)
```

oppure direttamente con systemd:

```bash
sudo systemctl restart bifrost-sidecar bifrost
sudo systemctl stop bifrost bifrost-sidecar
sudo systemctl disable --now bifrost bifrost-sidecar   # ferma e non riavviare al boot
sudo systemctl enable --now bifrost-sidecar bifrost    # il contrario
```

## Log

```bash
sudo journalctl -u bifrost -f            # lato LXMF: consegne, tentativi, indirizzo del bridge
sudo journalctl -u bifrost-sidecar -f    # lato WhatsApp
```

L'indirizzo del bridge è anche in `~/.bifrost/address.txt`. I log non contengono mai il testo dei messaggi.

## Risoluzione dei problemi

| Sintomo | Causa probabile |
|---|---|
| `/stato` non riceve risposta | come owner c'è l'hash dell'identità invece dell'indirizzo di consegna; cerca `Ignoro messaggio da` nel log |
| I messaggi WhatsApp non arrivano | guarda `journalctl -u bifrost-sidecar`; cerca le righe `upsert`; `msg=NULL` vuol dire che WhatsApp non è stato decifrato |
| Il sidecar si ferma con codice 2 | il telefono ha scollegato il dispositivo: `./setup.sh` → abbina di nuovo WhatsApp |
| Il journal è pieno di righe `Pathing` | il `loglevel` in `~/.reticulum/config` è troppo alto (metti 4) |
| `Il tuo ffmpeg non ha libcodec2` durante il setup | installa il pacchetto `ffmpeg` standard; alcune build omettono Codec2 |
| `Consegna fallita (tentativo n/4)` | il nodo owner ora non è raggiungibile; riprova ogni 30 s, poi rinuncia (o usa il propagation node se configurato) |

## Limiti noti

- **La consegna verso di te viene ritentata fino a 4 volte, a 30 s l'una dall'altra.** Dopo, se non c'è un `propagation_node`, il messaggio è registrato come perso (`Consegna fallita definitivamente`). Il fallback via propagation node è implementato ma non provato sul campo.
- Ignorati: reazioni, risposte/citazioni, modifiche e cancellazioni, sondaggi, stati. Le posizioni arrivano come testo.
- Un messaggio WhatsApp che non si decifra viene scartato.
- Ricevere un video sopra ~1000 KB è impossibile via LXMF (limite del router del client): i video *ricevuti* in quella fascia arrivano solo come avviso.
- Più proprietari sono supportati ma provati poco.
- I messaggi dei gruppi non seguiti vengono scartati senza traccia (a parte la loro voce in `/chat`).

## Note di sicurezza

- La cifratura end-to-end di WhatsApp termina sulla macchina dove gira Bifrost. `~/.bifrost/wa-auth` contiene la sessione WhatsApp: trattala come una password.
- Solo gli indirizzi LXMF elencati in `owner` possono comandare il bridge; tutto il resto è ignorato.
- Reticulum/LXMF cifra il tratto radio, ma la macchina del bridge vede tutto in chiaro.

## Sviluppo

```bash
tests/run_tests.sh              # catalogo, config, core (EN e IT); servono rns + lxmf + Pillow + ffmpeg
tests/e2e.sh python3 it         # end to end con un rnsd privato, il bridge vero e un sidecar finto
tests/test_setup.sh             # setup.sh contro sudo/systemctl/npm finti
```

Struttura: `bridge/` (logica del core, lato LXMF, transcodifica, messaggi), `sidecar/` (Baileys), `systemd/` (modelli dei service), `tools/` (editor della config), `tests/`.

Aggiungere una lingua: aggiungi il codice a `LANGS` in `bridge/i18n.py`, compila ogni messaggio (`tests/test_i18n.py` fallisce se ne manca uno), aggiungi gli alias dei comandi in `bridge/core.py` e traduci `setup.sh` e la config di esempio.

## Crediti

Idea e prove sul campo di [Giak88](https://github.com/Giak88). Progettato e scritto con Claude (Anthropic).

Costruito su [Reticulum](https://reticulum.network) e [LXMF](https://github.com/markqvist/LXMF) di Mark Qvist, sulle convenzioni di messaggi e media di [Sideband](https://github.com/markqvist/Sideband) e su [Baileys](https://github.com/WhiskeySockets/Baileys). Non affiliato né approvato da WhatsApp/Meta.

## Licenza

MIT, vedi [LICENSE](LICENSE).
