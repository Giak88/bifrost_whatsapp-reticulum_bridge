"""Sidecar WhatsApp finto: socket Unix con lo stesso protocollo NDJSON di index.mjs.
Uso: e2e_fake_sidecar.py <socket> <spool> <media_dir>
"""
import json
import os
import shutil
import socket
import sys
import time

sock_path, spool, media = sys.argv[1:4]
try:
    os.unlink(sock_path)
except FileNotFoundError:
    pass
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
srv.bind(sock_path)
srv.listen(1)
c, _ = srv.accept()
print("SIDECAR: bridge connected", flush=True)


def emit(o):
    c.sendall((json.dumps(o) + "\n").encode())


def spooled(name):
    p = os.path.join(spool, "wa-" + name)
    shutil.copy(os.path.join(media, name), p)
    return p


emit({"ev": "status", "state": "open"})
time.sleep(6)  # tempo al proprietario per annunciarsi
base = {"ev": "msg", "chat": "393331112222@s.whatsapp.net", "is_group": False, "chat_name": "Mario", "sender_name": "Mario"}
emit(dict(base, kind="text", text="hello from WhatsApp"))
emit(dict(base, kind="image", text="photo", path=spooled("foto.jpg")))
emit(dict(base, kind="audio", ptt=True, path=spooled("vo10.ogg")))
emit(dict(base, kind="audio", ptt=True, path=spooled("vo130.ogg")))

c.settimeout(60)
buf = b""
try:
    while True:
        d = c.recv(65536)
        if not d:
            break
        buf += d
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            cmd = json.loads(line)
            size = os.path.getsize(cmd["path"]) if cmd.get("path") else 0
            print("SIDECAR CMD:", cmd["kind"], cmd["to"], repr(cmd.get("text")), size, flush=True)
            emit({"ev": "result", "req": cmd["req"], "ok": True})
except socket.timeout:
    pass
