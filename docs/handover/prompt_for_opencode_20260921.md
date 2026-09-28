# OpenCode 引き継ぎ指示書 (2026-09-21 深夜セッションの残タスク)

**作成**: 2026-09-22 / OpenCode Orchestrator
**対象**: 次回の OpenCode セッション（または Codex / Jules）
**前提**: 本セッションで OpenCode × Jev-MCP マルチエージェント体制（11体・モデル選択・入力待ち通知）を配備完了済み。

---

## 0. 最初に読むもの（必須）
1. `AGENTS.md`（プロジェクト規約 / §4 が OpenCode 実行プロトコル）
2. `OPENCODE.md`（Jev Pre-flight / Tool Guard / Verifierゲート / **§2.5 モデル選択**）
3. `docs/specs/DESIGN_SPEC.md` **§21 / §23**（本体制の設計）
4. `active_context.md`（現在地）

---

## 1. 【P1】承認監査ログの契約違反（TODO手帳 ID 28）

**症状（実測済み）**:
- `approval_audit_logs.created_at` だけが**秒**、他テーブルは**ミリ秒**（1000倍の断絶）
  - 実測: `max(created_at) = 1789976380`（他は `1.7e12` 台）
  - 影響: `devices.last_seen`（ms）と JOIN すると監査ログが**1970年に沈み**、`ORDER BY created_at DESC` から消える
- `decision = "approve"`（69件）が正本語彙（`approved`）違反
- `decision_by = "pc_settings_ui"`（12件）が正本語彙（`human` / `policy_engine` / `timeout`）違反
  - 影響: 「人間が承認した件数」に SQL で答えられない（正しい実測値は **11件**、自動許可が58件）

**原因（コードで特定済み）**:
- `storage/models.py` の `AuditLog.created_at` が `int(time.time())`（秒）
- `api_agent_bridge.py` が `local_sync_server` の秒値をそのまま渡している
- `api_devices.py` が `decision="approved"` / `decision_by=actor`（IPや `pc_settings_ui`）を書いている

**⚠️ 最大の罠**: `tests/test_audit_logger.py` に**誤った秒単位が焼き込まれている**ため、TDDでは検出できない。
**先に `tests/test_db_invariants.py`（不変条件テスト）を Red で書くこと**から始める。

**手順**:
1. Red: 単位・語彙の不変条件テストを追加（`approval_audit_logs` の created_at がミリ秒であること / decision が正本語彙であること）
2. `storage/models.py` を `int(time.time() * 1000)` に修正
3. `api_devices.py` の `decision` / `decision_by` を正本語彙へ修正
4. **既存81行の移行SQL**を用意（秒→ミリ秒の換算、`approve`→`approved`）
5. 全回帰 `pytest tests/ -q` で ALL GREEN を確認（Verifier: `agent-tester` を実起動）

## 2. 【P1】Google予定の重複（TODO手帳 ID 29）

**症状（実測済み）**: `events.google_event_id` が重複し、**同一予定が最大9個**存在する
（例: `..._R20260817T090000@google.com` が9件 / `33qsnkoks2dvevsjj76dd4cbpv@google.com` が8件）

**原因**: Google/ICS 取り込みが**冪等でない**（`connection.py` の `events` に `google_event_id` の UNIQUE 制約が無い）

**手順**:
1. Red: 「同じ `google_event_id` を2回取り込んでも1件のまま」を検証するテスト
2. 取り込み側（`ics_tools.py` / `google_workspace_tools.py` / `calendar_repo.py`）を UPSERT 化
3. 既存の重複行の統合（**ボスの承認を得てから**実行。データ削除を伴うため）
4. `events` に UNIQUE インデックスを追加（移行手順つき）

---

## 3. モデル提供が変わったときの運用（定期）

```powershell
# 1) 実在モデル一覧を取得（OpenCode の models ツール / またはキャッシュ）して JSON 化
# 2) ドリフト検査
& "C:\Users\bonob\.gemini\tools\jev_router\.venv\Scripts\python.exe" `
  "C:\Users\bonob\.gemini\tools\jev_router\model_catalog.py" --check --live-json <一覧.json>
# 3) 差分に応じて model_policy.json に1行追記（コード変更は不要）
```

---

## 4. 規約・注意（本セッションで確定したもの）
- **モデル選択**: サブエージェント起動前に `jev_select_models` → `subagent` の `model` 引数へ。**承認帯（≥$1.0/M出力）はスマホ承認必須**
- **Jev Guard**: Hard ACL が `allow` の安全コマンドでは**呼ばない**（摩擦の是正 / A案）
- **プラグイン**: `@opencode/plugin` は import しない（実在しない）。素のオブジェクトを default export する
- **エージェント定義**: `.opencode/agents/*.md` は自動生成物。正本は `.agents/agents/*.md` → `tools/sync_opencode_agents.py` で再同期
- **完了時**: `notify_task_completed(agent_name="OpenCode")` で Desk Pet を歓喜させる

## 5. 完了報告の形式
作業完了時は、必ず以下を報告すること:
- 起動したサブエージェントID（sessionID）と実行結果
- 全回帰テストの合否（`pytest tests/ -q` の最終行）
- `docs/learning-memos/学習メモ_<日付>.md` への追記（**上書き禁止**）
