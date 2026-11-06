"""Config loading: new English keys, old Italian keys (alpha0.1/0.2), defaults. Needs the bridge deps (RNS, LXMF)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
from bifrost import load_config  # noqa: E402


def cfg(text):
    with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as f:
        f.write(text)
    try:
        return load_config(f.name)
    finally:
        os.unlink(f.name)


OWNER = "0123456789abcdef0123456789abcdef"

c = cfg(f"""[bridge]
owner = <{OWNER}>
language = it
max_send_mb = 12
[limits]
confirm_threshold_kb = 64
quality_img = medium
quality_audio = alto
groups = all
codec2_mode = 1600
""")
L = c["limits"]
assert c["owners"] == [OWNER] and c["lang"] == "it" and c["max_send_mb"] == 12
assert L.confirm_threshold_kb == 64 and L.quality_img == "medium" and L.quality_audio == "high"
assert L.groups == "all" and L.codec2_mode == "1600"

# alpha0.2 file, exactly as the old installer wrote it
c = cfg(f"""[bridge]
proprietario = {OWNER}
annuncio_min = 20
max_invio_mb = 30
dir = ~/.bifrost
[limiti]
soglia_conferma_kb = 32
max_file_mb = 0.9
qualita_img = basso
qualita_audio = medio
audio_mode = 2400
gruppi = seguiti
link_kbps = 1.2
""")
L = c["limits"]
assert c["owners"] == [OWNER] and c["announce_min"] == 20 and c["lang"] == "en" and c["max_send_mb"] == 30
assert L.quality_img == "low" and L.quality_audio == "medium" and L.groups == "followed"
assert L.confirm_threshold_kb == 32 and L.codec2_mode == "2400" and L.max_file_mb == 0.9

# two owners, defaults everywhere else
c = cfg(f"[bridge]\nowner = {OWNER}, <{'ab' * 16}>\n")
assert c["owners"] == [OWNER, "ab" * 16] and c["lang"] == "en" and c["name"] == "Bifrost"
assert c["limits"].quality_img == "low" and c["limits"].groups == "followed" and c["max_send_mb"] == 30
assert c["socket"].endswith("/.bifrost/ipc.sock")

# unknown language falls back to English
assert cfg(f"[bridge]\nowner = {OWNER}\nlanguage = fr\n")["lang"] == "en"
print("config ok")
