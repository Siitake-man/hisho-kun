# -*- coding: utf-8 -*-
"""index.html / sw.js / pet.js のキャッシュバージョン整合診断。"""
import io
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))


def read(path: str) -> str:
    return io.open(os.path.join(ROOT, path), encoding="utf-8").read()


html = read(os.path.join("web_pet", "index.html"))
versions = re.findall(r'src="[a-z_]+\.js\?v=([\d.]+)"', html)
print("index versions:", versions)

sw = read(os.path.join("web_pet", "sw.js"))
print("sw CACHE_NAME:", re.findall(r"CACHE_NAME\s*=\s*'[^']*'", sw))

pet = read(os.path.join("web_pet", "pet.js"))
print("pet keys:", re.findall(r"'neo-pet-v[\d.]*'", pet)[:5])
