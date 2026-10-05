# Antigravity 引き継ぎ指示書 (2026-10-05 / Cline 4スキル統合レビューより)

- **作成日時**: 2026-10-05
- **作成者**: Cline（holistic-code-review × ruthless-code-evaluation × deep-audit × codebase-design 統合診断）
- **診断レポート正本**: `docs/code_review_report_20261005.md`
- **検証エビデンス**: `docs/temp/pytest_run_20261005.log`（1025 passed / **2 failed** / 4 skipped）

---

## 🎯 ミッション（結論）

**本日実装した HTTP Framing 強化（未コミット）のテスト RED 2 件を GREEN 化し、全回帰 ALL GREEN を確認してからコミットして収束させること。**
その後、余力があれば P1 リファクタ 1 件（`migrate_legacy_data` 分割）に着手する。

---

## 🔴 最優先タスク P0: テスト RED 2 件の修正（未コミットWIPの収束）

### 背景
- `git status`: `local_sync_server.py`（M）＋ `tests/test_server_http_framing.py`（未追跡）が未コミット。
- 本日「ChatGPTレビュー & 悪魔の代弁者監査対応」として do_POST に HTTP Framing 5 ガード（Transfer-Encoding 検査 / Content-Length 重複検査 / 厳格パース / Slowloris / Truncated Body 検証）を実装済み。
- しかし全回帰で 2 件 RED のまま。**セキュリティ防御コードを RED 放置・未コミットのままにしないこと**（TDD 規律 AGENTS §2.9）。

### P0-1: `tests/test_server_seam_characterization.py::test_non_loopback_agent_ask_forbidden_contract`
- **症状**: `AttributeError: 'dict' object has no attribute 'get_all'`（`local_sync_server.py:661`）
- **真因**: テスト側の欠陥。`handler.headers` に素の `dict` をモック注入しているが、本番は `email.message.Message` の `get_all()` を使う。**本番コードは正しい。テストのモックを直すこと。**
- **修正**: 同ファイル 514 行目および 525 行目の `patch.object` 内 dict を、`email.message.Message` 実物（または `get_all` を実装したモック）へ置換。
- **完了条件**: `venv\Scripts\python.exe -m pytest tests/test_server_seam_characterization.py -q` が ALL GREEN。

### P0-2: `tests/test_server_http_framing.py::test_truncated_body_rejected_with_400`
- **症状**: `AssertionError: b'400 Bad Request' not found in b''` — 切断本文に対し 400 ではなく無応答切断。
- **仮説**: `local_sync_server.py:700` の `self.rfile.read(content_length)` が Windows ソケットの EOF/RST セマンティクスで `ConnectionError` 経路（706-709 行）へ落ち、ガード 5（712-718 行の 400 送出）に未到達。
- **手順**:
  1. まず再現ログで経路確定（「クライアントソケット切断」の debug ログが出るか）。
  2. EOF 短読みと接続異常を区別し、短読み時はガード 5 の 400 が送出されるよう実装修正。
  3. あるいは「切断許容」を契約とする判断なら、テストの期待値を修正し設計書へ明記。**契約と実装の不一致の放置は禁止**。
- **完了条件**: `venv\Scripts\python.exe -m pytest tests/test_server_http_framing.py -q` が ALL GREEN。

### P0 収束条件（両方共通）
1. 上記 2 テストが GREEN。
2. **全回帰 `venv\Scripts\python.exe -m pytest tests -q` が 0 failed**（エビデンスログを `docs/temp/` へ保存）。
3. `git add` ＋ コミット（WIP 解消）。コミットメッセージ例: `[Security] HTTP Framing 5ガード実装＋回帰テスト収束 (P0: Request Smuggling / Slowloris / Truncated Body 防御)`。

---

## 🟡 次点タスク P1（余力があれば・別コミットで）

### P1-1: `app_paths.migrate_legacy_data` の分割（認知複雑度 102 → 目標 30 以下）
- codebase-memory-mcp 実測で全コードベース最大の複雑度。データ移行は最高リスク処理のため優先分割。
- DB 退避 / トークン退避 / バックアップ退避の 3 サブ関数へ抽出。既存 Seam テストを Green 維持すること。

### P1-3: `api_agent_bridge.py` の `hub._lock` 直操作解消
- Bridge Hub 側へ公開メソッド（例 `resolve_and_archive`）を生やし、private メンバ露出を閉じる。

### P1-4: `ui/settings_tabs/` 4 ファイルの dispatch フォールバック共通化
- `google_section.py:71` / `ical_section.py:70` / `llm_brain_tab.py:120` / `tools_tab.py:116` の同形三連パターンを mixin/基底クラスの `post_ui()` へ集約。

---

## 禁止事項・注意
- P0 修正中に無関係なリファクタを混入させないこと（差分最小化）。
- `print` → `logging` 置換などの横断変更は本タスクのスコープ外。
- 作業完了時は `notify_task_completed` でペットを歓喜させること。

---

## 参照
- 診断レポート: `docs/code_review_report_20261005.md`（P2/P3 改善提案・4大弱点監査を含む全量）
- ロードマップ: `docs/specs/機能ロードマップ.md` §13.19 項番 46-47（本タスクと同期起票済み）
