# Antigravity 同期時の申し送り（OpenCode 側 最小修正3点）— 2026-09-23

**目的**: OpenCode セッション（2026-09-23 夜）で入れた**最小修正3点**を、Antigravity 側の次回同期・再生成時に**上書きしない**（または取り込んでから同期する）ための申し送り。

**重要**: 上書きされても**リポジトリの番人テストが Red で自動検知**します（データ・セキュリティへの実害はゼロ）。

---

## 修正1: `active_context.md` の MentisDB 記述5行へ境界マーカー付与

- **理由**: `tests/test_terminology_boundary.py` は、エージェントが最初に読む `active_context.md` の全行について「MentisDB を含む行は境界注記（`別物` / `旧呼称` / `汎用エージェント記憶MCP` / `混同禁止` / `現在の` / `呼称刷新`）を必須」とする番人。2026-09-23 18:50 の全面刷新で追加された5行が無注記のため Red になった。
- **修正**: 5行を `旧MentisDB（汎用エージェント記憶MCP）` 形式へ最小変更（内容・意味は不変）。
- **再適用**: 対象行に上記マーカーのいずれかを含めればよい。

## 修正2: `tools/audit_skills_with_jev.py` — 辞書キー揺れの後方互換吸収

- **理由**: ツール内部は `desc`、旧API/テストは `description` を渡すため `KeyError: 'desc'`。
- **修正**: `audit_domain_with_jev()` の冒頭で入力を正規化（`s.get("desc") or s.get("description")`）。

## 修正3: `tools/audit_skills_with_jev.py` — 末尾 `return` の復元

- **理由**: リファクタ時に `audit_domain_with_jev()` の末尾 `return {...}` が欠落し、暗黙 `None` を返していた（`test_jev_decisions_api_format_compatibility` が検出）。
- **修正**: 契約を復元 — `domain_id` / `canonical_master` / `redundancy_level` / `domain_action` / `skill_count` / **`confidence`**（`res.get("confidence", 0.0)`、エラー・例外時は `0.0`）。

## 修正4: `tools/audit_skills_with_jev.py` — CI 互換（JevClient 不在時の graceful import）★CI赤の真因

- **理由**: Jev クライアントは `~/.gemini/tools/jev_router`（ボスのローカル専用）にあり、**CI・配布環境には存在しない**。素の `from jev_client import JevClient` だと **pytest のテスト収集エラー**で全5テストジョブが赤になる（2026-09-23 の CI 失敗の真因）。
- **修正**: `try/except` の最終段で `JevClient = None` へ縮退（モジュールは import 可能）＋ `main()` 冒頭で明示 `SystemExit`（CI では実行不可の旨を表示）。

## 修正5: `tools/audit_skills_with_jev.py` — `REPORT_FILE` の絶対パス除去

- `Path(r"c:\Users\bonob\...")` のハードコードを `Path(__file__).resolve().parent.parent / "docs" / "reports" / ...` へ（CI・他端末互換）。

## 修正6: `tests/test_audit_skills_with_jev.py` — Jev 不在環境の skip ガード

- `@unittest.skipUnless(_JEV_AVAILABLE, "JevClient が未実装の環境 (CI等) のためスキップします")`（PR #7 の `test_jev_model_planner` / `test_tool_guard_hook` と同じ方針）。

## 修正7（引き算スプリント 2026-09-23）: `active_context.md` の履歴分離 ＋ `session-start` 読書規律

- **`active_context.md`**: 294,905 → **19,254 bytes**（93.5%削減）。履歴は `docs/handover/archive/active_context_history_2026Q3.md`（277,795 bytes・全量保存）へ分離。**本文は「現在地＋Next Actions＋直近セッション（09-22 Part 4/5・09-23 Part 6/7/8）」のみ**とする（再肥大させないこと。追記は直近分のみ・古い分は archive へ）。
- **履歴分離の規約（両スキルに明文化済み）**: 四半期ファイル（`active_context_history_<YYYY>Q<n>.md`）へ**追記のみ**（上書き禁止）。約50KB超で分離し、本文先頭にポインタを残す。`session-start` スキル「履歴アーカイブ規約」＋`session-wrap-up` ステップ3.5 が正本。
- **`docs/00_ドキュメント一覧.md`**: 重複していた詳細ディレクトリツリーを主要のみに圧縮（43,570 → 35,312 bytes）。
- **`.agents/skills/session-start/SKILL.md`**: ステップ0（Jev Pre-flight 必須）／再開宣言の必須欄（Jev 結果）／トークン効率の読書規律（自動ロード済みは再読しない・specsは目次＋該当節・index は差分時のみ）。**トークン予算目安: 約15k**（旧: 約170k）。
- 注: `active_context.md` / `docs/00_ドキュメント一覧.md` / `.agents/` は **.gitignore 対象**（Git ではなく OneDrive 同期で共有される設計）。

---

## 検証コマンド（どちらのエージェントでも同じ）

```powershell
cd "C:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん"
& ".\venv\Scripts\python.exe" -m unittest discover -s tests -p "test_terminology_boundary.py"   # Ran 4 tests OK
& ".\venv\Scripts\python.exe" -m unittest discover -s tests -p "test_audit_skills_with_jev.py" # Ran 8 tests OK
& ".\venv\Scripts\python.exe" -m pytest -q                                                     # 914 passed
```

**記録**: 2026-09-23 OpenCode セッション（P0-4 / ID 53 / ID 50 封鎖と同時に実施）。
