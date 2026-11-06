"""Bridge logic, independent of RNS and of the sidecar (testable on its own).

The core receives:
  - WhatsApp events from the sidecar -> on_wa_event(ev)
  - LXMF messages from the owner     -> on_lxmf(text, fields)
and calls two callbacks:
  - lx_send(text, fields)            LXMF message to the owner
  - wa_send(cmd)                     "send" command to the sidecar
"""

import json
import os
import re
import threading
import time
from dataclasses import dataclass

from i18n import LEVELS, make_t, norm_level
from media import (CODEC2_MODES, MediaError, audio_for, codec2_seconds, image_for,
                   image_to_jpeg, lxmf_audio_to_ogg)

FIELD_FILE_ATTACHMENTS = 0x05
FIELD_IMAGE = 0x06
FIELD_AUDIO = 0x07


@dataclass
class Limits:
    confirm_threshold_kb: int = 32    # above: notice + /download
    max_file_mb: float = 0.9          # above: not deliverable over LXMF
    codec2_mode: str = "2400"         # Codec2 mode used by the 'low' audio level
    quality_img: str = "low"          # default for received media (changeable from chat)
    quality_audio: str = "low"
    max_video_wa_mb: float = 16.0     # above, videos go to WhatsApp as a document
    link_kbps: float = 1.2            # real throughput estimate, only for the ETA
    pending_ttl_h: float = 24
    groups: str = "followed"          # none | followed | all
    history_h: float = 48             # how long sent messages stay available for /repeat
    history_max: int = 100            # ...and how many


def human_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def human_eta(nbytes, kbps):
    s = nbytes * 8 / (kbps * 1000)
    if s < 90:
        return f"~{s:.0f} s"
    if s < 5400:
        return f"~{s / 60:.0f} min"
    return f"~{s / 3600:.1f} h"


KIND_ICON = {"image": "🖼", "sticker": "🖼", "audio": "🎤", "video": "🎬", "document": "📎"}

# command aliases -> canonical command
COMMANDS = {
    "/help": "help", "/aiuto": "help", "/?": "help",
    "/chat": "chat", "/chats": "chat",
    "/to": "to", "/a": "to",
    "/r": "r",
    "/follow": "follow", "/segui": "follow",
    "/unfollow": "unfollow", "/ignora": "unfollow",
    "/pending": "pending", "/pendenti": "pending",
    "/download": "download", "/scarica": "download",
    "/cancel": "cancel", "/annulla": "cancel",
    "/quality": "quality", "/qualita": "quality", "/qualità": "quality",
    "/status": "status", "/stato": "status",
    "/repeat": "repeat", "/ripeti": "repeat",
}
QUALITY_KINDS = {"img": "img", "image": "img", "images": "img", "photo": "img", "photos": "img",
                 "immagini": "img", "immagine": "img", "foto": "img",
                 "audio": "audio", "voice": "audio", "vocali": "audio", "vocale": "audio"}


