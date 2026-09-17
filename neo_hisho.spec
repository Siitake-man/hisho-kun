# -*- mode: python ; coding: utf-8 -*-
"""
ネオ秘書くん - PyInstaller ビルド定義 (neo_hisho.spec)

配布形態: onedir (フォルダ + zip) — 起動が速く、AV (ウイルス対策ソフト) の
誤検知リスクが onefile より低い (ボス承認済み方針)。

設計方針 (Why):
- 読み取り専用リソース (web_pet/, assets/, docs/guides/, .env.example) は
  datas で _internal/ へ同梱する。アプリ側の ``Path(__file__).parent`` 相対
  ロジックは onedir では _internal を指すため、アプリコードは無変更で動作する。
- 書き込みデータ (DB, .env, models/, backups/, 各種設定JSON) は同梱せず、
  app_paths.get_app_root() が解決する exe 直下 (ポータブル運用) に置かれる。
- LLM モデル (GGUF) は同梱しない。``NeoHisho.exe --setup-model`` で
  Hugging Face からダウンロードする (tools/setup_local_model.py を利用)。

実行方法 (ボス手動):
    venv\\Scripts\\python.exe build_exe.py
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
from pathlib import Path
import sys

# プロジェクトルート: PyInstaller は spec 実行時に SPECPATH (spec のあるフォルダ) を
# 注入する。単体テスト等で exec される場合に備え、未定義なら CWD へフォールバックする。
_SPEC_DIR = globals().get("SPECPATH")
PROJECT_ROOT = Path(_SPEC_DIR).resolve() if _SPEC_DIR else Path.cwd().resolve()

# spec 実行時はプロジェクトルートが sys.path に無い場合があるため明示追加
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 同梱リソースの列挙（*.bak 等のバックアップ除外）は Deep Module へ集約し、テスト可能にする
from build_resources import iter_bundle_sources

# EXE/タスクバー用アイコン (初代秘書くん 256x256 .ico)
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"

a = Analysis(
    ['main.py'],
    pathex=[],
    # llama-cpp-python が ctypes でロードする llama.dll 等のネイティブDLL
    # (import 解析では検出されないため明示収集が必須)
    binaries=collect_dynamic_libs('llama_cpp'),
    datas=[
        ('web_pet', 'web_pet'),
        ('assets', 'assets'),
        # docs/guides は *.bak 等のバックアップを除いて同梱する（P1 / 2026-09-16 独立査読:
        # 旧バックアップ HTML が配布物へ混入していた）。判断は build_resources へ集約。
        *iter_bundle_sources(PROJECT_ROOT / 'docs' / 'guides', 'docs/guides'),
        ('.env.example', '.'),
        # customtkinter のテーマJSON等データファイル (未同梱だと起動時クラッシュする)
    ] + collect_data_files('customtkinter') + collect_data_files('llama_cpp'),
    hiddenimports=[
        # 関数内 import / 動的 import の取りこぼし防止のため明示列挙する
        'app_paths',
        'agent',
        'agent_bridge_client',
        'agent_identity',
        'agent_watcher',
        'briefing_engine',
        'character_manager',
        'database',
        'db_tools',
        'easter_egg_engine',
        'google_workspace_tools',
        'gui',
        'hisho_mcp_server',
        'i18n',
        'ics_tools',
        'life_coach_engine',
        'life_dreamer',
        'llm_factory',
        'local_sync_server',
        'mcp_installer',
        'mcp_manager',
        'pet_animator',
        'proactive_engine',
        'reminder_engine',
        'suggest_engine',
        'sync_config',
        'task_narrator',
        'tour_engine',
        'update_checker',
        'version',
        'vision_tools',
        'weather_tools',
        'web_assets',
        'webhook_tools',
        'web_tools',
        'whisper_transcriber',
        'ui.settings_window',
        'ui.calendar_window',
        'ui.db_viewer',
        'ui.qr_dialog',
        'ui.sticky_note',
        'tools.setup_local_model',
        # 関数内 import だが、事前解析を確実に通すため明示列挙 (保険)
        'llama_cpp',
        'llama_cpp.llama_chat_format',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 音声文字起こし (faster-whisper) は内部課題化中 (VOICE_INPUT_ENABLED=false) の
    # ため配布から除外する。whisper_transcriber は未導入環境を is_available()=False
    # で優雅に処理するため除外しても安全 (zip を数百MB〜数GB圧縮できる)。
    excludes=[
        'faster_whisper',
        'ctranslate2',
        'av',
        'onnxruntime',
        'tokenizers',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeoHisho',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed: ダブルクリックで黒コンソールを出さない GUI アプリ
    # 🖼️ EXE/タスクバーアイコン: 初代秘書くんの 256x256 .ico を適用 (タスク0)
    icon=str(ICON_PATH),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NeoHisho',
)
