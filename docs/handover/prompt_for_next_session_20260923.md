# 🚀 次セッション再開プロンプト（2026-09-23 以降 / OpenCode 用）

- **作成日時**: 2026-09-22 23:20（session-wrap-up）
- **前セッション**: 2026-09-22 Part 4/5（🛡️ P0×3 ゼロトラスト封鎖 = 手帳 ID 39・40・41）
- **正本**: `active_context.md`（現在地）／`docs/specs/機能ロードマップ.md` §13.18-12（P0×4）／`docs/specs/DESIGN_SPEC.md` §10・§10.2（設計不変条件）
- **学習資産**: `docs/learning-memos/学習メモ_20260922.md`（Part 3）／`docs/explainers/eli5_20260922_zero_trust_p0_sweep_loopback_and_shlex.html`

---

## 1. 現在の状態（結論）

| 項目 | 状態 |
|:---|:---|
| P0×4（レビュー確定の最優先セキュリティ） | ✅ P0-1（ID 39）／✅ P0-2（ID 40）／✅ P0-3（ID 41）／⬜ **P0-4（ID 42）** |
| 全回帰テスト | **833 passed / 4 skipped / 229 subtests**（P0-2・P0-3 の追加テスト込み） |
| バージョン | `version.py` = **1.1.7**（PWA キャッシュバス=1.1.7 に統一済み） |
| 未完了の手動操作 | ①Git セーブポイント（コミット）②ネオ秘書くんアプリ再起動（P0-2/P0-3 反映）③旧スマホ再ペアリング |
| 実行中/未確認 | P0-2 の再査読（quality-reviewer `ses_f36c44318ffeZLImBIr5xHT1rQ`）の結果確認 |

---

## 2. 次セッションの最優先: **P0-4（ID 42）**

**内容**: VAPID 秘密鍵（PKCS#8 PEM）と `neo_secretary.db` が **OneDrive 同期領域**に平文で存在する（レビュー実測: `vapid_keys` 1行・PEM 241文字・`approval_audit_logs` 103行）。
**方針（ADR-2）**: DB（＝鍵材料を含む）は **OS ユーザープロファイル配下の非同期フォルダ**（`app_paths.get_app_root()`）のみに配置し、クラウド同期フォルダを禁止する。

### 着手手順（5分マイクロタスク）
1. `codebase-memory-mcp` で実在確認: `search_graph` / `get_code_snippet` で `storage/vapid_key_repo.py`・`app_paths.py`・`database.py`（DB パス解決）・`storage/connection.py` の実シグネチャを確定（**推測禁止**）。
2. **TDD Red を1本書く**: 「DB パスが `app_paths.get_app_root()` 配下（非 OneDrive）を指す」不変条件テスト（`tests/test_db_location_boundary.py` 新設案）。
3. 実装 → 既存 DB の移行（初回起動時のコピー＋旧パスへの参照排除）→ 全回帰。
4. 検証者（`quality-reviewer` / `mimo-v2.6-pro`）＋ `devils-advocate`（カオス: 移行失敗・同時起動・WAL 残留）。
5. docs 4点セット同期＋ADR-2 の実装状況追記＋手帳 ID 42 完了＋Desk Pet 通知。

> ⚠️ **注意**: OneDrive 配下の既存 DB を削除する前に必ずバックアップ（`build_exe.py` や Git ではなく、`%LOCALAPPDATA%` への移行コピー）。削除は人間承認（AGENTS.md §3・`ask_human_approval`）。

---

## 3. バックログ（手帳 ID 47〜55 / ロードマップ §13.19）

