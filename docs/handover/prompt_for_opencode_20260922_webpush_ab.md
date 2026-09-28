# セッション引き継ぎプロンプト — 手順A→B 実行用（2026-09-22）

- **更新日時**: 2026-09-22
- **前セッション**: `ses_f405b8063ffeExNXBu9pabaNox`（OpenCode v2.0.11 / ネオ秘書くん）
- **引き継ぎ理由**: コンテキスト圧迫のため新セッションへ移行。
- **本セッションで決まったこと**: スマホ通知の課題は **A（即時検証）→ B（Web Push 構造解決）** の順で進める。

---

## 0. 【最優先】セーブポイント（未コミット12ファイル）

新セッションの**最初の1コマンド**として、以下をボスが手動実行すること（AIは自律実行禁止）。

```powershell
cd "C:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん"
git add tests/ ui/settings_window.py docs/handover/prompt_for_opencode_20260922_webpush_ab.md
git commit -m "test: add japanese google-style docstrings to 16 tests; fix hardcoded port literal; add ab handover"
git push
python C:\Users\bonob\.gemini\sync_ai_dotfiles.py
cd "$HOME/.ai_dotfiles"; git add -A; git commit -m "chore: backup ai dotfiles"; git push
```

> 未コミット対象 = `tests/` 11ファイル（Docstring 16件追加）+ `ui/settings_window.py`（ポートリテラル1行修正）。
> `docs/specs/DESIGN_SPEC.md` / `docs/specs/機能ロードマップ.md` は Antigravity のコミット `60027d9` で**取得済み**（再対象外）。

---

## 1. 完了済み（再実装・再調査しないこと）

### ① 通知経路の診断（完了・原因確定）
- **PC側（Plugin → 秘書くん）は正常**: `effect:"ask"` 検知 → 16ms 後 `HTTP 200 {"status":"queued","request_id":"req_c61c2b8a"}`。
- **スマホ側は受信不能だった**: 通知発火時も `devices.last_seen` = **901.7分前（未接続）**。
- **結論**: 壊れているのではなく、**PWAが開いている間の2秒ポーリングしか持たない構造的限界**。画面オフ・ブラウザ閉・スリープ中は原理的に届かない。
- 証跡: `%TEMP%\hisho-notify.log`（プラグイン診断の全履歴）。

### ② Web Push の起票（完了・ドキュメント同期済み）
- 秘書くん手帳 **TODO ID: 30**（priority: high / タイトル: 【宿題】スマホ通知を Web Push API へ移行…）。
- `docs/specs/機能ロードマップ.md` **§13.19 第4項**（作業ツリー L754 付近）にエビデンス付きで記載済み。コミット `60027d9` で確定。

### ③ テスト整理（完了・ALL GREEN）
- **元提案3点のうち2点を撤回**（自らの監査が過検出だったため）:
  - 重複テスト名4件 → **不要**。AST実装数 / スコープ付き一意ID / pytest実収集数が **763 = 763 = 763** で一致、同一スコープ衝突0件・未収集0件。全件が別クラススコープ。
  - 自明アサーション18件 → **不要**。全件 `assert_called_once_with(<literal>)` でモック委譲契約の正当な検証。
- **代わりに本物を2件投入**:
  1. Docstring未付与 **16件**（11ファイル）→ 全件修復（+63行 / 削除0 / ロジック変更0）。
  2. `ui/settings_window.py:497` の `8765` ベタ書き（設定画面ガイド）→ `f"...{SERVER_PORT}..."` に置換。
     - 失敗していた `test_production_code_has_no_default_port_literal` は**意図的なRed**（Docstringに「設定画面のガイド」が対象として明記）。放置するとポート変更時に承認通知が静かに全滅する。
- **独立検証（`agent-tester`, `ses_f394ad94affeZQjXAFG5X3VEzW`）→ ALL GREEN**。
  - `761 passed, 2 skipped` / failed 0、出力等価性 `trailing_brace_ok=True`、`ui/` の `8765` 残存0件。
- **合意済み（非推奨）**: `tests/test_device_ui_seam.py`（43テスト/718行）の分割は**しない**（破綻・重複なし。引き算の美学）。

---

## 2. Step A（30秒・新セッションの最初に実行）

**目的**: Plugin→PC→スマホ の**受信経路が生きていること**を目で確定させる（B着手前の前提確認）。

1. ボスが**スマホで PWA（卓上リモコン）を開いたまま**にする（2秒ポーリング中である必要がある）。
2. AI が **権限承認（`effect: "ask"`）が必要なシェルを1回実行**する → プラグインが発火。
   - 例: `& ".\venv\Scripts\python.exe" -c "import platform, uuid; print(platform.python_version()); print(uuid.uuid4().hex[:8])"`（allowlist 外なので ask 判定になる）
   - ※ 実行が**ブロックして承認ダイアログが出れば成功**＝本物の待ち状態の再現。
