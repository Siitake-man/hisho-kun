"""
Copies all remaining English infographics into docs/guides/assets/
and updates image references in docs/guides/NEO_HISHO_CHEAT_SHEETS_en.html.
"""
import shutil
from pathlib import Path

brain_dir = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\eab8962d-4cce-4707-a18b-1d07230cfddc")
assets_dir = Path("docs/guides/assets")
assets_dir.mkdir(parents=True, exist_ok=True)

asset_map = {
    "cs01_setup_en_1789301110319.jpg": "cs01_setup_en.jpg",
    "cs02_mobile_en_1789301130788.jpg": "cs02_mobile_en.jpg",
    "cs03_calendar_en_1789301152194.jpg": "cs03_calendar_en.jpg",
    "cs05_localllm_en_1789301172392.jpg": "cs05_localllm_en.jpg",
}

for src_name, dest_name in asset_map.items():
    src = brain_dir / src_name
    dest = assets_dir / dest_name
    if src.exists():
        shutil.copy2(src, dest)
        print(f"Copied {dest} ({dest.stat().st_size} bytes)")
    else:
        print(f"ERROR: Not found: {src}")

# Update HTML references in NEO_HISHO_CHEAT_SHEETS_en.html
html_path = Path("docs/guides/NEO_HISHO_CHEAT_SHEETS_en.html")
html_text = html_path.read_text(encoding="utf-8")

replacements = {
    "openLightbox('assets/cs01_setup.jpg')": "openLightbox('assets/cs01_setup_en.jpg')",
    'src="assets/cs01_setup.jpg"': 'src="assets/cs01_setup_en.jpg"',
    "openLightbox('assets/cs02_mobile.jpg')": "openLightbox('assets/cs02_mobile_en.jpg')",
    'src="assets/cs02_mobile.jpg"': 'src="assets/cs02_mobile_en.jpg"',
    "openLightbox('assets/cs03_calendar.jpg')": "openLightbox('assets/cs03_calendar_en.jpg')",
    'src="assets/cs03_calendar.jpg"': 'src="assets/cs03_calendar_en.jpg"',
    "openLightbox('assets/cs05_localllm.jpg')": "openLightbox('assets/cs05_localllm_en.jpg')",
    'src="assets/cs05_localllm.jpg"': 'src="assets/cs05_localllm_en.jpg"',
}

for old, new in replacements.items():
    html_text = html_text.replace(old, new)

html_path.write_text(html_text, encoding="utf-8")
print(f"Updated all infographic references in {html_path}")
