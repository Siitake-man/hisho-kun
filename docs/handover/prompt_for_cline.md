# 🤝 Cline への引き継ぎ指示書 (prompt_for_cline.md)

- **作成日時**: 2026-09-20 20:30 (Antigravity 担当セッション終了)
- **対象エージェント**: Cline (VS Code 拡張機能)
- **関連実装計画書**: [`implementation_plan.md`](file:///C:/Users/bonob/.gemini/antigravity/brain/8fdafe2a-21eb-40c8-94db-8071579539ee/implementation_plan.md)
- **作業ウォークスルー**: [`walkthrough.md`](file:///C:/Users/bonob/.gemini/antigravity/brain/8fdafe2a-21eb-40c8-94db-8071579539ee/walkthrough.md)

---

## 1. これまでの進捗（完了済み領域）

Antigravity 側にて、グラフエンジニアリング実装計画の **Phase 1 および Phase 2** を 100% 完遂し、テストオールグリーン（13 passed）を達成しました。

1. **`i18n.py`**:
   - イベント駆動型言語変更リスナー（`subscribe_language_change` / `unsubscribe_language_change`）を配備。
   - `ui.tray.*`, `ui.gui.*`, `ui.menu.*`, `ui.radial.*`, `ui.cal.*`, `ui.qr.*`, `ui.dev.*` の日英辞書キー全86件を完全対称で登録。
2. **Phase 1 (常時表示UI・全メニュー)**:
   - `gui.py`: 右クリックメニュー全15項目、吹き出しヘッダー、手帳ボタン、初期挨拶、リンクボタン、入力欄、FSM状態メッセージを `t()` 化。動的言語切替ハンドラ結合。
   - `ui/system_tray.py`: タスクトレイ全7項目およびツールチップを `t()` 化。動的言語追従および `stop()` 時のリスナー解除を配備。
   - `ui/radial_menu.py`: サークルメニュー6大ボタンのタイトル・ホバー説明文・台詞を `t()` 化。
3. **Phase 2 (統合手帳・接続ダイアログ)**:
   - `ui/calendar_window.py`: タイトル、ヘッダー、4大タブ（`Events`, `Tasks`, `Habits & Streak`, `Boss Insights`）、月週日ビュー、今日ボタン、タスク追加ボタンを `t()` 化。
   - `ui/qr_dialog.py`: タイトル、ヘッダー、説明文、接続先ラベルを `t()` 化。
   - `ui/device_approval_dialog.py`: タイトル、接続要求、端末情報、自動拒否タイマー、拒否/許可ボタンを `t()` 化。
4. **テスト保護**:
   - `tests/test_i18n_and_ui_protection.py`: 全13件合格（0.37s OK）。
   - `tests/test_terminology_boundary.py`: 全4件（23サブテスト）合格。

---

## 2. Cline に引き継ぐ残タスク（Phase 3: 設定画面・ツアー・ブリーフィング）

Cline は、[`implementation_plan.md`](file:///C:/Users/bonob/.gemini/antigravity/brain/8fdafe2a-21eb-40c8-94db-8071579539ee/implementation_plan.md) の **Phase 3** の実装を引き継いで完了させてください。

### 📌 タスク 3.1: 設定画面の残存日本語ラベルの `t()` 化 (`ui/settings_window.py`)
- **対象箇所**:
  - プロバイダ見出し（Google Gemini, Anthropic Claude, OpenAI, OpenCode GO, Groq, ローカルLLM 等）
  - MCP自動登録ボタン（`🚀 Antigravityに自動登録`, `📋 手動用 MCP設定JSONをコピー` 等）
  - Google OAuth / iCal連携の購読設定ラベルやボタン
  - トースト・保存完了ダイアログメッセージ
- **注意点**: 既存の `t('ui.settings.*')` の命名規則に従い、`i18n.py` の `_TRANSLATIONS['ja']` と `_TRANSLATIONS['en']` にキーを対称追加した上で置換すること。

### 📌 タスク 3.2: オンボーディングツアーの多言語化 (`ui/tour_overlay.py` & `tour_engine.py`)
- **対象箇所**:
  - `ui/tour_overlay.py`: ガイドカードのスキップボタン（`✕ スキップ` / `✕ Skip`）、戻るボタン（`◀ 戻る` / `◀ Back`）、次へボタン（`次へ ▶` / `Next ▶`）、完了ボタン（`🎉 完了` / `🎉 Done`）。
  - `tour_engine.py`: ツアーステップのタイトルおよび本文（ステップ1〜3）。
- **注意点**: 初回起動時の吹き出しメッセージも `t()` 経由で取得できるようにすること。

### 📌 タスク 3.3: ブリーフィングエンジンの多言語化 (`briefing_engine.py`)
- **対象箇所**:
  - 朝会/終礼/午後/夜間ブリーフィングのキャラクター挨拶テンプレート（dolphin, kyle, seal, kinoko, wombat, hisho）。
  - Markdown出力セクションタイトル（`🌡️ **現在の天気**`, `📅 **本日の予定タイムライン**`, `📝 **重要TODO**` 等）。
- **注意点**: `dt.strftime` による曜日表示（`月` / `Mon` 等）を `i18n.get_language()` に応じて切り替えること。

---

## 3. コーディング規約 ＆ 厳格な制約（AGENTS.md準拠）

- **推測によるコード記述の禁止**: メソッド名や引数は必ず既存コードをファクトベースで確認すること。
- **手抜き省略表現の禁止**: `// TODO` や `# ...省略` は一切使わず、プロダクション品質のコードを記述すること。
- **辞書キーの対称性厳守**: `i18n.py` に新しいキーを追加した際は、必ず `ja` と `en` の両方に同じキーを定義すること（`test_i18n_dictionary_symmetry` で不整合が検知されます）。
- **ドキュメント4点セットの同時更新**: 作業完了時は、`00_ドキュメント一覧.md`, `DESIGN_SPEC.md`, `機能ロードマップ.md`, `active_context.md` の4大ドキュメントを必ず同時更新すること。
- **作業後のテスト実行**:
  - `venv\Scripts\python.exe -m pytest tests/test_i18n_and_ui_protection.py -v`
  - `venv\Scripts\python.exe -m pytest tests/test_terminology_boundary.py -v`
