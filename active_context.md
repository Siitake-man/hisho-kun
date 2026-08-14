# 📍 ネオ秘書くん 状況共有ボード (active_context.md)

**最終更新**: 2026-08-15 03:50

---

## 1. 現在の開発フェーズ
- **フェーズ**: Phase 6 完了 ＆ レビューフレームワーク刷新完了
- **ステータス**: 🟢 全機能稼働中・コードグラフ同期完了

---

## 2. 実装完了機能一覧 (2026-08-15)

| 機能モジュール | 担当ファイル | 状態 | 概要 |
| :--- | :--- | :---: | :--- |
| **Multi-LLM Factory** | `llm_factory.py` | ✅ | OpenCode GO, LM Studio, Gemini の動的探索・切替・永続化 |
| **MentisDB型 長期記憶** | `database.py`, `db_tools.py`, `agent.py` | ✅ | ボスの制約・好みの自律学習＆動的プロンプト注入 |
| **ドット絵ペットUI** | `gui.py`, `generate_mascot_assets.py` | ✅ | レトロドット絵スプライト＋待機/瞬き/思考中/笑顔アニメーション |
| **スクロール対応吹き出し** | `gui.py` | ✅ | `CTkTextbox`（高さ140px固定）で長文でも入力欄とペットが一切潰れない |
| **TODOタスク管理エンジン** | `database.py`, `db_tools.py` | ✅ | `tasks` テーブル＋AIによるタスク登録・確認・完了ツール |
| **外部MCP連携マネージャー** | `mcp_manager.py`, `gui.py`, `agent.py` | ✅ | `mcp_config.json`＋設定画面トグル＋**新規MCP追加/削除ダイアログ** |
| **統合手帳ウィンドウ** | `gui.py` (`CalendarWindow`) | ✅ | 予定・TODOタスク・ボスのトリセツ（知見）を3タブで一括管理 |
| **MiniCPM型 画面見守り (Vision)** | `vision_tools.py`, `agent.py` | ✅ | 画面キャプチャ・エラー自動解析ツール（`capture_screen_tool` 等） |
| **プロアクティブ健康見守り** | `proactive_engine.py`, `main.py` | ✅ | 45分作業や夕方を検知し、ペットが自律的に優しく休憩・声掛け |
| **スマホ専用ペット端末 (Desk Pet)** | `web_pet/`, `local_sync_server.py` | ✅ | スマホを机上のペット端末にするPWA ＆ ポート8765ローカル同期API（IP設定モーダル付き） |
| **Google Workspace ダイレクト連携** | `google_workspace_tools.py`, `agent.py` | ✅ | Googleカレンダー予定取得/登録、Gmail未読検索ツール（OAuth2対応） |
| **iCalendar (.ics) 同期** | `ics_tools.py`, `agent.py` | ✅ | GoogleカレンダーやOutlookと相互連携できるICSエクスポート |
| **マルチペルソナ レビュー基盤** | `.agents/skills/holistic-code-review/` | ✅ | 5大エリートペルソナ（アーキテクト、PM、カオス、セキュリティ、デザイナー）による創発的レビュー |

---

## 3. 次回着手タスク（Next Action）
1. **`[P1-1] database.py` の SQLite コネクション管理の一元化（contextmanager化）**
2. **`[P2-1]` ポモドーロタイマー（ペット集中モード）の実装**