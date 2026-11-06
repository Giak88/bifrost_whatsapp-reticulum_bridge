"""Client LXMF "proprietario" che invia un file grande al bridge.
Uso: e2e_bigfile.py <rns_config> <workdir> <bridge_hash_hex> <MB>
"""
import os
import sys
import time

import LXMF
import RNS

cfg, work, bridge_hex, mb = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
RNS.Reticulum(cfg, loglevel=RNS.LOG_WARNING)
ident = RNS.Identity.from_file(os.path.join(work, "owner.id"))
router = LXMF.LXMRouter(identity=ident, storagepath=os.path.join(work, "owner-lxmf"), delivery_limit=100000)
dest = router.register_delivery_identity(ident, display_name="Test owner")


def on_msg(m):
    print("RECEIVED:", repr(m.content_as_string()), flush=True)


router.register_delivery_callback(on_msg)
router.announce(dest.hash)

bh = bytes.fromhex(bridge_hex)
t0 = time.time()
while RNS.Identity.recall(bh) is None and time.time() - t0 < 20:
    RNS.Transport.request_path(bh)
    time.sleep(1)
bdest = RNS.Destination(RNS.Identity.recall(bh), RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")


def send(text, fields=None):
    m = LXMF.LXMessage(bdest, dest, text, fields=fields, desired_method=LXMF.LXMessage.DIRECT)
    m.register_delivery_callback(lambda x: print("DELIVERED al bridge:", text[:20], flush=True))
    m.register_failed_callback(lambda x: print("FAILED verso il bridge:", text[:20], flush=True))
    router.handle_outbound(m)


time.sleep(8)  # il sidecar finto manda un messaggio che crea la chat #1
send("/to 1")
time.sleep(4)
data = os.urandom(int(mb * 1_000_000))
t1 = time.time()
send("guarda", {LXMF.FIELD_FILE_ATTACHMENTS: [["clip.mp4", data]]})
time.sleep(float(os.environ.get("WAIT", "25")))
print(f"END ({time.time() - t1:.0f} s dopo l'invio)", flush=True)
