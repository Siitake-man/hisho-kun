# 🤖 Jules / Codex 向け 非同期開発指示書 (prompt_for_jules.md)

**プロジェクト名**: ネオ秘書くん (Neo-Secretary)  
**作成日時**: 2026-08-15 03:20  
**前提環境**: Windows / Python 3.11+ / CustomTkinter / LangGraph / SQLite

---

## 1. 直前の開発状況サマリー
- **完了した機能**:
  1. Multi-LLM Factory（OpenCode GO / LM Studio / Gemini）動的モデル探索 ＆ 永続化
  2. MentisDB型 長期知見エンジン（`user_insights` テーブル ＆ 自動プロンプト注入 ＆ 自律知見抽出）
  3. レトロドット絵ペットUI（スプライト＋待機/瞬き/思考中/笑顔アニメーション）
  4. TODOタスク管理エンジン（`tasks` テーブル ＆ CRUDツール）
  5. 外部MCP連携マネージャー（`mcp_manager.py` ＆ 設定画面トグル ＆ 動的ツールバインド）
  6. 統合手帳ウィンドウ（`CalendarWindow` ➔ 予定/TODO/知見の3タブ手帳UI）
  7. 吹き出し長文スクロール対応（`CTkTextbox` による入力欄/ペット固定）

---

## 2. 次回実施してほしいタスク（Night Task）

### 🎯 タスク: MiniCPM型 画面見守り (Vision) ＆ 画面キャプチャツールのプロトタイプ実装
- **目的**: ユーザーが困っている画面（エラーやブラウザ）をAIが視覚認識してアドバイスできるようにする。
- **対象ファイル**:
  - `db_tools.py`:
    - `Pillow` の `ImageGrab.grab()` または `pyautogui` を用いた `capture_screen_tool()` の追加。
    - キャプチャした画像を一時ファイルまたは Base64 にエンコードし、Vision対応モデル（Gemini / OpenCode Vision / Local Vision）に渡せるインターフェースを準備。
  - `agent.py`:
    - `capture_screen_tool` を `tools` に登録。
- **制約事項**:
  - `AGENTS.md` のコーディング規約を厳守（厳格な型ヒント、logging、Google Style docstrings）。
  - UIスレッド（Tkinter）をフリーズさせないよう非同期設計を徹底すること。

---

## 3. 参照すべき仕様ドキュメント
- [docs/specs/DESIGN_SPEC.md](file:///c:/Users/bonob/OneDrive/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88/AntiGlavity/%E3%83%8D%E3%82%AA%E7%A7%98%E6%9B%B8%E3%81%8F%E3%82%93/docs/specs/DESIGN_SPEC.md)
- [docs/specs/機能ロードマップ.md](file:///c:/Users/bonob/OneDrive/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88/AntiGlavity/%E3%83%8D%E3%82%AA%E7%A7%98%E6%9B%B8%E3%81%8F%E3%82%93/docs/specs/%E6%A9%9F%E8%83%BD%E3%83%AD%E3%83%BC%E3%83%89%E3%83%9E%E3%83%83%E3%83%97.md)
- [AGENTS.md](file:///c:/Users/bonob/OneDrive/%E3%83%89%E3%82%AD%E3%83%A5%E3%83%A1%E3%83%B3%E3%83%88/AntiGlavity/%E3%83%8D%E3%82%AA%E7%A7%98%E6%9B%B8%E3%81%8F%E3%82%93/AGENTS.md)
