# 📍 ネオ秘書くん 状況共有ボード (active_context.md)

**最終更新**: 2026-08-15 03:20

---

## 1. 現在の開発フェーズ
- **フェーズ**: Phase 3 完了 ＆ Phase 4（外部拡張・手帳統合）完了
- **ステータス**: 🟢 健全（全主要機能が稼働中）

---

## 2. 実装完了機能一覧 (2026-08-15)

| 機能モジュール | 担当ファイル | 状態 | 概要 |
| :--- | :--- | :---: | :--- |
| **Multi-LLM Factory** | `llm_factory.py` | ✅ | OpenCode GO (DeepSeek-V4-Flash/V3/R1), LM Studio, Geminiの動的探索・切替 |
| **モデル/プロバイダ永続化** | `llm_factory.py`, `discovered_models.json` | ✅ | 探索したモデル一覧のJSONキャッシュと選択頭脳の.env保存 |
| **MentisDB型 長期記憶** | `database.py`, `db_tools.py`, `agent.py` | ✅ | `user_insights` テーブル＋ボスの制約・好みの自律学習＆動的プロンプト注入 |
| **ドット絵ペットUI** | `gui.py`, `generate_mascot_assets.py` | ✅ | レトロドット絵スプライト＋待機/瞬き/思考中/笑顔アニメーション |
| **スクロール対応吹き出し** | `gui.py` | ✅ | `CTkTextbox`（高さ140px固定）で長文でも入力欄とペットが一切潰れない |
| **TODOタスク管理エンジン** | `database.py`, `db_tools.py` | ✅ | `tasks` テーブル＋AIによるタスク登録・確認・完了ツール |
| **MCP連携マネージャー** | `mcp_manager.py`, `gui.py`, `agent.py` | ✅ | `mcp_config.json`＋設定画面トグル＋外部ツールの動的バインド |
| **統合手帳ウィンドウ** | `gui.py` (`CalendarWindow`) | ✅ | 予定・TODOタスク・ボスのトリセツ（知見）を3タブで一括管理 |

---

## 3. 次期着手タスク（Next Action）
1. **👁️ MiniCPM型 画面見守り (Vision) ＆ エラー検知ツールの実装**
   - 画面キャプチャをAIに渡し、開いている画面の作業アドバイスやエラー解決支援を行う機能。
2. **📱 Bluetoothダイレクト・スマホ専用ペット端末 (Desk Pet) PWAプロトタイプ**
   - 古いスマホのブラウザ（Web Bluetooth）で動く全画面ドット絵ペット画面の作成。