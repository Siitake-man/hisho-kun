---
name: holistic-code-review
description: ネオ秘書くんのコードベース全体をMCPグラフ分析と2軸レビュー（Standards/Spec）で網羅的にレビューし、優先度付き改善レポートを出力するスキル。
---

# スキル：全体コードレビュー (holistic-code-review)

このスキルは、プロジェクト「ネオ秘書くん（Neo-Secretary）」のコードベース全体を網羅的にレビューし、優先度付きの改善・修正点リストを出力する。

## 実行フロー

### Step 0: 前提確認 ＆ 知識同期
1. **codebase-memory-mcp 利用可否 ＆ インデックス最新化**: `index_repository` / `detect_changes` でコードグラフを更新。
2. **規約・仕様の確認**: `AI_RULES.md`, `DESIGN_SPEC.md`, `機能ロードマップ.md` をロード。

### Step 1: 規約ソース・Specソースの参照
- **Standards軸（規約準拠）**: `AI_RULES.md`（非同期ループのブロッキング防止、型安全、loggingの徹底、省略コメント禁止）
- **Spec軸（仕様適合）**: `DESIGN_SPEC.md`（LLM Factory、ドット絵ペットUI、LangGraph StateGraph、SQLite CRUD）

### Step 2: モジュール別並列レビュー
1. **Agent / LLM Factory 領域**:
   - `agent.py`, `llm_factory.py`, `db_tools.py`
   - チェック観点: LangGraphステートマシンの整合性、Tool定義の堅牢性、エラーハンドリング、プロンプトインジェクション対策
2. **GUI / ペットUI 領域**:
   - `gui.py`, `main.py`
   - チェック観点: Tkinterとasyncioのイベントループ共存、スレッドセーフティ、フォーカスアウト保存等のイベント駆動設計
3. **Database 領域**:
   - `database.py`, `neo_secretary.db`
   - チェック観点: Pydanticモデルバリデーション、SQLiteトランザクション、外部キー制約、インデックス

### Step 3: 動的ペルソナによる多角検証
1. 👥 **エンドユーザー（多忙なビジネスパーソン）視点**: 5分以内で直感的に操作できるか？
2. 💻 **Python/AIアーキテクト視点**: 非同期処理でハングしないか？API障害時にフォールバックできるか？
3. 😈 **Devil's Advocate（悪意あるテスター）視点**: 不正な日時文字列や空文字入力でクラッシュしないか？
4. 🚀 **Dreamer（イノベーター）視点**: ペットが愛着を持てる可愛いリアクションをしているか？

### Step 4: 統合レポート作成
- **出力先**: `docs/code_review_report_YYYYMMDD.md`
- 改善項目を P0（緊急バグ/ハング要因）〜 P3（軽微なリファクタリング）に分類して出力。

---

## 留意事項
- レビュー結果は批判に終始せず、具体的な修正コードの提案と「なぜ直すべきか（Why）」を必ず明記すること。