3. 確認: スマホに通知が届くこと / `%TEMP%\hisho-notify.log` 末尾に `HTTP 200 ... "queued"` が出ること。
4. **届かなかった場合**: 再度 `SELECT device_name, last_seen FROM devices` で `last_seen` を確認。**1〜2分以内でなければ PWA が開いていない**のが原因（回線・Plugin の問題ではない）。

---

## 3. Step B（Web Push API 導入 / 本命）

**背景**: A は運用でしのぐだけで、「席を外している＝PWAを開いていない」という**最も気づくべき場面**で届かない。コアバリュー（止まらない）の成立には B が必須。

**要件（方針）**:
1. **Service Worker + VAPID** で Web Push を導入し、PWA/ブラウザを閉じていても **OS 標準通知**として届ける。
2. PWA 起動時の**「取りこぼした通知のまとめ表示（未読バッジ）」**を併設（ポーリングの取りこぼし緩和）。
3. 対象イベント: `ask_input`（承認待ち） / `task_completed` / 予定リマインド。
4. **observe-only の原則を維持**: 通知は権限判定に一切介入しない（既存プラグイン `hisho-approval-notify` の設計思想を踏襲）。

**着手前ルール**:
- 実装コスト「中」のため、`ask_human_approval` でボス承認（Jev スコア付与は任意）。
- **セーブポイント（§0 の git commit）完了後に**着手すること。
- 規約: 厳格な型ヒント / 日本語 Google Style Docstring / TDD（先に失敗するテスト）/ 独立検証者（`agent-tester` または `quality-reviewer`）で ALL GREEN を確認してから完了宣言。
- 完了時は `notify_task_completed(agent_name="OpenCode", ...)`。

**参照ファイル**:
- `C:\Users\bonob\.config\opencode\plugins\hisho-approval-notify\index.ts`（現行ポーリング連携のPlugin / 保存でホットリロード）
- `docs/specs/機能ロードマップ.md` §13.19 第4項（起票内容）
- 秘書くん手帳 TODO ID: 30
- `docs/specs/DESIGN_SPEC.md` §21 / §23（アーキテクチャ）

---

## 4. このセッションで踏んだ罠（新セッションで繰り返さない）

1. **ロードマップは Antigravity と並行編集される**: 編集前に必ず**再読**する。前回はヘッダーと本文のインデントが食い違って2回編集失敗した（`3.` は2スペース、`-` は5スペース）。
2. **BOM (U+FEFF) 付きテスト2件**（`test_easter_egg_engine.py` / `test_qr_dialog.py`）は `ast.parse` が失敗する → **必ず `encoding="utf-8-sig"`** で読む。pytest 自体は問題なし。
3. **PowerShell の stdout は cp932**: `——` 等の特殊文字を print すると `UnicodeEncodeError` で落ちる。監査スクリプトの出力は ASCII 記号に留める。
4. **テスト監**テスト監査は1ヒューリスティックで告発しない**: 「重複名＝死にテスト」「引数がリテラル＝自明」と即断して2件誤検出した。**別々の原理で3計測が一致した時に初めて消去法で確信する**（AST数 / スコープ付き一意ID / pytest実収集数）。
5. **MCP サーバーのコード変更は `opencode service restart` が必要**（起動時にロードするため）。**プラグインは保存でホットリロード**（1リクエスト分スキルが空になるが自己回復）。
   - `& "C:\Users\bonob\AppData\Roaming\ai.opencode.desktop\cli\2.0.12\opencode-cli.exe" service restart`
  （注: 正しいパスは `%APPDATA%\Roaming\...` 配下であり `AppData\Local\Roaming\...` は存在しない。バージョン番号 `2.0.12` は `%APPDATA%\ai.opencode.desktop\cli\` 配下の最新ディレクトリを確認して置換すること。2026-09-22 修正）
6. **Git / ビルド / サーバー起動は AI が自律実行しない**（AGENTS.md §3）。PowerShell コマンドを提示してボスに手動実行させる。

---

## 5. 残っている軽微タスク（優先度低）

- P2: `tests/test_webhook_integration.py:31,47,66,85` の既存Docstring 4件が文末句点（`。`）なし。HEAD から存在。テスト合否に影響ゼロ、**このファイルに次に触れる時に**統一する。
- `test_device_ui_seam.py` の分割: **非推奨（合意済み・実施しない）**。
