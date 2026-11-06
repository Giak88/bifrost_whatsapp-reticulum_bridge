"""Messaggi di Bifrost in inglese e italiano / Bifrost messages in English and Italian.

t = make_t("it"); t("help"); t("to_ok", n=3, name="Mario")
Una chiave senza traduzione ripiega sull'inglese / a missing translation falls back to English.
"""

LANGS = ("en", "it")

MSG = {
    # ---------------------------------------------------------------- comandi
    "help": {
        "en": """Bifrost commands:
/chat - latest chats with their number
/to N - set the active chat (also /to +15551234567)
#N text - write to chat N without switching to it
/r text - reply to the last chat that wrote to you
/download N - fetch a pending media file
/cancel N - discard a pending media file
/pending - media waiting for confirmation
/follow N, /unfollow N - forward a group (or stop)
/quality - quality of the photos and voice notes you receive
/repeat N - send again the last N messages the bridge sent you (e.g. after being out of coverage)
/status - bridge status
Plain text goes to the active chat, and so do attachments.""",
        "it": """Comandi Bifrost:
/chat - ultime chat con il loro numero
/to N - imposta la chat attiva (anche /to +39333...)
#N testo - scrivi alla chat N senza cambiarla
/r testo - rispondi all'ultima chat che ti ha scritto
/scarica N - scarica un media in attesa
/annulla N - scarta un media in attesa
/pendenti - media in attesa
/segui N, /ignora N - inoltro di un gruppo
/qualita - qualità di foto e vocali che ricevi
/ripeti N - rimanda gli ultimi N messaggi che il bridge ti ha inviato (ad es. dopo essere stato fuori copertura)
/stato - stato del bridge
Il testo semplice va alla chat attiva. Allegati: alla chat attiva.""",
    },
    "no_active_chat": {
        "en": "No active chat. Use /chat and then /to N, or #N text.",
        "it": "Nessuna chat attiva. Usa /chat e poi /to N, oppure #N testo.",
    },
    "empty_message": {
        "en": "Empty message, nothing to forward.",
        "it": "Messaggio vuoto, niente da inoltrare.",
    },
    "chats_none": {"en": "No chats yet.", "it": "Nessuna chat ancora."},
    "tag_group_followed": {"en": " [group, followed]", "it": " [gruppo, seguito]"},
    "tag_group": {"en": " [group]", "it": " [gruppo]"},
    "tag_active": {"en": " ◀ active", "it": " ◀ attiva"},
    "to_ok": {"en": "Active chat: #{n} {name}", "it": "Chat attiva: #{n} {name}"},
    "to_usage": {"en": "Usage: /to N or /to +15551234567", "it": "Uso: /to N oppure /to +39333..."},
    "reply_none": {"en": "Nobody has written to you yet.", "it": "Nessuno ti ha ancora scritto."},
    "follow_usage": {
        "en": "Usage: {cmd} N (N is a group, see /chat)",
        "it": "Uso: {cmd} N (N di un gruppo, vedi /chat)",
    },
    "follow_ok": {"en": "Following group #{n} {name}", "it": "Seguo il gruppo #{n} {name}"},
    "unfollow_ok": {"en": "No longer forwarding #{n} {name}", "it": "Non inoltro più #{n} {name}"},
    "pending_none": {"en": "No pending media.", "it": "Nessun media in attesa."},
    "download_none": {
        "en": "No pending media with that number (see /pending).",
        "it": "Nessun media in attesa con quel numero (vedi /pendenti).",
    },
    "cancel_ok": {"en": "Discarded {n}.", "it": "Scartato {n}."},
    "cancel_none": {"en": "No pending media with that number.", "it": "Nessun media in attesa con quel numero."},
    "status": {
        "en": "{version}\nWhatsApp: {wa}\nActive chat: {chat}\nPending media: {pending}\n"
              "Followed groups: {followed} (policy: {policy})",
        "it": "{version}\nWhatsApp: {wa}\nChat attiva: {chat}\nMedia in attesa: {pending}\n"
              "Gruppi seguiti: {followed} (politica: {policy})",
    },
    "repeat_start": {"en": "Repeating the last {n} message(s):", "it": "Ripeto gli ultimi {n} messaggi:"},
    "repeat_none": {
        "en": "Nothing to repeat (the history keeps the bridge's messages for a limited time).",
        "it": "Niente da ripetere (lo storico conserva i messaggi del bridge per un tempo limitato).",
    },
    "repeat_usage": {
        "en": "Usage: /repeat N (e.g. /repeat 10 sends again the last 10 messages)",
        "it": "Uso: /ripeti N (ad es. /ripeti 10 rimanda gli ultimi 10 messaggi)",
    },
    "none_word": {"en": "none", "it": "nessuna"},
    "policy_none": {"en": "none", "it": "nessuno"},
    "policy_followed": {"en": "followed", "it": "seguiti"},
    "policy_all": {"en": "all", "it": "tutti"},
    "unknown_command": {
        "en": "Unknown command: {cmd}. /help for the list.",
        "it": "Comando sconosciuto: {cmd}. /aiuto per l'elenco.",
    },

    # ---------------------------------------------------------------- qualità
    "quality_set": {
        "en": "{what} you receive: {level} ({desc})",
        "it": "{what} che ricevi: {level} ({desc})",
    },
    "quality_what_img": {"en": "Images", "it": "Immagini"},
    "quality_what_audio": {"en": "Audio", "it": "Audio"},
    "quality_usage": {
        "en": "Usage: /quality img|audio low|medium|high|original",
        "it": "Uso: /qualita img|audio basso|medio|alto|originale",
    },
    "quality_summary": {
        "en": "Quality of the media you receive from WhatsApp:\nimages: {qi} ({di})\naudio: {qa} ({da})\n"
              "Levels: low, medium, high, original. Change with /quality img medium, /quality audio medium.\n"
              "If the result exceeds the limit it steps down on its own.\n"
              "What you send is compressed by your own client (Sideband): Bifrost forwards it without degrading it.",
        "it": "Qualità dei media che ricevi da WhatsApp:\nimmagini: {qi} ({di})\naudio: {qa} ({da})\n"
              "Livelli: basso, medio, alto, originale. Cambia con /qualita img medio, /qualita audio medio.\n"
              "Se il risultato supera il limite scende da solo di livello.\n"
              "Quello che invii tu lo comprime il tuo client (Sideband): Bifrost lo inoltra senza degradarlo.",
    },
    "level_low": {"en": "low", "it": "basso"},
    "level_medium": {"en": "medium", "it": "medio"},
    "level_high": {"en": "high", "it": "alto"},
    "level_original": {"en": "original", "it": "originale"},
    "img_desc_low": {"en": "320 px, WebP q22", "it": "320 px, WebP q22"},
    "img_desc_medium": {"en": "640 px, WebP q66", "it": "640 px, WebP q66"},
    "img_desc_high": {"en": "1280 px, WebP q75", "it": "1280 px, WebP q75"},
    "img_desc_original": {"en": "file unchanged", "it": "file invariato"},
    "aud_desc_low": {"en": "Codec2 2400, ~0.3 KB/s", "it": "Codec2 2400, ~0,3 KB/s"},
    "aud_desc_medium": {"en": "Opus 12 kbps, ~1.5 KB/s", "it": "Opus 12 kbps, ~1,5 KB/s"},
    "aud_desc_high": {"en": "Opus 24 kbps, ~3 KB/s", "it": "Opus 24 kbps, ~3 KB/s"},
    "aud_desc_original": {"en": "WhatsApp's Opus, unchanged", "it": "Opus di WhatsApp invariato"},

    # ---------------------------------------------------------------- media in arrivo da WhatsApp
    "pairing_code": {"en": "⚙️ WhatsApp pairing code: {code}", "it": "⚙️ Codice di abbinamento WhatsApp: {code}"},
    "send_failed": {
        "en": "⚠️ Sending to WhatsApp failed ({desc}): {error}",
        "it": "⚠️ Invio a WhatsApp fallito ({desc}): {error}",
    },
    "sent_to": {"en": "{what} to {chat}", "it": "{what} a {chat}"},
    "what_text": {"en": "text", "it": "testo"},
    "what_image": {"en": "image", "it": "immagine"},
    "what_voice": {"en": "voice note", "it": "vocale"},
    "what_video": {"en": "video {name}", "it": "video {name}"},
    "what_document": {"en": "file {name}", "it": "file {name}"},
    "kind_image": {"en": "image", "it": "immagine"},
    "kind_sticker": {"en": "sticker", "it": "sticker"},
    "kind_audio": {"en": "voice note", "it": "vocale"},
    "kind_video": {"en": "video", "it": "video"},
    "kind_document": {"en": "document", "it": "documento"},
    "kind_other": {"en": "file", "it": "file"},
    "label_image": {"en": "image {level}", "it": "immagine {level}"},
    "label_voice": {"en": "voice note {secs} s {level}", "it": "vocale {secs} s {level}"},
    "default_error": {"en": "error", "it": "errore"},
    "media_unavailable": {
        "en": "{head}: {icon} {kind} {size} not available ({error}). {caption}",
        "it": "{head}: {icon} {kind} {size} non disponibile ({error}). {caption}",
    },
    "media_not_convertible": {
        "en": "{head}: {icon} {kind} could not be converted ({error}). {caption}",
        "it": "{head}: {icon} {kind} non convertibile ({error}). {caption}",
    },
    "media_too_big": {
        "en": "{head}: {icon} {label}, {size}: too large for Reticulum (limit {limit} MB). {caption}",
        "it": "{head}: {icon} {label}, {size}: troppo grande per Reticulum (limite {limit} MB). {caption}",
    },
    "media_pending": {
        "en": "{head}: {icon} {label}, {size} ({eta} over LoRa). "
              "/download {pid} to receive it, /cancel {pid} to discard it. {caption}",
        "it": "{head}: {icon} {label}, {size} ({eta} su LoRa). "
              "/scarica {pid} per riceverlo, /annulla {pid} per scartarlo. {caption}",
    },
    "reduced_note": {
        "en": " [reduced to {level}: too large]",
        "it": " [ridotta a {level}: troppo grande]",
    },

    # ---------------------------------------------------------------- bridge (RNS/LXMF)
    "cfg_not_found": {"en": "Config not found: {path}", "it": "Config non trovata: {path}"},
    "owner_missing": {
        "en": "Set 'owner' in the config to your LXMF address",
        "it": "Imposta 'owner' (o 'proprietario') nella config con il tuo indirizzo LXMF",
    },
    "owner_invalid": {
        "en": "Invalid owner address '{value}': it must be 32 hexadecimal characters (edit config.ini)",
        "it": "Indirizzo 'owner' non valido '{value}': servono 32 caratteri esadecimali (modifica config.ini)",
    },
    "starting": {"en": "Bifrost {version} starting", "it": "Bifrost {version} in avvio"},
    "not_shared": {
        "en": "WARNING: not attached to rnsd, running as a standalone Reticulum instance",
        "it": "ATTENZIONE: non sono agganciato a rnsd, sto girando come istanza autonoma",
    },
    "address_log": {"en": "Bridge LXMF address: {addr}", "it": "Indirizzo LXMF del bridge: {addr}"},
    "reject_log": {
        "en": "Rejected a {size} send (limit {limit} MB)",
        "it": "Rifiutato un invio da {size} (limite {limit} MB)",
    },
    "reject_notice": {
        "en": "⚠️ Send rejected: {size} exceeds the {limit} MB limit (max_send_mb in config.ini).",
        "it": "⚠️ Invio rifiutato: {size} supera il limite di {limit} MB (max_send_mb in config.ini).",
    },
    "ignore_log": {
        "en": "Ignoring message from {src}: not an owner",
        "it": "Ignoro messaggio da {src}: non è un proprietario",
    },
    "internal_error": {"en": "⚠️ Internal error: {err}", "it": "⚠️ Errore interno: {err}"},
    "queued_log": {
        "en": "Queued for the owner: {chars} characters, fields {fields}",
        "it": "In coda per il proprietario: {chars} caratteri, campi {fields}",
    },
    "dropped_log": {
        "en": "Message dropped: recipient unknown for an hour",
        "it": "Messaggio scartato: destinatario sconosciuto da un'ora",
    },
    "delivered_log": {
        "en": "Delivered to the owner (attempt {n})",
        "it": "Consegnato al proprietario (tentativo {n})",
    },
    "sending_log": {"en": "Sending to the owner (attempt {n})", "it": "Invio al proprietario (tentativo {n})"},
    "retry_log": {
        "en": "Delivery failed (attempt {n}/{max}), retrying in 30 s",
        "it": "Consegna fallita (tentativo {n}/{max}), riprovo tra 30 s",
    },
    "propagation_log": {
        "en": "Direct delivery failed, trying the propagation node",
        "it": "Consegna diretta fallita, provo via propagation node",
    },
    "lost_log": {
        "en": "Delivery failed for good: message lost",
        "it": "Consegna fallita definitivamente: messaggio perso",
    },
    "sidecar_connected": {"en": "Connected to the WhatsApp sidecar", "it": "Collegato al sidecar WhatsApp"},
    "sidecar_link_error": {"en": "Sidecar link: {err}", "it": "Link sidecar: {err}"},
    "sidecar_not_connected": {"en": "sidecar not connected", "it": "sidecar non connesso"},
    "sidecar_unreachable": {
        "en": "⚠️ WhatsApp sidecar unreachable: {err}",
        "it": "⚠️ Sidecar WhatsApp non raggiungibile: {err}",
    },
    "state_unreadable": {
        "en": "state file unreadable, starting from scratch: {err}",
        "it": "stato illeggibile, riparto da zero: {err}",
    },
}


# Level words accepted from the user (either language) -> canonical English name.
LEVEL_ALIASES = {
    "low": "low", "basso": "low", "bassa": "low",
    "medium": "medium", "mid": "medium", "medio": "medium", "media": "medium",
    "high": "high", "alto": "high", "alta": "high",
    "original": "original", "orig": "original", "originale": "original",
}
LEVELS = ("low", "medium", "high", "original")


def norm_level(word, default=None):
    return LEVEL_ALIASES.get(str(word).strip().lower(), default)


def make_t(lang):
    lang = lang if lang in LANGS else "en"

    def t(key, **kw):
        entry = MSG[key]
        s = entry.get(lang) or entry["en"]
        return s.format(**kw) if kw else s

    t.lang = lang
    return t
