"""
Copies newly generated English infographics into docs/guides/assets/
and updates image references in docs/guides/NEO_HISHO_CHEAT_SHEETS_en.html.
"""
import shutil
from pathlib import Path

# Paths
banner_src = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\eab8962d-4cce-4707-a18b-1d07230cfddc\banner_main_en_1789300947520.jpg")
cs04_src = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\eab8962d-4cce-4707-a18b-1d07230cfddc\cs04_agent_en_1789300966983.jpg")

assets_dir = Path("docs/guides/assets")
assets_dir.mkdir(parents=True, exist_ok=True)

banner_dest = assets_dir / "banner_main_en.jpg"
cs04_dest = assets_dir / "cs04_agent_en.jpg"

shutil.copy2(banner_src, banner_dest)
print(f"Copied {banner_dest} ({banner_dest.stat().st_size} bytes)")

shutil.copy2(cs04_src, cs04_dest)
print(f"Copied {cs04_dest} ({cs04_dest.stat().st_size} bytes)")

# Update HTML references
html_path = Path("docs/guides/NEO_HISHO_CHEAT_SHEETS_en.html")
html_text = html_path.read_text(encoding="utf-8")

html_text = html_text.replace(
    "openLightbox('assets/banner_main.jpg')",
    "openLightbox('assets/banner_main_en.jpg')"
).replace(
    'src="assets/banner_main.jpg"',
    'src="assets/banner_main_en.jpg"'
).replace(
    "openLightbox('assets/cs04_agent.jpg')",
    "openLightbox('assets/cs04_agent_en.jpg')"
).replace(
    'src="assets/cs04_agent.jpg"',
    'src="assets/cs04_agent_en.jpg"'
)

html_path.write_text(html_text, encoding="utf-8")
print(f"Updated image references in {html_path}")
