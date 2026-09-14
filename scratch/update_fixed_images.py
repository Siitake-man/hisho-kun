"""
Updates cs02_mobile_en.jpg and cs05_localllm_en.jpg with the corrected,
100% English images (removing all Japanese text inside phone and laptop screens).
"""
import shutil
from pathlib import Path

brain_dir = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\eab8962d-4cce-4707-a18b-1d07230cfddc")
assets_dir = Path("docs/guides/assets")

cs02_src = brain_dir / "cs02_mobile_en_1789301331280.jpg"
cs05_src = brain_dir / "cs05_localllm_en_1789301367040.jpg"

shutil.copy2(cs02_src, assets_dir / "cs02_mobile_en.jpg")
print(f"Updated cs02_mobile_en.jpg ({cs02_src.stat().st_size} bytes)")

shutil.copy2(cs05_src, assets_dir / "cs05_localllm_en.jpg")
print(f"Updated cs05_localllm_en.jpg ({cs05_src.stat().st_size} bytes)")
