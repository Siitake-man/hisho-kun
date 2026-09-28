# OpenCode セッション引き継ぎ — 通知障害修理 ＋ PR #8 フォローアップ（2026-09-24 → 09-25）

**作成**: 2026-09-25 01:00 / OpenCode（🤖 [Agent: task-planner → python-architect/pixel-frontend-designer/agent-tester/quality-reviewer]）
**経緯**: `active_context.md` は Antigravity 側と並行編集となり上書きが発生したため、本記録を正本として保全する（active_context には要点のみ再追記）。

---

## 1. 🔧 通知障害の恒久修理（P0-4 派生インシデント第2弾・実機確認済み）

**真因**: 2026-09-23 18:01 のデータ境界移行（P0-4）で `.sync_token` が `%LOCALAPPDATA%\NeoHisho\` へ移動した際、**リポジトリ外の消費者3箇所が旧パス参照のまま**残った。

| # | ファイル | 症状（実測エビデンス） |
|:--|:--|:--|
| 1 | `~/.config/opencode/plugins/hisho-approval-notify/index.ts` | ENOENT（`%TEMP%\hisho-notify.log` 09-23 18:04〜） |
| 2 | `~/.gemini/tools/jev_router/tool_guard_hook.py` | 空トークン→401（`hook_debug.log` 09-24 22:29） |
| 3 | `~/.gemini/tools/jev_router/jev_mcp_server.py` | `~/.neo_secretary/data/` の古代パス |

**対処**: 3ファイルの解決順を「`NEO_HISHO_DATA_DIR` → `%LOCALAPPDATA%\NeoHisho` → 旧配置（互換）」へ修正。**実機テスト通知のスマホ着信で復旧実証**。AI Dotfiles へ保全・push 済み（`4a50112`）。
**恒久ルール**: 知識の宝庫 ID 19／codebase-memory ADR（DECISIONS 2026-09-24）。

## 2. ✅ PR #8（Jules夜間作業: ID 35/57/43）査読 → マージ（`0f083ae`）→ 回帰修正

- 🔴 回帰: `web_pet/pet.js` の `neolang:changed` モーダル再描画リスナーが撤去ブロックに巻き込まれ削除 → **+15行で復元**（git blob `4fa3b02` とバイト一致検証・node vm 発火テスト4/4）
- 🟠 ID 43 は**別ツール新設のみで実運用ツール未修理**（DRギャップ残存）→ 下記 3. で実修理
- 🟡 残骸一掃は ID 38 へ切り出し → 下記 4.

## 3. 🩹 ID 43 実修理（DRギャップ閉塞）

`~/.gemini/sync_ai_dotfiles.py` の `export_knowledge_vault()` の DB 参照をデータ境界追随へ（正本 `app_paths.get_db_path()` → env/`%LOCALAPPDATA%` → 旧配置）。py_compile・解決単体動作を実測。
**✅ 残作業**: ボスによる `python C:\Users\bonob\.gemini\sync_ai_dotfiles.py` 再実行 → `~/.ai_dotfiles/neo_secretary/user_insights.sql` 復活確認 → AI Dotfiles commit/push。

## 4. ✂️ ID 38（Whisper 分）実施

`neo_hiso.spec` hiddenimports 撤去／`requirements_whisper.txt` 削除（ボス承認）／`character_manager.py`×2・`main.py` docstring／JP+EN ガイド（`cheatsheet_05`・`CHEAT_SHEETS.html`）・`architecture.html`・機械可読 JSON・`docs/temp/generate_guide_html.py`（再混入防止）。

## 5. 📊 独立検証（2体）

- **V1 `agent-tester`（qwen3.8-flash）**: 全回帰 **919 passed / 2 skipped / 242 subtests**（ベースライン一致）＋機械検証6項目 ALL GREEN。
- **V2 `quality-reviewer`（mimo-v2.6-pro・ボス指示でKimi K3→MiMo）**: **CHANGES_REQUESTED → P1×2 即日全是正**
  - P1-1 英語版ガイドの撤去漏れ → JP と同文言へ更新
  - P1-2 pet.js 変更の版数未バンプ → **v1.1.9**（`version.py`／`version.js`／`index.html` の `?v=` 全18箇所）
  - P2 是正: `main.py` docstring/ラベル（💬）・メタ整合・残骸（JSON×2・alt・Voice Edition 表記）・**承認/質問シート保護ガード**（`pet.js` の `if (window.currentApprovalRequest) return;`＋`pet_ui.js` の `_currentOpenModalName` リセット）
  - **是正後の全回帰 919 passed を再実測**
- 残務: 手帳 **ID 62** ／ロードマップ §13.19-28（版数バンプ規約テスト・import硬化・絶対パス排除・表記統一・注記配置・PyInstaller実ビルド確認・画像目視）

## 6. 🗓 グラフエンジニアリング成果物

`C:\Users\bonob\.opencode\plan\implementation_plan.md`（DAG＋工程別マトリクス＋Jev エビデンス）。
Jev route: primary=python-architect / secondary=agent-tester ／ models: glm-5.3-flash・qwen3.8-flash・mimo-v2.6-pro（すべて auto 帯）。

## 7. ⚠️ 申し送り（Antigravity 側へ）

1. **`active_context.md` の並行編集**: 本記録をもって同期。Antigravity が再編集する際は「Part 11（OpenCode: 通知修理＋PR#8仕上げ）」ブロックを消さないこと（本ファイル参照リンクを維持）。
2. **`tools/jev_triage_extractor.py` の未コミット変更は Antigravity 側の作業**（OpenCode のコミット対象外）。
3. **通知系3ファイルのトークン解決を旧パスへ戻さない**（AI Dotfiles に保全済み・`4a50112`）。
4. **OpenCode プラグイン v1.2 は OpenCode 再起動後に有効**（ボス再起動済み）。