class Core:
    def __init__(self, state_path, spool_dir, limits, lx_send, wa_send, log=print, version="", lang="en"):
        self.state_path = state_path
        self.spool = spool_dir
        self.lim = limits
        self._raw_send = lx_send       # used by /repeat, so repeats are not recorded again
        self.lx_send = self._send
        self.wa_send = wa_send
        self.log = log
        self.version = version
        self.t = make_t(lang)
        self.lock = threading.RLock()
        self.wa_status = "unknown"
        self.req_n = 0
        self.req_desc = {}
        self.st = {"chats": {}, "next_chat": 1, "active": None, "last_in": None,
                   "follow": [], "pending": {}, "next_pending": 1, "quality": {},
                   "history": [], "next_hist": 1}
        self._load()

    # ------------------------------------------------------------ stato
    def _load(self):
        try:
            with open(self.state_path) as f:
                self.st.update(json.load(f))
            q = self.st.get("quality") or {}
            self.st["quality"] = {k: norm_level(v) for k, v in q.items() if norm_level(v)}
        except FileNotFoundError:
            pass
        except Exception as e:
            self.log(self.t("state_unreadable", err=e))

    def _save(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.st, f, indent=1)
        os.replace(tmp, self.state_path)

    def _chat_id(self, jid, name=None, is_group=False):
        for cid, c in self.st["chats"].items():
            if c["jid"] == jid:
                if name:
                    c["name"] = name
                return int(cid)
        cid = self.st["next_chat"]
        self.st["next_chat"] += 1
        self.st["chats"][str(cid)] = {"jid": jid, "name": name or jid.split("@")[0],
                                      "is_group": is_group, "last": 0}
        return cid

    def _chat(self, cid):
        return self.st["chats"].get(str(cid))

    # ------------------------------------------------------------ WhatsApp -> LXMF
    def on_wa_event(self, ev):
        with self.lock:
            kind = ev.get("ev")
            if kind == "status":
                self.wa_status = ev.get("state")
                if ev.get("state") == "pairing":
                    self.lx_send(self.t("pairing_code", code=ev.get("code")), {})
                return
            if kind == "result":
                desc = self.req_desc.pop(ev.get("req"), None)
                if not ev.get("ok"):
                    self.lx_send(self.t("send_failed", desc=desc or "?", error=ev.get("error")), {})
                return
            if kind == "msg":
                self._wa_msg(ev)

    def _wa_msg(self, ev):
        cid = self._chat_id(ev["chat"], ev.get("chat_name"), ev.get("is_group", False))
        chat = self._chat(cid)
        chat["last"] = time.time()

        if chat["is_group"]:
            pol = self.lim.groups
            if pol == "none" or (pol == "followed" and cid not in self.st["follow"]):
                self._drop_spool(ev.get("path"))
                self._save()
                return
            head = f"#{cid} {chat['name']}/{ev.get('sender_name') or '?'}"
        else:
            head = f"#{cid} {chat['name']}"
        self.st["last_in"] = cid

        k = ev.get("kind", "text")
        text = ev.get("text") or ""
        if k in ("text", "location", "other"):
            self.lx_send(f"{head}: {text}", {})
        else:
            self._wa_media(cid, head, ev)
        self._save()

    def _quality(self, kind):
        q = (self.st.get("quality") or {}).get(kind)
        if q not in LEVELS:
            q = norm_level(self.lim.quality_img if kind == "img" else self.lim.quality_audio)
        return q if q in LEVELS else "low"

    def _encode_media(self, k, path, raw, ev):
        """-> (LXMF fields, label, note, bytes). Images and voice notes step down a level
        until they fit under max_file_mb."""
        cap = self.lim.max_file_mb * 1024 * 1024
        if k in ("image", "sticker", "audio"):
            kind = "audio" if k == "audio" else "img"
            want = self._quality(kind)
            for lvl in LEVELS[:LEVELS.index(want) + 1][::-1]:
                if kind == "audio":
                    mode, payload = audio_for(path, lvl, self.lim.codec2_mode)
                    secs = ev.get("seconds") or (codec2_seconds(mode, len(payload)) if mode in CODEC2_MODES else 0)
                    field, label = {FIELD_AUDIO: [mode, payload]}, self.t("label_voice", secs=f"{secs:.0f}", level=self.t("level_" + lvl))
                else:
                    typ, payload = image_for(raw, lvl)
                    field, label = {FIELD_IMAGE: [typ, payload]}, self.t("label_image", level=self.t("level_" + lvl))
                if len(payload) <= cap or lvl == "low":
                    note = self.t("reduced_note", level=self.t("level_" + lvl)) if lvl != want else ""
                    return field, label, note, len(payload)
        name = ev.get("filename") or f"{k}{_ext(ev.get('mime', ''))}"
        return {FIELD_FILE_ATTACHMENTS: [[name, raw]]}, f"{self.t('kind_' + k) if k in KIND_ICON else k} {name}", "", len(raw)

    def _wa_media(self, cid, head, ev):
        k, path = ev["kind"], ev.get("path")
        caption = ev.get("text") or ""
        icon = KIND_ICON.get(k, "📎")
        kname = self.t("kind_" + k) if k in KIND_ICON else self.t("kind_other")
        if not path:
            self.lx_send(self.t("media_unavailable", head=head, icon=icon, kind=kname,
                             size=human_size(ev.get("size", 0)),
                             error=ev.get("error") or self.t("default_error"), caption=caption).strip(), {})
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
            field, label, note, size = self._encode_media(k, path, raw, ev)
        except MediaError as e:
            self._drop_spool(path)
            self.lx_send(self.t("media_not_convertible", head=head, icon=icon, kind=kname, error=e,
                             caption=caption).strip(), {})
            return

        head = head + note
        if size > self.lim.max_file_mb * 1024 * 1024:
            self._drop_spool(path)
            self.lx_send(self.t("media_too_big", head=head, icon=icon, label=label, size=human_size(size),
                             limit=self.lim.max_file_mb, caption=caption).strip(), {})
            return
        if size <= self.lim.confirm_threshold_kb * 1024:
            self._drop_spool(path)
            self.lx_send(f"{head}: {caption}" if caption else head, field)
            return

        # sopra soglia: lo teniamo da parte e chiediamo conferma
        pid = self.st["next_pending"]
        self.st["next_pending"] += 1
        blob = os.path.join(self.spool, f"pending-{pid}")
        with open(blob, "wb") as f:
            f.write(json.dumps(_encode_field(field)).encode())
        self._drop_spool(path)
        self.st["pending"][str(pid)] = {"blob": blob, "head": head, "caption": caption,
                                        "label": label, "size": size, "ts": time.time()}
        self.lx_send(self.t("media_pending", head=head, icon=icon, label=label, size=human_size(size),
                         eta=human_eta(size, self.lim.link_kbps), pid=pid, caption=caption).strip(), {})

    def _drop_spool(self, path):
        if path and os.path.dirname(os.path.abspath(path)) == os.path.abspath(self.spool):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

    # ------------------------------------------------------------ history / repeat
    def _send(self, text, fields):
        """Every message to the owner goes through here and is remembered for /repeat."""
        self._remember(text, fields)
        self._raw_send(text, fields)

    def _remember(self, text, fields):
        if self.lim.history_max <= 0:
            return
        hid = self.st["next_hist"]
        self.st["next_hist"] += 1
        entry = {"id": hid, "ts": time.time(), "text": text, "blob": None}
        if fields:
            blob = os.path.join(self.spool, f"hist-{hid}")
            try:
                with open(blob, "w") as f:
                    json.dump(_encode_field(fields), f)
                entry["blob"] = blob
            except OSError:
                pass
        hist = self.st["history"]
        hist.append(entry)
        while len(hist) > self.lim.history_max:
            self._drop_hist(hist.pop(0))

    def _drop_hist(self, entry):
        if entry.get("blob"):
            self._drop_spool(entry["blob"])

    def _expire_history(self):
        cutoff = time.time() - self.lim.history_h * 3600
        hist = self.st["history"]
        for e in [e for e in hist if e["ts"] < cutoff]:
            self._drop_hist(e)
            hist.remove(e)

    def _cmd_repeat(self, arg):
        """/repeat N: send again the last N messages the bridge sent you (any chat), oldest first."""
        t = self.t
        arg = arg.strip()
        if not arg.isdigit() or int(arg) == 0:
            return self._raw_send(t("repeat_usage"), {})
        sel = self.st["history"][-int(arg):]
        if not sel:
            return self._raw_send(t("repeat_none"), {})
        self._raw_send(t("repeat_start", n=len(sel)), {})
        for e in sel:
            fields = {}
            if e.get("blob"):
                try:
                    with open(e["blob"]) as f:
                        fields = _decode_field(json.load(f))
                except (OSError, ValueError):
                    pass
            fmt = "%d/%m %H:%M" if time.time() - e["ts"] > 20 * 3600 else "%H:%M"
            self._raw_send(f"\u21bb {time.strftime(fmt, time.localtime(e['ts']))} {e['text']}", fields)

    def expire_pending(self):
        with self.lock:
            now = time.time()
            for pid, p in list(self.st["pending"].items()):
                if now - p["ts"] > self.lim.pending_ttl_h * 3600:
                    self._drop_spool(p["blob"])
                    del self.st["pending"][pid]
            self._expire_history()
            self._save()

    # ------------------------------------------------------------ LXMF -> WhatsApp
    def on_lxmf(self, text, fields):
        with self.lock:
            text = (text or "").strip()
            fields = fields or {}
            target = self.st["active"]

            m = re.match(r"^#(\d+)\s*(.*)$", text, re.S)
            if m:
                target, text = int(m.group(1)), m.group(2).strip()
            elif text.startswith("/"):
                if self._command(text):
                    self._save()
                    return
                # /r con testo o allegato cade qui sotto
                target, text = self.st["last_in"], text[2:].strip()

            if target is None or not self._chat(target):
                self.lx_send(self.t("no_active_chat"), {})
                return
            chat = self._chat(target)
            sent = False
            if FIELD_IMAGE in fields:
                self._send_image(chat, fields[FIELD_IMAGE], text)
                sent, text = True, ""
            if FIELD_AUDIO in fields:
                self._send_audio(chat, fields[FIELD_AUDIO])
                sent = True
            for att in fields.get(FIELD_FILE_ATTACHMENTS, []) or []:
                self._send_file(chat, att, text)
                sent, text = True, ""
            if text:
                self._wa(chat, {"kind": "text", "text": text}, self.t("what_text"))
                sent = True
            if not sent:
                self.lx_send(self.t("empty_message"), {})
            self._save()

    def _command(self, text):
        """True if the command was handled; False for /r (text to forward)."""
        parts = text.split(maxsplit=1)
        raw, arg = parts[0].lower(), (parts[1].strip() if len(parts) > 1 else "")
        cmd = COMMANDS.get(raw)
        num = int(arg) if arg.isdigit() else None
        t = self.t
        say = lambda s: self.lx_send(s, {})

        if cmd == "help":
            say(t("help"))
        elif cmd == "chat":
            chats = sorted(self.st["chats"].items(), key=lambda kv: -kv[1]["last"])[:num or 10]
            if not chats:
                say(t("chats_none"))
            else:
                lines = []
                for cid, c in chats:
                    tag = ""
                    if c["is_group"]:
                        followed = int(cid) in self.st["follow"] or self.lim.groups == "all"
                        tag = t("tag_group_followed") if followed else t("tag_group")
                    star = t("tag_active") if int(cid) == self.st["active"] else ""
                    lines.append(f"#{cid} {c['name']}{tag}{star}")
                say("\n".join(lines))
        elif cmd == "to":
            if num is not None and self._chat(num):
                self.st["active"] = num
                say(t("to_ok", n=num, name=self._chat(num)["name"]))
            elif re.fullmatch(r"\+?\d{8,15}", arg.replace(" ", "")):
                jid = arg.replace(" ", "").lstrip("+") + "@s.whatsapp.net"
                cid = self._chat_id(jid)
                self.st["active"] = cid
                say(t("to_ok", n=cid, name=arg))
            else:
                say(t("to_usage"))
        elif cmd == "r":
            if self.st["last_in"] is None:
                say(t("reply_none"))
                return True
            return False
        elif cmd in ("follow", "unfollow"):
            c = self._chat(num) if num is not None else None
            if not c or not c["is_group"]:
                say(t("follow_usage", cmd=raw))
            elif cmd == "follow":
                if num not in self.st["follow"]:
                    self.st["follow"].append(num)
                say(t("follow_ok", n=num, name=c["name"]))
            else:
                if num in self.st["follow"]:
                    self.st["follow"].remove(num)
                say(t("unfollow_ok", n=num, name=c["name"]))
        elif cmd == "pending":
            p = self.st["pending"]
            say("\n".join(f"{pid}: {x['head']} {x['label']} {human_size(x['size'])}" for pid, x in p.items())
                or t("pending_none"))
        elif cmd == "download":
            p = self.st["pending"].pop(str(num), None) if num is not None else None
            if not p:
                say(t("download_none"))
            else:
                with open(p["blob"], "rb") as f:
                    field = _decode_field(json.loads(f.read()))
                self._drop_spool(p["blob"])
                self.lx_send(f"{p['head']}: {p['caption']}" if p["caption"] else p["head"], field)
        elif cmd == "cancel":
            p = self.st["pending"].pop(str(num), None) if num is not None else None
            if p:
                self._drop_spool(p["blob"])
                say(t("cancel_ok", n=num))
            else:
                say(t("cancel_none"))
        elif cmd == "quality":
            self._cmd_quality(arg)
        elif cmd == "repeat":
            self._cmd_repeat(arg)
        elif cmd == "status":
            a = self._chat(self.st["active"]) if self.st["active"] else None
            chat = f"#{self.st['active']} {a['name']}" if a else t("none_word")
            say(t("status", version=self.version, wa=self.wa_status, chat=chat,
                  pending=len(self.st["pending"]), followed=len(self.st["follow"]),
                  policy=t("policy_" + self.lim.groups) if self.lim.groups in ("none", "followed", "all")
                  else self.lim.groups))
        else:
            say(t("unknown_command", cmd=raw))
        return True

    def _cmd_quality(self, arg):
        t = self.t
        say = lambda s: self.lx_send(s, {})
        words = arg.lower().split()
        if len(words) == 2 and words[0] in QUALITY_KINDS and norm_level(words[1]):
            kind, lvl = QUALITY_KINDS[words[0]], norm_level(words[1])
            self.st.setdefault("quality", {})[kind] = lvl
            say(t("quality_set", what=t("quality_what_img" if kind == "img" else "quality_what_audio"),
                  level=t("level_" + lvl), desc=t(("img_desc_" if kind == "img" else "aud_desc_") + lvl)))
        elif words:
            say(t("quality_usage"))
        else:
            qi, qa = self._quality("img"), self._quality("audio")
            say(t("quality_summary", qi=t("level_" + qi), di=t("img_desc_" + qi),
                  qa=t("level_" + qa), da=t("aud_desc_" + qa)))

    def _wa(self, chat, cmd, desc):
        self.req_n += 1
        req = self.req_n
        self.req_desc[req] = self.t("sent_to", what=desc, chat=chat["name"])
        self.wa_send(dict(cmd, cmd="send", req=req, to=chat["jid"]))

    def _tmp(self, suffix, data):
        self.req_n += 1
        p = os.path.join(self.spool, f"out-{int(time.time())}-{self.req_n}{suffix}")
        with open(p, "wb") as f:
            f.write(data)
        return p

    def _send_image(self, chat, field, caption):
        try:
            jpg = image_to_jpeg(field[1])
        except MediaError as e:
            return self.lx_send(f"⚠️ {e}", {})
        self._wa(chat, {"kind": "image", "path": self._tmp(".jpg", jpg), "mime": "image/jpeg", "text": caption},
                 self.t("what_image"))

    def _send_audio(self, chat, field):
        try:
            ogg = lxmf_audio_to_ogg(field[0], field[1])
        except MediaError as e:
            return self.lx_send(f"⚠️ audio: {e}", {})
        self._wa(chat, {"kind": "audio", "path": self._tmp(".ogg", ogg)}, self.t("what_voice"))

    def _send_file(self, chat, att, caption):
        name = str(att[0]) if att and att[0] else "file"
        mime = _mime(name)
        kind = "document"
        if mime.startswith("video/") and len(att[1]) <= self.lim.max_video_wa_mb * 1024 * 1024:
            kind = "video"   # shows up as a video in WhatsApp, not as a file to download
        self._wa(chat, {"kind": kind, "path": self._tmp("", att[1]), "filename": name,
                        "mime": mime, "text": caption}, self.t("what_" + kind, name=name))

    def cleanup_outbox(self, max_age=3600):
        now = time.time()
        for n in os.listdir(self.spool):
            p = os.path.join(self.spool, n)
            if (n.startswith("out-") or n.startswith("wa-")) and now - os.path.getmtime(p) > max_age:
                os.unlink(p)


# ------------------------------------------------------------------ helper

def _encode_field(field):
    """Campi LXMF -> JSON (i bytes in hex)."""
    def enc(x):
        if isinstance(x, (bytes, bytearray)):
            return {"__b": bytes(x).hex()}
        if isinstance(x, list):
            return [enc(i) for i in x]
        return x
    return {str(k): enc(v) for k, v in field.items()}


def _decode_field(d):
    def dec(x):
        if isinstance(x, dict) and "__b" in x:
            return bytes.fromhex(x["__b"])
        if isinstance(x, list):
            return [dec(i) for i in x]
        return x
    return {int(k): dec(v) for k, v in d.items()}


_EXT = {"application/pdf": ".pdf", "video/mp4": ".mp4", "image/jpeg": ".jpg", "image/png": ".png",
        "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "application/zip": ".zip", "text/plain": ".txt"}


def _ext(mime):
    return _EXT.get((mime or "").split(";")[0].strip(), "")


def _mime(name):
    import mimetypes
    return mimetypes.guess_type(name)[0] or "application/octet-stream"
