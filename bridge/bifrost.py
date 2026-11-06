#!/usr/bin/env python3
"""WhatsApp <-> Reticulum/LXMF bridge.

Attaches to rnsd as a client of the shared instance (never opens serial ports)
and to the WhatsApp sidecar through a Unix socket.
Usage: bifrost.py [config.ini]
"""

import configparser
import json
import os
import re
import socket
import sys
import threading
import time

import LXMF
import RNS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Core, Limits  # noqa: E402
from i18n import LANGS, make_t, norm_level  # noqa: E402

APP = "bifrost"
VERSION = "alpha0.3"


# Old (Italian) config names, still read for backward compatibility.
_OLD_SECTION = {"limits": "limiti"}
_OLD_KEY = {
    "owner": "proprietario", "name": "nome", "announce_min": "annuncio_min", "max_send_mb": "max_invio_mb",
    "confirm_threshold_kb": "soglia_conferma_kb", "codec2_mode": "audio_mode",
    "quality_img": "qualita_img", "quality_audio": "qualita_audio", "groups": "gruppi",
}
_OLD_GROUPS = {"nessuno": "none", "seguiti": "followed", "tutti": "all"}


def _get(cp, section, key, default=None):
    """Value from [section] key, falling back to the old Italian section/key name."""
    for sec in (section, _OLD_SECTION.get(section)):
        for k in (key, _OLD_KEY.get(key)):
            if sec and k and cp.has_option(sec, k):
                return cp.get(sec, k)
    return default


def load_config(path):
    cp = configparser.ConfigParser()
    if path and not cp.read(path):
        sys.exit("Config not found / Config non trovata: " + path)
    # [bridge] and [limits] may still be called by their old names; the lookup handles it
    base = os.path.expanduser(_get(cp, "bridge", "dir", "~/.bifrost"))
    lang = (_get(cp, "bridge", "language") or _get(cp, "bridge", "lingua") or "en").strip().lower()[:2]
    if lang not in LANGS:
        lang = "en"
    owners = [h.strip().replace("<", "").replace(">", "")
              for h in _get(cp, "bridge", "owner", "").split(",") if h.strip()]
    lim = Limits()
    for k, typ in (("confirm_threshold_kb", int), ("max_file_mb", float), ("codec2_mode", str),
                   ("link_kbps", float), ("pending_ttl_h", float), ("groups", str),
                   ("quality_img", str), ("quality_audio", str), ("max_video_wa_mb", float)):
        v = _get(cp, "limits", k)
        if v is not None and v.strip() != "":
            setattr(lim, k, typ(v.strip()))
    lim.groups = _OLD_GROUPS.get(lim.groups.lower(), lim.groups.lower())
    for k in ("quality_img", "quality_audio"):
        setattr(lim, k, norm_level(getattr(lim, k), "low"))
    return {
        "dir": base,
        "lang": lang,
        "socket": os.path.expanduser(_get(cp, "bridge", "socket") or os.path.join(base, "ipc.sock")),
        "rns_config": os.path.expanduser(_get(cp, "bridge", "rns_config")) if _get(cp, "bridge", "rns_config") else None,
        "owners": owners,
        "name": _get(cp, "bridge", "name") or "Bifrost",
        "announce_min": float(_get(cp, "bridge", "announce_min", "15")),
        "max_send_mb": float(_get(cp, "bridge", "max_send_mb", "30")),
        "propagation": _get(cp, "bridge", "propagation_node", "").strip().replace("<", "").replace(">", ""),
        "limits": lim,
    }