| ID | 優先 | 内容 |
|:---|:---:|:---|
| **52** | **高** | `respond_checked` の自己承認判定を**チャネル資格ベース**へ（Serve 経由スマホの承認不能デグレ ＋ `127.0.0.1`/`::1` 迂回） |
| **55** | **高** | 管理系APIの **loopback 専用リスナ分離**（プロキシ善意への依存を構造的に排除） |
| 47 | 高 | Host ヘッダ許可リスト（400 応答）と `*.ts.net` 以外のプロキシ対応 |
| 48 | 中 | 失効×復帰レースの CAS 化／承認ダイアログの失効復帰警告／403 自動再ペアリング停止 |
| 49 | 低 | 401/403/429 応答ブロックの Deep Module 化（P0-2 と同一コミット推奨） |
| 50 | 高 | ペアリング承認の1クリック横取り防止＋台帳行マッチの属性依存解消（nonce/UUID 化） |
| 51 | 中 | 端末管理UIの暗黙物理削除・DTO deny-list の再帰化・Webhook 認証の Fail-Open |
| 53 | 中 | Serve 経由ペアリング端末の台帳アイデンティティ（ip=127.0.0.1 登録 → cleanup 誤削除・行増殖） |
| 54 | 中 | 外部 Webhook 認証の死にコード解消＋`hmac.compare_digest` 化 |

**その他**: ID 32/33/34/37/43（QRラベル・gemini 400・スキップラベル・`update_task`・dotfiles insight エクスポート）、クイックウィン3件（P1-N1 unsubscribe 所有者検証／`cryptography` requirements 追記／`weather_tools.py:160` の HTTPS 化）、引き算スプリント（ID 35/36/38）。

---

## 4. 本セッションで確立した設計不変条件（壊してはならない）

1. **失効（AD-3）**: `is_revoked = 0` を書けるのは `restore_device()` のみ（ソース凍結テストあり）。認証経路（`sync_device_session`）は**台帳へ書き込まない**。資格情報の束縛は人間承認済みペアリング経路（`reuse_identity=True`）のみ。
2. **マスター鍵**: HTTP で**一切配布しない**（loopback には `loopback_token`＝プロセス内生成・台帳非登録・非ループバックでは 401）。
3. **loopback 信頼の3条件**: ①TCPピア loopback ②中継ヘッダ無し（XFF/Host/Proto・Forwarded・Via・Tailscale-*、**複数出現も Fail-Closed**）③Host が loopback 名（**完全形のみ**・Host 無しは Fail-Closed）。
4. **承認ポリシー**: `shlex` 構造判定。**`commenters=""` 必須**（語中 `#` の読み捨て防止）／**句読点のみのトークン＝演算子ラン**／危険語は非クォートのトークンで判定（引用符内の誤検知＝アラート疲れ防止）。
5. **ペアリング**: 個別トークン発行で `close_pairing()` を即時実行（Single-Use）。

---

## 5. セッション開始手順（コピペ用プロンプト）

```text
session-start を実行してください。active_context.md を読み、前セッション（2026-09-22 Part 4/5）の成果を同期したうえで、
docs/specs/機能ロードマップ.md §13.18-12 の P0-4（ID 42: VAPID秘密鍵＋DBの OneDrive 退避）から TDD で着手してください。
検証者は quality-reviewer（mimo-v2.6-pro）。設計不変条件の正本は docs/specs/DESIGN_SPEC.md §10・§10.2、
学習資産は docs/learning-memos/学習メモ_20260922.md（Part 3）と docs/explainers/eli5_20260922_zero_trust_p0_sweep_loopback_and_shlex.html です。
```

---

## 6. 参考: 本セッションの検証エビデンス（sessionID）

| エージェント | sessionID | 判定 |
|:---|:---|:---|
| 😈 devils-advocate（P0-1 第1ラウンド） | `ses_f372959f3ffeUDEUYLbMQy60N3` | P0×1 検出 → A案で封鎖 |
| 🛡️ quality-reviewer（P0-1） | `ses_f372959e9ffe1qZWa3FW2p8K07` | CHANGES_REQUESTED → 全項目是正 |
| 😈 devils-advocate（P0-1 第2ラウンド / A案再検証） | `ses_f370ece1dffeCZXg3DrgYAVE99` | 条件付きYES → P0-3 を最優先へ |
| 😈 devils-advocate（P0-3 第3ラウンド） | `ses_f36de91aeffe9QWODSXbahJyG2` | 配布構成では RESILIENT → N1〜N4 即時硬化・N5〜N7 起票 |
| 🛡️ quality-reviewer（P0-2） | `ses_f36d84d7effeCG6NXY4T1CSogz` | CHANGES_REQUESTED（P0×2）→ 是正 |
| 🛡️ quality-reviewer（P0-2 再査読） | `ses_f36c44318ffeZLImBIr5xHT1rQ` | 結果確認待ち |
