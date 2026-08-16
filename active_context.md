# ネオ秘書くん アクティブコンテキスト (active_context.md)

- **最終更新日時**: 2026-08-16 20:08 (Phase H-1 ワンクリックMCP自動登録 ＆ Phase G-2 ニュースURLブラウザ起動ボタン実装完了)
- **現在のステータス**: ✅ **Phase A〜E 完了 ＆ Phase G/H 先行実装完了**（Pillow純粋スライサー、URL検出ブラウザ起動、設定画面からのMCPワンクリック自動登録）

---

## 🎯 今回の追加実装ハイライト

1. **🌐 AIニュース等のURLリンク自動検出 ＆ ブラウザワンクリック起動 (`gui.py`)**:
   - サジェストメッセージ内に URL（`https://...`）が含まれている場合、吹き出し下部に **「🌐 記事をブラウザで開く」** ボタンが動的に出現。
   - クリックすると、OS既定のWebブラウザ（Chrome / Edge 等）が起動して記事が即座に開きます。

2. **🔌 誰のPCでも一発で動く「MCP自動セットアップ」(`mcp_installer.py` & `ui/settings_window.py`)**:
   - `sys.executable` とプロジェクト位置を自己検出し、Antigravity（`~/.gemini/config/mcp_config.json`）や Claude Desktop（`claude_desktop_config.json`）へ正しいパスを自動注入。
   - ネオ秘書くんの「⚙️ 設定画面」➔「外部連携 (MCP)」タブに **「🚀 Antigravityに自動登録」「🚀 Claude Desktopに自動登録」** ボタンを実装。他者に配布した際もワンクリックで設定が完了します。

3. **🖼️ Pillow純粋実装スライサー (`scratch/deploy_pure_pillow.py`)**:
   - `numpy` 依存をゼロにし、仮想環境標準の Pillow のみで白背景完全2値化透過（1-bit Alpha）＆ 全29フレーム配置を完了。

---

## 🗺️ 次期マスター作業計画（Phase F〜H）

- 📄 参照: `master_workplan_game_ux_20260816.md`
- **Phase F**: ゲーム級アニメーション（ポモドーロネオン円形ゲージ・集中時の闘気・炎・猛烈タイピングエフェクト）
- **Phase G**: メッセージ領域のカード型スマートバッジ（TODO/ニュース/予定の色分け・フォント洗練）
- **Phase H**: 配布パッケージング（インストーラー統合・Inno Setup）