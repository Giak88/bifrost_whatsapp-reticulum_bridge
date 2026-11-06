#!/usr/bin/env python3
"""Small config.ini editor used by setup.sh. Keeps comments and layout (configparser would not).

  cfgtool.py get     FILE SECTION KEY
  cfgtool.py set     FILE SECTION KEY VALUE
  cfgtool.py migrate FILE LANG        rename alpha0.1/0.2 Italian names to the current ones
"""
import re
import sys

OLD_SECTION = {"limiti": "limits"}
OLD_KEY = {"proprietario": "owner", "nome": "name", "annuncio_min": "announce_min", "max_invio_mb": "max_send_mb",
           "soglia_conferma_kb": "confirm_threshold_kb", "audio_mode": "codec2_mode",
           "qualita_img": "quality_img", "qualita_audio": "quality_audio", "gruppi": "groups"}
OLD_VALUE = {"basso": "low", "medio": "medium", "alto": "high", "originale": "original",
             "nessuno": "none", "seguiti": "followed", "tutti": "all"}
NEW_SECTION = {v: k for k, v in OLD_SECTION.items()}
NEW_KEY = {v: k for k, v in OLD_KEY.items()}

SEC = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KV = re.compile(r"^(\s*)([A-Za-z0-9_]+)(\s*[=:]\s*)(.*?)\s*$")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def write(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def find(lines, section, key):
    """(section_header_index, key_line_index or None); accepts old names too."""
    names = {section, NEW_SECTION.get(section, section)}
    keys = {key, NEW_KEY.get(key, key)}
    sec_i, cur = None, None
    for i, line in enumerate(lines):
        m = SEC.match(line)
        if m:
            cur = m.group(1).strip()
            if cur in names and sec_i is None:
                sec_i = i
            continue
        if cur in names:
            kv = KV.match(line)
            if kv and not line.lstrip().startswith(("#", ";")) and kv.group(2) in keys:
                return sec_i, i
    return sec_i, None


def cmd_get(path, section, key):
    lines = read(path)
    _, i = find(lines, section, key)
    if i is not None:
        print(KV.match(lines[i]).group(4))


def cmd_set(path, section, key, value):
    lines = read(path)
    sec_i, i = find(lines, section, key)
    if i is not None:
        m = KV.match(lines[i])
        lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3)}{value}"
    elif sec_i is not None:
        lines.insert(sec_i + 1, f"{key} = {value}")
    else:
        lines += ["", f"[{section}]", f"{key} = {value}"]
    write(path, lines)


def cmd_migrate(path, lang):
    out, cur = [], None
    for line in read(path):
        m = SEC.match(line)
        if m:
            cur = OLD_SECTION.get(m.group(1).strip(), m.group(1).strip())
            out.append(f"[{cur}]")
            continue
        kv = KV.match(line)
        if kv and not line.lstrip().startswith(("#", ";")):
            key = OLD_KEY.get(kv.group(2), kv.group(2))
            val = kv.group(4)
            if kv.group(2) == "nome" and re.fullmatch(r"Bifrost alpha0\.\d+", val.strip()):
                continue   # the old installer pinned the version into the announced name
            if key in ("quality_img", "quality_audio", "groups"):
                val = OLD_VALUE.get(val.strip().lower(), val)
            out.append(f"{kv.group(1)}{key}{kv.group(3)}{val}")
        else:
            out.append(line)
    write(path, out)
    _, i = find(out, "bridge", "language")
    if i is None:
        cmd_set(path, "bridge", "language", lang)


if __name__ == "__main__":
    c, a = sys.argv[1], sys.argv[2:]
    {"get": cmd_get, "set": cmd_set, "migrate": cmd_migrate}[c](*a)
