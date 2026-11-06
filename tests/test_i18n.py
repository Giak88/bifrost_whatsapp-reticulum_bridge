"""Message catalogue checks: every key has EN and IT, placeholders match, help lists every command."""
import os
import re
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
from core import COMMANDS  # noqa: E402
from i18n import LANGS, LEVEL_ALIASES, LEVELS, MSG, make_t, norm_level  # noqa: E402

fields = lambda s: {f for _, f, _, _ in string.Formatter().parse(s) if f}
bad = []
for key, entry in MSG.items():
    for lang in LANGS:
        if not entry.get(lang):
            bad.append(f"{key}: missing {lang}")
    if fields(entry["en"]) != fields(entry["it"]):
        bad.append(f"{key}: placeholders differ {fields(entry['en'])} vs {fields(entry['it'])}")
assert not bad, "\n".join(bad)

# every level has a name and a description in both languages
for lvl in LEVELS:
    for pre in ("level_", "img_desc_", "aud_desc_"):
        assert pre + lvl in MSG, pre + lvl
# policy words used by /status
for k in ("policy_none", "policy_followed", "policy_all", "none_word"):
    assert k in MSG, k

# help mentions each canonical command in each language
for lang in LANGS:
    h = make_t(lang)("help")
    for word in ("/chat", "/to", "/r", "/status" if lang == "en" else "/stato"):
        assert word in h, (lang, word)
    first = {"en": ("/download", "/cancel", "/pending", "/follow", "/unfollow", "/quality"),
             "it": ("/scarica", "/annulla", "/pendenti", "/segui", "/ignora", "/qualita")}[lang]
    for word in first:
        assert word in h, (lang, word)

# the words shown in help are real aliases
for w in ("/download", "/scarica", "/cancel", "/annulla", "/pending", "/pendenti", "/follow", "/segui",
          "/unfollow", "/ignora", "/quality", "/qualita", "/status", "/stato", "/help", "/aiuto"):
    assert w in COMMANDS, w
for w, canon in LEVEL_ALIASES.items():
    assert canon in LEVELS
assert norm_level("Basso") == "low" and norm_level("MEDIUM") == "medium" and norm_level("x") is None
assert make_t("xx")("pending_none") == MSG["pending_none"]["en"]   # unknown language -> English
print(f"i18n ok: {len(MSG)} messages x {len(LANGS)} languages")
