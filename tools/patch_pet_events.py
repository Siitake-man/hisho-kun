# -*- coding: utf-8 -*-
import os
f = os.path.join(os.path.dirname(__file__), "..", "web_pet", "pet.js")
with open(f, "r", encoding="utf-8") as fh:
    text = fh.read()
old = 'return `<div class="note-item"><div class="note-title">📅 ${escapeHtml(e.title)}</div><div class="note-desc">🕐 ${escapeHtml(dt)}</div></div>`;'
new = 'return `<div class="note-item"><div class="note-title">📅 ${escapeHtml(e.title)}</div><div class="note-desc">🕐 ${escapeHtml(dt)}${e.source_name ? " ／ " + escapeHtml(e.source_name) : ""}</div></div>`;'
if old in text:
    text = text.replace(old, new)
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("PATCH_OK")
else:
    print("MATCH_FAILED")