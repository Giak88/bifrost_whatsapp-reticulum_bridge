"""Client LXMF "proprietario" per la prova end-to-end (fa la parte di Sideband).
Uso: e2e_owner.py <rns_config> <workdir> <bridge_hash_hex>
"""
import os
import sys
import time

import LXMF
import RNS

cfg, work, bridge_hex = sys.argv[1], sys.argv[2], sys.argv[3]
RNS.Reticulum(cfg, loglevel=RNS.LOG_WARNING)
ident = RNS.Identity.from_file(os.path.join(work, "owner.id"))
router = LXMF.LXMRouter(identity=ident, storagepath=os.path.join(work, "owner-lxmf"))
dest = router.register_delivery_identity(ident, display_name="Test owner")
got = []


def on_msg(m):
    got.append(m)
    f = {k: (v[0], len(v[1])) if k in (6, 7) else [(a[0], len(a[1])) for a in v] for k, v in (m.fields or {}).items()}
    print("RECEIVED:", repr(m.content_as_string()), f, flush=True)


router.register_delivery_callback(on_msg)
router.announce(dest.hash)
print("OWNER", dest.hash.hex(), flush=True)

bh = bytes.fromhex(bridge_hex)
t0 = time.time()
while RNS.Identity.recall(bh) is None and time.time() - t0 < 20:
    RNS.Transport.request_path(bh)
    time.sleep(1)
bdest = RNS.Destination(RNS.Identity.recall(bh), RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")


def send(text, fields=None):
    router.handle_outbound(LXMF.LXMessage(bdest, dest, text, fields=fields, desired_method=LXMF.LXMessage.DIRECT))


# aspetta i messaggi WhatsApp inoltrati dal sidecar finto
time.sleep(float(os.environ.get("WAIT", "12")))
send("/pending")
time.sleep(4)
send("/download 1")
time.sleep(6)
send("/to 1")
time.sleep(3)
send("hello from the LoRa")
time.sleep(3)
send("photo", {LXMF.FIELD_IMAGE: ["webp", open(os.path.join(work, "img.webp"), "rb").read()]})
time.sleep(5)
print("END", len(got), flush=True)
