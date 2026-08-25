import shutil
from pathlib import Path

brain_dir = Path(r"C:\Users\bonob\.gemini\antigravity-ide\brain\605760ac-15e6-4456-9d48-1c07d6248420")
assets_dir = Path(__file__).parent / "assets"
assets_dir.mkdir(exist_ok=True)

# 1. お部屋
room_src = brain_dir / "bg_cozy_room_1786932244187.jpg"
if room_src.exists():
    shutil.copy(room_src, assets_dir / "bg_room.jpg")
    print("bg_room.jpg copied")

# 2. カフェ
cafe_src = brain_dir / "bg_rainy_cafe_1786932259361.jpg"
if cafe_src.exists():
    shutil.copy(cafe_src, assets_dir / "bg_cafe.jpg")
    print("bg_cafe.jpg copied")
