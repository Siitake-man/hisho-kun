# OpenCode 引き継ぎ正本 (2026-09-28 Part 2): 🏛️ ID 76 Fat Module 分割リファクタ設計書 Sprint （＋承認カード表示回帰 Fix）

- **最終更新**: 2026-09-28 23:35 (🤖 OpenCode)
- **位置づけ**: 本ファイルが本セッションの**詳細正本**（active_context は要点＋ポインタのみ・ID 21 規約）
- **main 起点**: `3593bb3`（OmO v5 資産確定コミット後）
- **セッションID**: `ses_f1825c4f4ffdknLSU6As2wPaU9`（本体）／サブエージェント各IDは §3 参照

---

## 1. エグゼクティブ・サマリ

1. **ID 76 設計書 Sprint 完遂**: `docs/specs/Fatモジュール分割リファクタ設計書_20260928.md` **Rev 2** 策定（local_sync_server.py 2,296行 / ui/settings_window.py 1,930行 の Seam 分割設計）。**独立査読2体（devils-advocate P0×3／quality-reviewer P1×3 等）の全指摘を是正済み**。
2. **承認カード表示回帰 Fix**: プラグイン `hisho-approval-notify` **v1.3.1**（describeRequest の title が双方向・ポーリング両経路で定型文に上書きされていた配線回帰を復元・8編集）。**実機確認は手帳 ID 79（OpenCode 再起動後に要実施）**。
3. **全回帰 964 passed / 4 skipped / 335 subtests** を二重エビデンスで確認（本体＋独立検証 agent-tester）。
4. **起票**: 手帳 ID 79／80／83 ＋ ロードマップ §13.19-36／37／39（※38 は並行セッションの Stitch 機密流出対策が使用・衝突解消済み）。

---

## 2. 成果物（コミット対象）

| 種別 | パス | 状態 |
|:--|:--|:--|
| 🏛️ 設計書 Rev 2 | `docs/specs/Fatモジュール分割リファクタ設計書_20260928.md` | 新規・**ボス承認済み** |
| 📜 ロードマップ同期 | `docs/specs/機能ロードマップ.md` | §13.19-33 完了化／-36・37・39 起票／ヘッダ Rev 49 |
| 💡 ELI5 動く図解 | `docs/explainers/eli5_20260928_fat_module_seam_and_patch_traps.html` | 新規（Seam分割とpatchの罠・3層構造） |
| 📘 学習メモ | `docs/learning-memos/学習メモ_20260928.md` | Part 2 追記 |
| 📋 本ファイル | `docs/handover/20260928_opencode_id76_fat_module_design_sprint.md` | 新規 |

---

## 3. DAG 実行エビデンス（conversationId・AGENTS 2.8 準拠）

| Node | 内容 | セッションID | モデル | 結果 |
|:--|:--|:--|:--|:--|
| N0 | 残務コミット（OmO v5 資産） | — | — | `3593bb3`・機密スキャン CLEAN |
| N1 | local_sync_server 構造解析 | `ses_f1813e42effe6MqAiZXRyQamfC` | glm-5.3-flash | ✅ Seam候補S1〜S6・依存・テスト影響27ファイル |
| N2 | settings_window 構造解析 | `ses_f180f5a26ffe6fj3k4mvfY52TF` | glm-5.3-flash | ✅ inventory・結線31件検証・**`_render_mcp_servers` 未定義参照の発見** |
| N3 | 先行事例＆テスト影響マップ | `ses_f1813e417ffeXgjuqjG9KCg75Y` | glm-5.3-flash | ✅ 先行原則15項・証跡訂正（964出典=main `c9d08c6`） |
| N4 | 設計書執筆 | （初回起動はプロンプト欠陥で成果なし `ses_f1805818bffe0yH4onksaf88hb`） | — | ✅ **本体執筆で代替**（逸脱記録・Rev 2 まで是正済み） |
| N5 | Devils-Advocate 査読 | `ses_f17fef31dffeVV4hyMNJKnsS7p` | kimi-k3（承認帯・スマホ承認済） | ✅ CHANGES_REQUESTED P0×3 → 全件是正 |
| N6 | 品質査読 | `ses_f17fef316ffeLToKv9GiaAmi5a` | kimi-k3（同上） | ✅ CHANGES_REQUESTED P1×3 → 全件是正（格付けB+相当） |
| N8 | 最終回帰（独立検証） | `ses_f17a16c07ffe6nKNGLWX5gw9Gs` | cline-pass glm-5.3-flash | ✅ **964/4/335・exit 0**（GO リミット回避の3度目で成立） |

