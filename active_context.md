# ネオ秘書くん アクティブコンテキスト (active_context.md)

- **最終更新日時**: 2026-08-16 19:30 (Phase 8.7 MCP連携堅牢化・ツール拡充 ＆ SQLiteオンライン自動バックアップ完了)
- **現在のステータス**: ✅ **Phase 8.7 完了**（`hisho_mcp_server.py` のツール拡充、WALモード並行処理強化、SQLite Online Backup による起動時自動バックアップと世代管理の実装完了）

---

## 🎯 達成された主要機能 (Phase 8.7)

1. **🔌 外部MCPサーバーのツール拡充 ＆ 堅牢化 (Phase E-1)**:
   - `hisho_mcp_server.py` に新しいMCPツールを追加：
     - `create_task`: TODOタスクの登録
     - `complete_task`: TODOタスクの完了化
     - `create_calendar_event`: 手帳カレンダーへの予定登録
     - `remember_boss_insight` / `get_boss_insights`: MentisDB長期知見の記憶と検索
     - `ask_human_approval` / `notify_task_completed` / `notify_user_input_needed`: Agent Bridge連携
   - FastMCP（2026-07-28最新仕様）および標準 JSON-RPC 2.0 stdio の両方に対応。

2. **💾 データベースの耐障害性 ＆ オンライン自動バックアップ (Phase E-2)**:
   - **WAL (Write-Ahead Logging) モード有効化**: GUIスレッドとローカルHTTPサーバー間の同時読み書きによるロック競合（`database is locked`）を完全解消。
   - **SQLite Online Backup (`backup_database`)**: アプリ稼働中・書き込み中でも破損ゼロで安全に `.bak` スナップショットを作成（`backups/` ディレクトリに最新7世代を自動ローテーション保存）。
   - **起動時自動バックアップ (`auto_backup`)**: `main.py` 起動時にバックアップを自動実行。

---

## 📝 記録された未解決・改善タスク（Backlog）

1. **🎨 4大キャラクタースプライトの自作画像の組み込み**:
   - ユーザーが `docs/CHARACTER_PROMPTS_SPEC.md` をもとに生成したスプライトシートまたは個別画像を `assets/` に配置・反映。
2. **📱 PWAオフラインキャッシュ（Service Worker）の追加**:
   - スマホ側でのオフライン起動とPWAアイコン設定。