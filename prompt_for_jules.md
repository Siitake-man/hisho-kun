# 🤖 Jules / Codex 向け 非同期開発指示書 (prompt_for_jules.md)

**プロジェクト名**: ネオ秘書くん (Neo-Secretary)  
**作成日時**: 2026-08-15 03:50  
**前提環境**: Windows / Python 3.11+ / CustomTkinter / LangGraph / SQLite

---

## 1. 直前の開発状況サマリー
- **完了した機能**:
  1. Multi-LLM Factory（OpenCode GO / LM Studio / Gemini）動的探索 ＆ 永続化
  2. MentisDB型 長期知見エンジン（`user_insights` テーブル ＆ 自律学習）
  3. レトロドット絵ペットUI ＆ アニメーション（待機/瞬き/思考中/笑顔）
  4. TODOタスク管理エンジン ＆ 3タブ統合手帳ウィンドウ
  5. 外部MCP動的マネージャー ＆ 新規サーバー登録/削除ダイアログ
  6. 吹き出し長文スクロール対応（`CTkTextbox` による固定レイアウト）
  7. MiniCPM型 画面見守り (Vision) ＆ エラー自動検知ツール
  8. 自律プロアクティブ健康ケアエンジン
  9. スマホ専用ペット端末 (Desk Pet) PWA ＆ ポート8765ローカル同期API（接続先IP変更対応）
  10. Google Workspace (Calendar & Gmail) Directツール ＆ iCalendar (.ics) 同期
  11. マルチペルソナ全体コードレビューフレームワーク（5大エリートペルソナ）

---

## 2. 次回実施してほしいタスク（Night Task）

### 🎯 タスク 1: [P1-1] `database.py` の SQLite コネクション管理の一元化
- **目的**: 各CRUD関数での `sqlite3.connect()` 呼び出しを `contextlib.contextmanager` を用いた一元管理にリファクタリングし、例外時のロールバックとコネクションリークを完全に防ぐ。
- **対象ファイル**: `database.py`
- **コーディング規約**:
  - `AGENTS.md` 厳守（厳格な型ヒント、logging、Google Style docstrings）。

### 🎯 タスク 2: [P2-1] ポモドーロタイマー（ペット集中モード）の実装
- **目的**: 25分集中＋5分休憩のタイマーカウントを `proactive_engine.py` / `gui.py` に追加し、ドット絵ペットと連動させる。

---

## 3. 参照すべき仕様ドキュメント
- [docs/specs/DESIGN_SPEC.md](file:///c:/Users/bonob/OneDrive/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88/AntiGlavity/%E3%83%8D%E3%82%AA%E7%A7%98%E6%9B%B8%E3%81%8F%E3%82%93/docs/specs/DESIGN_SPEC.md)
- [docs/temp/code_review_report_20260815.md](file:///c:/Users/bonob/OneDrive/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88/AntiGlavity/%E3%83%8D%E3%82%AA%E7%A7%98%E6%9B%B8%E3%81%8F%E3%82%93/docs/temp/code_review_report_20260815.md)
- [AGENTS.md](file:///c:/Users/bonob/OneDrive/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88/AntiGlavity/%E3%83%8D%E3%82%AA%E7%A7%98%E6%9B%B8%E3%81%8F%E3%82%93/AGENTS.md)