**GO リミット事象**: opencode-go が当日利用上限に到達し、N8 の agent-tester 起動が2回失敗（`Go usage limit exceeded`）→ **cline-pass プロバイダへ Jev 再選定して回避**（実績: ALL GREEN）。恒久運用知見として知識の宝庫候補に含めた。

---

## 4. 設計書 Rev 2 の是正ハイライト（査読→対策）

| 指摘 | 内容 | 対策（Rev 2） |
|:--|:--|:--|
| DA-01/02/03（P0） | **patch ターゲットの無効化**（get_bridge_hub 10箇所・TOKEN_FILE 3箇所・ASSETS_DIR 4箇所が vacuous green 化） | **§6.3.1 patch ターゲット移行表を新設**・Facade の限界条件を §4.3 に明文化・F10 完了条件に8ファイル全緑 |
| Q-1（P1） | S1（約600行）が自基準（200〜400行）違反 | **S1a/S1b/S1c へ三分割**（153/約300/約150行） |
| Q-2/DA-04/05（P1） | AGENT_ONLY_PATHS「撤去」の RCE 遮断欠落・pytest 非収集 | §5.1 Route Record 仕様（`auth_level="loopback"` へ**移管**・無ラッパ直接参照・非ループバック403の Red テスト新設） |
| Q-3（P1） | 知識の宝庫 ID 11/13/19 の不変条件が F7 未配線 | F7b/F7c 完了条件へ個別テスト指定（一字一句不変） |
| Q-4/DA-12（P2） | ToolsTab 約600行・F8 抱き合わせ | T5a/T5b/T5c 再分割・F8a/F8b 分離 |
| 他 P2/P3 多数 | 算術不整合・行番号1行ズレ・件数陳腐化・順序矛盾 等 | 全件是正（詳細は設計書 §改訂履歴） |

---

## 5. 承認カード表示回帰 Fix（プラグイン v1.3.1・中央環境）

- **真因**: `describeRequest()` が組み立てる「⚠️ 承認待ち（OpenCode）: <コマンド先頭80字>」title（ID 26 規約）が、**双方向経路 `runBidirectionalApproval`（index.ts:366）とポーリング経路 `scanPending`（同:458）で既定の定型文に上書き**。加えて PWA 質問シート（pet_ui.js:588）が details を描画しないため、見出し・詳細の双方からコマンドが消えていた。
- **修正**: 両経路へ title を伝送（8編集）＋ resources 空時は action へフォールバック。セーブポイント `index_v1.3.bak.ts`・bun 構文検査 `SYNTAX_OK`。
- **残作業（手帳 ID 79）**: **OpenCode 再起動 → 外部パス書き込み等で ask 誘発 → カード見出し/Push冒頭にコマンドが出ることを実機確認**。
- **将来改善（手帳 ID 80・§13.19-37）**: PC 側解決時にスマホの保留カードを自動解除する「保留中 ask_input 取消 API」。

---

## 6. 次アクション（次回再開時）

1. 🏗️ **ID 76 実装フェーズ（F0〜F10）の別スプリント起票**（設計書 §8・推定3〜4セッション。ボス判断事項2件: 並行性リスク4点の別チケット化／フリーズ是正の別フェーズ化 ← 設計書の既定推奨どおりで可）
2. 📱 **ID 79 実機確認**（OpenCode 再起動後・承認カード見出し）
3. 🧾 **残留同期（wrap-up 残）**: DESIGN_SPEC への設計書ポインタ＋§13.7「database.py Phase 2 次回着手予定・1,960行」の**実態乖離是正**（設計書 附属④）
4. 🩹 **ID 77（Jules 実行待ち）**: 例外握り潰し是正＋**追記2箇所**（settings_window.py:1882-1883／`_check_auth` 内3箇所の搬送除外・設計書 §9⑤⑥）
5. 🧪 **ID 83**: test_task_lists tearDown の OneDrive flake 恒久対策（Jules 指示書 追記済み）
6. 📊 通常バックログ: ID 80／65／64／78／61

---

## 7. 注意事項

- **並行セッション衝突**: 本日中に別 OpenCode セッションが「Stitch MCP 移植＋AI Dotfiles 平文シークレット流出対策（§13.19-38・手帳 ID 81/82）」を実施済み。**§13.19-38 は両者で番号衝突したため本セッション分を §13.19-39 へ改番**。共有ボード（active_context / ロードマップ）編集時は最新を確認すること。
- **AI Dotfiles の push コマンドは §13.19-38 の止血（mcp_config.json 除外＋git rm --cached）完了を確認してから実行**。
- 未コミット（本セッション分）: `docs/specs/Fatモジュール分割リファクタ設計書_20260928.md`（新規）／`docs/specs/機能ロードマップ.md`（変更）。