class LxmfSide:
    def __init__(self, cfg):
        self.cfg = cfg
        self.t = make_t(cfg["lang"])
        self.reticulum = RNS.Reticulum(cfg["rns_config"])
        if not self.reticulum.is_connected_to_shared_instance:
            RNS.log(self.t("not_shared"), RNS.LOG_WARNING)

        id_path = os.path.join(cfg["dir"], "identity")
        if os.path.isfile(id_path):
            self.identity = RNS.Identity.from_file(id_path)
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(id_path)

        # delivery_limit is in KB: by default an LXMF router refuses deliveries over 1000 KB
        self.router = LXMF.LXMRouter(identity=self.identity, storagepath=os.path.join(cfg["dir"], "lxmf"),
                                     delivery_limit=int(cfg["max_send_mb"] * 1000))
        self.dest = self.router.register_delivery_identity(self.identity, display_name=cfg["name"])
        self.router.register_delivery_callback(self._on_delivery)
        if cfg["propagation"]:
            self.router.set_outbound_propagation_node(bytes.fromhex(cfg["propagation"]))
        self.owners = [bytes.fromhex(h) for h in cfg["owners"]]
        self.core = None
        self.outq = []
        self.qlock = threading.Lock()
        self._last_reject = 0
        self._orig_advertised = self.router.delivery_resource_advertised
        self.router.delivery_resource_advertised = self._advertised
        RNS.log(self.t("address_log", addr=RNS.prettyhexrep(self.dest.hash)), RNS.LOG_NOTICE)
        try:   # so that setup.sh (and you) can read the address without parsing logs
            with open(os.path.join(cfg["dir"], "address.txt"), "w") as f:
                f.write(self.dest.hash.hex() + "\n")
        except OSError:
            pass

    def _advertised(self, resource):
        """Same check as the router, but tells the owner when it rejects one of their sends."""
        ok = self._orig_advertised(resource)
        if not ok:
            try:
                size = resource.get_data_size() or 0
                ident = resource.link.get_remote_identity()
                sender = RNS.Destination.hash(ident, "lxmf", "delivery") if ident else None
            except Exception:
                size, sender = 0, None
            limit = f"{self.cfg['max_send_mb']:g}"
            RNS.log(self.t("reject_log", size=RNS.prettysize(size), limit=limit), RNS.LOG_NOTICE)
            if sender in self.owners and time.time() - self._last_reject > 30:
                self._last_reject = time.time()
                self.send_text(self.t("reject_notice", size=RNS.prettysize(size), limit=limit))
        return ok

    def announce(self):
        self.router.announce(self.dest.hash)

    def _on_delivery(self, lxm):
        if lxm.source_hash not in self.owners:
            RNS.log(self.t("ignore_log", src=RNS.prettyhexrep(lxm.source_hash)), RNS.LOG_NOTICE)
            return
        try:
            self.core.on_lxmf(lxm.content_as_string(), lxm.fields)
        except Exception as e:
            RNS.trace_exception(e)
            self.send_text(self.t("internal_error", err=e))

    # ---- outgoing to the owner, waiting for the path
    def send(self, text, fields):
        with self.qlock:
            for o in self.owners:
                self.outq.append({"to": o, "text": text, "fields": fields or {}, "t0": time.time(), "asked": 0, "tries": 0})
        RNS.log(self.t("queued_log", chars=len(text or ""), fields=sorted((fields or {}).keys())), RNS.LOG_NOTICE)

    def send_text(self, text):
        self.send(text, {})

    def pump(self):
        with self.qlock:
            pending, self.outq = self.outq, []
        keep = []
        for m in pending:
            ident = RNS.Identity.recall(m["to"])
            if ident is None:
                if time.time() - m["asked"] > 15:
                    RNS.Transport.request_path(m["to"])
                    m["asked"] = time.time()
                if time.time() - m["t0"] < 3600:
                    keep.append(m)
                else:
                    RNS.log(self.t("dropped_log"), RNS.LOG_WARNING)
                continue
            dest = RNS.Destination(ident, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
            lxm = LXMF.LXMessage(dest, self.dest, m["text"], fields=m["fields"] or None,
                                 desired_method=LXMF.LXMessage.DIRECT)
            lxm.register_delivery_callback(lambda l, m=m: RNS.log(
                self.t("delivered_log", n=m["tries"] + 1), RNS.LOG_NOTICE))
            lxm.register_failed_callback(lambda l, m=m: self._on_failed(l, m))
            RNS.log(self.t("sending_log", n=m["tries"] + 1), RNS.LOG_NOTICE)
            self.router.handle_outbound(lxm)
        with self.qlock:
            self.outq = keep + self.outq

    MAX_TRIES = 4

    def _on_failed(self, lxm, m):
        m["tries"] += 1
        if m["tries"] < self.MAX_TRIES:
            RNS.log(self.t("retry_log", n=m["tries"], max=self.MAX_TRIES), RNS.LOG_WARNING)
            m["asked"] = 0
            m["t0"] = time.time()
            threading.Timer(30, lambda: self._requeue(m)).start()
        elif self.cfg["propagation"]:
            RNS.log(self.t("propagation_log"), RNS.LOG_WARNING)
            retry = LXMF.LXMessage(lxm.get_destination(), self.dest, lxm.content, title=lxm.title,
                                   fields=lxm.fields, desired_method=LXMF.LXMessage.PROPAGATED)
            self.router.handle_outbound(retry)
        else:
            RNS.log(self.t("lost_log"), RNS.LOG_ERROR)

    def _requeue(self, m):
        with self.qlock:
            self.outq.append(m)


class SidecarLink:
    def __init__(self, path, t):
        self.t = t
        self.path = path
        self.sock = None
        self.wlock = threading.Lock()
        self.on_event = None

    def send(self, obj):
        line = (json.dumps(obj) + "\n").encode()
        with self.wlock:
            if not self.sock:
                raise ConnectionError(self.t("sidecar_not_connected"))
            self.sock.sendall(line)

    def run(self):
        while True:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(self.path)
                self.sock = s
                RNS.log(self.t("sidecar_connected"), RNS.LOG_NOTICE)
                buf = b""
                while True:
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if line.strip():
                            try:
                                self.on_event(json.loads(line))
                            except Exception as e:
                                RNS.trace_exception(e)
            except (FileNotFoundError, ConnectionRefusedError):
                pass
            except OSError as e:
                RNS.log(self.t("sidecar_link_error", err=e), RNS.LOG_WARNING)
            self.sock = None
            time.sleep(3)


def main():
    cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    t = make_t(cfg["lang"])
    spool = os.path.join(cfg["dir"], "spool")
    os.makedirs(spool, mode=0o700, exist_ok=True)
    if not cfg["owners"]:
        sys.exit(t("owner_missing"))
    for h in cfg["owners"]:
        if not re.fullmatch(r"[0-9a-fA-F]{32}", h):
            sys.exit(t("owner_invalid", value=h))

    RNS.log(t("starting", version=VERSION), RNS.LOG_NOTICE)
    lx = LxmfSide(cfg)
    side = SidecarLink(cfg["socket"], t)

    def wa_send(cmd):
        try:
            side.send(cmd)
        except Exception as e:
            lx.send_text(t("sidecar_unreachable", err=e))

    core = Core(os.path.join(cfg["dir"], "state.json"), spool, cfg["limits"],
                lx_send=lx.send, wa_send=wa_send, log=lambda s: RNS.log(s, RNS.LOG_NOTICE), version="Bifrost " + VERSION,
                lang=cfg["lang"])
    lx.core = core
    side.on_event = core.on_wa_event
    threading.Thread(target=side.run, daemon=True).start()

    lx.announce()
    last_ann = last_clean = time.time()
    while True:
        lx.pump()
        now = time.time()
        if now - last_ann > cfg["announce_min"] * 60:
            lx.announce()
            last_ann = now
        if now - last_clean > 600:
            core.expire_pending()
            core.cleanup_outbox()
            last_clean = now
        time.sleep(1)


if __name__ == "__main__":
    main()
