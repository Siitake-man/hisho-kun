<!--
  Cline 引き継ぎ指示書 (prompt_for_cline_20260903.md)
  更新日時: 2026-09-02
  更新内容: セキュリティ＆堅牢化スプリント完了 (リクエストDTO化/自己治癒watchdog/CORS是正/機密監査CLEAN)。テスト基準 277件
-->

# 🤖 Cline 引き継ぎ指示書 (2026-09-03 セッション用)

## 📌 現在のステータス
- **2026-09-02 スプリント成果** (全てTDD Red→Green):
  - タスクA: 無応答200 → 明示エラー応答化 (api_tasks 7 + api_agent_bridge 3 ガード)
  - Block1: P2①第三段 リクエストDTO化 (`sync_dtos.parse_request` + 5 DTO / api_tasks 7アクション)
  - Block2: 自己治癒watchdog (`LocalSyncServer` 周期プローブ→同ポート再バインド)
  - Block3: CORS `*` 廃止→同一オリジン限定 (`_set_cors_headers`) ＋ 脅威モデリング (`docs/security_assessment_20260902.md`)
  - Block4: git履歴機密監査 **CLEAN** (`tools/scan_git_secrets.py` 恒久ゲートツール化)
- **テスト基準**: 全 **277テスト OK** (基準線。作業後はこの数以上で全パス必須)
- **コミット**: 2026-09-02 分はボス確認後の手動コミット待ち

## 🎯 次回タスク: **Sprint A** (戦略grilling確定計画の第1弾)
> 全体計画: **Sprint A**(今回) → Sprint B(デバイス台帳+watchdog分離) → Sprint C(CI+公開踏切)。俯瞰図: docs/architecture/federation-20260902.html

1. **【第1】400化構造改革**: `ApiContext.write_json` を**遅延ヘッダー送出**方式に改修(初回書き込み時に自動でヘッダー送出・`status_code` 引数追加)。local_sync_server.do_POST の前置き200送出(約L1144)を廃止 → 既存ハンドラはほぼ無変更。characterization 277件がリグレッション保险
2. **【第2】レートリミット (方式b)**: 「401失敗をIP別にカウント(1分10回)→ 5分間締め出し」のメモリ上テーブル。超過時は **429 + Retry-After** を返す(第1の土台が必要)
3. **【第3】重複ガードのヘルパー抽出**: api_tasks.py の `invalid request body` / `missing parameter: <param>` 応答 ×7 重複 → `_respond_invalid_body(ctx, action)` / `_respond_missing_param(ctx, name)` ヘルパー (Fowler Duplicated Code 解消)
4. **TDD厳守**: 各ステップで失敗するテストを先に書く。完了条件: 全テスト(277+)全パス + py_compile + 秘書君通知

## 📌 Sprint B/C 予告 (Sprint A 完了後)
- **Sprint B**: デバイス台帳 (devices テーブル: 個別トークン・token_hash保存・個別失効・last_seen) / watchdog を server_watchdog.py へ分離 + 連続2回失敗ヒステリシス + バックオフ
- **Sprint C**: CI (GitHub Actions: unittest + tools/scan_git_secrets.py ゲート) / README・LICENSE / 機密監査最終実行 → **公開踏切**
- **Non-Goals (やらない宣言・2026-09-02 grilling確定)**: TLS実装(v2ネイティブ・ピンニングへ道を譲る) / 監査ログDB永続化 / SSE・WebSocket強化 / 多言語・マルチプラットフォーム / Docker・K8s(本アプリに不適合) / 演出追加(Backlog P3)
- **別プロジェクト枠 (秘書くんリポジトリには組み込まない)**: お尋ね者(独立アプリ・Genspark設計済み → 新規リポ `otazunemono` 化) / EmoLog v2 統合(Firebase 既存稼働中。「統合契約の設計文書」から着手し、実装前に emolog-sync の該当コードを精査すること)
- **【残課題】Jules PR #1 処理** (分岐点 bfdffeb のためマージすると P2①②③ が巻き戻る → Close か再PR依頼)

## ⚠️ 注意事項 (環境地雷・教訓)
- **UTF-8ファイルの読み書きは必ず Python io.open で encoding=utf-8** (PowerShell 5.1 は日本語ファイルを破壊する)
- **run_commands の複数コマンドは並行実行され得る** → patch→test は別コールで逐次実行
- **PowerShell `Select-String` は大小文字区別なし** → セキュリティスキャンは `-CaseSensitive` か tools/scan_git_secrets.py を使用
- **長パイプラインはシェル統合で出力不可** → 監査系はスクリプト化
- **api_tasks.py のハンドラ契約**: `handler(ctx)->bool` (True=応答済み)。壊れたJSONは `"invalid request body"` / パラメータ欠落は `"missing parameter: <param>"` エラーJSON。リクエストパースは `sync_dtos.parse_request(ctx.body, DTO)` を使用 (生 json.loads に戻さないこと)
- **CORS**: `_set_cors_headers` は**許可ヘッダー発行ゼロ** (no-op)。`*` も Origin エコーも禁止 (DNSリバインディング迂回対策・deep-audit P1是正済み)
- **メソッド実在は search_graph / 実コードで確認** (推測禁止)

## 🛠️ 検証コマンド (PowerShell)
```powershell
# 全テスト実行 (基準: 277件全パス)
& .\venv\Scripts\python.exe -m unittest discover -s tests -p test_*.py | Select-Object -Last 4

# 構文検証
& .\venv\Scripts\python.exe -m py_compile <対象ファイル>

# 機密監査ゲート
& .\venv\Scripts\python.exe tools\scan_git_secrets.py
```

## 📚 参照ドキュメント
- active_context.md (2026-09-02 スプリント+戦略grilling記録)
- docs/security_assessment_20260902.md (脅威モデリング・残存リスク R1-R5)
- docs/code_review_report_20260902_sprint_deep_audit.md (deep-audit+冷徹評価・P1是正記録)
- docs/architecture/federation-20260902.html (3アプリ連携俯瞰図)
- docs/learning-memos/学習メモ_20260902.md (本日の教訓)
- docs/handover/archive/ (前回までの引き継ぎ書)
- AGENTS.md (開発規約・4大弱み克服)
