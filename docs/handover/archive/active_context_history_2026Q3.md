# active_context 履歴アーカイブ (〜2026-09-22 Part 3)

**作成**: 2026-09-23 引き算スプリント（active_context.md のトークン肥大を2段階で分離: 294KB → 約20KB）
**位置づけ**: 2026-09-22 Part 3 以前の完了アクション履歴（必要時のみ参照）。
現在地・Next Actions・直近セッションは `active_context.md` を参照。

---

- **🧠 本日完了アクション (2026-09-22 セッション Part 3: 手順A検証 ＆ Plugin v1.1 ＆ Web Push 実装)**:
  - ✅ **Step A: スマホ通知の受信経路検証（30秒手順）**:
    - allowlist外シェルを1回発火 → `effect:"ask"` 検知 11ms 後 `HTTP 200 queued (req_b142cf14)` → スマホ受信を確認。PC→サーバ→PWA経路は全生きていることを確定。
  - 📲 **Plugin v1.1: `hisho-approval-notify` に question 回答待ち通知を追加 (`~/.config/opencode/plugins/hisho-approval-notify/index.ts`)**:
    1. **課題**: AI が `question` ツールで質問して待機している間、権限評価上は `effect:"allow"` のため通知されず、ボスが別作業していて待ちぼうけになる実害が発生。
    2. **修正**: `describeRequest` に question 分岐を追加（`source.id` 単位の一意要求ID・見出し「💬 OpenCode が回答を待っています」）、`evaluate` フィルタを「deny 除外 ＋ ask または question で通知」に拡張。観測のみの設計思想は維持。
    3. **実機検証**: question 発火 → 19ms 後 `HTTP 200 queued (req_be9c4b46)` → スマホ受信確認済み（ホットリロードで即反映）。
  - 🔍 **調査の効率化実績**: codebase-memory-MCP の `search_code` / `trace_path` / `get_code_snippet` に切り替えた結果、手動 grep では未発見だった「`sw.js` が誰にも登録されていない（`navigator.serviceWorker.register` = 0件）」を含む Web Push 実装の影響範囲を一括確定。
- **🧠 本日完了アクション (2026-09-22 セッション Part 2: 社内勉強会マニュアル・Marpスライド ＆ Dotfilesセキュリティ監査)**:
  - 🎓 **社内勉強会用「超詳細・超ボリューム」完全マニュアル (`docs/articles/社内勉強会_AI自律開発スタイル完全マニュアル.md`)**:
    1. **背景**: ChatGPTの会話ボットしか使ったことがない社内の初心者に向けて、「動くモノを作る開発スタイル」の全ノウハウを伝える勉強会の資料を作成。
    2. **構成**: なぜチャットだと挫折するのか（会話ボットと自律エージェントの決定的違い）、厳選7大Skill ＆ 3大MCPの道具箱、山田流5大奥義、30分ライブ開発実演シナリオ（無茶振りお題〜逆尋問〜工程表〜実装〜監査〜動く図解フィニッシュ）。
  - 📽️ **`minorun-marp-skill` 導入 ＆ Marpスライドデッキ (`docs/articles/社内勉強会スライド_marp.md`)**:
    1. **スキル配備**: `slide-story`, `slide-figures`, `slide-design-dark` および `minorun-dark.css` を中央Wiki（`~/.gemini/config/skills/`）へ導入。
    2. **スライド設計**: 聴衆の心の声を代弁する中扉（crosshead）を配置し、文字を読ませず話し手がテンポよく語る紙芝居形式で作成。まとめスライドは作らず行動喚起中扉で締める型を遵守。
    3. **ゼロコンフィグ解決**: Marp for VS Code で外部テーマ（`minorun-dark`）が認識されずプレビュー不可となった問題を、スライド内に `<style>` タグでCSSルールを直接インライン埋め込みすることで、追加設定なしで開くだけで即座にプレビュー描画されるように改修。
  - 🛡️ **AI Dotfiles リポジトリの緊急セキュリティ監査 (`~/.ai_dotfiles`)**:
    1. **機密情報の検出**: `antigravity/config/mcp_config.json` 内に本物の GitHub PAT (`ghp_...`) および Stitch API Key (`AQ.Ab...`) が直書きで混入していることを発見。
    2. **対策と提言**: 第三者招待を直ちに中止し、トークンの破棄（Revoke）を案内。個人DR用リポジトリ（Private）と社内配布用スターターキット（Public）を明確に2リポジトリ分離する運用原則を確立。
- **🧠 本日完了アクション (2026-09-22 セッション Part 1: 全権限Hook通知 ＆ AI Dotfiles Gitバックアップ)**:
  - 🛡️ **全権限インターセプト通知の配備 (`~/.gemini/config/hooks.json`, `.agents/hooks.json`, `tool_guard_hook.py`, `tests/test_tool_guard_hook.py`)**:
    1. **真因解明**: 従来の Hook matcher は `grep_search|run_command` のみだったため、ワークスペース外（`~/.config/` 等）への `list_dir` や `view_file` 時に IDE が出す権限確認ダイアログで Hook が呼ばれず、通知が飛ばなかった。
    2. **対策**: matcher を `grep_search|run_command|list_dir|view_file|write_to_file|replace_file_content` に拡張。`is_external_workspace_path` 関数を実装し、ワークスペース外（`HISHO_ROOT` 以外）のファイル・ディレクトリ操作を検知した瞬間に `notify_waiting` を発火させて PC ペットとスマホ Desk Pet を鳴動させる仕組みを確立。
  - 📦 **全エージェント統合 AI Dotfiles バックアップ ＆ 復元ツール (`~/.gemini/sync_ai_dotfiles.py`, `~/.ai_dotfiles/`)**:
    1. **背景**: Antigravity, OpenCode, Cline, Codex の4大エージェントに分散した設定・スキル・ルールや、秘書くんの「知識の宝庫 (`user_insights`)」を安全にGit差分管理し、新端末へ1コマンドで復元できるDR基盤が求められていた。
    2. **機能**: `--export`（実機から `~/.ai_dotfiles` へ集約コピー＋SQLite知見テキストSQLダンプ）、`--restore`（新端末の実機各所へ自動再展開＋SQLインポート）、Git-Safeな `.gitignore` 自動生成（秘密鍵・生DBバイナリ・キャッシュ除外）。
    3. **関心の分離（引き算の美学）**: 秘書くんリポジトリ内には個人用インフラツールを混入させず、グローバルツール（`~/.gemini/`）および専用バックアップリポジトリ（`~/.ai_dotfiles/`）へ完全に分離配置。
    4. **セッションラップアップ統合**: `.agents/skills/session-wrap-up/SKILL.md` および `AGENTS.md` §2.14 に、ラップアップ時のGitコマンド提示で AI Dotfiles 同期コマンドも併記する手順を正式制定。
  - 🗺️ **機能ロードマップ ＆ システム設計書同期 (`docs/specs/機能ロードマップ.md`, `docs/specs/DESIGN_SPEC.md`, `docs/00_ドキュメント一覧.md`, `active_context.md`)**:
    1. **背景**: エージェント側のHooks設定（Antigravityのhooks.jsonやOpenCodeのプラグイン）をユーザーが簡単に導入できるガイド機能と、最新機能（Agent Bridge/Desk Pet/0fps省電力/統合手帳/多言語切替）を伝える新ツアー（英語版含む）の必要性を整理。
    2. **ロードマップ策定**: セクション 13.18 / DESIGN_SPEC セクション 22 に「Hooks設定ガイドウィザード（ワンクリックコピー・自動配備・Pingテスト）」および「新・4ステップオンボーディングツアー（日英完全対応）」を策定・同期。

  - 📲 **OpenCode実証済み「ask_input非ブロッキング通知」のAntigravity移植 (`tool_guard_hook.py`, `tests/test_tool_guard_hook.py`)**:
    1. **原因解明**: 旧実装では `/api/agent/notify` を叩いていたため、PCペットの `alarm_ask` やスマホDesk PetのBuzzチャイム・画面演出が発火しなかった。
    2. **移植内容**: `POST /api/agent/ask_input` を `wait_decision: False`、`timeout: 5`、`choices: []` で即時キューイング送信。`agent_bridge_client._post_to_hub` を再利用し、ポート解決・Bearerトークン・例外隔離を完全共通化。
    3. **スパム防止**: コマンドのSHA256ハッシュに基づく60秒クールダウン（`NOTIFY_COOLDOWN_SEC = 60`）を敷設。
    4. **TDD検証**: `agent-tester`（Conversation ID: `36f3e145-7f30-4f3a-bcb3-66b8d3c695c6`）により全9テスト ALL GREEN を確認。

  - 📱 **スマホ承認ダイアログ多重ポップアップの完全根治 (`ui/device_approval_dialog.py`, `web_pet/pet_auth.js`, `tests/test_device_connection_approval.py`)**:
    1. **原因**: スマホPWA起動時の2秒ポーリングとカレンダー/TODO並列リクエストが未認証（401）となった際、1回目のダイアログで「許可」した瞬間にサーバー側の合流フラグ（`_is_dialog_active`）が解除され、直後に届いた2発目の要求を「新しい端末接続」と誤認して2個目のダイアログを連続で開いていた。
    2. **サーバー側対策**: `ui/device_approval_dialog.py` に `_recent_approvals`（10秒デバウンスキャッシュ）を新設。一度許可した同一端末（`client_ip:device_name`）は10秒以内であればダイアログを再表示せず即時 `True`（承認済み）でバイパス。
    3. **クライアント側対策**: `web_pet/pet_auth.js` の `requestSyncToken()` に 3秒間のインターバルクールダウン（`TOKEN_REFRESH_COOLDOWN_MS = 3000`）を敷設し、リクエスト多重打ちを水際で防止。403時のみトークンをクリアするように堅牢化。
    4. **TDD検証**: `test_dialog_recent_approval_debounce` を新設し、直近再要求でダイアログが再生成されないことを担保。
  - 🛡️ **Antigravity Tool Guard Hook の新設 (`.agents/hooks.json`, `~/.gemini/config/hooks.json`, `tool_guard_hook.py`, `tests/test_tool_guard_hook.py`)**:
    1. **背景**: プロンプト規約（Rule）だけではAIの焦りや悪い癖（脊髄反射的な grep や自律コマンド実行）を100%防げず、コンテキスト汚染を招く。
    2. **対策**: Antigravity 公式の `PreToolUse` Lifecycle Hook を採用。AIが `grep_search` や `run_command` を呼んだ瞬間にインラインACLが割り込み、関数名・クラス名の構造探索クエリや危険コマンドを物理的に `deny` 遮断して `codebase-memory-mcp` へ決定論的に誘導。日本語検索・エラー文・設定パスは摩擦ゼロでパススルー。
  - ⚡ **Jev MCP 意思決定エンジンの堅牢化 (`jev_client.py`, `jev_mcp_server.py`)**:
    1. **原因**: API通信の一時エラー時に空辞書が返り、`confidence: 0.0` のデフォルト値があたかも正常判定であるかのようにサイレント偽装されていた。
    2. **対策**: 最大2回試行（1秒待機）の自動リトライを実装し、エラー時は `"error"` を明示的に上位へ通知するフェイルファスト設計に是正。
- **🧠 本日完了アクション (2026-09-21 深夜セッション: OpenCode モデル選択 ＆ 入力待ち通知の完成)**:
  - ⚡ **Jev モデル選択（3ツール版MCP / `jev_mcp_planner.py`）**:
    1. **背景**: Antigravity は「サブエージェントごとにモデル指定すると直列化する」ため、モデル選定は OpenCode 専用にする必要があった。
    2. **対策**: **契約の境界を分離**（Antigravity=`jev_mcp_server.py` 2ツールのまま / OpenCode=`jev_mcp_planner.py` 3ツール）。`jev_guard_command` / `jev_route_agent` は **Antigravity側の関数を同一オブジェクトで import** して登録し、挙動がズレる余地を構造的に排除。
    3. **`jev_select_models` は候補をクライアントが渡す設計**（Jevはモデル名を知らない）→ GO契約の実在モデルは `tools.opencode.models` から**ライブ取得**し陳腐化を防止（実測: 既存キャッシュ37件中**10件が廃止済み**だった）。
  - 💰 **コスト帯ポリシー（`model_policy.json` = ボスが編集する唯一のファイル）**:
    1. 出力 **$1.0/M 未満＝常用帯（自動）／以上＝承認帯（スマホ承認必須）**。実装の既定は `deepseek-v4.1-flash` / `glm-5.3-flash`（ボス指定）、監査は `glm-5.3` / `grok-4.6` / `kimi-k3`。
    2. **B案（厳格運用）**: 指定モデル以外は候補から除外（安い逃げ道を廃止）。変更は `model_policy.json` に1行追記するだけ（コード変更不要）。
    3. **ドリフト検知CLI**（`model_catalog.py --check --live-json`）: 推奨モデルの**廃止**・**新モデルの出現**・**価格改定**を機械検知（実測: 新モデル `stealth-free-2026` を自動検出 ✅）。
    4. **実機E2E**: 実装→`glm-5.3-flash`（確信度0.81）/ 監査→`kimi-k3`＋**要承認**（$0.45）。**候補を絞ったら確信度が 0.51→0.80 に上昇**（引き算が精度にも効く実証）。
  - 🐬 **入力待ち通知プラグイン（`~/.config/opencode/plugins/hisho-approval-notify/index.ts`）**:
    1. **背景**: OpenCodeが「⚠️ 権限が必要です」で止まってもボスが気づけず待ちぼうけになる（**ネオ秘書くんの存在意義そのもの**）。Antigravityは `PreToolUse` Hook で解決したが、OpenCodeに Hook は無い。
    2. **対策**: **Plugin** の `ctx.permission.hook("evaluate")` で検知（イベントに `effect: "ask"` が含まれる → **判断が必要なときだけ通知**してスパムを防止）→ `POST /api/agent/ask_input`（**`wait_decision:false`**）で PCペットが `alarm_ask`＋スマホへプッシュ。
    3. **実測**: ボスが**実際に通知を受信**（`HTTP 200 {"status":"queued"}`）。診断ログ `%TEMP%\hisho-notify.log` に検知・通知の全履歴を記録。
    4. **落とし穴の記録**: `import { Plugin } from "@opencode/plugin"` は**この環境では解決不可**（`Cannot find package`）。`Plugin.define` は素通し関数のため **import を省いて素のオブジェクトを export** すれば等価（実測で解決・再起動不要のホットリロードで反映）。
  - 🛡️ **`sync_opencode_agents.py` の独立査読是正（P0×1 / P1×6）**: `git branch *` allow の決定論的ホール（**P0**）／エージェント権限の後勝ち上書き（P1-1）／`mainAgent` 無視で mode 固定（P1-2）／孤立検知・終了コード契約・KeyError即死。**TDD: Red 29 failed → Green 22 passed** を実証。全回帰 **753 passed / 2 skipped**。
  - 📨 **Antigravity への技術移管**: 入力待ち通知の実装ノウハウ（`wait_decision:false` 必須／Bearer認証／`_post_to_hub` 再利用／逆allowlist方式）を指示文として提供し、Antigravity側の実装完了を確認。
- **🧠 本日完了アクション (2026-09-21 セッション: OpenCode × Jev-MCP 自律マルチエージェント体制 実機配備完了)**:
  - ⚡ **Jev-MCP の OpenCode 配線 (`~/.config/opencode/opencode.jsonc`, `opencode.json`)**:
    1. **背景**: OpenCode v2.0.11 は V1形式の `mcpServers` を解釈せず、V2形式の `mcp.servers`（`type: "local"` / `command` 配列）を要求する。また自動ロードされる指示ファイルは `AGENTS.md` のみで、`instructions` フィールドは V2 では解決されない。
    2. **対策**: グローバル設定 `~/.config/opencode/opencode.jsonc` に `jev-mcp` / `codebase-memory-mcp` / `neo_hisho_bridge`（`HISHO_AGENT_NAME=OpenCode`）の**3サーバーを集約**（当初はブリッジをプロジェクト側に置いたが、ボス判断により「どのプロジェクトからでもスマホ承認」を優先してグローバルへ移設 / 単一情報源化）。プロジェクト側 `opencode.json` は Hard ACL 44ルールのみを定義。`venv` に `mcp==1.30.0` を導入（`pip --dry-run` で既存固定依存が無変更であることを事前確認）。
    3. **実測**: 3サーバーがライブ接続。Jev Route は `pixel-frontend-designer` 66.0% を推薦、`git reset --hard` を deny（確信度0.39 ← 確率的ソフト層の限界を実証）。
  - 🤖 **11体のサブエージェント配備 (`tools/sync_opencode_agents.py`, `.opencode/agents/*.md`)**:
    1. **背景**: Antigravity形式の frontmatter `tools: [...]` は OpenCode V2 では使われず、`permissions: [{action, resource, effect}]` が必要。また2ファイルの二重管理は必ずドリフトする。
    2. **対策**: 正本 `.agents/agents/*.md` から V2 形式へ自動変換する同期ジェネレータを新設（`--check` でドリフト検知・正本ハッシュを刻印し直接編集を禁止）。Read-Only 7体は edit/shell/subagent を deny、`agent-tester` は pytest のみ allow。
    3. **実測**: `agent-tester` を**実起動**して回帰テストを実行（sessionID: `ses_f403c6456ffespdn2ra9zrqxQF`）→ **684〜686件 ALL GREEN**（failed=0 / errors=0 / 47〜54秒）。
  - 🛡️ **二層防御 Hard ACL (`opencode.json` permissions 44ルール)**:
    1. シェルは原則 `ask`、安全コマンド（git status/diff/log・pytest・py_compile）は allowlist で無承認、破壊的コマンド22種（`rm -rf /`・`git reset --hard`・`git push --force`・`git clean -f`・`git branch -D/-f/-m`・`DROP TABLE`・`mkfs` 等）は **deny**。
    2. `.env` / `*.db` の編集・参照は必ず `ask`（秘密情報・個人データ保護）。
    3. **設計判断**: 安全性の最終責任を LLM の確率出力に負わせず、決定論的 ACL が保証する。
    4. **A案適用 (2026-09-21)**: Hard ACL が `allow` する安全コマンドでは Jev Guard を呼ばない（過剰な摩擦の是正）。`OPENCODE.md` §2.2 / `AGENTS.md` §4.2 を是正済み。B案（プラグイン自動強制）は引き算の美学により見送り。
  - 📜 **規約の三層配置 (`OPENCODE.md`, `AGENTS.md` §4, `~/.config/opencode/AGENTS.md`)**:
    1. `OPENCODE.md` に Jev Pre-flight / Tool Guard / Verifierゲート / Desk Pet通知 / Hard ACL / Antigravity⇆OpenCode 読み替え表を体系化。
    2. `AGENTS.md` §4「OpenCode 実行環境プロトコル」を追記（V2が自動ロードする唯一の経路 / 追記と同時にライブ反映を確認）。
    3. グローバル `AGENTS.md` は `~/.gemini/GEMINI.md` を正本とする薄いブリッジ（単一情報源を死守しドリフトゼロ）。
  - 📊 **ドキュメント4点セット同期**: `00_ドキュメント一覧.md` / `DESIGN_SPEC.md` §21 / `機能ロードマップ.md` / `active_context.md` を同時更新。連携仕様書は **v1.1.0**（§0 As-Built 新設 + V1記述への警告3箇所 + V1→V2対応表）。
  - 🔒 **ゼロトラスト発見（未対応・宿題）**: `~/.gemini/config/mcp_config.json` に StitchMCP のAPIキーと GitHub PAT が**平文**で保存されている。`{env:...}` 参照への是正を推奨（Antigravity側の別タスク）。
  - 🛡️ **独立査読ラウンド（quality-reviewer / sessionID: `ses_f40392574ffeGcarX95KVihv67`）**: 判定 **CHANGES_REQUESTED**（P0×1 / P1×6）。
    1. **P0 検出**: `git branch *` の allow が `git branch -D/-f/-m` を**無承認で**通す決定論的ホール（私の設計ミス）→ allow を読み取り専用形（`git branch` / `--list` / `-v` / `-a`）へ限定し、破壊形7パターンを deny に追加。
    2. **P1-1 根治**: エージェント権限に `shell` の allow を再宣言していたため、**後勝ち**でグローバル deny を上書きし得た → ポリシーテーブルから allow を全廃（`INHERIT_PROJECT_ACL = ()`）。「締める方向にのみ働く」不変条件をテストで凍結。
    3. **P1-2 是正**: 正本の `mainAgent: true` を捨てて `mode: subagent` に固定していた → `resolve_mode()` を新設し **7体=all / 4体=subagent** へ（`hisho-orchestrator` を primary としても選べるようになり、名乗りが実体を伴う）。
    4. **P1-3〜P1-5 是正**: `--check` の孤立生成物検知 / 終了コード契約の恒偽バグ / 権限未定義時の KeyError 即死。
    5. **TDD 履行（P1-6）**: `tests/test_sync_opencode_agents.py` を新設し、**Red（29 failed）→ Green（22 passed / 74 subtests）** を実証。
    6. **P2 反映**: Read-Only 7体の MCP書き込み禁止 / `*.db` の read 承認制 / ハッシュの改行正規化 / 用語（`bash`→`shell`）併記 / 陣形数 11 統一。
    7. **最終ゲート**: 全回帰 **709 passed / 3 skipped**（ALL GREEN）。再E2E: `agent-tester` が無承認で pytest 実行可能（sessionID: `ses_f402dd885ffeynbud4q1pjgbRi`）。
- **🧠 本日完了アクション (2026-09-21 セッション: 英語挨拶メッセージ ＆ OpenCode仕様書 v1.1.6)**:
  - 🌐 **サーバー側英語挨拶メッセージの追加 (`local_sync_server.py`)**:
    1. **原因**: スマホ側で言語を英語（EN）に切り替えても、PCサーバーから返されるステータスの `default_msg` が日本語で固定されていたため、吹き出しに「ふぁ…まだ起きています？無理は禁物ですよ、ボス。」と表示され続けていた。
    2. **対策**: `local_sync_server.py` の挨拶生成ロジックに `is_en` 分岐を追加し、時間帯別の英語メッセージ（Good morning, Boss! / Yawn... Still awake? 等）を配備。
  - ⚡ **OpenCode Desktop 導入仕様書の策定 (`docs/guides/OPENCODE_JEV_MULTIAGENT_INTEGRATION_SPEC.md`)**:
    1. Jev-MCPによるSystem One高速ルーティングとTool Guardのアーキテクチャ解説。
    2. OpenCodeでのプロジェクト専用サブエージェント配置（`.opencode/agents/`）と多種多様なサブエージェント陣形（実装時点で11体）の定義。
    3. OpenCodeがそのまま読み込んで自律実行できるマスタールール（`OPENCODE.md`）と `opencode.json` 設定例を完備。
- **🧠 本日完了アクション (2026-09-21 セッション: スマホUI言語切替タッチ強化 ＆ トースト視覚化 v1.1.6)**:
  - 🌐 **スマホUI言語切り替えボタンのタップ判定確実化 (`web_pet/lang.js`, `web_pet/style.css`, `web_pet/index.html`)**:
    1. **原因**: スマホ（タッチ環境）において幅28px・高さ22pxの極小ボタンかつ `onclick` インラインハンドラのみに依存していたため、微細なドラッグやタップ遅延によりイベントがキャンセルされやすかった。また、切り替わっても視覚フィードバック（トースト）がなかったため、変化に気づきにくかった。
    2. **対策**: `web_pet/lang.js` に `bindToggleButton()` を新設し、`click` と `touchend` の両方を安全にリスン（300msガード付き）。切り替え完了時に `showToast()` を発火させ、スマホ画面中央に金色の切替トーストを即時表示。
    3. **タッチターゲット拡大**: `style.css` および `index.html` で幅36px・高さ26pxに拡大し、`touch-action: manipulation`（ダブルタップ遅延根絶）および `z-index: 20` を付与。
    4. **PWAキャッシュ強制更新**: `version.py`, `web_pet/version.js`, `web_pet/index.html` を `1.1.6` にインクリメント。起動時のキャッシュ自動パージを発火。
- **🧠 本日完了アクション (2026-09-21 セッション: 双方向言語同期 ＆ 巻き戻しガード v1.1.5)**:
  - 🌐 **双方向言語同期の配備 (`api_agent_bridge.py`, `local_sync_server.py`)**:
    1. **原因**: スマホ側で言語を切り替えてもPCサーバーへ通知するAPIが存在せず、サーバーは常にPC設定の `"language": "ja"` を返し続けていた。そのため、2秒ごとの `fetchStatus` が走った瞬間にスマホ側の `NeoLang.setLang('ja')` が呼び出され、強制的に日本語へ巻き戻されていた（ボタンを押しても何も変わらないように見えた真因）。
    2. **対策**: `api_agent_bridge.py` に `action_set_language` を新設し、`local_sync_server.py` の `ACTION_HANDLERS_DEVICE` に登録。スマホ側で言語を変更すると即座に PC側の `i18n.set_language()` も同期更新される双方向連携を確立。
    3. **手動切替オーバーライドガード (`web_pet/lang.js`, `web_pet/pet.js`)**: ユーザーがスマホで言語を切り替えた直後5秒間は、サーバーからの古いステータスによる上書き巻き戻しを無視する `isUserOverrideActive()` ガードを敷設。
- **🧠 本日完了アクション (2026-09-21 セッション: HTTPスレッド安全性・多重合流・端末削除 v1.1.4)**:
  - 🛡️ **`main thread is not in main loop` 例外の完全根絶 (`ui/device_approval_dialog.py`)**:
    1. **原因**: HTTPワーカースレッドから `ask_device_approval_gui` が呼ばれた際、関数の冒頭で `actual_root.winfo_exists()` を直接呼び出していた。TkinterのCラッパー内部でメインスレッド外呼び出しが検知され、`RuntimeError: main thread is not in main loop` が発生して即座に拒絶されていた。
    2. **対策**: HTTPスレッド側では Tkinter ウィジェットのメソッドを一切触らず、`gui.post_action(_show)` でダイアログ生成をメインGUIスレッドへ完全移管。`winfo_exists` や親子探索は `_show` 内（メインスレッド上）で安全に実行するように改修。
    3. **同一端末の合流待機 (Coalesce)**: スマホ側が2秒周期でポーリングして `/api/auth/token` を再要求してきた場合、同一端末（IP+名前）であればビジー拒絶（403）せず、現在表示中のダイアログの承認結果イベント（`_active_result_event`）に相乗り合流して待機するように改善。
  - 🌐 **スマホ側多重リクエスト重複排除 (`web_pet/pet_auth.js`)**:
    1. `requestSyncToken()` による In-Flight Promise Deduplication を導入。複数のAPIが同時に401を受け取っても、1本のリクエストのみを送信して結果を共有。
  - 🗑️ **端末台帳の重複防止 ＆ 物理削除機能の実装 (`storage/device_repo.py`, `database.py`, `ui/device_manager_panel.py`)**:
    1. **重複増殖防止 (`storage/device_repo.py`)**: 同一IPかつ同一端末名の端末が再接続した際、古い未失効レコードを更新再利用して新規行の無限増殖を防止。
    2. **物理削除 API (`storage/device_repo.py`, `database.py`)**: `delete_device(device_id)` を新設。
    3. **UI削除ボタン (`ui/device_manager_panel.py`)**: 設定画面「接続端末管理」の各端末カードに「🗑️ 削除」ボタンを新設。確認ダイアログ付きで不要セッションを即時抹消可能に。
  - 🧪 **単体テストの拡充 (`tests/test_device_connection_approval.py`, `tests/test_device_ui_seam.py`)**:
    1. `test_dialog_coalesce_same_device`: 同一端末からの多重要求が合流して双方 True を受け取ることを検証。
    2. `test_delete_device_entry_success` / `test_delete_device_entry_exception_returns_false`: 端末削除 Seam の正常系・異常系を検証。
  - 🛡️ **二重呼出排他ミューテックスの完全クリーンアップ (`ui/device_approval_dialog.py`)**:
    1. **原因**: `ask_device_approval_gui` で `_is_dialog_active = True` にした後、タイムアウトや例外時にフラグが解除されない潜在リスクがあり、後続の接続要求やテストがビジー拒絶される可能性があった。
    2. **対策**: 関数全体を `try...finally` で囲み、どのような脱出経路（正常終了、タイムアウト、例外）でも確実に `with _dialog_lock: _is_dialog_active = False` を実行するよう改修。
    3. **テスト状態汚染の根絶 (`tests/test_device_connection_approval.py`)**: `setUp` および `tearDown` にて `_is_dialog_active = False` と `local_sync_server.set_gui_instance(None)` を確実に実行するように強化し、テストメソッド全体をデコレータでパッチして決定論的・安定的に ALL GREEN になるよう適正化。
- **🧠 本日完了アクション (2026-09-20 セッション: P0端末承認ダイアログエラー根絶 ＆ ペット吹き出し多言語化 v1.1.2)**:
  - 🛡️ **P0 端末承認ダイアログ呼び出しエラーの根絶 (`ui/device_approval_dialog.py`, `local_sync_server.py`)**:
    1. **原因**: `local_sync_server.py` の `_approval_cb` から `ask_device_approval_gui` に `NeoSecretaryGUI` インスタンスが直接渡され、`root.winfo_exists()` で AttributeError が発生。Fail-Closed により外部端末接続が自動拒絶（403）されていた。
    2. **対策**: `actual_root = getattr(root, "root", root)` による二重防御（Defense-in-Depth）を配備。`NeoSecretaryGUI` と `tk.Tk` の双方を安全に受け入れ、承認ダイアログが確実に最前面表示されるように是正。
    3. **回帰防止テスト (`tests/test_device_connection_approval.py`)**: GUIインスタンスを直接渡した場合でも正常に `root` を抽出して承認フローが動作することを検証する単体テストを追加。
  - 🌐 **デスクトップペット吹き出しの多言語化 (`gui.py`, `i18n.py`)**:
    1. **原因**: スマホ自動最小化トグル、徘徊モード、LLM切替、スマホ呼び出し通知などの吹き出しテキストが日本語ハードコードされていた。
    2. **対策**: `i18n.py` に `ui.pet.auto_minimize_toggle`, `ui.pet.status_enabled`, `ui.pet.status_disabled`, `ui.pet.roaming_mode_toggle`, `ui.pet.switch_brain_success` 等を追加し、`gui.py` の全該当箇所を `i18n.t()` 化。
    3. **バージョンインクリメント**: `version.py` および `web_pet/version.js` を `1.1.2` に更新。
- **🧠 本日完了アクション (2026-09-20 セッション: デスクトップ⇆スマホ双方向多言語同期 ＆ PWA動的モーダルローカライゼーション完遂 v1.1.1)**:
  - 🌐 **デスクトップ ⇆ スマホ双方向多言語同期 ＆ PWA全域多言語化 (v1.1.1)**:
    1. **バックエンド同期の配備 (`sync_dtos.py`, `local_sync_server.py`)**:
       - `StatusResponse` DTO に `language: str = "ja"` を定義。
       - `local_sync_server.py`: `import i18n` を配備し、`/api/status` レスポンスに現在のデスクトップ言語 `"language": current_lang` を同梱。吹出メッセージおよびポモドーロ状態ラベルを多言語辞書 `i18n.t()` 経由で生成。
    2. **PWAフロントエンドの全域多言語化 (`web_pet/lang.js`, `web_pet/pet_ui.js`, `web_pet/pet.js`)**:
       - `web_pet/lang.js`: ヘッダー、ブリーフィング、サジェスト、TODO、カレンダー、日報、設定モーダル用の辞書キーを大幅拡充。
       - `web_pet/pet_ui.js`: `updateAllScreenLabels()` を新設。`neolang:changed` イベントでメイン画面のバナー、サジェスト、ドック、ボタンツールチップを一斉更新。
       - `web_pet/pet.js`: `fetchStatus` で `data.language` を受信して `NeoLang.setLang(data.language)` によりサーバーと自動同期。TODO・カレンダー・ノート・設定の各モーダル生成ロジックに `NeoLang.t()` を完全適用。設定モーダル内に `🇯🇵 日本語` / `🇺🇸 English` 切替チップを追加。`neolang:changed` リスナーで開いているモーダルを即座に再描画。
    3. **キャッシュバスターのインクリメント (`version.py`, `web_pet/version.js`, `web_pet/sw.js`, `web_pet/index.html`)**:
       - `version.py`: `__version__ = "1.1.1"` に更新。
       - `web_pet/version.js`: `1.1.1` に更新。
       - `web_pet/sw.js`: キャッシュ対象に `'./lang.js'` を追加。
       - `web_pet/index.html`: `style.css?v=1.1.1` および全 scripts の `?v=1.1.1` を更新。
    4. **TDDテスト配備 (`tests/test_sync_dtos.py`)**:
       - `StatusResponse` に `language` フィールドが含まれ、型検証されることを確認する単体テストを追加。
- **🧠 本日完了アクション (2026-09-20 セッション: P0/P1時限爆弾撤去 ＆ 多言語化Phase 4完遂)**:
  - 🛡️ **P0/P1時限爆弾の撤去（安定性・堅牢性の根本治療）**:
    1. **P0 スレッド競合即死クラッシュ根絶 (`main.py`)**: `async_mainloop` で `app.loop = asyncio.get_running_loop()` を保持し、`post_human_message` を `asyncio.run_coroutine_threadsafe()` へ是正（HTTPワーカースレッドからの非同期タスク安全化）。
    2. **P1 予定通知二重発火の根絶 (`main.py`, `proactive_engine.py`)**: `proactive_engine.check_event_reminders` を no-op 化し、予定リマインダー通知責務を `reminder_engine.py` に完全一本化。スケジューラ側の重複呼び出しも撤去。
    3. **P1 繰り返しタスクDBカラム逆転汚染の根絶 (`storage/task_repo.py`)**: `complete_task` 内の INSERT 文で `list_id` と `tags` のカラム逆転を修正。
    4. **P1 監視ウォッチドッグの自爆ポート競合防止 (`local_sync_server.py`)**: `ServerWatchdog` の失敗許容回数を 1 ➔ 3、タイムアウトを 1.0s ➔ 2.0s に緩和（ポート10048 WinErrorを根治）。
  - 🌐 **多言語化 Phase 4 完遂**:
    1. **AIエージェント多言語プロンプト化 (`agent.py`)**: システムプロンプト内の日本語規則ハードコードを `get_prompt_language_instruction()` による動的制御へ置換。
    2. **起動時言語自動ロード (`i18n.py`)**: 環境変数 `APP_LANGUAGE` または `.env` から初期言語を自動認識する `_init_language_from_env()` / `reload_language_from_env()` を配備。
    3. **デスクトップ半透明スマート付箋の多言語化 (`ui/sticky_note.py`)**: タイトル、プレースホルダー、空タスク通知、緊急度バッジを `i18n.t()` 化し、`subscribe_language_change` による動的再描画に対応。
    4. **単体テスト拡張 (`tests/test_i18n_and_ui_protection.py`)**: 付箋の多言語辞書および環境変数言語リロードの単体テストを追加。
- **🧠 本日完了アクション (2026-09-20 セッション: Sprint Global 完遂)**:
  - 🌐 **Sprint Global (多言語対応 ＆ UIレイアウト耐性6大防壁)**:
    1. **PWAフロントエンド (`web_pet/lang.js`, `style.css`, `index.html`, `pet_ui.js`)**:
       - 短縮Microcopy（`Tasks / Cal / Daily / Config`, `Approve / Deny`, `🟢 JEV: ALLOW`）。
       - ヘッダー右上ワンタップ言語トグルボタン（`[EN] / [JA]`）＆ localStorage 永続化。
       - 承認ボタンの `position: sticky; bottom: 0;` 固定化（長文スクロール深海沈没を根絶）。
       - 吹き出しの `max-height: 120px` ＆ `word-break: break-word`。
    2. **デスクトップGUI ＆ LLM制御 (`i18n.py`, `ui/pet_window.py`, `ui/settings_window.py`)**:
       - `i18n.py`: UI辞書追加、`get_no_chinese_instruction()` 動的化、`get_prompt_language_instruction()` 新設。
       - `ui/pet_window.py`: 文字数に応じた横幅伸縮（220px〜320px）、1000文字爆弾 Truncate (180文字)、最大高clamp (140px)、25文字超トークン強制分割。
       - `ui/settings_window.py`: 「一般」タブ言語選択、`grid_columnconfigure(1, weight=1)` Auto-fit、切り替え時即時再描画。
    3. **TDDテスト ＆ カオス破壊監査 (`tests/test_i18n_and_ui_protection.py`)**:
       - 辞書対称性、LLM動的言語ガード、境界値、ヘッドレスCanvasモック、1000文字爆弾、型例外耐性テスト全網羅。
- **🧠 本日完了アクション (2026-09-20 セッション: Sprint C 完遂 ＆ Jev バッジデータフロー根治)**:
  - 📱 **Jev 安全審査バッジのデータ伝達断絶根治 ＆ PWA v1.0.4 適用**:
    1. **原因**: `local_sync_server.py` の `AgentBridgeRequest.to_dict()` に `summary` / `safety_level` キーが含まれず `undefined` になっていたこと、および `pet_ui.js` が `req.title` を見ていなかった2重要因を特定。
    2. **バックエンド強化 (`local_sync_server.py`, `api_agent_bridge.py`)**: `AgentBridgeRequest` に `summary`, `safety_level` を追加し、`to_dict()` で出力。`handle_agent_ask` で `summary` から Jev 審査レベルを自動抽出。
    3. **フロントエンド堅牢化 (`web_pet/pet_ui.js`)**: `buildJevBadge()` で `summary`, `title`, `content` 全体を包括スキャンし、ボトムシートのタイトルにもフォールバック適用。
    4. **キャッシュ自動更新**: `version.py`, `web_pet/version.js`, `web_pet/index.html` を `1.0.4` にインクリメント。
    5. **TDDテスト配備 (`tests/test_agent_bridge_jev_badge.py`)**: ハブと API のデータ伝達整合性を検証する単体テストを追加。
  - 🚀 **Sprint C: GitHub Actions CI/CD パイプライン構築 (`.github/workflows/ci.yml`)**:
    1. **Fail-Fast な2段構成**: `lint` ジョブ（`python -m compileall` 構文検査 ＋ `ruff check` 静的解析）を先行させ、構文バグを秒速で検知して無駄なテスト実行を遮断。
    2. **CIによる潜在的NameErrorバグの早期根治 (初回CI検知)**:
       - `hisho_mcp_server.py`: `datetime` インポート漏れ（F821）を修正。
       - `ui/settings_window.py`: `Optional` インポート漏れ（F821）を修正。
       - `ui/tour_overlay.py`: `TourStep` インポート漏れ（F821）を修正。
    3. **CI環境差異 ＆ P0-2 ゼロトラスト整合テスト修正 (全8件解消)**:
       - `tests/test_terminology_boundary.py`: CI環境で `.gitignore` 対象ファイル不在時の `skipTest` ガード追加（4件）。
       - `tests/test_asset_path_security.py`: Windows 8.3短縮パス（`RUNNER~1`）の `resolve()` 正規化（1件）。
       - `tests/test_device_individual_tokens.py` & `tests/test_sync_lan_selfheal.py`: P0-2 承認コールバックのモック設定（3件）。
    4. **セキュリティ検査独立**: `secret-scan`（`tools/scan_git_secrets.py`）を並行実行し、APIキー・認証情報の漏洩を完全ブロック。
    5. **クロスプラットフォーム・マトリクス最適化**:
       - `ubuntu-latest` × Python `3.11`, `3.12`, `3.13`（Linux全走破）
       - `windows-latest` × Python `3.12`, `3.13`（CPython 3.11 Windows GCクラッシュ 0x80000003 を回避し実用環境に完全整合）
    6. **Ubuntu ヘッドレス GUI サポート**: `xvfb` (X Virtual Framebuffer) を配備し、`xvfb-run -a pytest -v --tb=short` で Tkinter/CustomTkinter 依存テストをスキップさせずに100%実走・合格。
    7. **ビルドハング防止 ＆ キャッシュ**: `llama_cpp_python` を CI 依存関係から除外（スタブ注入）し、`cache: 'pip'` でセットアップ時間を 2分 → 15秒 へ短縮。
  - 📱 **未承認端末接続時の Human-in-the-Loop 承認ダイアログ (P0-2) ＆ Jevバッジ (P0-3) 完了**:
    1. `ui/device_approval_dialog.py`: 10秒カウントダウン、最前面ダイアログ、`_is_dialog_active` 排他ミューテックス配備（ダイアログスタックDoS防止）。
    2. `local_sync_server.py`: `cb is None` 時の 403 Fail-Closed 遮断（P1ゼロトラスト脆弱性封鎖）＆ 外部端末からのトークン発行要求時の人間承認結合。
    3. `web_pet/pet_ui.js`: Jev安全審査バッジ（ネオン枠線・文字シャドウ）配備 ＆ 「🟢 🟢」二重アイコンバグ解消。
    4. `tests/test_device_connection_approval.py`: 全11件 0.410秒 完全合格（OK）。
  - ⚡ **Jev意思決定エンジン（System One）のアーキテクチャ的大進化**:
    1. **引き算の美学**: OpenCode GOの直列外部推論呼び出しを撤去し、15ms・0.0001ドル極小コストの超高速構造化判定に純化。
    2. **全119スキル100%ノーカット全文渡し**: 300文字制限を完全撤廃し、最長1,056文字（`google-cloud-storage-fuse`）を含む全スキルの `description` を完全網羅。キーワード欠落を完全根絶。
    3. **2段階選抜（リランキング）方式**: 確率スコア（％）付きの候補ランキング（スキルTOP 7、MCP TOP 5、エージェントTOP 5）出力。
    4. **実測パフォーマンス**: `codebase-memory-mcp: 98%`、`graph-engineering: 86%`、`hisho-orchestrator: 49%` と圧倒的な確信度・精度を実証。
  - 🔌 **MentisDB（汎用エージェント記憶MCP）の Antigravity 正本登録**:
    - `config/mcp_config.json` のコマンドを絶対パス `"C:\\Users\\bonob\\.cargo\\bin\\mentisdb.exe"` に是正し、Jev選択肢に正式組み込み完了。
  - 🌐 **全プロジェクト共通 Jev MCP サーバー完全開通 (`jev-mcp 🟢`)**:
    - 独立専用仮想環境 (`~/.gemini/tools/jev_router/.venv/`) に `mcp<2` (FastMCP安定版) および `httpx` を配備。
    - `~/.gemini/config/mcp_config.json` へ正式統合し、IDEコマンド承認ポップアップ（Allow running command?）を完全根絶。
    2. 6層アーキテクチャ、全ツール相関図、依存関係マトリクス、昼夜非同期サイクル（Antigravity ⇆ Jules）の体系化。
    3. 4大記憶境界（知識の宝庫 vs codebase-memory vs MentisDB（汎用エージェント記憶MCP・別物） vs NotebookLM）の厳格定義。
  - 🎨 **動的相関図・Showcase HTMLの完成 (`docs/ecosystem_showcase.html` / `~/.gemini/docs/ecosystem_showcase.html`)**:
    1. Canvas描画によるノード・リンク・パケット送受信アニメーション。
    2. 昼（Antigravity）/ 夜（Jules）モード切り替え、Jev Tool Guard / 歓喜通知シミュレーター配備。
  - 🧠 **TypeSafe Jev 1.13 意思決定エンジンの配備 (`jev_client.py`, `jev_mcp_server.py`)**:
    1. OpenRouter Decisions API (`/api/alpha/decisions`) 経由で本家 `typesafe/jev-1.13-20260917` との接続・判定を確立。
    2. Windows環境変数 `OPENROUTER_API_KEY` を直接参照するゼロトラスト設計（コードやGitへのキー露出を恒久防止）。
    3. 実測パフォーマンス: `git status` コマンドに対し `allow` (確信度 1.0) をミリ秒判定。1回わずか 0.0028円。
  - 🛠️ **Antigravity用 MCPサーバー登録 (`~/.gemini/antigravity/mcp_config.json`)**:
    - `jev-mcp`（`jev_guard_command`, `jev_route_agent`, `jev_custom_decide`）を常駐登録。
  - 📜 **新スキル配備 (`jev-brain`)**:
    - ワークスペース (`.agents/skills/jev-brain/`) およびグローバル (`~/.gemini/config/skills/jev-brain/`) へ同時配備。
  - 🔒 **全エージェント向けマスタールール・規約への恒久刻印**:
    - `~/.gemini/GEMINI.md`: 「# JEV: TypeSafe Jev (System Oneモデル) 意思決定連携の鉄則」を追記。
    - `AGENTS.md`: 「2.11 Jev意思決定エンジン連携規約（引き算の美学：秘書くん本体には推論を持たせず、エージェント側で判定してスコアを添える）」を制定。
    - `docs/specs/ADR_20260920_jev_integration.md`: アーキテクチャ決定記録を新規起票。
    - 知識の宝庫 (Knowledge Vault): 登録スクリプト `scratch_register_insight.py` を配備。
  - 🛡️ **ゼロトラストP0脆弱性封鎖 (`storage/device_repo.py`, `local_sync_server.py`)**:
    1. `SyncTokenManager.regenerate()` 連動で `revoke_all_devices()` を同期実行（スマホ全解除時の一括失効）。
    2. `DeskPetSyncHandler.timeout = 10.0`（Slowlorisスレッド枯渇防止）。
    3. Fail-Closed: 個別トークン発行失敗時のマスターキー漏洩フォールバックを廃止し HTTP 500 返却。
    4. `_dispatch_get_devices`: ループバック限定ガードで台帳覗き見防止。
  - 📋 **日報集計バグ根治 (`storage/task_repo.py`, `briefing_engine.py`)**:
    - `get_tasks_completed_today()` Seam新設により、終礼日報の過去全タスク誤出力バグを解消。
  - 📱 **実機スマホ接続の完全復帰確認**: ボス実機スマホからのDesk Pet PWA通信が緑画面で完全復帰。
  - 🧹 **ループバック（127.0.0.1）の台帳完全除外 (`storage/device_repo.py`, `local_sync_server.py`, `ui/device_manager_panel.py`)**:
    1. `cleanup_loopback_devices()` 新設: DB内の `127.0.0.1` / `::1` ゴミレコードを一括削除。
    2. `_handle_auth_token` ＆ `_check_auth`: ループバック時は台帳登録・同期をスキップ。
    3. `build_device_rows`: ループバックIPを表示対象外とし、台帳を外部スマホ専用に純化。
  - 🛡️ **スマホ側 403 自動リカバリ ＆ 無効トークン自動消去 (`web_pet/pet_auth.js`)**:
    - `authFetch` にて 401 だけでなく 403 受信時にも `/api/auth/token` による自動再取得を試行。
  - 🚪 **QRダイアログ連動ライフサイクル (`ui/qr_dialog.py`)**:
    - ダイアログを閉じた際（`destroy`）に確実に `close_pairing` を呼ぶ直感ライフサイクルへ是正。
  - 💡 **ボスの知見を知識の宝庫へ永続化**:
    - 「端末ペアリングはHuman-in-the-Loop（人間承認）を原則とすること...」を永続記憶（insight_id: 2）。
  - 💡 **二重資産化の達成**:
    - ELI5動く図解HTML: `docs/explainers/eli5_20260918_zero_trust_device_pairing_and_recovery.html`
    - 学習メモ: `docs/learning-memos/学習メモ_20260918.md`
    - Obsidianノート: `G:\マイドライブ\Obsidian_Antigravity\Projects\ネオ秘書くん\2026-09-18_ネオ秘書くん.md`
    - Jules指示書: `docs/handover/prompt_for_jules_20260918.md`
  - 欢 **作業完了通知発行**: `notify_task_completed`（agent_name: "Antigravity"）でスマホDesk Petとデスクトップペットへ歓喜リアクションを発火済み。

- **🧠 直近完了アクション (2026-09-18 セッション: 端末台帳のゼロトラスト個別トークン化 ＆ 復帰API)**:
  - 🔐 **端末固有トークンの自動発行 (`storage/device_repo.py`, `local_sync_server.py`)**:
    1. `issue_device_token()`: 256bit 暗号論的乱数 (`secrets.token_hex(32)`) を発行し、DBへは SHA-256 ハッシュのみ永続化。平文はメモリ返却のみのゼロトラスト徹底。
    2. `/api/auth/token`: ペアリング開放時および外部/スマホ端末接続時に個別トークンを発行・返却。PC内・内部テストはグローバルトークンで後方互換100%維持。
    3. `_check_auth`: グローバルトークン（PC/Agent Bridgeマスターキー）と端末個別トークンの2層判定。端末Aを失効させても端末Bは影響なく通信継続（真の個別失効達成）。
    4. `dev.token_hash` を直接 `touch_device_last_seen` へ渡し、hashlib依存排除と Deep Module 原則を遵守。
  - ♻️ **端末単位の復帰（un-revoke API ＆ UI） (`api_devices.py`, `ui/device_manager_panel.py`)**:
    1. `restore_device()`: `UPDATE devices SET is_revoked = 0 WHERE id = ?`
    2. `POST /api/devices/restore`: ループバック限定・二重防御 Seam ハンドラ新設。
    3. `record_device_restore()`: 復帰操作を `approval_audit_logs` へ同期書き込み（who / when / which device）。
    4. 設定画面UI: 失効済み端末カードに「♻️ 接続復帰」ボタンを配備。確認ダイアログ・ヘッダー説明文を最新化。
  - 🧪 **TDDテスト完備 ＆ 独立査読 APPROVED**:
    1. `tests/test_device_individual_tokens.py`: 2端末個別発行・2行登録、個別失効、復帰、監査ログ、`_check_auth` 2層検証。
    2. `tests/test_api_devices_seam.py`: 復帰監査ログテスト。
    3. `tests/test_device_ui_seam.py`: `restore_device_entry` および `section.restore(row)` GUI結合テスト。
    4. `quality-reviewer` 多角査読（Zero-Trust、後方互換、例外安全、型規約）で満点 APPROVED 獲得。

  - **査読**: 独立サブエージェント2名（Zero-Trust＋カオス／アーキテクト＋PM＋QA）＋統括で未コミット差分を冷徹査読（総合6.8/10）。レポート: `docs/code_review_report_20260916_ruthless.md`。
  - **P0-1 修正（`web_assets.py` 新設）**: `/assets` のパス検証を純粋 Seam へ集約（①`\`・`:`・`%`・先頭`/`の事前排除 ②画像拡張子アローリスト ③`resolve()` 後のルート配下検証）。実測PoCで `\Windows\win.ini` 等の任意ファイル読み出しが **404**（修正前は200）になり、正規アイコンは200を維持。テスト `tests/test_asset_path_security.py`（14件）。
  - **P0-2 修正（テスト健全化）**: `importlib.reload`＋`os.environ.pop` を全廃し、環境変数検証はサブプロセス隔離へ。`NEO_HISHO_PORT=1500` で全586件green（修正前は5件FAILの偽陽性）。AST走査で再流入を防止。
  - **P1-1 修正（案内の真実化）**: `sync_config.read_port_from_env_file()` を新設し、**OS環境変数 → `.env` → 既定8765** の順で解決（stdlibのみ・os.environ非汚染）。`.env.example` の記載がそのまま有効に。
  - **P3 YAGNI削除**: 参照0件の `NeoSecretaryTray` 別名を削除。

- **直近完了アクション (2026-09-16 Cline Desktop: 5大アップグレード・パッケージ)**:
  - 🖼️ **タスク0: 秘書くんアイコン化 ＆ キャラ着せ替え連動**:
    1. **新設 `ui/window_icon.py`**: `apply_window_icon(window)` が `iconbitmap(assets/icon.ico)` → `iconphoto(PNG)` の順で例外安全に適用（`PhotoImage` の GC 対策で参照保持）。メインウィンドウ (`gui.py`) / 手帳 / 設定 / QR接続ダイアログの4箇所へ配備。
    2. **タスクトレイ**: `_ASSET_CANDIDATES` 最優先を `assets/dot/hisho/idle_1.png` へ変更。`resolve_character_icon_path()` / `load_character_tray_image()`（64x64・NEAREST）と `SystemTrayManager.update_character_icon()` を新設し、`gui.switch_character_skin()` から着せ替え連動で呼び出し。キャラIDは `^[a-z0-9_]+$` で正規化（パストラバーサル遮断）。
    3. **EXE**: `neo_hisho.spec` の `icon=None` を `icon=str(ICON_PATH)`（`SPECPATH` から解決した `assets/icon.ico`）へ変更。
  - 🧹 **タスク1: ハードコード解消 ＆ 衛生クリーンアップ**:
    1. **新設 `sync_config.py`（ポートの唯一の情報源）**: `SERVER_PORT`（既定 8765 / `NEO_HISHO_PORT` で上書き可・不正値は既定へ安全退避）。`local_sync_server` / `ui/qr_dialog` / `main._auto_tailscale_serve` がすべて参照。
    2. **`ui/qr_dialog.py` の URL ベタ書き排除**: `http://localhost:8765/api/test_buzz` → `build_loopback_api_url("/api/test_buzz")`。`TAILSCALE_SERVE_COMMAND` も定数から動的生成（ファイル内の 8765 リテラルは 0 件）。
  - ⚡ **タスク2: 省電力スプリント完遂（P1-2 / P1-3 / P1-4）**:
    1. **P1-2 (`storage/connection.py`)**: `idx_tasks_status_due (status, due_date)` / `idx_events_start_end (start_time, end_time)` を `init_db()` に追加。既存DBへも冪等に付与され、フルスキャン O(N) → 索引スキャン O(log N)。
    2. **P1-3 (`main.py`)**: `MAIN_LOOP_IDLE_SLEEP_SEC = 0.03`（約30Hz）へ緩和。UIイベント処理（`process_action_queue` / `root.update`）は毎ティック継続。
    3. **P1-4 (`sync_config.py`)**: ポートの単一情報源化 ＋ 環境変数オーバーライド（`.env.example` に `NEO_HISHO_PORT` を追記）。
  - 📱 **タスク3: スマホPWAホーム画面アイコンの最適化**:
    1. **旧 manifest の実バグを2件根治**: 実在しない `./assets/idle_1.png`（32x32・404）参照と、128x128 実体を 192/512 と宣言していたサイズ不一致。
    2. **新設 `tools/build_pwa_icons.py`**: ドット絵から `assets/pwa/icon_192.png` / `icon_512.png`（any）・`icon_maskable_512.png`（maskable・不透過）・`apple_touch_icon_180.png`（iOS用）を NEAREST 拡大で生成（再現可能）。
    3. **`web_pet/` 三点整合**: `manifest.json`（実在×サイズ一致）、`index.html`（apple-touch-icon / favicon / app-title 追加）、`sw.js`（4アイコンを `ASSETS_TO_CACHE` へ追加）。
  - 🛡️ **タスク4: 設定画面のゼロトラスト接続端末一覧UI（Sprint C 先取り）**:
    1. **新設 `ui/device_manager_panel.py`**: Seam 関数 `build_device_rows` / `list_device_rows` / `revoke_device_entry` ＋ GUI `DeviceManagerSection`。
    2. **設定画面に「📱 接続端末管理」タブを新設**し、端末名（UA解析補完）・UA/IP・初回/最終アクセス・認証ステータス（🟢有効 / 🚫拒否済み）を一覧表示。赤系「🔒 接続解除」→ 確認ダイアログ → `database.revoke_device()` → 即時再描画。失効済みはボタン無効化。
  - 🧪 **TDDテスト7本新設 ＋ 既存1本拡張**: `tests/test_tray_character_icon.py` / `test_db_indexes.py` / `test_main_loop_power.py` / `test_port_single_source.py` / `test_window_icon_seam.py` / `test_pwa_icons.py` / `test_device_ui_seam.py`、`test_packaging_support.py` に EXEアイコン検証を追加。すべて Red → Green を実測確認。

- **🧠 用語定義（恒久・2026-09-16 ボス指定）**:
  - **知識の宝庫 (Knowledge Vault)** ＝ 秘書くんアプリ内のボス知見ストア（`storage/insight_repo.py`・`user_insights` テーブル／`neo_secretary.db`）。書き込み `remember_boss_insight` ／ 読み出し `get_boss_insights`（neo_hisho_bridge）。**ボスの制約・好み・恒久ルールは必ずこちらへ。**
  - **MentisDB** ＝ Cline環境側の汎用エージェント記憶MCP（チェーン/セッション継続用）。**知識の宝庫とは別物・混同禁止。** 2026-09-14 に「MentisDB ➔ 知識の宝庫」呼称刷新（残存0件）を完了済み。旧ドキュメント・アーカイブに残る "MentisDB" は当時の呼称の歴史記録。
  - **codebase-memory-mcp** ＝ コード構造の知識グラフ ＋ ADR（`manage_adr`）。設計決定・Gotchaはこちらへ永続化する。
  - 回帰防止: `tests/test_terminology_boundary.py`（混同の再流入を Red で検知する番人テスト）。


- **✅ 完了 (2026-09-16 実機検証フェーズ → ボス確認OK)**:
  1. ~~【最優先】ボス実機目視確認~~ → **✅ OK**（タスクバー/トレイアイコン・キャラ着せ替え連動・各ダイアログのアイコン）
  2. ~~【スマホ実機】~~ → **✅ OK**（ホーム画面追加のアイコン・「📱 接続端末管理」一覧・接続解除）
  3. ~~【コミット】~~ → **✅ 完了 `278845f`**（36 files, +2616/-64）。未pushは2コミット（`d4cdf15` と `278845f`）。
  4. ~~**【未コミット】** セキュリティ自己点検ツール等~~ → **✅ コミット済み**（`62cc5b4` 自己点検ツール／`31ddfc3` P1-2／`9ae694b` P1-3・P1-4／`3ac2493` 中国語化・P2群／`36ffe7d` P2・P3群）
- **🎯 次回再開タスク (2026-09-18 更新・個別トークン化完遂後)**:
  1. ~~**【完了】端末台帳の個別トークン化**~~ → **✅ 完了（2026-09-18）**: `issue_device_token` / `verify_device_token` / 2端末独立発行・個別失効開通。
  2. ~~**【完了】un-revoke API ＆ UI**~~ → **✅ 完了（2026-09-18）**: `POST /api/devices/restore` / `restore_device` / PC設定画面「♻️ 接続復帰」ボタン開通。
  3. **【P3 残】** `main._auto_tailscale_serve` の失敗を設定画面UIへ可視化（現状は warning ログのみ）／Tailscale 既存マッピングの置換挙動の実機検証。
  4. **【残バックログ】** Sprint C（GitHub Actions CI/CD ＆ 公開踏切）／Phase G&H（MiniCPM-Pet進化系）／3キャラ（marmot/seal/kinoko）の理想スプライト詰めと `character_manager.py` 再登録。



- **直近完了アクション (2026-09-16 環境強化・リポジトリ衛生・Cline超詳細引き継ぎ準備)**:
  - 🧹 **Grokbot PR #5 マージ ＆ リポジトリ衛生完了**:
    1. **個人絶対パス完全除去 (`docs/specs/MCP_INTEGRATION.md`)**: ボスの個人Windows絶対パスを `<path-to-repo>/hisho_mcp_server.py` に置換し、OSSとしての安全性を担保。
    2. **セキュリティポリシー新設 (`SECURITY.md`)**: Local-First思想、シークレット非コミット規約、脆弱性報告フローを正式制定。
    3. **不要ファイル・バックアップ一掃**: `docs/guides/NEO_HISHO_CHEAT_SHEETS.html.bak` および一時ファイルを整理。`.gitignore` に `*.bak` を追加し、バックアップファイルの誤コミットを恒久防止。
  - 🧠 **codebase-memory-mcp 0.11.0 覚醒 ＆ ADR（設計決定記録）永続化**:
    1. **最新版 0.11.0 導入**: ノード数 380 ➔ **2,777**、エッジ数 373 ➔ **11,750** へ解像度と網羅性が劇的向上。JS cross-file reference も完全追跡可能に。
    2. **ADR初登録**: `manage_adr` を用い、ネオ秘書くんの三層構造、Seamテスト、0fps Canvasループ、5分PM哲学、トレードオフを公式永続化。
  - 🤝 **Cline Desktop への超詳細引き継ぎ指示書整備 (`docs/handover/prompt_for_cline_20260916.md`)**:
    1. **5大タスクのステップバイステップ仕様書**: ①秘書くんアイコン化＆着せ替え連動、②ハードコード解消、③SQLiteインデックス＆適応型スリープ、④PWAホーム画面アイコン、⑤設定画面ゼロトラスト端末一覧UI。
    2. **Codebase Design 規約**: Deep Moduleの原則、Seam維持、神ファイル肥大化抑止を明文化。
  - 🎨 **Canvas適応型描画ループ ＆ 0fpsスリープ ＆ Wake-on-Demand (P1-1)**:
    1. **画面非表示時の完全停止 (`web_pet/pet_particles.js`)**: `document.hidden` 検知時に `stopParticleLoop()` を実行し、`cancelAnimationFrame(animFrameId)` で保留フレームを完全破棄。画面OFF/バックグラウンド時のCanvasループを **0fps（CPU/GPU負荷ゼロ）** に完全縮退。
    2. **Wake-on-Demand 最小限復帰**: 画面復帰時（`visibilitychange`）やユーザー操作時（なでなで `spawnTouchParticles`、タスク完了 `spawnCelebrationConfetti`）のみ `wakeParticleLoop()` で安全に叩き起こすオンデマンド機構を配備。
    3. **多重ループ完全抑止 ＆ エントリーポイント一元化 (`web_pet/pet.js`)**: `pet.js` の初期化（98行目）を直接の `requestAnimationFrame` から `wakeParticleLoop()` 経由へ統一し、重複発火（120fps化）リスクを根絶。
    4. **SSR/Node例外安全性**: トップレベルバインドに `typeof window !== 'undefined'` ガードを配備。
    5. **TDDテスト新設 ＆ 独立査読APPROVED (`tests/test_pet_seam_canvas_power_save.py`)**: 全8項目テストを配備し、`quality-reviewer` から APPROVED 判定を獲得。全体テスト **474 passed in 31.7s** を達成。
  - ⚡ **Jules PR #4 マージ ＆ 習慣TTLキャッシュ開通 (P0-1)**:
    1. **30秒TTLキャッシュ (`local_sync_server.py`)**: スマホPWAの2秒ポーリング `/api/status` 内で、習慣データと70日ヒートマップの集計クエリを30秒TTLでインメモリキャッシュ化。SQLiteへの不要な高頻度I/Oを激減。
    2. **即時無効化 (`api_tasks.py`, `ui/calendar_window.py`)**: 習慣の追加・トグル・削除時に `invalidate_habit_cache()` を即時実行し、データ一貫性と即時反映UXを担保。
    3. **TDDテスト完備 (`tests/test_habit_cache.py`)**: クエリ回数とキャッシュ無効化の動作を自動検証。
  - 🔋 **PWA画面非表示時の省電力化 ＆ タイマー二重発火防止 (P0-2)**:
    1. **Page Visibility API 連動 (`web_pet/pet.js`)**: `document.hidden` 検知時にポーリング間隔を 2秒 ➔ `FETCH_HIDDEN_INTERVAL = 30000` (30秒) へ動的間引き。画面OFF/別アプリ中のスマホバッテリー消耗と発熱を根治。
    2. **遅延ゼロ復帰 ＆ 即時同期**: 画面復帰時（`!document.hidden`）は待機タイマーを即座に破棄し、0秒で即時フェッチ＆2秒通常ポーリングへ復帰。操作待ちゼロを保証。
    3. **タイマー一元管理 (`pollingTimerId` & `clearTimeout`)**: ポーリング発火・画面復帰・バックグラウンド遷移の全経路でタイマーを管理し、多重ループやメモリリークを完全遮断。
    4. **TDDテスト新設 (`tests/test_pet_seam_pwa_power_save.py`)**: 定数、判定ロジック、タイマーリセットを完全網羅。
    5. **独立検証者 (`quality-reviewer`) APPROVED 獲得**: P2改善（未定義シンボル残骸の排除）も即座に織り込み。
  - 🛠️ **Tcl_AsyncDelete スレッドクラッシュの第一原理分析 ＆ 完全根治**:
    1. **真因究明 (Why)**: 全体テスト終盤の「ドット15個」の直後に Tcl が abort していた原因を特定。付箋テスト2件（`test_sticky_note_position.py` 8件 ＋ `test_sticky_quick_add.py` 7件 ＝ 計15件）が `setUp` で毎回 `tk.Tk()` を作っては生の `root.destroy()` で破棄していたため、CustomTkinterのDPI/外観監視タイマーが宙に浮き、Tcl非同期ハンドラがGCスレッドから削除されてクラッシュしていた。
    2. **根本治療 (What)**: `setUpClass` / `tearDownClass` へ移行し、テストメソッド毎の `tk.Tk()` 乱造・乱破棄を 15回 ➔ わずか2回 へ激減。さらに `ui/tk_teardown.py` の `quiet_destroy`（トラッカー停止 ➔ 未消化タイマー全キャンセル ➔ 安全破棄）を完全適用。
    3. **実測結果**: **466 passed, 0 skipped, 0 failed in 57.49s**（全テスト完全走破・All Green）。
  - 🧪 **7件テスト失敗の完全根治 ＆ 全471テスト完全合格（全緑達成）**:
    1. **バックグラウンドWorker外部LLM通信遮断ガード (`lib/core/suggestion_engine.py`, `tests/test_perf_step2.py`)**: `start_worker=False` 時の終了処理エラーと未モックGemini API通信によるハングを根治。`_generate_3line_summary` にテスト環境ガードを配備し、`shutdown_worker()` を try-finally 保護。
    2. **キャッシュバスター整合性 Seamテスト改修 (`tests/test_pet_seam_*.py`)**: `web_pet/version.js` の `v1.0.3` に伴う `?v=1.0.3` 導入により失敗していた完全一致テストを、正規表現および前方一致アサーションへと改修。キャッシュゾンビ防御と自動テストの共存を達成。
    3. **実測結果**: **471 passed, 2 skipped, 0 failed in 32.60s**（デグレゼロ、全緑復元）。
  - 💡 **ELI5動くビジュアル図解HTML（二重資産化）自動生成 (`docs/explainers/eli5_20260914_pwa_flicker_and_test_guard.html`)**:
    1. **動くSVGシミュレータ**: 直接描画（白飛びフリッカー発生）vs ダブルバッファリング（裏舞台転換）のリアルタイム比較アニメーション、歓喜パーティクル連動。
    2. **物理構造解説 ＆ 身近な例え**: 劇場の幕と大道具転換、ディスプレイVSync周期の壁、テスト環境における未モック外部通信遮断の原則。
    3. **専門用語完全解体辞典**: ダブルバッファリング、キャッシュバスター、Seamテスト、知識の宝庫のアコーディオン解説。
  - 🛠️ **セッションスキルのアップデート (`.agents/skills/session-wrap-up/`, `session-start/`)**:
    1. `init-session-skills` の仕様に基づき、ネオ秘書くんのプロジェクト構成に最適化された最新の二重資産化（学習メモ＋ELI5動く図解HTML）ワークフローを完全配備。
  - 🏛️ **知見蓄積機能の呼称刷新（MentisDB ➔ 「知識の宝庫 / Knowledge Vault」全面統一）**:
    1. **MCP・サーバー層 (`hisho_mcp_server.py`)**: `remember_boss_insight` / `get_boss_insights` のツール説明文、Docstring、レスポンスメッセージ（「ボスの知見を知識の宝庫に永続化しました。」）を全面刷新。
    2. **ストレージ層 (`storage/models.py`, `storage/insight_repo.py`, `storage/connection.py`)**: `UserInsight` モデル、リポジトリ、テーブル定義コメントをすべて「知識の宝庫 (Knowledge Vault) 長期知見記憶」に刷新（DBテーブル名 `user_insights` や基本クラス名は後方互換性維持）。
    3. **推論・サジェスト・UI層 (`agent.py`, `suggest_engine.py`, `suggest_config.json`, `ui/settings_window.py`)**: LangGraphプランナーDocstring、サジェストタグ（`"tag": "知識の宝庫"`）、設定画面の説明文を全面統一。
    4. **Web Showcase & ドキュメント (`docs/neo-secretary-showcase*.html`, `docs/specs/DESIGN_SPEC.md`, `docs/specs/機能ロードマップ.md`, `docs/specs/MCP_INTEGRATION.md`)**: コードベースおよび全ドキュメントにおいて 旧呼称「MentisDB」の文字列を完全ゼロ（0件）化。
  - ⚡ **6大パフォーマンス・省電力設計の設計書・ロードマップ正式刻み込み**:
    1. **システム設計書 (`docs/specs/DESIGN_SPEC.md` Section 19)**: 「パフォーマンス最適化・省電力設計 (Performance & Battery Optimization - v1.0.3)」を新設。P0（PWA非表示ポーリング抑制、習慣キャッシュ）、P1（Canvas適応型ループ、DOM間引き、SQLiteインデックス）、P2（100Hz GUI適応型スリープ）の論理構造・Why/What・設計図を刻み込み完了。
    2. **機能ロードマップ (`docs/specs/機能ロードマップ.md` Section 13.11)**: 「⚡ パフォーマンス最適化・省電力スプリント (🔲 次回以降着手・v1.0.3)」を新設し、各タスクの優先度と受入基準を正式配備。
  - 🔍 **深層パフォーマンス監査 ＆ 6大ボトルネック特定 (`docs/code_review_report_20260914_deep_audit.md`)**:
    1. **`/deep-audit` × `/ruthless-code-evaluation` × `/holistic-code-review` × `codebase-memory-mcp` 多角査読**: 5大エリートペルソナ（Architect, PM, Chaos, Security, Retro-Perf）による多角査読とFowlerコード臭12種マトリクス診断を実施。総合格付け **Sランク** を獲得。
    2. **6大潜伏パフォーマンスボトルネックの特定**:
       - 📱 **PWA**: 画面非表示時（`document.hidden`）も2秒ポーリングが継続（バッテリー浪費）。
       - 🎨 **Canvas**: 毎フレーム60fpsの無条件ループとアンビエント光生成によるGCプレッシャー。
       - 🐾 **DOM**: 120ms（秒間8.3回）の無条件 `petWanderTick` による強制インラインスタイル書き込み。
       - ⚡ **SQLite**: `/api/status` 内でタスク/予定は2秒TTLキャッシュがあるが、習慣＆70日ヒートマップデータがキャッシュ漏れし毎秒重クエリ直撃。
       - 🏛️ **Index**: `tasks.status`, `tasks.due_date`, `events.start_time` のインデックス欠落による将来のテーブルフルスキャン懸念。
       - 💻 **GUI**: `main.py` の `async_mainloop` で `await asyncio.sleep(0.01)`（100Hz）が常時稼働しPC側CPUコアを占有。
    3. **P0〜P3ロードマップ策定**: 次回即座に着手できる5分ファーストタスク（P0-1: 習慣＆ヒートマップのキャッシュ化）を定義。
  - 🛡️ **PWA通知無限復活（ゾンビ通知バグ）の完全根治 (`web_pet/pet_ui.js`, `web_pet/pet.js`)**:
    1. **二重防壁（Double Shield）設計**: サーバーへ `POST /api/agent/dismiss_completed` を非同期送信してサーバー側TTL（90秒）を即時破棄。さらにクライアント側で `_dismissedCompletedIds = new Set()` と `isCompletedDismissed()` ヘルパーを新設し、受信データとの照合ガードで100%ゾンビ化を遮断。
    2. **知識の宝庫 知見永続化**: `remember_boss_insight` (ID: 6) へ重要Gotchaとして記録（※実体は neo_hisho_bridge＝秘書くんの知識の宝庫。汎用MCP「MentisDB」とは別物）。
  - ✨ **歓喜ジャンプ時の背景チラつき（フリッカー）完全根治 (`web_pet/pet_particles.js`, `web_pet/pet_motion.js`, `web_pet/index.html`)**:
    1. **ダブルバッファリング新設 (`pet_particles.js`)**: オフスクリーンCanvas（`bgCacheCanvas`）で背景シーンを事前レンダリングし、毎フレームは `drawImage` 1発で転送。毎秒数百回のパス再描画と `clearRect` 直後の透明フリッカーを完全根絶。
    2. **WebKit GPU レイヤー点滅遮断 (`index.html`)**: `.pet-stage` に `isolation: isolate;` を配備。ジャンプ中は `filter: none !important;` を適用し、激しいアニメーション中の重い `drop-shadow` 毎フレーム再計算によるGPUレイヤー点滅を遮断。
    3. **多重発火ガード (`pet_motion.js`)**: `window._celebratingUntil` ガードで同一ターン内での3重発火と強制同期リフロー（`void sprite.offsetWidth`）の連打を防止。
    4. **キャッシュバスター付与**: `index.html` 内の全スクリプトに `?v=1.0.3` を付与。`version.py` を `v1.0.3` へ更新。
  - 🧹 **死にコード削除 ＆ AIスキャン高速化（クリーンアップ）**:
    1. **非推奨・未使用関数の削除 (`local_sync_server.py`)**: 呼び出し元ゼロかつRCE警告付きの `respond()` メソッドを完全削除し、自己承認防御済みの `respond_checked()` へ一本化。
    2. **`.antigravityignore` 新設**: `backups/`, `restore_assets_*/`, `scratch/`, `models/*.gguf` 等の重いディレクトリをAIのスキャン対象から完全除外。検索オーバーヘッドを抜本的に削減。
  - 📅 **スマホ予定表示の日跨ぎ判定バグ根治 (`suggest_engine.py`)**:
    1. **真因特定**: `suggest_engine.py` のカレンダーサジェスト生成で、`get_upcoming_events(days=1)` 取得時に開始日付と現在日付（`st.date() == now_dt.date()`）を比較せず、60分超のイベントを一律 `urgency = f"【本日 {time_str}〜】"` と決め打ちしていた仕様欠陥を特定。
    2. **日付識別エンジンの改修**: `ev_date` と `today_date` / `tomorrow_date` を厳密判定し、【本日 HH:MM〜】、【明日 HH:MM〜】、および【M/D HH:MM〜】を正しく出力するよう改修。
    3. **TDDテスト新設 (`tests/test_suggest_calendar_dates.py`)**: 本日・明日・明後日の予定サジェスト出し分けを自動テスト化。
  - 💬 **デスクトップ秘書くん吹き出しマークダウン太字強調 (`ui/markdown_helper.py`, `gui.py`)**:
    1. **マークダウンパーサー新設 (`ui/markdown_helper.py`)**: `**太字**` の位置スパンを解析し、生のアスタリスク文字を安全に除去したクリーンテキストを生成するヘルパー関数群を実装。
    2. **Tkinter Text タグ結合 (`gui.py`)**: `CTkTextbox` 内部の `tk.Text` に対し、`md_bold` タグ（太字＋濃茶色 `#4A3728`）を構成して自動スタイリングを適用。生のアスタリスク文字が露出するUX問題を解消。
    3. **TDDテスト新設 (`tests/test_gui_markdown_parser.py`)**: 複数太字、改行混在、アスタリスク単体のエッジケースを自動テスト化。
  - 🗄️ **バックエンド `database.py` Seam分割 Phase 2 完遂 (`storage/` ＆ `database.py`)**:
    1. **ドメインRepositoryの完全分離**: `calendar_repo.py`, `sticky_repo.py`, `insight_repo.py`, `habit_repo.py`, `minigame_repo.py`, `task_repo.py` を新設し、接続・バックアップ機能を `storage/connection.py` に集約。
    2. **`storage/__init__.py` 集約エクスポート**: 全Pydanticモデルおよび全リポジトリ関数を完全網羅した `__all__` を定義。
    3. **`database.py` の純薄Facade化**: 1,721行の実体コードを完全削除し、`storage` パッケージから再エクスポートする **243行の薄型Facade** へスリム化。既存コードベースとの100%後方互換性を死守。
    4. **回帰防止テスト新設 (`tests/test_storage_seam_phase2_step2.py`)**: 全シンボルエクスポート、Facadeポインタ同一性、ドメイン別CRUD、DB自動バックアップを網羅的に自動検証。
  - 🧪 **全体テスト446件完全全緑達成 (444 passed, 2 skipped, 0 failed, 65.97s)**:
    1. **Seam分割後のテストアサーション整合性修復 (`tests/test_sync_lan_selfheal.py`)**: `sw.js` の `version.js` 一元化定数参照（SSOT）アサーションへ更新、および `pet_motion.js` 切り出し後の `updateLifeSprite` / `CHARACTERS` 配信アサーションへ強化。
    2. **Tkinter ヘッドレス/CLI環境フォールバック (`tests/test_calendar_ui_smoke.py`)**: `TCL_LIBRARY` 未設定のWindows CLI環境での `TclError` を安全に `skipTest` するよう try-except ガードを配備。
    3. **全スイート446件中 0 failure 完全合格**: デグレゼロ、後方互換性100%を自動テストで証明。
  - 📦 **バックエンド `database.py` Seam分割 Phase 1 完了 (Quality Gate APPROVED)**:
    1. **Pydantic V2 モデル群の完全分離 (`storage/models.py`)**: 13モデル（カレンダー、付箋、知識の宝庫知見、タスク、習慣、ミニゲーム、ゼロトラスト端末台帳）を完全集約。
    2. **WAL接続＆マイグレーション分離 (`storage/connection.py`)**: WALモード、`busy_timeout=30000`、`init_db` スキーマ定義・マイグレーションを集約。
    3. **`database.py` の Facade パターン化**: 2,498行から **1,960行** へ約538行スリム化。
    4. **回帰防止テスト新設 (`tests/test_storage_seam_phase1.py`)**: 4件全パス。
  - 🌟 **Web Showcase 日英完全同期 ＆ database.py Repository パターン分割設計策定完了**:
    1. **Web Showcase 日英完全同期 (`docs/neo-secretary-showcase.html` & `docs/neo-secretary-showcase-en.html`)**: 主要チップスに「🛡️ 遠隔承認リモコン (Approval Remote)」および「📜 承認監査ログ (Audit Log)」を追加。`COMPONENT_DETAILS` / `eli5-data` を最新Seam分割構成（`pet_auth, pet_audio_se, pet_particles, pet_motion, pet_ui, pet.js v1.0.0`）に同期。チートシート相互リンクの整合性を点検。
    2. **Qiita限定公開記事の確認**: 社内レビュー中ドラフト（`https://qiita.com/kangen_yamada_atsushi/private/c72a0fc7639c4111c353`）の本文・図解構成を精査。
    3. **`database.py` Repository パターン分割設計 (Facade Pattern)**: 2,498行の単一DBファイルを `storage/` パッケージ（8ドメイン）へ分割し、`database.py` を薄いFacadeとして再エクスポート維持することで71件の既存テストを100%無停止で後方互換性を死守するアーキテクチャを確定（`DESIGN_SPEC.md` Section 18、`機能ロードマップ.md` 13.7.3）。ゼロオーバーヘッド。
  - 🚑 **PWAフロントエンド 起動時SyntaxError根絶 ＆ カオス耐性フェイルセーフ初期化完了 (Quality Gate APPROVED)**:
    1. **真因究明（Why）**: `pet_motion.js` で先行宣言された `var WALK_CAPABLE_CHARS, currentCharacterId, currentActivity` を、後続の `pet.js` 冒頭で `let/const` 再宣言していたため、V8/JSエンジンがスクリプトパース時に `Uncaught SyntaxError: Identifier '...' has already been declared` を投げて `pet.js` 全体が1行目で停止。背景消失・未接続・無反応の真因を100%特定。
    2. **スコープ衝突の完全解消（What）**: `pet.js` 側の再宣言を廃止し、`typeof ... === 'undefined'` による安全な参照・同期へ改修。
    3. **古いスマホ環境（ES2020以前）互換性**: `pet_ui.js` および `pet.js` の `?.` オプショナルチェイニングを完全排除。
    4. **不滅の初期化エンジン (`initDeskPetApp`)**: `document.readyState !== 'loading'` 即時実行フォールバックと全モジュール個別の `try-catch` サンドボックス化。
    5. **コード重複排除**: `dismissCompleted` と `escapeHtml` の二重定義を委譲参照へ一本化。
    6. **独立検証者 (`quality-reviewer`) APPROVED 獲得**: P3最適化（起動時 `fetchStatus` 二重呼び出し解消）も織り込み済み。
  - 🏃‍♂️ **PWAフロントエンド Seam分割 第4弾 (`web_pet/pet_motion.js`) ＆ 第5弾 (`web_pet/pet_ui.js`) 一括完了 (TDD ＆ Quality Gate APPROVED)**:
    1. **モーション・生活・歩行エンジンの分離 (`pet_motion.js`)**: キャラ定義・プリロード、生活リズム・睡眠サイクル、大歓喜バウンスジャンプ、自律歩行（地面歩行・吹き出し追従）、なでなでインタラクションを集約。
    2. **UI・承認・Bottom Sheet の分離 (`pet_ui.js`)**: HUDトースト、サジェストカード／Glass Bottom Sheet、エージェント承認バナー（スワイプ／MediaSessionノールック承認）、時計・ポモドーロUI、エージェント稼働ライブバッジ、XSS防御（escapeHtml）を集約。
    3. **独立検証者 (`quality-reviewer`) による多角査読 ＆ 満点 APPROVED 獲得**:
       - 🛡️ **[P1] サジェストスワイプ初期化**: `setupSuggestSwipe()` を `DOMContentLoaded` に明示配備し、モバイルでのフリック切替を保証。
       - 🛡️ **[P2] `_hideBanner` 重複排除・完全統合**: `pet.js` との二重定義を解消し、スワイプ変形リセットとイベント状態初期化を含む完全版を `pet_ui.js` に一本化。
       - 🛡️ **[P2] イベント状態同期**: `currentActiveEvent = null` を確実に同期。
       - 🛡️ **[P3] エイリアス維持**: `setPetSprite` 互換エイリアスを `pet_motion.js` に配備。
    4. **`pet.js` の抜本的スリム化**: 重複コード（約915行）を削除・委譲化し、行数を 2,519行 ➔ **1,604行**（当初3,335行から通算約1,731行スリム化、半分以下に圧縮）へ削減。
    5. **回帰防止テスト新設 (`tests/test_pet_seam_motion_ui.py`)**: 6大テスト項目でファイル・シンボル・ロード順・SWキャッシュ・HTTP静的配信を完全自動検証。
  - 🌸 **PWAフロントエンド Seam分割 第3弾 (`web_pet/pet_particles.js` 切り出し) 完了 (TDD ＆ Quality Gate)**:
    1. **背景・天候・パーティクルエンジンの完全分離**: `web_pet/pet_particles.js` を新設（約600行）し、5大背景テーマ（書斎・カフェ・森・海・サイバー）、Canvas初期化とリサイズ同期、天候パーティクル（雨・雪・雷・落ち葉）、なでなでパーティクル、歓喜セレブレーション紙吹雪を完全集約。
    2. **独立検証者 (`quality-reviewer`) 指摘のP0〜P3完全反映**:
       - 🛡️ **[P0] 双方向状態同期**: `Object.defineProperty(window, 'currentEnvIndex')` および `setEnvTheme()` API 配備でDOMの `active` クラスとパーティクル種別を完全同期。
       - 🛡️ **[P1] NoSleep Canvas 参照保証**: `window.envCanvas` / `window.envCtx` をトップレベルで確実に公開し、`NoSleep`（`captureStream()`）の破損を根治。
       - 🛡️ **[P2] 不滅のアニメーションループ**: `particleLoop` および `drawEnvScene` を `try-finally` で保護し、例外時でも `requestAnimationFrame` が止まらないフェイルセーフ構造を確立。
       - 🛡️ **[P3] 放物線スプリング重力**: 紙吹雪（`spawnCelebrationConfetti`）に重力加速度 `0.14` と減衰率 `0.985` を与え、リアルでオーガニックな舞い散り物理を実現。
    3. **`pet.js` / `sw.js` / `index.html` 結合**: `index.html` で `pet_audio_se.js` 直後に配備、`sw.js` キャッシュ登録、`pet.js` 内の重複描画コード（約816行）を削除して委譲化（3,335行 ➔ 2,519行に大幅スリム化）。
    4. **回帰防止テスト新設 (`tests/test_pet_seam_particles.py`)**: 5大テスト項目でファイル・シンボル・ロード順・SWキャッシュ・HTTP静的配信を完全検証。
  - 🎵 **PWAフロントエンド Seam分割 第2弾 (`web_pet/pet_audio_se.js` 切り出し) 完了 (TDD ＆ Quality Gate)**:
    1. **Web Audio SE エンジンの完全分離**: `web_pet/pet_audio_se.js` を新設し、Web Audio API によるローカルシンセサイザー合成（サイン波・三角波・矩形波）、`unlockAudio`（多重User Gesture解錠リスナー）、チャイム音、判定音、キャラ別固有SE（秘書くん、キノコ、アザラシ、ウォンバット、カイル）を集約。
    2. **フェイルセーフ ＆ 未知キャラフォールバック**: 全関数に `try-catch` 例外ガードを配備。未知のキャラIDに対して無駄なノード生成を防止し、デフォルト（`hisho`）へ安全にフォールバック。
    3. **`pet.js` / `sw.js` / `index.html` 結合**: `index.html` で `pet_auth.js` 直後に配備、`sw.js` キャッシュ登録、`pet.js` 内の重複オーディオロジック（約120行）を削除して委譲化。
    4. **独立検証者 (`quality-reviewer`) による多角査読 APPROVED 獲得**: ライフサイクル、自動再生ポリシー、例外安全性、情緒デザインの全観点で合格。
    5. **回帰防止テスト新設 (`tests/test_pet_seam_audio.py`)**: 5大テスト項目でファイル・シンボル・ロード順・SWキャッシュ・HTTP静的配信を完全検証。
  - 🛡️ **PWAフロントエンド Seam分割 第1弾 (`web_pet/pet_auth.js` 切り出し) 完了 (TDD ＆ Quality Gate)**:
    1. **認証・自己治癒の完全Seam化**: `web_pet/pet_auth.js` を新設し、Bearer Token管理、URLクエリ即時消去（画面共有時の漏洩防止）、401時の `/api/auth/token` 再取得と自動リトライ（`_retried` ガード付き）、同一オリジン保護を完備。
    2. **`pet.js` / `sw.js` / `index.html` 結合**: `index.html` での先頭読み込み、`sw.js` キャッシュ登録、`pet.js` からの委譲呼び出し（`getSyncToken()` / `setSyncToken()`）。
    3. **独立検証者 (`quality-reviewer`) による多角査読 APPROVED 獲得**: URLサニタイズ、同一オリジン判定、FormData対応などP2改善を即座に織り込み。
    4. **回帰防止テスト新設 (`tests/test_pet_seam_auth.py`)**: 5大テスト項目でファイル・シンボル・ロード順・SWキャッシュ・HTTP静的配信を完全検証。
    5. **ChatGPT指摘の監査表現安全化**: README_en、Showcase、チートシートの `tamper-proof` を `tamper-resistant and persistent trail` に改訂。
  - 🏛️ **バージョン定数一元化 (`version.js` 動的配信 ＆ PWA結合) 完了 (TDD)**:
    1. **Single Source of Truth 確立**: `version.py` (`__version__ = "1.0.0"`) を唯一の真実の源として確定。
    2. **動的配信エンドポイント新設 (`local_sync_server.py`)**: `DeskPetSyncHandler.do_GET` において、`/version.js` および `/web_pet/version.js` への要求に対し、`self.APP_VERSION` / `self.WEB_PET_CACHE_NAME` を含む JavaScript を動的生成・レスポンス（Cache-Control: no-cache）。
    3. **Service Worker ＆ フロントエンド結合 (`web_pet/sw.js`, `web_pet/pet.js`, `web_pet/index.html`)**: `sw.js` 冒頭で `importScripts('./version.js')` を実行し `CACHE_NAME` を自動解決。`pet.js` のキャッシュパージを `window.WEB_PET_CACHE_NAME` 参照へ移行。`index.html` の先頭に `<script src="version.js"></script>` を配備。散弾銃手術（Shotgun Surgery）を完全根絶。
    4. **TDD 単体テスト新設 (`tests/test_version_endpoint.py`)**: エフェメラルポートでの HTTP 疎通、ヘッダー、動的追従性、静的フォールバック実在を自動検証。
  - 🔍 **外部AI (GitHub Copilot) ブラインドレビュー知見統合 ＆ 6大専任ペルソナ総合深層監査完了**:
    1. **総合監査報告書策定 (`docs/code_review_report_20260914_deep_audit.md`)**: 総合格付け **S+ (9.2/10点・上位0.5%)**。Copilot が絶賛した「AI Agent Governance / Remote Approval Hub としての稀有な市場価値」と「NW×PM×AIの運用設計」を正式統合。
    2. **知見永続化**: `manage_adr`（codebase-memory ADR）および `remember_boss_insight`（知識の宝庫）により知見を永続記録。
    3. **ドキュメント4点セット同期**: `00_ドキュメント一覧.md`, `DESIGN_SPEC.md`, `機能ロードマップ.md`, `active_context.md` を完全同時同期。
- **過去完了アクション (2026-09-13)**:
  - 🎨 **Qiita記事ドラフト (`docs/articles/qiita_draft_20260912.md`) ビジュアル完全強化**:
    1. **メインバナー配置**: 冒頭アイキャッチに `banner_main.jpg` を配備。
    2. **Before/After情景画像生成**: 「AIの承認待ちダイアログで画面に縛られ疲弊するBefore」vs「卓上スマホ（Desk Pet）でコーヒーを飲みながらリラックスしてワンタップ承認するAfter」の対比イラスト（`qiita_scene_before_after.jpg`）を生成・配備。
    3. **4大インフォグラフィック配置**: 古いスマホ転生（`cs02_mobile.jpg`）、4ステップMCPリモートスマート承認（`cs04_agent.jpg`）、完全ローカルLLM＆プライバシー保護（`cs05_localllm.jpg`）をストーリーの要所に埋め込み。
    4. **Showcase ＆ チートシート日英両対応リンク**: 記事末尾の誘導リンクに英語版Showcase/チートシートも完備。
  - 🌐 **グローバル展開: README・Showcase・公式チートシート・全インフォグラフィック完全英語化**:
    1. **READMEビジュアル ＆ アーキテクチャ図**: `README_en.md` および `README.md` にメインバナー画像、Showcase/チートシート公式バッジ、Mermaidダイアグラム、ASCIIデータフロー図を配備。海外エンジニアが3秒で本質（3-Tier Policy + Audit Log + Mobile Cockpit）を理解できる構成へ強化。
    2. **公式チートシート英語版新設 (`docs/guides/NEO_HISHO_CHEAT_SHEETS_en.html`)**: 初期セットアップ、スマホQR/VPN接続、統合手帳、エージェント遠隔承認、ローカルLLM、FAQの全5大セクションを自然なプロフェッショナル英語で完全翻訳。日本語版との双方向トグルを完備。
    3. **公式インフォグラフィック全6枚の完全英語化 (`docs/guides/assets/`)**: メインバナー（`banner_main_en.jpg`）およびチートシート①〜⑤の全インフォグラフィックを超高精細AI生成。スマホ画面内の「Neo-Secretary」やノートPC内の「Settings」に至るまで1文字の日本語も残さず完全英語化。
    4. **5大チートシート Raw Markdown 英語版新設 (`docs/guides/cheatsheet_0X_..._en.md`)**: GitHubリポジトリ上で直接ドキュメントを閲覧する海外開発者のため、①〜⑤の全Markdown版を英訳し、インフォグラフィック画像を埋め込み配備。
    5. **動く全体鳥瞰図 Web Showcase 英語版新設 (`docs/neo-secretary-showcase-en.html`)**: `eli5-data` および `eli5-ui` JSONを完全英訳し、専用アーキテクチャ図（`neo-secretary-architecture-en.html`）をiframe結合。シグナルトレースやインタラクティブSVG描画が完全英語で動作する世界水準のShowcaseを配備。
    6. **GitHub Pages 連携保護**: `.gitignore` に `!docs/neo-secretary-showcase-en.html`, `!docs/neo-secretary-architecture-en.html` を追加し、Pagesでの404を恒久防止。
    7. **ドキュメント4点セット同期**: `docs/00_ドキュメント一覧.md`、`docs/specs/DESIGN_SPEC.md`、`docs/specs/機能ロードマップ.md`、`active_context.md` の4大ドキュメントを完全同期。
  - 🎭 **演出のコントラスト最適化 ＆ 承認時引き締め（PWA v5.32）**:
    1. **承認時ジャンプの撤去**: ボスのUX審美眼に基づき、Strict承認タップ時の不自然な歓喜ジャンプを即座に撤去。承認時は「承知いたしました！作業を続行します(｀・ω・´)ゞ」とキリッと引き締め、PC側ペットも集中作業（Focus）へ遷移。
    2. **歓喜ジャンプの特権化**: CSS物理バウンスジャンプ（`@keyframes celebrate-jump`）×ドット絵パラパラ×紙吹雪パーティクル大噴射（18個）は、「AIがタスクを完了した時（完了通知）」限定の最高報酬演出へと純化。
    3. **PWAキャッシュ更新**: `web_pet/sw.js` および `web_pet/pet.js` を `v5.32` へ更新。
  - 🎉 **ペット大歓喜ジャンプモーション ＆ ドット絵パラパラ ＆ 紙吹雪実装 (PWA v5.31)**:
    1. **CSS物理バウンス (`@keyframes celebrate-jump`)**: 溜め ➔ 上空ジャンプ ➔ 浮遊 ➔ 着地クッション ➔ リバウンドのオーガニックスプリングアニメーションを `web_pet/index.html` に配備。足元シャドウも連動して薄く縮小。
    2. **ドット絵パラパラアニメーション**: 各キャラ固有の `celebrate_1` ⇄ `celebrate_2` ⇄ `celebrate_3` ⇄ `happy` を220ms間隔で切り替え、手足をパタパタさせるドット絵モーションを開通。
    3. **紙吹雪大噴射**: 🎉✨🌟💖🎊👏⭐🎈 のお祝いパーティクル18個を扇状に大噴射。
    4. **完全結線 ＆ トースト残骸根絶**: 完了通知受信時、PC側celebrate受信時に `triggerCelebrateReaction` を連動。承認タップ時に出ていた上部トーストの残骸を完全廃止し、ペット頭上の漫画吹き出しに一本化。
  - 🎨 **全着信トースト（完了・リマインダー・buzz）完全廃止 ＆ バナー・コミック吹き出し純化**:
    1. **作業完了・リマインダー・buzzトーストの完全撤去**: `web_pet/pet.js` 内で `active_event`、`latest_notification`、`due_reminders`、`data.buzz` のすべての着信時 `showToast` を完全削除。
    2. **画面純化**: バナー表示時はバナーのみ、完了・通知時はペット頭上のコミック吹き出しとセレブレーション歓喜のみに一本化。上部HUDトーストの被りを100%根滅。PWAバージョンを `v5.30` に更新。
  - 🎨 **ペット吹き出し（Comic Balloon A案）刷新 ＆ しっぽ表示・歩行追従**:
    1. **しっぽ切り取り（クリッピング）根治**: `.speech-bubble` の `overflow-y: auto` が要素外の `::after` / `::before`（下向き三角形のしっぽ）をブラウザで切り取っていたバグを特定し、`overflow: visible !important;` へ修正＋しっぽサイズ拡大。
    2. **ペット歩行連動追従**: カイル等のペットが部屋を左右にトコトコ歩く（`petWanderTick`）のに合わせ、吹き出しの横位置（`style.left`）もペットの頭上にリアルタイム連動（22%〜78%の画面端はみ出し防止クランプ付き）。
    3. **着信時トーストの廃止**: `web_pet/pet.js` で承認着信時の重複 `showToast` を完全削除し、中央の操作バナーに視線を一本化。PWAキャッシュを `v5.29` に更新。
  - 🛠️ **AUTO_ALLOW滞留・通知無限ループバグ根治 ＆ PWA多重防壁配備**:
    1. **AUTO_ALLOW即時pop**: `api_agent_bridge.py` でポリシー自動許可（AUTO_ALLOW）判定時、`hub.pending_requests.pop()` を即座に実行し保留辞書から完全排除。
    2. **get_latest_pendingクリーンアップ**: `local_sync_server.py` で `status != 'pending'` の解決済みオブジェクトを即座に破棄して `history` へ移動。真に保留中のリクエストのみ配信。
    3. **PWA側ローカル重複遮断Set (`_resolvedRequestIds`)**: 一度でも承認/却下した `request_id` をローカルSetに記録し、同一リクエストの再表示をブラウザ側でも100%遮断。PWAバージョンを `v5.27` に更新。
  - 🛠️ **PWAバナー透明化（opacity: 0ゾンビ化）＆ トースト上書きバグ根治**:
    1. **トースト上書きブロック**: `web_pet/pet.js` で `pending_approval` 着信時に `window._notifDisplayedAt = Date.now()` を記録し、同一周期の `data.buzz` による `showToast('📲 ボスが呼んでいます！')` 上書きを1.5秒間厳格に抑制。
    2. **不透明度・変形完全リセット**: スワイプdismissで付与されたインラインスタイル `opacity: 0` / `transform` が残存する問題を、`fetchStatus` 表示時および `_hideBanner` で `opacity = '1'` / `transform = ''` / `transition = ''` を明示的にリセットするよう修正。
    3. **PWAキャッシュ更新**: `web_pet/sw.js` および `web_pet/pet.js` を `v5.26` へインクリメントし、即時パージ・最新コード強制反映。
    4. **実機承認実証**: `ask_human_approval` (strict: `git reset --hard HEAD~1`) のテスト発行を行い、ボスによるスマホ上でのリアルタイム「✅ 承認」タップとサーバー応答（status: success, decision: approve）を完全確認。
  - 🎬 **Block 4: 広報・拡散・実機実証（動画 ＆ Qiita記事）完了**:
    1. **30秒デモ動画絵コンテ・実写撮影ガイド (`docs/guides/DEMO_VIDEO_STORYBOARD.md`)**: 開始3秒フック、スマホ卓上コックピット覚醒、神の一手（ワンタップ承認）、AI爆速疾走＆ペット歓喜のカット割りと発火用テストワンライナーを完備。
    2. **Qiita記事最終調整 (`docs/articles/qiita_draft_20260912.md`)**: 3段階判定（Auto-Allow/Prompt/Strict）、監査ログ（Audit Log）、全404テスト全緑、Showcase/チートシートリンクを網羅した完全版へアップデート。
  - 🛡️ **Block 3: 失敗モード堅牢化 ＆ PWA危険度UI連携完了 (TDD)**:
    1. **失敗モード・セキュリティ境界テスト (`tests/test_agent_failure_modes.py`)**: 期限切れ遅延応答拒否、自己承認（同一IP）拒否、重複タップ・再送の冪等性保証、HTTP API レスポンス契約テスト（計7件）新設・100%パス。
    2. **冪等性保証 (`local_sync_server.py` & `api_agent_bridge.py`)**: 既済リクエストの重複判定を history から逆引きし、`already_resolved` / `duplicate: True` で安全に応答。
    3. **PWA 危険度別バナー ＆ 警告シート (`web_pet/index.html` & `web_pet/pet.js`)**: strict（深紅パルス/警告バイブ/シート警告）と prompt（琥珀色）の差別化、自己承認エラー誤表示抑止。
  - 🛡️ **Block 2: Agent Approval Platform への昇格完了 (TDD)**:
    1. **Agent Approval Protocol (`agent_adapter.py`)**: 共通DTO `AgentApprovalRequest` (Pydantic v2) および Claude Code / Cline / 汎用エージェントのアダプター自動正規化基盤を新設。
    2. **Approval Policy 3段階判定エンジン (`approval_policy.py`)**: 🟢 Auto-Allow (閲覧・テスト自動即時許可) / 🟡 Prompt (通常編集) / 🔴 Strict (破壊的変更) のコマンド判定エンジン新設。
    3. **Audit Log 承認監査ログ基盤 (`audit_logger.py` & `database.py`)**: SQLite `approval_audit_logs` テーブルおよび非同期安全な `AsyncAuditLogger` を配備。
    4. **エンドツーエンド統合 (`api_agent_bridge.py`)**: `handle_agent_ask` で上記3モジュールを結合。Auto-Allow によるゼロ秒即時承認と全監査ログ永続化を開通。
    5. **TDDテスト4本新設**: `test_agent_adapter.py`, `test_approval_policy.py`, `test_audit_logger.py`, `test_agent_approval_flow_e2e.py`。
  - 🚀 **GitHub Release v1.0.0 正式公開**: クリーンZIP（100.4MB）を添付し世界へ出荷完了。update_checker開通。
- **直近Nextアクション**:
  1. 📱 **ボスによる30秒実写撮影（5分）**: 絵コンテに従い、卓上スマホの赤バナーワンタップ動画を撮影。
  2. 📝 **Qiita記事公開 ＆ X（Twitter）発信**: 動画GIFを添付して記事公開・世界へシェア。
  3. 🏛️ **v1.1.0 スプリント: Codebase Design ＆ Seam 分割リファクタリング (P1)**:
     - ✅ **第1弾完了**: `web_pet/pet_auth.js` 切り出し ＆ `tests/test_pet_seam_auth.py` 完備。
     - ✅ **第2弾完了**: `web_pet/pet_audio_se.js` 切り出し（Web Audio SE エンジン独立化）＆ `tests/test_pet_seam_audio.py` 完備。
     - 🔲 **第3弾**: `web_pet/pet_motion.js` 切り出し（物理演算・歩行・歓喜ジャンプ制御）。
     - 🔲 **第4弾**: `database.py` (2,498行) の Repository パターン分割（`task_repo.py`, `calendar_repo.py`, `insight_repo.py`, `audit_repo.py`）。



---

（以下、第1段で分離した 2026-09-13 以前の履歴）

## 🟢 2026-09-13 3社AIブラインドレビュー ＆ Grilling戦略合意
- **背景**: 公開リポジトリを ChatGPT（市場・戦略トップダウン）、Grok（実装・配布ボトムアップ）、Genspark（文脈統合）の3社AIにブラインドレビューさせ、Grilling壁打ちを実施。
- **確定したプロダクト三層構造**:
  1. **【コア (A)】AIコーディングエージェントの遠隔承認リモコン**: 90日後に使われていたい本命。世界で戦える独自の痛点解決。競合はSlack/通知bot程度で、物理デバイス×キャラの承認面は極めて希少。
  2. **【世界観 (B)】ドット絵ペット・卓上相棒**: 愛着装置・ブランド。自作キャラMod基盤（フォルダに置くだけ）のみ最小実装し、キャラ量産はコミュニティ開放。既存ミニゲーム・演出は現状凍結。
  3. **【居場所 (C)】手帳・TODO・習慣・iCal**: 承認リモコンを常駐させるための背景。TickTick/Notionと戦わない（主役にしない）。現状維持。
- **ChatGPT & Grok 指摘によるコア機能昇格 (P0 / v1.1.0)**:
  - **Agent Adapter**: 共通DTO `AgentApprovalRequest` を策定し、Claude Code, Cline, Cursor, Codex, OpenCode を包含する「AI Agent承認プラットフォーム」へ昇格。
  - **Approval Policy**: 🟢 Auto-Allow (test/status) / 🟡 Prompt (install/edit/commit) / 🔴 Strict (rm/push --force) の3段階判定エンジンで認知負荷を激減。
  - **Audit Log**: 誰が・何を・いつ承認したかをSQLite `approval_audit_logs` に記録し、企業のセキュリティ監査にも耐えうる信頼性を獲得。
- **Grok指摘によるP0盲点の即時手当**:
  1. **リポジトリAboutが「javascript AI秘書ペット」**: Python実装と矛盾し第一印象を壊しているため `Remote Approval Companion & Desktop Pet for AI Coding Agents (Claude Code, Cline, Cursor)` へ即時修正。
  2. **v1.0.0 なのに GitHub Release が0本**: アプリ内 `update_checker.py` が空振りする。最新コード（OpenCode対応・トレイ終了三重防御・ストリーミング）で再ビルドしたzipをRelease添付して開通。
  3. **「ゼロトラスト」の表現**: 「ローカル完結・最小権限・承認必須」と誠実に説明する方が技術者から信頼される。
  4. **Tkinterの限界への回答**: PC側は引き算（スマホ接続時はPCペット自動非表示・操作面はPWAへ全面移管）。中長期（v2.0）でTauri/PyWebViewへ移行するADRを記録。
- **広報・動画戦略**:
  - 30秒デモ動画は **実写（人間の指がスマホ承認する神の一手）× Google Artemis（PWA機能ラッシュ自動録画＆フロント実機自動テスト）** のハイブリッドで制作。
  - 完成動画またはGIFを埋め込んだ状態でQiita記事を投稿し、効果を最大化する。

## 🟢 2026-09-09 Sprint C-1/C-2 ＆ Jules夜間タスク根治 (Cline)
- **Jules タスクA (ResourceWarning nul/cp932)**: 根本原因は `llama_cpp/_utils.py` が import 時に `open(os.devnull,"w")`(encoding指定なし→cp932) を2本開き放し。`llm_factory.py` に `_close_llama_cpp_devnull_leaks()`/`_register_llama_cpp_devnull_cleanup()`(atexit・冪等) 新設、llama import 直後に登録。
- **Jules タスクB (invalid command name ...update/check_dpi_scaling)**: 根本原因は CustomTkinter 内部の `ScalingTracker`/`AppearanceModeTracker` が root 破棄後も after 自己再スケジュール。`ui/tk_teardown.py` 新設 (トラッカー辞書クリア→Tcl `after info` 全件キャンセル→destroy + quiet ガード)。`gui.py` 終了処理/`main.py` finally/`tests/test_calendar_ui_smoke.py` tearDown に統合。
- **Jules タスクC (P1-B 第一歩)**: `api_devices.py` 新設 (`handle_get_devices(ctx)->bool`)、`local_sync_server.py` に `GET_PATH_HANDLERS` ディスパッチ導入。Bearer 認証は do_GET 側で適用。
- **Sprint C-1**: `LICENSE` (MIT・Copyright Siitake-man 2026) 新設、README に CI/License/Python バッジ＋ライセンス節リンク化。
- **Sprint C-2**: `.github/workflows/ci.yml` 新設 (windows-latest × Python 3.11/3.12/3.13、unittest discover、`fetch-depth:0` 機密スキャンゲート、PYTHONUTF8=1)。`llama_cpp_python` は CI 除外インストール→`test_local_llm_cache.py` に `skipIf` ガード (ローカル挙動不変)。
- **TDD**: `tests/test_tk_teardown.py` (6件) / `tests/test_api_devices_seam.py` (4件) / `tests/test_llama_devnull_cleanup.py` (4件) 新設。学習メモ: `tk.Tk().destroy()` 後は `winfo_exists()` が False ではなく `TclError` を raise する (=完全破棄の証)。
- **コミット**: 未コミット (ボス検証リラン後の手動コミット推奨)
- **追記 (2026-09-12 実機運用フィードバック)**:
  1. **OpenCode 400 MissingSessionID 根治**: OpenCode Zen (Console Go) が chat/completions に `x-opencode-session` ヘッダー必須化 (2026-09 仕様変更)。`llm_factory.py` にプロセス内安定UUID (`_OPENCODE_SESSION_ID`・`.env` の `OPENCODE_SESSION_ID` で上書可) を `default_headers` 注入。実機 200 応答確認済み。TDD: `tests/test_opencode_session_header.py` (4件)。
  2. **トレイ「終了」でプロセス残存を根治**: トレイの on_quit が `root.quit()` (自前ループでは no-op) を呼んでいたため、トレイのみ消えてプロセスが残存 (多重起動検知の誤発火)。`SystemTrayManager.request_quit()` 新設 → `gui.quit_app` へ委譲。TDD: `tests/test_system_tray_quit.py` (3件)。
  3. **仕様変更追随力の強化**: ① `llm_factory.format_llm_error_hint()` 新設 — provider 由来の具体的エラー型 (例: MissingSessionID) を吹き出しに1行表示 (APIキー/Bearer/JWTはマスク)。`main.py` の推論エラー経路に適用。TDD: `tests/test_error_hint.py` (5件)。② `tools/check_llm_health.py` 新設 — 全設定済みプロバイダに1トークン ping (httpx経由・urllib UAはCF 1010ブロック回避)。TDD: `tests/test_llm_health.py` (4件)。テスト基準 **358件**。
  4. **ロックソケットの監視可能化**: 二重起動防止ロック (54321) が bind のみで listen していなかったため netstat/Get-NetTCPConnection に現れず、残留プロセスの掃除が不可能だった。`main.acquire_single_instance_lock()` 新設 (bind＋listen)。TDD: `tests/test_single_instance_lock.py` (1件)。テスト基準 **359件**。
  6. **応答速度スプリント (A1-A3＋Bストリーミング・2026-09-12)**: 20-30秒応答の増幅要因を診断 (①タイムアウト15秒×リトライ=30秒エラー ②推論モデルの思考トークン ③Planner2往復 ④ainvoke完全待ち)。対策: **A1** `LLM_REQUEST_TIMEOUT_SEC` 15→60秒 / **A2** OpenCode に `extra_body={"reasoning_effort":"low"}` 注入 (実機200応答確認済み・`.env` の `OPENCODE_REASONING_EFFORT` で上書き・空で無効化) / **A3** システムプロンプトにツール連打抑制の効率規律を追加＋`recursion_limit=40` / **B** 🆕 `agent_stream.py` — `run_agent_streaming()` が `astream_events(v2)` を消費しトークン逐次表示＋ツール開始通知＋throttle (0.05s)。`main.py` は provider 分岐 (LOCAL_GGUF→従来ainvoke / その他→ストリーミング)。TDD: `tests/test_reasoning_effort.py` (5件)・`tests/test_agent_stream.py` (5件)。テスト基準 **372件**。**実機検証OK (2026-09-12): トークン逐次表示を確認・応答大幅短縮 (ボス報告「少しずつ会話が出ました・かなり早くなりました」)**。残タスク: スクショ撮影 → README画像有効化 → v1.0.0 リリース。
  7. **Gemini外部レビュー対応 (P0/P1全消化・2026-09-12)**: レビュー指摘をファクト検証のうえ実施。**P0-1** tools のワンオフ生成スクリプト5件 (C:\Users\bonob 絶対パス直書き) を .gitignore 化 (追跡解除は `git rm --cached` がボス手動) / **P0-2** ルート学習メモを docs/learning-memos へ移動＋`学習メモ*.md` 無視化 (`git add -A` 誤コミット防止) / **P0-3** `.gitignore` を `docs/*` ＋選択的例外 (`!docs/guides/`・DESIGN_SPEC・機能ロードマップ・MCP_INTEGRATION) に改訂し README の docs リンク404を解消・README 誤字/化け文字を一括修復 (テーマ行・見出し・構成ツリー・リンク先) / **P1-1 ゼロトラスト根治**: `/api/auth/token` の発行を「ペアリング開放中 or ループバック」のみに限定 (共有Wi-Fiでの無条件発行ホールを塞ぐ・LAN再接続はQR再ペアリング or トークン保持)。TDD: LAN シミュレートテスト2件 (`_is_loopback` 偽装) / **P1-2** `agent_stream` に最終トークンフラッシュ追加 (throttle 取りこぼし防止)。テスト基準 **374件**。
  8. **第3次レビュー (コード本体・2026-09-12) 対応**: ①**ゼロトラスト根治**: `_check_auth` の「同一LANなら GET は無条件許可」を撤廃し **ループバックのみ**へ (共有Wi-Fi の第三者による /api/status 覗き見を封鎖・TDD: LAN偽装テスト) ②**OOM DoS 防御**: `do_POST` に Content-Length 上限5MB＋数値ガード (超過は413・TDD: 生ソケットで巨大ヘッダ検証) ③**exe書込クラッシュ根治**: `easter_egg_engine.STATE_PATH` を `Path(__file__).parent` → `app_paths.get_app_root()` に統一 (PyInstaller 解凍先は読取専用・TDD: app_root 追従テスト) ④**Claudeの100%失敗フォールバック撤去**: langchain-anthropic 未導入時は pip install ヒント付き ImportError で安全に縮退 (OpenAI互換でのAnthropic URL偽装を削除・TDD)。⑤`web_tools` の同期HTTPは「LangGraphのsyncノードはワーカースレッド実行のためUIフリーズは生じない」と判定し **v1.0.x 改善へ延期**。テスト基準 **379件**。
  9. **CIゲート偽陽性の根治 (2026-09-12)**: 新テスト `test_error_hint.py` のダミーキー (`sk-abc...`) が機密スキャナに12件検出され CI ゲートが赤化 → `tools/scan_git_secrets.py` に `is_scan_excluded()` を新設し、除外リストを「スキャナ自身＋ダミーキーを含むテスト (`test_error_hint.py`)」としてデータ駆動化 (TDD 2件)。検出力は維持 (通常のソース/テストは除外しない)。検出12件は全て偽陽性 (実キーでは無いためローテーション不要)。**LAN未認証GETの正セマンティクスは 401** (403は失効端末・エージェント専用API用) と確定。テスト基準 **381件**。
  10. **CI失敗の根治 (2026-09-12)**: 全3ジョブが failure (1m40s)。真因は **`langgraph` が requirements.txt に未宣言** (ローカル venv には 1.0.10 が入っていたためローカルでは緑・CIでは `import langgraph` 失敗で赤)。`langgraph==1.0.10` を追加し、**再発防止テスト** `tests/test_requirements_pinning.py` を新設 (実行時必須12依存の宣言を凍結・プロジェクト全体のimport走査で他に未宣言のサードパーティが無いことを確認済み)。テスト基準 **382件**。
  11. **CI失敗②の根治 (2026-09-12)**: Annotationsに `ImportError: cannot import name 'ExecutionInfo' from 'langgraph.runtime'` が出て確定。真因は **LangGraph の同伴パッケージ (langgraph-checkpoint / -prebuilt / -sdk / langsmith) が未固定**で、CIのpipがローカルと異なるバージョン組み合わせを解決したこと (部分固定の罠)。ローカルで実証済みの `langgraph-checkpoint==4.0.1` / `langgraph-prebuilt==1.0.8` / `langgraph-sdk==0.3.9` / `langsmith==0.7.14` を requirements.txt に追加固定。**CI診断の自動化**として、ci.yml が失敗テスト名と例外詳細・トレースバック末尾を GitHub Annotations に `::error::` で出力するよう改造 (1往復で真因特定できる)。また `.env.example` が `.env.*` パターンで未コミットだった問題を `!.env.example` で根治 (ユーザーのREADME手順も修復)。
  5. **destroy 中断 (can't delete Tcl command) の三重防御で完全根治**: 計測計装で「トレイ→キュー→quit_app までは正常・destroy が例外で中断」を特定。真因は CTk トラッカーが毎tick同一クラスメソッド名を再登録し `_tclCommands` に重複蓄積 → `after_cancel` 内部の deletecommand で不整合 → destroy 中断。対策: ①cancel は生 `tk.call("after","cancel")` ②`dedupe_tcl_commands()` 新設 ③destroy 失敗時は `tk.call("destroy", root._w)` フォールバック。実機で完全終了を確認 (root破棄・プロセス消滅・2026-09-12 14:12)。テスト基準 **361件**。

## 🟢 2026-09-06 集中開発4サイクル完全達成サマリ
- **成果**:
  1. **サイクル1 (UX/音声)**: `ui/settings_window.py` Tab 2 に「🔊 PC音声読み上げ通知」トグル追加。スマホPWA 予定リマインダー紫バナー（`.reminder`）、チャイム音、パルスバイブレーション、表情変化を実装。
  2. **サイクル2 (常駐性)**: `ui/system_tray.py` (`pystray` + `PIL`) 新設。右クリックメニューから「ペット表示/非表示/設定/手帳/QR/終了」を提供。Tkinter スレッドセーフディスパッチ統合。
  3. **サイクル3 (ゼロトラスト端末台帳)**: `database.py` に `devices` テーブルおよび CRUD 実装。トークン SHA-256 ハッシュ照合・失効判定（403）・`last_seen` 自動更新、`/api/devices` (GET) および `/api/devices/revoke` (POST) ループバック限定エンドポイント新設。
  4. **サイクル4 (自己治癒アーキテクチャ深化)**: `server_watchdog.py` への watchdog 分離（連続2回失敗ヒステリシス、指数バックオフ、終端契約）。`LocalSyncServer` の Divergent Change 解消。
  5. **ホリスティック監査・P1即時対応**: `touch_device_last_seen` の DB ロック耐性（Fail-Safe）、`/api/devices/revoke` のループバック制限、機密スキャナ偽陽性除外（`tools/scan_git_secrets.py` CLEAN）。
  6. **テスト整備**: `tests/test_device_registry.py` (5件)、`tests/test_server_watchdog_standalone.py` (3件)、`tests/__init__.py` 新設。
- **次回 Sprint C**:
  - **CI/CD パイプライン整備 (.github/workflows/ci.yml)**: Python 3.11-3.13 マトリクス自動テスト ＆ 機密スキャンゲート。
  - **README/LICENSE 最終整備 ＆ v1.0.0 リリースタグ ＆ GitHub 公開**。
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

## 🟢 2026-09-02 戦略grilling完了: 引き上げ計画＆3アプリ連携構想（ボス×Cline壁打ち確定）
- **目的定義 (質問1)**: 秘書くんは **GitHub公開によるポートフォリオ(キャリア証明)** が主目的。副産物としてサーバー領域(GCP)学習
- **確定した設計判断**:
  1. **TLS は Non-Goal 宣言** (脅威モデル=信頼できるLAN)。将来: v2 ネイティブアプリ化で証明書ピンニング / v3 BLE近接チャンネルで解消パスをADR記録
  2. **トークンのデバイス台帳化** (devices テーブル: 個別トークン・token_hash保存・個別失効・last_seen)
  3. **400化構造改革を次回スプリント第1弾に** (ApiContext.write_json を遅延ヘッダー送出化 → 全ハンドラほぼ無変更でステータスコード制御可能に)
  4. **レートリミットは「401失敗のIP別カウント→締め出し」方式** (429 + Retry-After。ATMの暗証番号ルールのWeb版)
  5. **CI (GitHub Actions) は公開の前に整備** (unittest + tools/scan_git_secrets.py ゲート + 緑バッジ)
  6. **Non-Goals 6点を宣言**: TLS実装 / 監査ログDB永続化 / SSE・WebSocket強化 / 多言語・マルチプラットフォーム / Docker・K8s(本アプリには不適合) / ミニゲーム・演出追加
- **スプリント計画**: **Sprint A**(400化+レートリミット+重複ガード抽出, 3-4h) → **Sprint B**(デバイス台帳+watchdog分離・ヒステリシス, 3-4h) → **Sprint C**(CI+README/LICENSE+機密監査最終+公開踏切, 3h)
- **3アプリ連携構想 (俯瞰図: docs/architecture/federation-20260902.html)**: 秘書くん(実行/Windows) × お尋ね者(記録/独立アプリ・Genspark設計済み) × EmoLog Sync(振り返り/GCP・Next.js+Firebase+Capacitor) の三つ巴。**統合はMCP契約+共通Google認証のみ**で、コード共有・窓口アプリは作らない
- **リポジトリ戦略**: 3リポジトリ独立運用。**お尋ね者用に新規リポジトリ `otazunemono` を作成**(Genspark成果物をgit管理化)。公開時にGitHub プロフィールREADMEで相互リンク
- **K8s homelab 構想は GCP(Firebase)学習トラックに一本化**(Cloud Run/Firestore/Firebase Auth が直接キャリア価値)
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

## 🟢 2026-09-02 Block4: git履歴機密監査 CLEAN（Cline実装）
- **監査ツール恒久化**: `tools/scan_git_secrets.py` 新設 (Phase J 公開準備の必須ゲート)。git履歴全体 (--all -p) を機密パターン (Google/OpenAI/sk-proj-/Anthropic/GitHub/Slack/AWS/秘密鍵/JWT) でスキャン＋機密ファイル (.env/*.db/*.gguf/*.pem/.sync_token 等) の追加コミット履歴検査。検出値は先頭6文字のみ表示のマスク設計 (レポート二次漏洩防止)
- **TDD実証**: `tests/test_secret_scanner.py` 6件新設。テストが `sk-proj-` (ハイフン含有) の検出漏れを発見 → パターン追加で修正 (TDDの効果を実証)
- **監査結果**: **CLEAN** (機密パターン0件・機密ファイル履歴0件・SCAN_EXIT=0)。※簡易PowerShellスキャンの1件ヒットは `Select-String` 大小文字区別なしによる `task-xxx` 部分一致の偽陽性と確認 (CaseSensitive で0件)
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

- **脆弱性是正**: 全レスポンスに付与されていた **`Access-Control-Allow-Origin: *` を廃止**し、同一オリジン (PWA配信元) のみ Origin エコー方式へ変更 (`local_sync_server._set_cors_headers`)。**脆弱性の実態**: スマホのブラウザで開いた任意のWebサイトが `GET /api/status` (LAN内トークン不要) をクロスオリジン読み取り可能な情報漏洩経路。PWAは同一オリジン配信のため機能影響なし
- **脅威モデリング**: `docs/security_assessment_20260902.md` 新設 (資産/攻撃対象面・既存防御6点の確認・是正記録・残存リスク R1-R5 と推奨対策)。総合評価 B+ → A-。R1 (TLS化) は社外展開前必須と記録
- **既存防御の確認済み**: 256bitトークン+`hmac.compare_digest` / ペアリングFail-Closed / AGENT_ONLY_PATHS / 自己承認IP一致検査 / regenerate()
- **TDD**: `tests/test_cors_hardening.py` 4件新設 (Red 2件失敗確認 → Green)。**全271テスト OK** (基準線267 → 271) / py_compile OK
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

- **改修内容**: `LocalSyncServer` に **自己治癒watchdog** を実装 (2026-09-02 ディープ監査の残存リスク「スリープ復帰時の再バインド自動復帰テスト未整備」対策)。周期 (5秒) ヘルスプローブ (`is_healthy()`: スレッド生存＋ループバック疎通) で serve_forever スレッド死亡を検出し、**解決済みポート (`_bound_port`) へ再バインド**して自動復旧。port=0 (エフェメラル) 起動時も再起動でポートが変わらない
- **終端契約**: `stop()` は `_stop_event` セット → httpd shutdown/close → スレッドjoin → watchdog join で **ゾンビ再起動を構造的に防止** (proactive_scheduler.stop() のプラグインクリア契約と同型)
- **TDD**: `tests/test_server_watchdog.py` 4件新設 (Red: is_healthy 未実装を確認 → Green)。スレッド強制停止→自動再起動・同ポート維持・健全サーバー誤再起動なし・stop後ゾンビなし。**全267テスト OK** (基準線263 → 267) / py_compile OK
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

- **改修内容**: `api_tasks.py` 7アクション (complete/reopen/toggle_habit/add_habit/quick_add_task/update/delete) の受信パース (`json.loads` → 生dict操作) を `sync_dtos.parse_request` による **Pydantic リクエストDTO型付け** へ移行 (Primitive Obsession 解消)。新設DTO: TaskActionRequestDTO / HabitActionRequestDTO / AddHabitRequestDTO / QuickAddRequestDTO / UpdateTaskRequestDTO
- **設計**: `extra=allow` で未知フィールド透過 (PWA契約保護)・`model_fields_set` で「明示送信キー」と「欠落」を区別 (update_task の null=未指定契約を完全維持)。壊れたJSON/空ボディ/非オブジェクトは `parse_request` が None → ハンドラが **"invalid request body"** 明示エラー応答 (旧: Python例外メッセージがそのまま応答される)。文字列 "7" → int 7 の型正規化も実施
- **ファクト更正**: 引き継ぎ書の「db_tools.py 内部の生辞書」は誤り → `db_tools.py` は Pydantic モデル直接使用の文字列アダプタで dict処理が主ではない。実体は api_tasks.py の受信パースだった
- **TDD**: `tests/test_action_request_dtos.py` 12件新設 (Red: ImportError確認 → Green)。**全263テスト OK** (基準線251 → 263) / py_compile OK
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

## 🟢 2026-09-02 無応答200 → 明示エラー応答化（Cline実装）
- **改修内容**: 既知アクションのパラメータ欠落・GUI未起動時に**無応答200 (空ボディ)** だった旧仕様を廃止し、**明示エラーJSON** (`{"status": "error", "message": "..."}`) を返すように変更。対象は全10ガード箇所: api_tasks.py 7件 (complete/reopen/toggle_habit/add_habit/quick_add_task/update_task/delete_task の task_id・habit_id・title・text 欠落) + api_agent_bridge.py 3件 (start_pomodoro/stop_pomodoro/show_pc_pet の GUI未起動)
- **設計決定**: HTTPステータスは **200のまま** error JSON を返す (unknown action と同型)。理由: `/api/action` ディスパッチは前置きで200ヘッダー送出済みのため、ハンドラ内から400を送るとステータス行が二重送信されストリーム破綻する。**400化は do_POST のヘッダー送出構造改革が必要なためフォローアップ課題化**。メッセージ規約: パラメータ欠落 `missing parameter: <param>` / GUI未起動 `PC GUI is not running for action: <action>`
- **TDD**: 該当3件 (test_missing_param / test_quick_add_task_empty_text / test_pomodoro_without_gui) の期待値を先に更新 (Red確認: 30件中10件失敗) ＋ 未カバー7ガードの新テスト追加 → 実装後 **全251テスト OK** (基準線244 → 251に更新) / py_compile OK
- **PWA影響監査**: 対象10アクションは pet.js が常にパラメータを付与するため正常系への影響なし。空ボディによる `res.json()` パース失敗より明示エラーの方が安全性向上
- **ハンドラ契約**: `handler(ctx) -> bool` の意味論を更新 — True=応答書き込み済み (ガード未成立時もエラーJSON書き込み) / False=例外等で応答不能な場合のみ。api_context.py / api_tasks.py / api_agent_bridge.py / local_sync_server.py のDocstring・コメントを整合
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

## 🟢 2026-09-02 P2③ 分割リファクタ完了: local_sync_server.py ＆ gui.py（Cline実装）
- **local_sync_server.py**: 1,823行 → 1,035行。do_POST God Function (約700行・循環的複雑度127) を解体し、**認証 → ループバック制限 (AGENT_ONLY_PATHS/RCEチェーン遮断) → ディスパッチ** のみに縮小。
  - 新設: `api_context.py` (ApiContext Seam + 共通JSONレスポンスヘルパ) / `api_tasks.py` (手帳系10アクション) / `api_agent_bridge.py` (エージェントBridge 6パス系 + デバイス系13アクション) / `api_calendar.py` (外部SaaS Webhook 2パス系)
  - `local_sync_server.py` 側に **明示的ディスパッチテーブル** (`ACTION_HANDLERS_TASKS` / `ACTION_HANDLERS_DEVICE` / `ACTION_HANDLERS` / `POST_PATH_HANDLERS`) を定義。ハンドラ契約は `handler(ctx) -> bool` (True=応答済み / False=旧仕様どおり無応答200)
- **gui.py**: 1,530行 → 971行。ポモドーロ＋サウンド (winsound) / サークルメニュー / オンボーディングツアーを **Mixin Seam 化**: 新設 `ui/pomodoro.py` (PomodoroMixin) / `ui/radial_menu.py` (RadialMenuMixin) / `ui/tour_overlay.py` (TourOverlayMixin)。`NeoSecretaryGUI` は3 Mixin を継承。**Tkinter × asyncio 分離規約 (gui.post_action 徹底) は全移管メソッドで死守**
- **TDD**: characterization テスト `tests/test_action_dispatch_characterization.py` 23件を新設し現行振る舞いを固定 → 分割前後で同結果 (Green)。**ファクト発見**: 既知アクションのパラメータ欠落時は unknown action エラーではなく **無応答200 (空ボディ)** になる旧仕様を確認・characterization で凍結 (将来の改善候補: エラー応答化)
- **テスト更新**: `tests/test_tour_engine.py` の _get_tour_target_rect ソーススキャン先を gui.py + ui/tour_overlay.py 連結へ変更 (移管追従)。**全244テスト OK** (基準線221 + characterization 23) / py_compile OK / import チェーン検証 OK
- **コミット**: ✅ `cf75d6b` 済み (ボス手動・2026-09-02)
- **ディープ監査**: Antigravity 6ペルソナ監査で **総合 A+** (`docs/code_review_report_20260902_deep_audit.md`: 保守性 5.5→8.0・TDD規律 Lv.5)。※レポートの「suggest_engine スレッド残存」「P2①②未完了」はファクト誤り (P2②移管済み・テスト検証済み)
- **引継ぎ準備**: 学習メモ0902・Cline引き継ぎ書0903 (`docs/handover/prompt_for_cline_20260903.md`) 作成済み

## 🟢 2026-09-01 20:40 P2①＋P2②対応完了（Cline実装）
- **P2①第一段: Pydantic DTO移行** (`sync_dtos.py` 新設): /api/status と get_tasks_view のレスポンス契約を Pydantic v2 で型付け。設計: 既知フィールド厳格検証＋未知フィールドは extra=allow 透過 (PWA契約保護)＋ValidationError時は生辞書フォールバック (「まず繋がる体験」縮退設計)。local_sync_server.py L951/L1560 に組み込み。**ファクト更正**: 引き継ぎ書の「/api/tasks」GETは実在しない (実在契約は /api/status と get_tasks_view アクション)
- **P2②第二段: スケジューラ移管** (`proactive_scheduler.py`): `PeriodicThrottle` (初回tick即実行→interval間引き) ＋ `register_periodic()` 新設。reminder_engine/life_coach_engine の専用スレッド (_loop/_thread) を廃止し共有デーモンスレッドへ移管 (公開API start/stop/is_running は後方互換維持)。**残: suggest_engine SuggestBgWorker** (初回即生成+force_refresh割込みのため次回)
- **テスト**: `tests/test_sync_dtos.py` 6件＋`tests/test_scheduler_periodic.py` 8件 新設 (TDD Red→Green)。**全209テスト OK** / py_compile OK
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

## 🟢 2026-09-01 21:20 P2②第二段完了: suggest_engine スケジューラ移管（Cline実装）
- **suggest_engine.py**: SuggestBgWorker 専用スレッド (_worker_thread/_worker_stop/_background_worker_loop) を廃止 → `scheduler.register(_on_scheduler_tick)` プラグイン方式へ移管。強制更新 (request_refresh) は従来「次の30秒周期」反映だったが **tick (1秒) 以内の即時反映へ向上**。`shutdown_worker()` は unregister 方式へ (後方互換)
- **proactive_scheduler.py**: `stop()` をライフサイクル終端契約へ強化 — 登録済みプラグインもクリア (幽霊プラグイン残留を構造的に防止)。全テストで発見した 1件失敗 (plugin_count 2≠1) の根本修正
- **テスト**: tests/test_perf_step2.py を新契約へ刷新 (旧ワーカーループテスト → スケジューラ移管テスト4件) + stop() クリア契約テスト追加 → **全213テスト OK** / py_compile OK
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

## 🟢 2026-09-01 23:30 P2①第二段完了: DB戻り値モデル化＋実バグ修正（Cline実装）
- **database.py**: `HabitWithStatus` / `HabitHeatmapPoint` モデル新設。`get_habits_with_status` / `get_habit_heatmap_data` を dict 生辞書 → Pydantic モデル返却へ移行。これで database.py の getter は**全てモデル返却に統一** (get_recent_minigame_scores は既に MinigameScore モデルのため対象外と確定)
- **実バグ修正 (Pydantic化の効果を実証)**: `briefing_engine.py` が存在しない `is_done` キーを `h.get("is_done")` で参照 → 朝会/終礼の「習慣達成数」が常に 0 だった。純粋関数 `_build_habit_summary()` を切り出し `completed_today` 参照へ修正
- **呼び出し元4ファイルの属性アクセス化**: life_coach_engine / briefing_engine / ui/calendar_window (ヒートマップ+習慣カード計12箇所) / local_sync_server (JSON送信用に model_dump 化)
- **テスト**: `tests/test_habit_models.py` 8件新設 (モデル契約・旧dictキー後方互換・is_done回帰防止) → **全221テスト OK** / py_compile OK
- **コミット**: 未コミット (ボス確認後の手動コミット推奨)

## 🎯 次回再開タスク (2026-09-01 23:30 更新)
1. **【後続】GitHub 公開準備 → Release・アップデート通知の有効化**: ①**git履歴全体の機密監査** (APIキー・トークン・個人情報の漏洩チェック。`build_exe.py` のスキャンは配布zipのみ対象でgit履歴は別物) ②README/ライセンス整備 ③`git push origin v1.0.0` (タグは作成済み・未push) ④GitHub Release 作成 (`docs/releases/v1.0.0.md` をリリースノートに流用・zip添付) ⑤公開後 `update_checker` が自動的に実働開始 (認証なしAPIは非公開リポジトリで404のため現状は dormant・害なし)
2. **【次期機能】AI生活変化エンジン Phase L2**: マイクロ提案カード (スマホ suggest-card) ＋ `nudges` テーブル (✅試した/❌パス記録) ＋ 次回分析への履歴注入 (学習ループ)。仕様書 §3-F2/F3 参照
3. **【軽微】task_parser の解析精度チューニング**: 「の朝 」残骸 / 「9時」→09:59 の時刻解決改善
4. **【内部課題】音声入力の品質向上 → 条件合格後に解放**: `VOICE_INPUT_ENABLED=false` 中。解放条件: 実機品質合格＋キャラエリア大型マイクボタン移設
5. **【内部課題】3キャラの理想スプライト詰め**: marmot/seal/kinoko の理想デザイン確定後に `character_manager.py` へ再登録
6. **【レビュー対応】P2残タスク ＆ コード肥大化解消計画**: 引き継ぎ書 `docs/handover/prompt_for_cline_20260901.md` 参照。**P2①Pydantic DTO移行 — ✅第一・第二段完了 (2026-09-01 23:30)** (第一段: `sync_dtos.py`。第二段: `get_habits_with_status`/`get_habit_heatmap_data` を `HabitWithStatus`/`HabitHeatmapPoint` モデル返却へ移行・呼び出し元4ファイルを属性アクセス化。**実バグ修正**: briefing_engine が存在しない `is_done` キーを参照し朝会の習慣達成数が常に0だった潜在バグ)。**P2②ProactiveScheduler共通化 — ✅第二段完了 (2026-09-01 21:20)** (`PeriodicThrottle`+`register_periodic()` 新設、reminder_engine/life_coach_engine/suggest_engine の専用スレッドを全廃止し共有デーモンスレッド1本へ集約。`ProactiveScheduler.stop()` はプラグインもクリアするライフサイクル契約へ強化)。**P2③コード肥大化解消 (Divergent Change・次セッション以降の本格リファクタ)**: `gui.py` (約1600行) は tour/pomodoro/circle_menu/サウンドへ Seam 分割、`local_sync_server.py` (約1800行) は APIハンドラ (DeskPetSyncHandler) をルーティングテーブル化して機能別モジュール (api_calendar/api_tasks/api_agent_bridge) へ分離。各分割は「テスト追加 → 移動 → 全テスト」の3ステップで1モジュールずつ。P3は完了 (7476e1d)
7. **⚠️ 恒久ルール**: UTF-8ファイルの読み書きは必ず Python `io.open(encoding='utf-8')` を使用（PowerShell 5.1 は日本語ファイルを破壊する）

## 🎨 2026-09-01 19:35 P3対応＋UXバグ修正完了（Cline実装）
- **P3: オンボーディングツアー3ステップ化** (`tour_engine.py`+`gui.py`): 7ステップ → ①右クリックで設定 ②スマホQR連携 ③会話・手帳 へ凝縮。`_get_tour_target_rect` の旧IDハードコード解消。**デッド契約発見**: 旧ステップの `highlight_callback` (flash_menu_btn等) は gui が消費しない死んだ参照だった → 全廃し契約テストで回帰防止
- **B-2修正: カイルのタップ無音**: `pet.js` `playCharacterSE()` に kyle 分岐が存在しなかった (hisho/kinoko/seal/wombat のみ) → 貝型PC風8bit 2連音を追加
- **B-1確認: スマホのマイクボタン**: ソース上は `hidden` 済み (8/31対応済み)。見えていたのはキャッシュ残骸 → キャッシュバス 5.21→**5.22** 三点同期 (index.html 8スクリプト/sw.js/pet.js)。**スマホで1度再読込すれば解消**
- **コミット**: `7476e1d` (6ファイル, +148/-89)。検証: 全189テスト OK / node --check OK / py_compile OK

## 🟡 2026-09-01 19:15 コードレビュー P1対応完了（Cline実装・グラフエンジニアリング稼働）
- **P1-3: LLM APIタイムアウト境界＆縮退通知統一**: `llm_factory.py` に `LLM_REQUEST_TIMEOUT_SEC=15.0` ＋ `is_llm_network_failure()` 新設。Gemini/Claude/OpenAI互換に15秒タイムアウト適用。`agent.py`/`main.py` の縮退通知を「🌐 通信が途切れました。後ほど再試行します。」に統一
- **P1-4: スマホ連携 全解除ボタン**: `SyncTokenManager.regenerate()` 新設 ＋ 設定画面外部ツールタブに赤系カード実装 ＋ `tests/test_sync_token_regenerate.py` 5シナリオ新設
- **コミット**: `6bc72b8` (P1-3) / `67d4797` (P1-4中核)。⚠️ `ui/settings_window.py` は開始前からの未コミット変更（モデルDL GUI関連）混在のため未コミット残留 — ボス手動確認推奨
- **検証**: 全182テスト OK / py_compile OK / 同期系結合テスト10件 OK / 独立Verifier監査合格
- **ファクト更正**: レビュー対象指定の `proactive_engine.py` はLLM非使用を確認（呼び出し経路は llm_factory→agent/life_coach/life_dreamer/suggest_engine/task_narrator）

## 🔴 2026-09-01 18:50 コードレビュー P0対応完了（Cline実装）
- **P0-1: SQLite接続時TRUNCATEチェックポイント廃止** (`database.py`): `get_db_connection()` の接続ごと `PRAGMA wal_checkpoint(TRUNCATE)` を廃止し、`PRAGMA wal_autocheckpoint=1000` によるエンジン自動チェックポイントへ一本化。スマホ高頻度ポーリング時のI/O競合・ロック遅延を解消
- **P0-2: 管理者権限フォルダ実行時のAppData自動フォールバック** (`app_paths.py`): `_is_writable()` (プローブファイル書き込み判定) 新設、書き込み不可時は `%APPDATA%\NeoHisho` へ自動フォールバック＆ディレクトリ自動作成。判定結果はプロセス内キャッシュ (`_APP_ROOT_CACHE`) でI/O最小化。「まず繋がる体験」の死守
- **テスト追加**: `tests/test_packaging_support.py` に `TestAppRootWritableFallback` 3ケース追加 (フォールバック動作/書き込み可能時の後方互換/判定キャッシュ)
- **検証**: 対象26テスト OK ＋ **全テスト 177件 OK** (unittest discover / Re-Verification Loop: 改修前23テストOK → 改修後も同一結果)。独立Verifier監査合格 (`get_app_root()` 全呼び出し元16ファイルの影響確認含む)
- **remaining**: P1〜P3 は引き継ぎ書参照 (上記「次回再開タスク」6番)

## 📦 2026-08-31 22:55 v1.0.0 手渡し配布開始（C案確定）
- **判断**: リポジトリは非公開のまま (匿名アクセス404確認済み)。Release作成・公開リポジトリ化は準備未完了のため後続タスクへ繰り越し、**zipは手渡し配布** (受け取り側にGitHubアカウント不要)
- **ローカルタグ `v1.0.0` 作成済み** (HEAD=bfdffeb に付与・未push)。公開準備完了後に `git push origin v1.0.0` で即 Release 体制へ
- **リリースノート原稿**: `docs/releases/v1.0.0.md` 作成済み (docs/ は .gitignore 対象のためローカル運用。GitHub入力欄へコピペ想定)
- **UPDATE_GUIDE.md**: 手渡し配布中である旨の注記を冒頭に追加 (通知→Releases DL フローはリポジトリ公開後に自動有効化)
- **再ビルド**: `NeoHisho_v1.0.0_win64.zip` 60.6MB / SHA256 `67d581e2c7ddb788...` (ガイド改訂版同梱)

## 🔔 2026-08-31 22:35 アップデート通知 Level 1.5 ＋ ダウンロードガイド
- **PC側通知のクリック導線** (既存機能の確認と汎用化): `update_message` は本文中のURLを自動検出して **🌐 リンクをブラウザで開く** ボタンを動的表示 (`_open_current_link` → webbrowser.open)。ボタンラベルを「記事をブラウザで開く」→「リンクをブラウザで開く」に汎用化。`update_checker.py` の通知文にガイド参照を追加
- **🆕 `docs/guides/UPDATE_GUIDE.md`** 新設 (spec の datas 設定により配布物へ自動同梱): 通知の見方 / **Git不要**のReleasesダウンロード手順 / 配置手順 (データ移行チェックリスト: db・.env・models・backups・suggest_config・webhook_config・.sync_token) / よくある配置ミス5パターンと対処 / FAQ (ロールバック含む)
- **再ビルド**: `NeoHisho_v1.0.0_win64.zip` 60.6MB / SHA256 `67d581e2c7ddb788...` / `_internal/docs/guides/UPDATE_GUIDE.md` 同梱確認 (2892文字)
- **検証**: 全172テスト OK / py_compile OK

## 📦 2026-08-31 22:10 v1.0.0 配布ビルド完成
- **spec更新** (`neo_hisho.spec`): hiddenimports に `life_coach_engine` / `i18n` / `reminder_engine` / `whisper_transcriber` / `agent_identity` を追加。**excludes に `faster_whisper` / `ctranslate2` / `av` / `onnxruntime` / `tokenizers` を追加** (音声入力は内部課題化中のため配布から除外 → zipを大幅圧縮)
- **検収結果**: `dist/NeoHisho/NeoHisho.exe` (18.6MB) ＋ `_internal/web_pet` ＆ `_internal/assets` 同梱 ✓ / PYZ に新モジュール5種すべて同梱 ✓ / **機密混入スキャン CLEAN** (.env/.db/.token/.gguf ゼロ) ✓ / whisper は「optional除外」として whisper_transcriber の `is_available()=False` フォールバックで安全に動作 ✓
- **成果物**: `dist/NeoHisho_v1.0.0_win64.zip` (**60.6MB**, 1645ファイル, SHA256 `065be742f4c2...23aadbb`)
- **配布時の案内事項**: ①zip展開→`NeoHisho.exe` ダブルクリックで起動 ②ローカルLLMは `.\NeoHisho.exe --setup-model 350m` でDL (~230MB) ③または設定画面でクラウドプロバイダAPIキー設定 ④音声入力は無効 (内部課題)
- **実機起動テスト**: ボス手動 (exeダブルクリック → GUI起動・PCペット・スマホペアリング確認)

## 🧭 2026-08-31 21:55 分析タイミングを2時間周期に変更＆ニュース同期
- **ボス確定**: 「分析は1〜2時間に1度走ってもいい」「ニュース取得も同じタイミングで」
- **変更** (`life_coach_engine.py`): 毎晩23時＋朝補完の1日1回 → **`ANALYSIS_INTERVAL_SEC=7200` (2時間) の定周期**。`_last_run_ts_ms` を `coach_reports` から復元し、再起動後も間隔判定が正しく機能。分析完了時に `_refresh_suggestions()` → `suggest_engine.request_refresh()` で**ニュース取得＋AIサマリを同じタイミングで更新**
- **スキーマ変更**: `coach_reports` の主キーを run_date (日付) → created_at (実行時刻ms) に変更し、1日複数回の分析履歴を保持可能に
- **テスト**: 間隔スロットル・再起動復元・ニュース同期トリガー等 11件に刷新 → **全172テスト OK**


- **キーデシジョン確定** (仕様書 §6): ①プロバイダ=選択式 (llm_factory 現行設定) ②タイミング=毎晩23時＋朝6時以降補完 ③送信データ=統計のみ (タスク本文は送らない)
- **`life_coach_engine.py` 新設**: 日次統計集約 (タスク完了・期限切れ・習慣streak) → LLM分析 (JSON固定スキーマ `{analysis, micro_actions, encouragement, risk_flags}`) → 失敗時 i18n ルールフォールバック → `coach_reports` テーブルへ永続化 (再起動後も復元)
- **`i18n.py` 新設**: `t(key, **params)` ヘルパー＋ja/en辞書 (L3でzh/ko/es拡張予定)
- **組み込み**: `main.py` 起動部 (PC吹き出し) / `local_sync_server.py` `/api/status` に `life_coach` フィールド追加
- **テスト**: `tests/test_life_coach_engine.py` 9件新設 → **全170テスト OK** / `py_compile` パス

## 🔇 2026-08-31 21:10 音声入力の内部課題化 (フィーチャーフラグ)
- **判断**: 実機マイクでの文字起こし品質が実用に届かないため、機能として表に出すことを一時停止。品質向上が成功した時点で解放する
- **実装** (`web_pet/pet.js`): 冒頭に `VOICE_INPUT_ENABLED = false` フラグ新設 → `startVoiceInput()` 冒頭でガード (無効時は console.info のみ)。`web_pet/index.html` の上部バー 🎤 ボタンに `hidden` 付与 (DOMは温存、解放時に移設修正のみで復活可能)
- **解放時UI仕様 (確定)**: 上部バーの小さなボタンは使わず、**キャラエリア直下の大型マイクボタン**を新設する
- **付随修正**: 既定キャラIDの残骸 `'seal'` (登録削除済みキャラ) を `'hisho'` に修正。キャッシュバス 5.20 → **5.21** 三点同期 (index.html / sw.js / pet.js)
- **検証**: 全161テスト OK / `node --check` パス

## 🎧 2026-08-31 20:45 音声認識品質の第2弾改善 (実マイク音声対策)
- **既定モデルを small→medium に格上げ** (`whisper_transcriber.py`): 日本語認識精度はモデルサイズにほぼ比例。環境変数 `HISHO_WHISPER_MODEL=small` で速度優先に戻せる。初回は ~1.5GB ダウンロード済み・E2E再検証で完全復元を確認
- **推論パラメータ追強**: `best_of=5` (フォールバック候補拡大) ＋ `vad_parameters={"min_silence_duration_ms": 300}` (短いポーズでの過剰分割防止)
- **録音側の音質改善** (`pet.js`): `audioBitsPerSecond: 128000` を明示 (既定約32kbpsの子音欠落対策) ＋ 録音 mimeType に応じた拡張子をサーバへ送信 (iPhoneの audio/mp4 を voice.webm として送る誤りを解消)
- **検証**: 全161テスト OK / `node --check` パス / `py_compile` パス / E2E (medium) 全ステップOK

## 🔧 2026-08-31 20:10 音声品質改善＋TODO編集UI＋DB掃除
- **Whisper品質向上** (`whisper_transcriber.py`): ドメイン語彙 `initial_prompt` (タスク頻出語を事前文脈化) ＋ `beam_size=5` ＋ `vad_filter=True` ＋ `condition_on_previous_text=False` (幻覚連鎖遮断)。E2E再検証で「明日の9時に企画書のレビューをしてください。」を**完全一致復元** (prob=1.00)
- **スマホTODO編集UI復活** (`pet.js` / `index.html`): `openTaskEditSheet` / `saveTaskEdit` / `deleteTaskFromEdit` 新設 — 4象限ビュー・リストビュー両方のタスクに ✏️ 編集リンク。サーバー `update_task` (タイトル/期限/優先度/タグ/重要度×緊急度ホワイトリスト) ＆ `delete_task` と連携。`.task-edit-link` CSS を index.html へ追加
- **テストゴミTODO掃除**: 実DB `neo_secretary.db` からテスト由来12件 (ID 10-21「未完了のまま/毎週の掃除/取り消しテスト」×4) を削除。ID 22-24 (打ち合わせ×2・低品質文字起こし1) は実データ可能性のため保持 → スマホ編集UIでボス自身に削除依頼
- **検証**: 全161テスト OK / `node --check` パス / `py_compile` パス


## 🎙️ 2026-08-31 B20 音声パイプライン E2E 検証完了
- **依存導入**: venv に `faster-whisper 1.2.1` (ctranslate2 4.8.1 / onnxruntime 1.29.0 同梱) ＋ `edge-tts` をインストール済み
- **E2E検証ツール**: `tools/e2e_voice_check.py` 新設 — edge-tts (ja-JP-NanamiNeural) で合成音声 MP3 を作り → `WhisperTranscriber.transcribe` (model=small/int8/cpu) → `task_parser.parse_input` まで通し検証
- **実測結果**: 「明日の朝9時に企画書のレビューをしてください」→ 文字起こし**完全一致** (lang=ja, prob=1.00) → due=2026-09-01 09:59 と正しく日時解決
- **既知の軽微課題**: タイトルに「の朝 」残骸 / 「9時」→09:59 解決 (task_parser チューニングで対応、パイプライン自体のブロッカーではない)
- **スマホ経路**: local_sync_server.py の `transcribe_voice` アクションは同一経路 (transcript → parse_input → create_task) なので本検証で実質カバー

## 🗂️ 2026-08-31 初回リリーススコープ縮小 (5キャラ → 2キャラ)
- **判断**: ボス実機確認の結果、アザラシ横顔化リファイン後も「アザラシに見えない」・マーモットは「クマにしか見えない」・キノコは「きもい」との評価。**機能実装を優先**するため、初回リリースは **秘書くん＋カイルの2キャラ** とする
- **変更内容**:
  - `character_manager.py`: `CHARACTERS_DATA` から marmot/seal/kinoko の登録を削除 (hisho/kyle の2登録に縮小)。`_character_has_frames()` フォールバックガードは既存キャラの安全機構として維持
  - `gui.py` / `ui/settings_window.py` / `web_pet/pet.js`: キャラ選択肢の列挙を CHARACTERS_DATA 由来に統一 (ハードコード撤去)
  - **資産温存**: `assets/dot/{marmot,seal,kinoko}` (404 PNG) と `tools/generate_kawaii_sprites_v2.py`、Antigravity コンセプト画は削除せず内部課題の検討材料として保持
- **検証**: **全161テスト OK** / `node --check` OK / marmot・seal・kinoko のコード残留参照ゼロ (backups・brain を除くアクティブコード)
- **インシデント修正**: pet.js の ServiceWorker キャッシュパージ許可キーが 5.19 の取り残し (`'neo-pet-v5.19'`) だったため 5.20 に更新 → 三点同期 (index.html / sw.js / pet.js) 復元。**これが「スマホで再読込まで新JSが効かない」系症状の温床になるため、バージョンバンプ時は必ず3箇所同期** (tests/test_sync_lan_selfheal.py が自動検出)

## 🔍 2026-08-31 検証インシデント (Pillow 14 ImageChops 誤検知)
- **経緯**: 茶柱王冠実装後の検証で「王冠が描かれない」「宝石0」「フレーム差分ゼロ」と3つの異常が報告され長時間デバッグ → 結論は**すべて検証ツール側の誤検知**で、生成物は最初から正しかった
- **原因1**: `ImageChops.difference(a,b).getbbox()` が Pillow 14 環境で実際には差分があるのに `None` を返す (md5不一致＋bbox None の矛盾で判明)。**生ピクセル比較 (`list(img.getdata())`) が確実**
- **原因2**: 検証スクリプト側の色定数 (255,215,0) と本体パレット P_GOLD=(255,213,40) の不一致 → 「宝石検出0」誤検知。**検証コードは本体から定数をインポートすること**
- **実測値**: 王冠 gold=464px / 緑宝石=48px / tea_pillar_1 vs 2 sway差分=496px (x=56-68, y=44-100) / tea vs idle 差分 bbox=(12,0,124,32)=頭部王冠
- **教訓**: 汎用エージェント記憶MCP「MentisDB」の LessonLearned (index 87) に記録済み（※秘書くんの知識の宝庫とは別物）


## 🌳 2026-08-31 リスト階層化 (Block 1.6-R・TickTick風UI)
- **TickTick仕様調査**: 左サイドバー = スマートリスト(📥すべて/🗂未分類) → 「リスト」セクション(絵文字＋未完了件数バッジ縦並び) → 折りたたみ可能フォルダ(📁)。公式はフォルダ>リストの1階層だが、ボス要望「リストの中にさらにリスト」を実現するため **task_lists.parent_id 汎用ツリー(多階層)** として上位互換実装
- **database.py**: `task_lists.parent_id` 追加 (PRAGMA安全マイグレーション) / `create_task_list(parent_id=)` 親存在検証 / **`move_task_list` 新設** (自分自身・子孫を親に指定はValueError循環防止) / `delete_task_list` は子リストを親の親へ昇格 (ツリー分断防止) / `get_task_lists` が parent_id を返却
- **ui/calendar_window.py**: 横並びチップバーを廃止し **左サイドバー＋右メインの2分割** へ刷新 — サイドバーは ▶/▼ 折りたたみツリー・子孫合計の件数バッジ・行ごとの「＋」子リスト作成・⚙リスト管理フッター。右メインはヘッダ「{絵文字}リスト名 — N件」。親リスト選択時は子孫リストのタスクも表示 (TickTickフォルダ挙動)。管理ダイアログに「⇄ 移動」(循環候補を構造的に排除した移動先選択)
- **local_sync_server.py**: `list_task_lists` レスポンスに parent_id 同乗
- **pet.js**: スマホTODOのリストチップを階層順 (深さ優先＋ `└` インデント) で表示 (walkLists)
- **テスト**: tests/test_task_lists.py に階層5件追加 (親付き作成/存在しない親/移動/循環防止3パターン/削除時子昇格) → **全155テスト OK**
- **キャッシュバス**: 5.18 → **5.19** 三点同期 (index.html 全8スクリプト / sw.js CACHE_NAME / pet.js パージキー)

### ⚠️ インシデント報告 (web_petエンコード破損と復旧)
- バージョンバンプ作業で PowerShell の `Get-Content`(ANSI/cp932誤読) → `Set-Content`(UTF-8) を使用した結果、web_pet 3ファイルが文字化け＋行結合 (マルチバイト列が改行を吞む) で破損。node --check が検出
- pet.js / index.html / sw.js は git HEAD (1e834a7・5.17版) から復元し、本セッション差分 (階層チップ / undoTask / 5.19バンプ) を再適用して復旧
- **未復元**: 5.18の「✓ボタン明示完了＋6秒猶予オートリフレッシュ」設計は失われたため、代替として「行タップで完了 → 完了行タップでundo (reopen_task 同期・誤タップ対策は維持)」を実装
- **教訓**: UTF-8ファイルの読み書きは必ず Python (`io.open(encoding='utf-8')`) を使うこと。PowerShell 5.1 の Get-Content/Set-Content は既定エンコードが ANSI のため日本語ファイルを破壊する

## 🆕 2026-08-31 TODO視認性・誤タップ対策 (ボス実機フィードバック第2弾)
- **属性・期日の視認性**: スマホTODO一覧に 🔥重要/⚡緊急 バッジ (明示属性のみ・未設定は推定しない正直表示) ＋ 期日は期限切れを赤字「期限切れ」強調で常時表示 (pet.js renderTodoModal / index.html .badge-imp/.badge-urg/.due-overdue)
- **誤タップ対策**: 行タップ完了を廃止し **✓ボタン明示操作** に変更 (.task-done-btn)。完了直後は同一行が「⟲ 誤タップ？ここをタップで元に戻す」の受け皿になり、6秒の猶予後に一覧再取得。サーバーは reopen_task アクション＋ database.reopen_task (tests/test_reopen_task.py 3件)
- **PC手帳**: タスク一覧のメタ行に 🔥重要/⚡緊急/繰り返し/期日を常時表示 (calendar_window.py:723)
- **テスト**: **全139テスト OK** / キャッシュバス **5.18** 三点同期

## 🆕 2026-08-31 Plan E スプリント (1.15 / 1.14 / 1.12)
- **1.15 TODO UI刷新**: スマホTODOモーダルのフィルタ行をラベル付き2段化 (📋 リスト / 🗓 期間+🎯4象限トグル / 🏷 タグ)。リスト未登録時は行ごと非表示 (`pet.js` `renderTodoModal`, `index.html` `.todo-filter-label`)
- **1.14 タスク属性**: quick-add 構文 `※重要/※非重要/※緊急/※非緊急` 解析 (task_parser `_RE_IMPORTANCE/_RE_URGENCY`、連続フラグ対応のため lookahead に `※` 許容) ＋ `tasks.importance_flag/urgency_flag` カラム＋PC手帳セレクト (`calendar_window.py`) ＋スマホ quick_add 反映。4象限は明示属性最優先→未設定は優先度/期限でフォールバック
- **1.12 繰り返しタスク**: 「毎日/毎週[月〜日]曜/毎月D日」解析 (task_parser `_RE_RECURRENCE`+`_resolve_recurrence_due`) ＋ `tasks.recurrence` カラム＋完了時次回自動生成 (database `_next_recurrence_due`/`complete_task`)。放置していた期間はスキップして未来日へ、月末はクランプ (1/31→2/28)
- **技術的教訓**: `complete_task` の接続内で別接続の `create_task` を呼ぶと SQLite が "database is locked" → 同一トランザクション内で直接 INSERT する設計に修正
- **テスト**: test_task_parser.py に繰り返し7件＋DB次回生成2件追加 → **全136テスト OK**
- **キャッシュバス**: 5.16 → **5.17** 三点同期 (10箇所)

## 🔍 2026-08-31 ロードマップ総点検 (Antigravity監査 × Cline再精査)
- **完了化 (✅)**: 7.8/11.4 ブリーフィング (`briefing_engine.py` 4モード+テスト) / 11.1 kyle31種 (`character_manager.py`) / 11.2 「お前を消す方法」(`easter_egg_engine.py`) / 11.3 段階演出 (`easter_eggs.js` CRT/グリッチ/8bit音) / 11.5 ミニゲーム5種 (`minigame_arcade.js`+ハイスコアAPI) / 11.6 Web Speech音声＆TTS (`pet.js`) — いずれもコード・テストで実在確認済み
- **新規登録**: 9.14 通知エージェント自動識別 (`agent_identity.py`) / 1.14 タスク属性(重要度×緊急度) / 1.15 TODO UI刷新
- **Phase 状況**: Phase F 完了化 (`_draw_pomodoro_arc`/`EffectOverlay`) / Phase L 主要実装完了へ更新 / パフォーマンス Step1-3・ミニゲーム5種を完了済み章へ記載
- **既知課題**: ~~4象限は重要度/緊急度の属性カラム未整備~~ → **解消済み** (Plan E 1.14 で明示属性＋フォールバック実装)
- **1.6 は 🚧 へ格下げ** (PC手帳UI側リスト管理が未実装のため)

## ⏰ 2026-08-31 後続計画 A→B→C 完了

### Plan B: 時刻ベースリマインダー (roadmap 3.1) — 新規実装
- **reminder_engine.py 新設**: 30秒周期のデーモンスレッドでタスク期限 (due_date) と予定開始 (start_time) を監視。期限10分前 (REMINDER_LEAD_MINUTES) に発火、期限切れ30分超は黙秘 (取りこぼし猶予)
- **重複防止**: database.py に reminders_sent テーブル (UNIQUE(item_type,item_id)冪等) + is_reminder_sent/mark_reminder_sent 新設 → 再起動後も二重通知しない
- **通知経路**: PC → main.py `_on_reminder` (post_action 経由で吹き出し+alarm_ask状態8秒) / スマホ → /api/status に `due_reminders` 配列追加 (TTL 5分で自動消滅)
- **テスト**: tests/test_reminder_engine.py 6件新設 (通知窓発火/二重防止/完了スキップ/遠未来スキップ/予定発火/TTL消滅) → **全121テスト OK**

### Plan C: スマホTODOビュー強化 (リスト/タグ/期間フィルタ)
- **local_sync_server.py**: `get_tasks_view` アクション新設 (tags/due_date/list_id 付きタスク100件を返却)
- **pet.js**: TODOモーダルを刷新 — リスト切替チップ (📥すべて+登録リスト) / 期間フィルタ (🗂すべて・⏰今日・📅今週 = スマートリスト1.7の最小実装) / タグバッジタップで絞り込み (インデックス参照でXSS安全) / タスク行に期限日時+タグ表示
- **index.html**: .todo-filter-bar / .todo-chip / .todo-tag CSS 新設
- **キャッシュバス**: 5.14 → **5.15** 三点同期 (index.html 全8スクリプト / sw.js / pet.js)


## 🎮 2026-08-31 ミニゲーム性刷新3件 (ボス実機フィードバック第2弾)

### 根本原因と刷新内容
- **① 電脳イライラ棒 = 単なる迷路だった**: 静的ジグザグ迷路+GOAL方式を**ファミコン風無限生成スクロール**へ全面書き換え。コース中心線をランダムウォーク(傾き制限+直線休憩区間)で逐次生成し右から左へ流れ続ける。プローブはデルタ追従ドラッグでコース内に留め続け、壁接触で即ショート終了。スコア=進行距離(10px=1m、50mごと合図音)、距離に応じて加速+コース幅低下
- **② 糸通し = 紙飛行機の柱避けだった**: プレイヤーを「針」から「**波打つ白い糸**」へ変更。障害物を「下から立つ縫い針+先端の穴(リング)」にし、**穴を通過した本数のみカウント**(上空飛び越えは無得点→針の高さへ降りて通すゲーム性)。針の穴は前針から±150px以内で生成(到達不能配置の排除)。10本ごとに加速+穴幅低下
- **③ 刹那の見斬り = 敵が反応せず対戦未満だった**: 敵CPU反応ロジックを新設。合図後 `cpuMs` (ベース420ms→300ms×0.55〜1.0ばらつき、ラウンド毎に鋭くなる) 経過で敵の先手→ラウンド敗北。プレイヤーが `cpuMs` 未満で抜けば勝利(反応速度スコア加点)。result画面に「敵の反応 ms」表示、done画面に「N勝N敗」表示
- **キャッシュバス**: 5.13 → **5.14** 三点同期 (index.html 全8スクリプト / sw.js CACHE_NAME / pet.js パージキー)
- **検証**: node --check 5ファイル全OK / unittest **111件全OK**

### 根本原因と修復
- **① インベーダー消滅**: 端末キャッシュに旧 pixel_defense.js (登録ブロック無し) が残存 → キャッシュバス **5.13** 一斉更新 (index.html ?v / sw.js CACHE_NAME / pet.js パージキー, 計10箇所)
- **② ブロック崩しパドル消滅**: タッチイベントに e.clientX は存在しない (実体は e.touches[0]) → NaN が paddle.x に入り描画消滅。pointOf() 正規化 + [0,W] クランプで修復
- **③ 電脳イライラ棒操作不能**: タップ開始時に startGame() 後 return して dragging が立たずスマホで固まって見える + 絶対座標追従でタップ位置へワープ即ショート。**デルタ追従方式** (指の移動量のみ反映) に刷新し操作感を正常化
- **検証**: node --check 8ファイル全OK / unittest **111件全OK** / キャッシュバス3点同期テストOK



## ✅ 2026-08-31 Step 4: TickTick機能 (タスク管理拡張) 完了

- **task_parser.py 新設**: クイック追加構文「明日18時に会議資料 #仕事 !3」をタイトル/期限(epoch ms)/優先度/タグに解析。日本語時刻 (午後6時30分/18時/18時半+に・まで・ごろ)、今日/明日/明後日、M月D日、M/D、曜日 (次回同曜日) 対応
- **database.py 拡張**: tasksテーブルに list_name/tags/notes カラム追加(PRAGMA検査+ALTER TABLEの安全マイグレーション)・Taskモデル拡張・create_task/get_tasks拡張
- **db_tools.py**: quick_add_task_tool をAIエージェントツールへ新設登録 ※list_task_lists_tool は Step 4 では未実装だったが、**2026-08-31 整合性Fix (Plan A)** で追実装
- **local_sync_server.py**: /api/action に quick_add_task アクション追加 (※「DBキャッシュ無効化連動」と記載していたが実体は 2秒TTLキャッシュ任せ — 訂正。list_task_lists アクションも Plan A で追実装)
- **スマホペットUI**: TODOモーダルへクイック追加バー新設 (タグ/優先度バッジ表示、pet.js 5.12)
- **テスト**: tests/test_task_parser.py 11件新設 → **全111テスト OK**(Verifierゲートで「18時に」の助詞残存バグを検出・_RE_TIME_JP拡張で修正済み)

## 🕹️ 2026-08-30 秘密の部屋レトロミニゲームセンター拡張 (オムニバス5種)

### ✅ 完了 (2026-08-30 23:10)

- **minigame_arcade.js 新設**: カートリッジ型マネージャー (レジストリ登録・ガチャ起動・◀[L]/▶[R]切替・HI表示・共通submitScore・矩形波Sfx)。arcade所有rAFループで単一ループ統合
- **pixel_defense.js 最小改修**: activate()/deactivate() 分離＋起動時ハイスコアGET取得＋Escape/背景クリックのarcade連携。window.PixelDefense.show()/hide() エイリアスで後方互換100%維持
- **新ゲーム4種実装** (各自己完結IIFE・自己rAFループ・タッチ+キーボード両対応): minigame_itotooshi.js (🪡 糸通し・長押し上昇・10本ごと加速) / minigame_cyber_wire.js (⚡ 電脳イライラ棒・ドラッグ配線追従) / minigame_setsuna.js (⚔️ 刹那の見斬り・反射神経勝負) / minigame_retro_breakout.js (🧱 ブロックラリー・usesArrowKeys)
- **バックエンド**: GET /api/minigame/high?game_id=xxx 新設 (Bearer認証・game_id必須400・database.get_high_score 再利用)
- **キャッシュバス**: index.html 全8スクリプト ?v=5.11 / sw.js neo-pet-v5.11 / pet.js パージキー 同期
- **設計書**: docs/specs/レトロミニゲームセンター拡張設計書_20260830.md 新設
- **検証**: py_compile OK / node --check 6ファイル OK / unittest **97 tests OK** (test_minigame_score +3件・test_sync_lan_selfheal +3件・キャッシュバス8本化)
- **スクリプト読込順**: pixel_defense → arcade → 新4ゲーム → pet (arcadeエイリアス付与に PixelDefense 定義済みが必要)


## 📱 2026-08-30 スマホペットUX改善 3点セット (ボス実機フィードバック)

### ✅ 完了 (2026-08-30 21:55)

- **① インベーダー横画面見切れ修正** (web_pet/index.html): キャンバス幅に calc((94vh - 56px) * 0.7619) の縦方向フィット制約を追加＋パネル max-height: 96vh。タッチ座標は既に矩形スケーリング対応のためCSSのみで完結
- **② AIニュース3ポイントサマリ化** (suggest_engine.py): _extract_content_points() 新設でdescriptionを文単位分解し、タイトル反復/媒体名/日付等のノイズを除外した実内容ポイントを抽出。3ポイント構成を優先し案内文は最大1行のみ (旧: 案内文2行パディング)。LLM出力3行未満時も本文ポイントで補完
- **③ 通知エージェント自動識別** (agent_identity.py 新設 + hisho_mcp_server.py): ハードコードされた Codex を廃止。HISHO_AGENT_NAME 環境変数 → シグネチャ環境変数 (Claude Code/Cursor/Codex/Gemini CLI) → プレフィックス → 親プロセス名 (psutil任意・VS Code子=Cline推定) の順で自動検出。execute関数/ツールスキーマ/ディスパッチハンドラ計8箇所を変更
- **キャッシュバス3点同期**: index.html ?v=5.10 / sw.js CACHE_NAME / pet.js パージキー を一斉更新
- **検証**: py_compile OK / unittest **87 tests OK** (新規: test_agent_identity 7件・test_suggest_news_summary +4件更新)
- **緊急ホットフィックス**: 実行中アプリのログから `llm_factory.py` (Step 3のTTLキャッシュ) に `import time` 欠落による NameError 連発 (メニュー展開全壊) を発見 → import 追加で修復・インポート検証+87 tests OK を確認
- **事故と修復**: Set-Content による index.html UTF-8→ANSI破損を検出 → git checkout 復元後エディタツールで再適用し完全修復 (UTF-8検証・diff最小化を確認)


## ⚡ 2026-08-30 パフォーマンス短期改善スプリント (Step1-3) 開始


### ✅ 短期改善スプリント Step 1-3 全完了 (2026-08-30 21:40)

- **Step 1**: 手帳カレンダー8/31バグ修正 (ui_notify新設/登録後即時リフレッシュ/refresh_events_only/60秒自動更新/FocusIn) — コミット c34cac4
- **Step 2**: サジェスト BGワーカー化 (SuggestBgWorker 30秒周期+get_cached_suggestions 1ms読み出し) ＋ AgentWatcher 列挙/読取分離 (ターゲットglob 30秒TTLキャッシュ・1.5秒ループはstatのみ)
- **Step 3**: sync_all_discovered_models を ThreadPoolExecutor 並列化 (max 4) ＋ is_provider_configured 60秒TTLキャッシュ (save_settingsで無効化) ＋ 起動時モデル同期を15秒遅延化
- **検証**: py_compile 12ファイル OK / unittest **76 tests OK** (venv)
- **次の候補**: Step 4 TickTick機能 (DB拡張 lists/tags/notes + task_parser.py + クイック追加バー) — 中期は機能凍結後に実施 (ボス承認済み)


### ✅ Step 2 完了: ボトルネック①②解消 (2026-08-30 21:30)

- [x] `suggest_engine.py`: SuggestBgWorker スレッド新設 (30秒周期・デーモン)。`get_cached_suggestions()` (ロック即時読み) / `request_refresh()` (非ブロッキング再生成依頼) / `shutdown_worker()` を追加。`toggle_source`/`set_news_keywords` から request_refresh 呼出
- [x] `local_sync_server.py:721`: /api/status ハンドラを `generate_suggestions()` 直呼び → `get_cached_suggestions()` に置換。ポーリング時のDB/LLM/RSS処理がHTTPスレッドから消え GIL 競合解消
- [x] `agent_watcher.py`: 監視対象列挙を30秒周期キャッシュ化 (`_get_watch_targets_cached`)。1.5秒周期ループは既知ファイルの stat 差分のみに。新規ログ検知は最大30秒遅延 (実害なし)
- [x] テスト: `tests/test_perf_step2.py` 10件追加 + `test_sync_lan_selfheal.py` のモックを新API対応 → **全76テスト OK**


### ✅ Step 1 完了: 手帳カレンダー表示バグ (2026-08-30 21:10)

- **根本原因**: `refresh_all_data()` が手帳生成時/開き直し時の2箇所でしか呼ばれず、開きっぱなし中の新規登録 (AIチャット/スマホ/MCP) が反映されなかった (8/31の予定が見えなかったボス報告の原因)
- [x] `ui_notify.py` 新設: バックグラウンドスレッドから GUI へ `post_action(refresh_calendar_if_open)` を送る薄いブリッジ (GUI未起動時は静かにスキップ)
- [x] `db_tools.create_event_tool` / `hisho_mcp_server.execute_create_calendar_event` の登録成功後に通知追加 (webhookはサーバーハンドラで既存対応済み)
- [x] `calendar_window.py`: `refresh_events_only()` 新設 (予定のみ軽量再取得・数ms) ＋ 60秒周期の自動リフレッシュ (手帳閉じたら自動停止) ＋ `<FocusIn>` 即時再取得
- [x] `gui.refresh_calendar_if_open` を軽量経路優先に変更 (後方互換フォールバック付き)
- [x] 新規テスト `tests/test_ui_notify.py` 7件 → **全テスト66件 OK** (venv) / py_compile 6ファイル OK

- 設計書: `docs/specs/パフォーマンス短期改善設計書_20260830.md` (4大ボトルネック短期解消プラン確定)
- **Step 1**: 手帳カレンダー「開きっぱなし中の新規予定が表示されない」バグ — 登録後リフレッシュ全経路通知 + `refresh_events_only()` 新設 + 周期リフレッシュ + FocusIn
- **Step 2**: ①サジェスト生成のバックグラウンドワーカー化 (/api/status はキャッシュ即答化) ②AgentWatcher 列挙(30秒)/読取(1.5秒)分離
- **Step 3**: ③起動時LLM疎通の選択プロバイダ限定+遅延化 ④メニュー env読み 60秒TTLキャッシュ → Verifierゲート
- 中期(Tauri移行/LFM Scene Engine/TickTick超え/SSE)は機能凍結後の別スプリントで実施 (**ボス承認済み**: 配布リスク回避のため表現方式は現状維持)

---

## 📱 2026-08-30 スマホ/PC連携 6大バグ修正セッション (ボス実機フィードバック対応)

### Verifier 繧ｲ繝ｼ繝育ｵ先棡 (蜈ｨ繧ｰ繝ｪ繝ｼ繝ｳ)
- `py_compile`: local_sync_server.py / suggest_engine.py / command_router.py / agent.py / llm_factory.py / main.py **蜈ｨ6繝輔ぃ繧､繝ｫ OK**
- `unittest discover` (venv): **59 tests OK** (譌ｧ51 + 譁ｰ隕・`tests/test_command_router.py` 8莉ｶ)
- `node --check`: pet.js / sw.js **OK**
- 繧ｭ繝｣繝・す繝･繝舌せ3轤ｹ蜷梧悄 v5.9: `pet.js:10` / `sw.js:5` / `index.html` script繧ｿ繧ｰﾃ・

### 菫ｮ豁｣蜀・ｮｹ
- [x] **Bug 3: 繧ｹ繝槭・AI繝九Η繝ｼ繧ｹ隕∫ｴ・・驥崎､・賜髯､** (`suggest_engine.py`):
  - `_normalize_for_compare()` / `_texts_near_duplicate()` (豁｣隕丞喧蛹・性 + Jaccard 竕･0.6) 繧偵Δ繧ｸ繝･繝ｼ繝ｫ繝倥Ν繝代・縺ｨ縺励※譁ｰ險ｭ
  - 繝九Η繝ｼ繧ｹ蜿門ｾ励Ν繝ｼ繝励↓繧ｿ繧､繝医Ν驥崎､・賜髯､ + 3莉ｶ蜿門ｾ励〒譌ｩ譛・break (繧ｯ繝ｩ繧ｦ繝鵜LM驕・ｻｶ繧定｡ｨ遉ｺ莉ｶ謨ｰ縺ｫ蛻ｶ髯・
  - LLM隕∫ｴ・・蟠ｩ螢雁・蜉・蜷御ｸ陦後・郢ｰ繧願ｿ斐＠)繧・`_summary_lines_are_degenerate()` 縺ｧ讀懃衍縺励Ν繝ｼ繝ｫ繝吶・繧ｹ縺ｸ繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ
  - `factory.create_model()` 繧剃ｽｿ逕ｨ (蟄伜惠縺励↑縺・`get_llm()` 繧剃ｿｮ豁｣) + LOCAL_GGUF譎ゅ・ LLM 隕∫ｴ・ｒ繧ｹ繧ｭ繝・・
- [x] **Bug 5: 繝ｭ繝ｼ繧ｫ繝ｫLLM縺ｮ蛛ｽ螳御ｺ・ｱ蜻・(縲檎匳骭ｲ縺励∪縺励◆縲榊ｹｻ隕・ 縺ｮ譬ｹ譛ｬ隗｣豎ｺ**:
  - `command_router.py` **譁ｰ險ｭ**: 縲梧・譌･15譎ゅ↓笳銀雷繧貞・繧後※縲咲ｭ峨・鬮倅ｿ｡鬆ｼ莠亥ｮ夂匳骭ｲ謖・､ｺ繧呈ｭ｣隕剰｡ｨ迴ｾ+譌･譎りｧ｣譫舌〒**豎ｺ螳夊ｫ也噪縺ｫ螳溯｡・* (create_event_tool 逶ｴ謗･invoke縲´LM髱樔ｾ晏ｭ・縲よ尠譏ｧ蜈･蜉帙・ None 縺ｧ LLM 縺ｸ蟋碑ｭｲ
  - `llm_factory.py`: `supports_tool_calling()` 霑ｽ蜉 (LOCAL_GGUF 縺ｯ髱槫ｯｾ蠢懊→蛻､螳・
  - `agent.py`: planner蜀帝ｭ縺ｧ繧ｳ繝槭Φ繝峨Ν繝ｼ繧ｿ繝ｼ逶ｴ謗･螳溯｡・(LLM謗ｨ隲悶せ繧ｭ繝・・) / 髱槫ｯｾ蠢懊Δ繝・Ν縺ｫ縺ｯ繧ｷ繧ｹ繝・Β繝励Ο繝ｳ繝励ヨ縺ｧ螳御ｺ・ｱ蜻顔ｦ∵ｭ｢繧貞宍螳域欠遉ｺ / `_enforce_response_honesty()` 隱螳滓ｧ繧ｬ繝ｼ繝・(繝・・繝ｫ譛ｪ螳溯｡後・蠢懃ｭ斐′螳御ｺ・ｒ陦ｨ譏弱＠縺溘ｉ隱螳溘↑蠢懃ｭ斐∈鄂ｮ謠・
  - 譁ｰ隕上ユ繧ｹ繝・`tests/test_command_router.py` 8莉ｶ (逶ｸ蟇ｾ譌･/蜊亥ｾ・邨ｶ蟇ｾ譌･莉・譎ょ綾逵∫払/繧ｿ繧､繝医Ν謚ｽ蜃ｺ/蟋碑ｭｲ蛻､螳・
- [x] **繧ｹ繝槭・謇句ｸｳ譎ょ綾陦ｨ遉ｺ** (`local_sync_server.py`): 繝溘Μ遘偵ち繧､繝繧ｹ繧ｿ繝ｳ繝励ｒ `_fmt_event_dt()` (繝｢繧ｸ繝･繝ｼ繝ｫ繝ｬ繝吶Ν) 縺ｧ 'YYYY-MM-DD HH:MM' 譁・ｭ怜・蛹・- [x] **switch_character 讀懆ｨｼ蠑ｷ蛹・* (`local_sync_server.py`): char_id 蝙九・蟄伜惠繝√ぉ繝・け + 荳肴・ action 縺ｸ縺ｮ譏守､ｺ繧ｨ繝ｩ繝ｼ蠢懃ｭ・- [x] ｩｹ **繧ｻ繝・す繝ｧ繝ｳ蜀・ｿｮ蠕ｩ**: 蜑榊屓邱ｨ髮・〒谿句ｭ倥＠縺ｦ縺・◆譌ｧ events 繝ｪ繧ｹ繝域悴髢蛾事縺ｫ繧医ｋ `SyntaxError` (`local_sync_server.py` L662莉倩ｿ・ 繧呈､懃衍繝ｻ菫ｮ蠕ｩ縲～_fmt_event_dt` 繧偵Δ繧ｸ繝･繝ｼ繝ｫ繝ｬ繝吶Ν縺ｸ遘ｻ險ｭ
- [x] 薄 **繧ｭ繝｣繝・す繝･繝舌せ v5.8 竊・v5.9** (pet.js:10 / sw.js:5 / index.html scriptﾃ・)

### 繝懊せ蜀阪ユ繧ｹ繝井ｾ晞ｼ (6轤ｹ)
1. 繧ｹ繝槭・AI繝九Η繝ｼ繧ｹ: 隕∫ｴ・↓蜷御ｸ譁・・郢ｰ繧願ｿ斐＠縺悟・縺ｪ縺・％縺ｨ (Bug 3)
2. 繧ｹ繝槭・繝√Ε繝・ヨ縺ｧ縲梧・譌･15譎ゅ↓髢狗匱莨夊ｭｰ繧貞・繧後※縲坂・ 謇句ｸｳ縺ｫ逋ｻ骭ｲ縺輔ｌ縲∝ｱ蜻翫′莠句ｮ溘→荳閾ｴ縺吶ｋ縺薙→ (Bug 5)
3. 繝ｭ繝ｼ繧ｫ繝ｫLLM驕ｸ謚樊凾縺ｫ縲後ち繧ｹ繧ｯ逋ｻ骭ｲ縺励※縲阪→鬆ｼ繧 竊・蛛ｽ縺ｮ縲檎匳骭ｲ縺励∪縺励◆縲阪′蜃ｺ縺夊ｪ螳溘↑譯亥・縺ｫ縺ｪ繧九％縺ｨ (Bug 5)
4. 繧ｹ繝槭・謇句ｸｳ縺ｮ莠亥ｮ夐幕蟋区凾蛻ｻ縺梧｡∵焚蟄励〒縺ｪ縺・'YYYY-MM-DD HH:MM' 陦ｨ遉ｺ縺ｫ縺ｪ繧九％縺ｨ
5. 繧ｭ繝｣繝ｩ蛻・崛縺梧ｭ｣蟶ｸ縺ｫ蜿肴丐縺輔ｌ繧九％縺ｨ
6. 繧ｹ繝槭・蜀崎ｪｭ霎ｼ2蝗・竊・譁ｰUI (v5.9) 縺碁・菫｡縺輔ｌ繧九％縺ｨ

---

## 噫 2026-08-30 遉ｾ蜀・・蟶・せ繝励Μ繝ｳ繝・(10譎る俣險育判 窶・譛邨ょｷ･遞・ 遉ｾ蜀・う繝ｳ繧ｹ繝医・繝ｩ繝ｼ驟榊ｸ・

### 豎ｺ螳壻ｺ矩・- **驟榊ｸ・ｽ｢諷・*: PyInstaller **onedir繝輔か繝ｫ繝 + zip** (繝懊せ謇ｿ隱・縲Ｐnefile縺ｯ豈手ｵｷ蜍輔・閾ｪ蟾ｱ隗｣蜃阪〒襍ｷ蜍輔′驕・￥縲、V隱､讀懃衍繝ｪ繧ｹ繧ｯ螟ｧ縺ｮ縺溘ａ遉ｾ蜀・・蟶・・荳肴治逕ｨ縲・itHub蜈ｬ髢区凾縺ｮ縲後す繝ｳ繧ｰ繝ｫexe縲・Phase J譁ｹ驥・ 縺ｯ蠕梧律蟇ｾ蠢懊→縺励※邯ｭ謖√・
### Phase 1 螳御ｺ・ 遘伜ｯ・・驛ｨ螻九い繧､繝ｪ繧ｹ縲悟・髱｢鮟貞喧縲肴隼菫ｮ 笨・- [x] 菅 **譬ｹ譛ｬ蜴溷屏迚ｹ螳壹→菫ｮ豁｣** (`web_pet/index.html` `.iris-hole`):
  - 譌ｧ `transform: scale` 縺ｯ box-shadow 縺ｮ螟門捉縺ｾ縺ｧ荳邱偵↓邵ｮ繧√ｋ縺溘ａ縲∵ｼ泌・邨ら乢縺ｫ鮟偵′逕ｻ髱｢遶ｯ縺九ｉ蜑･縺後ｌ縺ｦ縲碁ｻ偵＞蜀・′邵ｮ繧縺縺代阪↓縺ｪ繧翫∵怙邨ゅヵ繝ｬ繝ｼ繝縺悟・髱｢鮟偵↓縺ｪ繧峨↑縺九▲縺滂ｼ医・繧ｹ謖・遭縺ｮ譬ｹ譛ｬ蜴溷屏・・  - 遨ｴ縺ｮ `width/height` 繧堤峩謗･繧｢繝九Γ縺吶ｋ譁ｹ蠑上∈螟画峩・磯ｻ貞ｽｱ繧ｹ繝励Ξ繝・ラ 120vmax 縺ｯ荳榊､・竊・遨ｴ=0 縺ｮ譛邨ゅヵ繝ｬ繝ｼ繝縺ｧ鮟貞ｽｱ蜊倅ｽ薙′逕ｻ髱｢繧貞ｮ悟・縺ｫ隕・＞縲・*謨ｰ蟄ｦ逧・↓蜈ｨ髱｢鮟偵ｒ菫晁ｨｼ**・・  - `prefers-reduced-motion` 迺ｰ蠅・・繧｢繝九Γ逵∫払縺ｧ蜊ｳ證苓ｻ｢・域ｼ泌・霆ｽ驥丞喧繝昴Μ繧ｷ繝ｼ貅匁侠・・- [x] `web_pet/pet.js` JS繝ｭ繧ｸ繝・け辟｡螟画峩・医ム繝悶ΝrAF / try/finally / 蜀榊・繧ｬ繝ｼ繝峨・邯ｭ謖・ｼ峨ゅさ繝｡繝ｳ繝医・縺ｿ譁ｰ譁ｹ蠑上↓蜷医ｏ縺帶峩譁ｰ
- [x] 薄 **繧ｭ繝｣繝・す繝･繝舌せ v5.7 竊・v5.8** (`pet.js:10` / `sw.js:5` / `index.html` script繧ｿ繧ｰﾃ・)
- [x] 潤 **Verifier讀懆ｨｼ繧ｰ繝ｪ繝ｼ繝ｳ**: `node --check` pet.js/sw.js OK ・・`unittest discover` 竊・**41 tests OK** ・・v5.7谿句ｭ倥ぞ繝ｭ・・轤ｹ蜷梧悄OK・・
### Phase 2 螳御ｺ・ PyInstaller繝代ャ繧ｱ繝ｼ繧ｸ繝ｳ繧ｰ螳溯｣・笨・(2026-08-30 17:30)
- [x] 剥 逶｣譟ｻ螳御ｺ・ 縲後Δ繝・Ν邂｡逅・衡ab荳榊惠竊蛋--setup-model` CLI縺ｧ莉｣譖ｿ / `mcp_installer` frozen蟇ｾ蠢・(`[exe, "--mcp-serve"]`) / `httpx2==2.10.0` 豁ｻ縺ｫ萓晏ｭ伜炎髯､ / `.env` 隱ｭ霎ｼ縺ｮCWD萓晏ｭ倩ｧ｣豸・- [x] ｧｭ `app_paths.py` 譁ｰ險ｭ (**繝代せSSOT**): `is_frozen()` / `get_app_root()` (exe逶ｴ荳・譖ｸ霎ｼ) / `get_resource_root()` (`_MEIPASS`=隱ｭ蜿・ / `ensure_env_file()` (蛻晏屓 `.env` 閾ｪ蜍慕函謌・
- [x] 逃 譖ｸ霎ｼ繝代せ繧・`get_app_root()` 縺ｸ蜈ｨ髱｢遘ｻ險ｭ (16繝輔ぃ繧､繝ｫ): DB / `.env` 隱ｭ譖ｸ / `models/` / `backups/` / config蜷ЙSON (mcp/suggest/webhook/character) / `.sync_token` / screenshots / `discovered_models.json`
- [x] 坎 `main.py` 譌ｩ譛溘ョ繧｣繧ｹ繝代ャ繝・(`_early_cli_dispatch`): `--mcp-serve` (MCP繧ｵ繝ｼ繝舌・繝｢繝ｼ繝・ / `--setup-model [350m|1.2b]` (繝｢繝・ΝDL縲『indowed exe縺ｧ縺ｯ螳御ｺ・ｒ繝｡繝・そ繝ｼ繧ｸ繝懊ャ繧ｯ繧ｹ騾夂衍) 繧帝㍾import繧医ｊ蜑阪↓蜃ｦ逅・竊・**exe蜊倅ｽ薙〒GUI/MCP繧ｵ繝ｼ繝舌・/繝｢繝・ΝDL縺ｮ3蠖ｹ**
- [x] 肌 `llm_factory.py` (ENV_PATH / DISCOVERED_MODELS_PATH / MODELS_DIR / 謗｢邏｢models_dir) 遘ｻ險ｭ繝ｻ`main()` frozen繝悶・繝医せ繝医Λ繝・・ (CWD蝗ｺ螳・+ .env菫晁ｨｼ + stdout None閠先ｧ)
- [x] 箕・・`ui/settings_window.py` MCP逋ｻ骭ｲ4繝｡繧ｽ繝・ラ (`_copy_claude_mcp_config` / `_copy_codex_mcp_config` / `_copy_claude_code_cmd`) 繧・`mcp_installer.get_current_mcp_config()` SSOT縺ｸ蟋碑ｭｲ + `_copy_claude_mcp_config` 莠碁㍾螳夂ｾｩ髯､蜴ｻ (P3蟇ｾ蠢・
- [x] 逃 `neo_hisho.spec` 譁ｰ險ｭ: onedir / `web_pet` + `assets` + `docs/guides` + `.env.example` 繧・`_internal` 蜷梧｢ｱ / customtkinter繝・・繧ｿ+llama_cpp DLL蜿朱寔 (`collect_data_files`/`collect_dynamic_libs`) / GGUF繝｢繝・Ν髱槫酔譴ｱ (DL驕狗畑)
- [x] 女・・`build_exe.py` 譁ｰ險ｭ: PyInstaller閾ｪ蜍募ｰ主・竊偵ン繝ｫ繝俄・**讖溷ｯ・ｷｷ蜈･繧ｹ繧ｭ繝｣繝ｳ** (`.env`/`*.db`/`*.gguf`/`.sync_token`遲・竊蛋NeoHisho_v1.0.0_win64.zip` 逕滓・ (version.py SSOT蜿ら・繝ｻSHA256陦ｨ遉ｺ)
- [x] 塘 `docs/guides/INSTALL_GUIDE.md` 譁ｰ險ｭ (驟榊ｸ・髄縺・ SmartScreen/OneDrive豕ｨ諢・繝｢繝・ΝDL/MCP/繝医Λ繝悶Ν繧ｷ繝･繝ｼ繝・繝・・繧ｿ菫晏ｭ伜ｴ謇)
- [x] 潤 **Verifier繧ｲ繝ｼ繝・*: `py_compile` 19繝輔ぃ繧､繝ｫOK / `unittest discover` 竊・**51 tests OK** (譁ｰ隕・`tests/test_packaging_support.py` 10莉ｶ: app_paths dev/frozen繝ｻ.env逕滓・繝ｻMCP config繝ｻspec雉・肇螳溷惠) / `main.py` import+繝・ぅ繧ｹ繝代ャ繝＾K / `.gitignore` 縺ｫ `!neo_hisho.spec` 霑ｽ蜉 (`*.spec` 髯､螟悶・遨ｴ蝪槭℃)
- 東 iris v5.8 蜈ｨ髱｢鮟貞喧縺ｯ Phase 1 縺ｧ螳御ｺ・ｸ医∩ (carry-over譽壼査縺励〒遒ｺ隱阪・譛ｬ繧ｹ繝励Μ繝ｳ繝医〒縺ｯ蟇ｾ蠢應ｸ崎ｦ・

### Phase 3 (繝懊せ謇句虚 窶・繝薙Ν繝・驟榊ｸ・
- [ ] `venv\Scripts\python.exe build_exe.py` 螳溯｡・竊・`dist/NeoHisho_v1.0.0_win64.zip` 逕滓・ (PyInstaller譛ｪ蟆主・縺ｪ繧芽・蜍輔う繝ｳ繧ｹ繝医・繝ｫ)
- [ ] 繧ｯ繝ｪ繝ｼ繝ｳ迺ｰ蠅ウ2E: zip螻暮幕竊蛋NeoHisho.exe` 襍ｷ蜍・(蛻晏屓 `.env` 逕滓・遒ｺ隱・ / MCP閾ｪ蜍慕匳骭ｲ / `--setup-model` / 繧ｹ繝槭・QR / `models/` 隗｣豎ｺ蜈・- [ ] `INSTALL_GUIDE.md` 繧呈ｷｻ縺医※遉ｾ蜀・・蟶・
### 繝懊せ謇句虚繧ｿ繧ｹ繧ｯ・亥ｮ滓ｩ滓怙邨ら｢ｺ隱搾ｼ・- [ ] 繧ｹ繝槭・螳滓ｩ溘〒繝壹・繧ｸ蜀崎ｪｭ霎ｼ・・蝗橸ｼ俄・ 太遘伜ｯ・・驛ｨ螻九ち繝・・: **遶ｯ縺九ｉ鮟偵′豬ｸ鬟溘＠縲∵怙邨ゅヵ繝ｬ繝ｼ繝縺悟・髱｢鮟偵↓縺ｪ縺｣縺ｦ縺九ｉ繧ｲ繝ｼ繝螻暮幕**縺吶ｋ縺薙→・・5.8・・- [ ] 劫繝昴Δ繝峨・繝ｭ 竢ｹ蛛懈ｭ｢縺悟柑縺上％縺ｨ・・5.7謾ｹ菫ｮ縺ｮ蝗槫ｸｰ遒ｺ隱搾ｼ・
---

## ・ 2026-08-30 Desk Pet 蠕ｩ譌ｧ螳御ｺ・そ繝・す繝ｧ繝ｳ (繧ｹ繝槭・PWA蜈ｨ貊・囿螳ｳ縺ｮ譬ｹ譛ｬ隗｣豎ｺ)

### 髫懷ｮｳ讎りｦ・繧ｹ繝槭・Desk Pet (port 8765) 縺・00%讖溯・荳榊・ 窶・蜷梧悄繝ｻ謠冗判繝ｻ繧ｵ繧ｸ繧ｧ繧ｹ繝医・繝溘ル繧ｲ繝ｼ繝蜈ｨ貊・・
### 螳御ｺ・- [x] ｩｹ **P0: pet.js 驥崎､・ｮ｣險 SyntaxError 縺ｮ譬ｹ譛ｬ菫ｮ蠕ｩ** (`web_pet/pet.js`):
  - `let currentActivity` 莠碁㍾螳｣險 (譌ｧL866) 繧貞炎髯､縺怜・鬆ｭ螳｣險縺ｫ邨ｱ蜷・  - `const CHARACTERS` 莠碁㍾螳｣險 (譌ｧL1802) 繧貞炎髯､縺怜腰荳螳｣險縺ｫ邨ｱ蜷茨ｼ・cycleCharacter`/`selectCharacter` 蜈ｱ逕ｨ・・  - CHARACTERS 縺ｯ **4菴捺ｧ区・** (seal/hisho/kinoko/kyle) 縺ｫ謨ｴ逅・窶・retro_dolphin 髯､蜴ｻ・医・繧ｹ譁ｹ驥晁､・焚蝗樊価隱肴ｸ医∩・・  - 讀懆ｨｼ: `node --check` 縺ｧ pet.js / easter_eggs.js / pixel_defense.js **蜈ｨ3繝輔ぃ繧､繝ｫ讒区枚OK**
- [x] 菅 **P0霑ｽ蜉: /api/status 縺悟ｸｸ縺ｫ error 繧定ｿ斐☆ NameError 繧剃ｿｮ豁｣** (`local_sync_server.py` L782):
  - 繝壹う繝ｭ繝ｼ繝牙・ `token_mgr.token` 蜿ら・譎ゅ↓ `token_mgr` 縺梧悴螳夂ｾｩ・井ｻ悶Γ繧ｽ繝・ラ縺ｮ繝ｭ繝ｼ繧ｫ繝ｫ螟画焚繧定ｪ､蜿ら・・俄・ `NameError` 縺ｧ繧ｹ繝槭・蜷梧悄縺悟・貊・＠縺ｦ縺・◆**隨ｬ3縺ｮ蜴溷屏**縲ゅワ繝ｳ繝峨Λ蜀・〒 `token_mgr = get_sync_token_manager()` 繧貞ｮ夂ｾｩ縺励※隗｣豸・- [x] ｧｭ **繧ｭ繝｣繝・す繝･繝舌せ邨ｱ荳** (`web_pet/pet.js`, `web_pet/index.html`):
  - SW菫晁ｭｷ繧ｭ繝ｼ `neo-pet-v5.5` 竊・`v5.6` (sw.js 縺ｮ `neo-pet-v5.6` 縺ｨ荳閾ｴ)縲Ｔcript 繧ｿ繧ｰ 3譛ｬ繧・`?v=5.6` 縺ｫ邨ｱ荳 竊・譌ｧ繧ｭ繝｣繝・す繝･縺檎｢ｺ螳溘↓蜑･縺後ｌ繧・- [x] 白 **P1: record_minigame_score 縺ｮ蜈･蜉帙け繝ｩ繝ｳ繝・* (`local_sync_server.py`):
  - 髱樊焚蛟､/雋蛟､繧ｹ繧ｳ繧｢繧・0 縺ｫ繧ｯ繝ｩ繝ｳ繝暦ｼ・ypeError/ValueError謐墓拷・砧ax(0, score)・峨ゅΞ繧ｹ繝昴Φ繧ｹ縺ｫ `score` 繝輔ぅ繝ｼ繝ｫ繝芽ｿｽ蜉
- [x] 式 **P2: Pixel Defense 繧ｲ繝ｼ繝繧ｪ繝ｼ繝舌・蠕・遘偵け繝ｼ繝ｫ繝繧ｦ繝ｳ** (`web_pet/pixel_defense.js`):
  - `GAMEOVER_COOLDOWN_MS = 1000` + `game.gameoverAt` 險倬鹸 竊・GAME OVER 逕ｻ髱｢縺瑚ｪ､繧ｿ繝・・縺ｧ蜊ｳ繧ｹ繧ｭ繝・・縺輔ｌ繧九・繧帝亟豁｢
- [x] ｧｪ **譁ｰ隕冗ｵ仙粋繝・せ繝・* (`tests/test_sync_lan_selfheal.py` 7莉ｶ):
  - 繧ｨ繝輔ぉ繝｡繝ｩ繝ｫ繝昴・繝・(0逡ｪ) + DB螳悟・Mock髫秘屬 竊・**譛ｬ逡ｪ繧｢繝励Μ遞ｼ蜒堺ｸｭ縺ｧ繧ょｮ牙・縺ｫ螳溯｡悟庄閭ｽ**
  - 繧ｫ繝舌・: 髱咏噪驟堺ｿ｡ no-store / `?v=5.6` 繝舌せ / LAN閾ｪ蟾ｱ豐ｻ逋・GET險ｱ蜿ｯ / 繝医・繧ｯ繝ｳ閾ｪ蟾ｱ豐ｻ逋帝・蟶・/ POST 401 / Bearer莉榔OST謌仙粥 / 繧ｹ繧ｳ繧｢繧ｯ繝ｩ繝ｳ繝・- [x] 売 **譌｢蟄倥ユ繧ｹ繝医・髯ｳ閻仙喧菫ｮ豁｣** (`tests/test_sync_auth.py`):
  - T1/T3 繧・2026-08-30 閾ｪ蟾ｱ豐ｻ逋剃ｻ墓ｧ倥↓譖ｴ譁ｰ・域立Fail-Closed蜑肴署縺ｮ縺ｾ縺ｾ縺ｧ縺ｯ迴ｾ蝨ｨ縺ｮ繧ｳ繝ｼ繝峨〒蠢・★RED・峨５1b(螟夜ΚIP 403)繝ｻT3b(POST 401) 霑ｽ蜉縺ｧ繧ｻ繧ｭ繝･繝ｪ繝・ぅ蝗槫ｸｰ繧ｫ繝舌・縺ｯ邯ｭ謖・- [x] 潤 **蜈ｨ繝・せ繝医げ繝ｪ繝ｼ繝ｳ**: `python -m unittest discover -s tests` 竊・**41 tests OK**

### ・ 螳滓ｩ溽｢ｺ隱阪ヵ繧｣繝ｼ繝峨ヰ繝・け縺ｮ霑ｽ蜉菫ｮ豁｣ (2026-08-30 15:13)
- [x] 劫 **繝昴Δ繝峨・繝ｭ繝懊ち繝ｳ縺ｮ逵溘ヨ繧ｰ繝ｫ蛹・* (`web_pet/pet.js` `togglePomodoro`):
  - 譌ｧ螳溯｣・・迥ｶ諷九↓髢｢菫ゅ↑縺丞ｸｸ縺ｫ `start_pomodoro` 繧帝∽ｿ｡ 竊・蜀肴款荳九〒繧ｫ繧ｦ繝ｳ繝医′繝ｪ繧ｻ繝・ヨ縺輔ｌ繧九□縺代〒 OFF 縺ｫ縺ｪ繧峨↑縺九▲縺・  - `currentPomodoro.active` 繧貞愛螳壹＠縲∝ｮ溯｡御ｸｭ縺ｯ繧ｵ繝ｼ繝舌・譌｢蟄倥・ `stop_pomodoro` 繧｢繧ｯ繧ｷ繝ｧ繝ｳ (`local_sync_server.py` L1216) 繧帝∽ｿ｡
  - 螳溯｡御ｸｭ縺ｯ繝倥ャ繝繝ｼ繧｢繧､繧ｳ繝ｳ繧・`劫竊停昌` 縺ｫ蛻・崛縺励梧款縺吶→豁｢縺ｾ繧九阪％縺ｨ繧貞庄隕門喧
- [x] 太 **遘伜ｯ・・驛ｨ螻九い繧､繝ｪ繧ｹ繧｢繧ｦ繝亥・髱｢蛻ｷ譁ｰ** (`web_pet/index.html`, `web_pet/pet.js` `triggerSecretRoomIris`):
  - 譌ｧ螳溯｣・・莠碁㍾谺髯･: 竭`display:none竊鍛lock` 縺ｨ繧ｯ繝ｩ繧ｹ螟画峩縺悟酔繝輔Ξ繝ｼ繝縺ｧ驕ｷ遘ｻ繧｢繝九Γ縺檎匱轣ｫ縺励↑縺・竭｡鮟貞ｹ輔ｒ `clip-path` 縺ｧ荳ｸ縺上け繝ｪ繝・・縺吶ｋ譁ｹ蠑上・貍泌・縺ｨ縺励※隲也炊縺碁・ｼ亥精縺・ｾｼ縺ｿ縺ｫ縺ｪ繧峨↑縺・ｼ・  - 譌ｧ繝槭Μ繧ｪ縺ｨ蜷後§讒矩縺ｸ蛻ｷ譁ｰ: 繧ｿ繝・・轤ｹ荳ｭ蠢・・縲碁乗・縺ｪ遨ｴ・狗ｩｴ縺ｮ螟門・繧貞沂繧√ｋ蟾ｨ螟ｧ縺ｪ鮟貞ｽｱ (`.iris-hole`)縲阪ｒ `transform: scale` 縺ｧ邵ｮ蟆鞘・繧ｲ繝ｼ繝襍ｷ蜍補・螻暮幕縲ゅム繝悶Ν rAF 縺ｧ謠冗判遒ｺ螳壹ｒ菫晁ｨｼ縲～try/finally` 縺ｧ繧ｪ繝ｼ繝舌・繝ｬ繧､谿狗蕗・医°縺､縺ｦ縺ｮ逕ｻ髱｢蟆・事髫懷ｮｳ・峨ｒ讒矩逧・↓蟆√§縲∵ｼ泌・荳ｭ縺ｮ騾｣謇灘・蜈･繧る亟豁｢
  - z-index 99999 竊・100001 (繧ｲ繝ｼ繝繝｢繝ｼ繝繝ｫ 100000 縺ｮ荳・ 縺ｧ髢句ｹ輔・繧｢繧､繝ｪ繧ｹ繧､繝ｳ繧りｦ九○繧・- [x] ｧｪ **繧ｭ繝｣繝・す繝･繝舌せ3轤ｹ蜷梧悄繝・せ繝医・讒矩逧・ｼｷ蛹・* (`tests/test_sync_lan_selfheal.py`):
  - `?v=5.6` 繝上・繝峨さ繝ｼ繝峨ｒ蟒・ｭ｢縺励景ndex.html 3譛ｬ縺ｮscript繧ｿ繧ｰ縺ｮ ?v= 荳閾ｴ ・・sw.js CACHE_NAME ・・pet.js 繝代・繧ｸ險ｱ蜿ｯ繧ｭ繝ｼ縺ｮ荳閾ｴ縲阪ｒ閾ｪ蜍墓､懆ｨｼ縺吶ｋ譁ｹ蠑上∈・井ｻ雁ｾ後・繝舌・繧ｸ繝ｧ繝ｳ譖ｴ譁ｰ縺ｧ繝・せ繝医′螢翫ｌ縺ｪ縺・ｼ・- [x] 薄 **繧ｭ繝｣繝・す繝･繝舌せ v5.6 竊・v5.7** (`web_pet/pet.js:10` / `web_pet/sw.js:5` / `web_pet/index.html` script繧ｿ繧ｰﾃ・)
- [x] 潤 **蜀肴､懆ｨｼ繧ｰ繝ｪ繝ｼ繝ｳ**: `node --check` 4繝輔ぃ繧､繝ｫOK ・・`unittest discover` 竊・**41 tests OK (EXITCODE=0)**

### 繝懊せ謇句虚繧ｿ繧ｹ繧ｯ・亥ｮ滓ｩ滓怙邨ら｢ｺ隱搾ｼ・- [ ] 繧｢繝励Μ蜀崎ｵｷ蜍・ `start.bat` 繧貞ｮ溯｡鯉ｼ・owerShell: `.\start.bat`・・- [ ] 繧ｹ繝槭・螳滓ｩ溘〒繝壹・繧ｸ蜀崎ｪｭ霎ｼ・・蝗槭Μ繝ｭ繝ｼ繝画耳螂ｨ・・蝗樒岼縺ｧ譁ｰsw.js蜿冶ｾｼ縲・蝗樒岼縺ｧ譁ｰpet.js謠冗判・・- [ ] 蜍穂ｽ懃｢ｺ隱・ 蜷梧悄 陦ｨ遉ｺ / 繧ｵ繧ｸ繧ｧ繧ｹ繝医せ繝ｯ繧､繝・/ TODO繝ｯ繝ｳ繧ｿ繝・・螳御ｺ・- [ ] 蜍穂ｽ懃｢ｺ隱・ 劫繝昴Δ繝峨・繝ｭ 髢句ｧ・竊・螳溯｡御ｸｭ縺ｫ繝懊ち繝ｳ(竢ｹ)縺ｧ**蛛懈ｭ｢**縺吶ｋ縺薙→
- [ ] 蜍穂ｽ懃｢ｺ隱・ 太遘伜ｯ・・驛ｨ螻・繧ｿ繝・・縺ｧ**蜷ｸ縺・ｾｼ縺ｿ 竊・繧ｲ繝ｼ繝螻暮幕**縺ｮ繝｢繝ｼ繧ｷ繝ｧ繝ｳ
- [ ] (莉ｻ諢・ 繧｢繝励Μ蛛懈ｭ｢荳ｭ縺ｫ `venv\Scripts\python.exe tests\test_sync_auth.py` 縺ｧ繝昴・繝・765螳溽ｵ仙粋縺ｮ隱崎ｨｼ繝・せ繝・
---

## ・ 2026-08-30 繧ｻ繝・す繝ｧ繝ｳ謌先棡縺ｨ蜿悶ｊ邨・∩荳ｭ縺ｮ譛ｪ隗｣豎ｺ繧ｿ繧ｹ繧ｯ

### 螳御ｺ・- [x] 太 **遘伜ｯ・・驛ｨ螻・繧ｵ繝ｼ繧ｯ繝ｫ證苓ｻ｢・医い繧､繝ｪ繧ｹ繧｢繧ｦ繝茨ｼ峨ヨ繝ｩ繝ｳ繧ｸ繧ｷ繝ｧ繝ｳ** (`web_pet/index.html`, `web_pet/pet.js`):
  - CSS `clip-path: circle(...)` 縺ｫ繧医ｋ繝ｬ繝医Ο繧ｲ繝ｼ繝鬚ｨ縺ｮ蜷ｸ縺・ｾｼ縺ｿ證苓ｻ｢繧｢繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ繧貞ｮ溯｣・・- [x] 誓 **繝壹ャ繝医・閾ｪ蠕狗函豢ｻ繧ｵ繧､繧ｯ繝ｫ ・・繝昴Δ繝峨・繝ｭ豁灘万繝｢繝ｼ繧ｷ繝ｧ繝ｳ** (`web_pet/pet.js`):
  - 譎る俣蟶ｯ・磯｣滉ｺ九・莉穂ｺ九・隱ｭ譖ｸ繝ｻ縺企｢ｨ蜻ゅ・逹｡逵・峨♀繧医・豌励∪縺舌ｌ陦悟虚縺ｫ蠢懊§縺溘せ繝励Λ繧､繝・蜿ｰ隧槭・閾ｪ蜍募・譖ｿ・・5遘偵＃縺ｨ・峨→縲√・繝｢繝峨・繝ｭ邨ゆｺ・凾縺ｮ豁灘万繝繝ｳ繧ｹ繝ｻ繧ｯ繝ｩ繝・き繝ｼ貍泌・・・30 XP・峨・- [x] 漕 **繧ｵ繧ｸ繧ｧ繧ｹ繝医き繝ｼ繝峨・謫堺ｽ懈ｧ蠑ｷ蛹・・・TODO繝ｯ繝ｳ繧ｿ繝・・螳御ｺ・* (`web_pet/index.html`, `web_pet/pet.js`):
  - 繧ｫ繝ｼ繝牙崋螳夐ｫ倥＆・・18px・峨√き繝ｼ繝牙・逶ｴ謗･縲娯怛 螳御ｺ・阪・繧ｿ繝ｳ險ｭ鄂ｮ縲√せ繝ｯ繧､繝励→繝懊ち繝ｳ繧ｿ繝・・縺ｮ謗剃ｻ門宛蠕｡縲・- [x] 糖 **start.bat 縺ｮ邏尿SCII螳悟・蛻ｷ譁ｰ** (`start.bat`):
  - Windows 繧ｳ繝槭Φ繝峨・繝ｭ繝ｳ繝励ヨ・・P932・峨〒縺ｮ譁・ｭ怜喧縺第ｧ区枚蟠ｩ螢翫ｒ譬ｹ邨ｶ縲・- [x] 孱・・**蜷御ｸLAN蜀・閾ｪ蟾ｱ豐ｻ逋偵ヨ繝ｼ繧ｯ繝ｳ繝上Φ繝峨す繧ｧ繧､繧ｯ** (`local_sync_server.py`, `web_pet/pet.js`):
  - 蜷御ｸLAN謗･邯壽凾縺ｮ `/api/auth/token` 閾ｪ蜍暮・蟶・√せ繝・・繧ｿ繧ｹAPI縺ｸ縺ｮ `sync_token` 豺ｻ莉倥↓繧医ｋ閾ｪ蟾ｱ豐ｻ逋偵・- [x] ｧｹ **荳崎ｦ√Ξ繧ｬ繧ｷ繝ｼ繧｢繧ｻ繝・ヨ縺ｮ螳悟・謦､蟒・* (`assets/`):
  - 驥崎､・＠縺ｦ縺・◆繧､繝ｫ繧ｫ繧ｭ繝｣繝ｩ・・assets/dot/dolphin/`・峨♀繧医・譌ｧ莠ｺ蝙狗ｧ俶嶌縺上ｓ・・assets/images/characters/hisho/`・峨・迚ｩ逅・炎髯､縲・
### 螳御ｺ・- [x] 倹 **API繧ｭ繝ｼ荳崎ｦ√・逋ｻ骭ｲ荳崎ｦ√・Web讀懃ｴ｢/繝九Η繝ｼ繧ｹ蜿門ｾ怜渕逶､** (`web_tools.py` 譁ｰ險ｭ):
  - Google News RSS & Jina Search / Jina Reader 縺ｫ繧医ｋ繧ｼ繝ｭ險ｭ螳壹・螳悟・辟｡譁吶・螟夜Κ繝ｪ繧ｵ繝ｼ繝√Δ繧ｸ繝･繝ｼ繝ｫ縲・angGraph Tool蟇ｾ蠢・- [x] 笞呻ｸ・**繧ｵ繧ｸ繧ｧ繧ｹ繝磯未蠢・く繝ｼ繝ｯ繝ｼ繝峨・險ｭ螳壹き繧ｹ繧ｿ繝槭う繧ｺ** (`suggest_config.json`, `suggest_engine.py`, `ui/settings_window.py`, `local_sync_server.py`):
  - 繝ｦ繝ｼ繧ｶ繝ｼ縺斐→縺ｫ闊亥袖縺ｮ縺ゅｋ蛻・㍽・井ｾ・ `AI, 繝阪ャ繝医Ρ繝ｼ繧ｯ, 繧ｯ繝ｩ繧ｦ繝荏・峨ｒ險ｭ螳啅I縺九ｉ繧ｫ繝ｳ繝槫玄蛻・ｊ縺ｧ閾ｪ逕ｱ蜈･蜉帙・豌ｸ邯壼喧
- [x] ｧ **3陦窟I繧ｵ繝槭Μ讖溯・・医ワ繧､繝悶Μ繝・ラ譁ｹ蠑擾ｼ・* (`suggest_engine.py`):
  - RSS遲峨・險倅ｺ句叙蠕玲凾縺ｫ遘俶嶌縺上ｓ蜀・Κ縺ｮ雜・ｻｽ驥就I・・LLMFactory`・峨〒隕∫せ繧偵後・繝昴う繝ｳ繝・\n繝ｻ繝昴う繝ｳ繝・\n繝ｻ繝昴う繝ｳ繝・縲阪・3陦後↓閾ｪ蜍戊ｦ∫ｴ・ゅが繝輔Λ繧､繝ｳ/繧ｨ繝ｩ繝ｼ譎ゅ・蜿･轤ｹ蛻・牡繝ｫ繝ｼ繝ｫ繝吶・繧ｹ縺ｸ閾ｪ蜍輔ヵ繧ｩ繝ｼ繝ｫ繝舌ャ繧ｯ
- [x] 套 **螟夜Κ繧ｫ繝ｬ繝ｳ繝繝ｼ繝ｻSaaS繝槭Ν繝∽ｸｭ邯儻ebhook騾｣謳ｺ蝓ｺ逶､** (`webhook_tools.py`, `local_sync_server.py`, `ui/settings_window.py`, `agent.py`):
  - Google蜈ｬ蠑衆Auth縺ｮ100蜷榊宛髯舌ｒ蝗樣∩縺励√Θ繝ｼ繧ｶ繝ｼ閾ｪ霄ｫ縺ｮ縲兄apier / Make / IFTTT / GAS縲晃ebhook URL繧定ｨｭ螳壹☆繧九□縺代〒Google繧ｫ繝ｬ繝ｳ繝繝ｼ繝ｻNotion繝ｻSlack繝ｻLINE縺ｨ蜿梧婿蜷大酔譛溘〒縺阪ｋ逍守ｵ仙粋繝上ヶ蝓ｺ逶､繧貞ｮ悟・螳溯｣・  - `POST /api/webhook/calendar`, `POST /api/webhook/task` 縺ｫ繧医ｋ蜿嶺ｿ｡逕ｨ繧ｨ繝ｳ繝峨・繧､繝ｳ繝医→蜈ｱ譛峨す繝ｼ繧ｯ繝ｬ繝・ヨ隱崎ｨｼ繧貞ｮ悟ｙ
- [x] ｧｪ **迢ｬ遶区､懆ｨｼ・・erifier・牙腰菴薙ユ繧ｹ繝井ｽ懈・**:
  - `tests/test_suggest_news_summary.py` (繝九Η繝ｼ繧ｹ繧ｵ繧ｸ繧ｧ繧ｹ繝亥腰菴薙ユ繧ｹ繝・
  - `tests/test_webhook_integration.py` (Webhook騾∝女菫｡繝ｻDB蜿肴丐蜊倅ｽ薙ユ繧ｹ繝・

---

## ・ 2026-08-29 繧ｻ繝・す繝ｧ繝ｳ謌先棡 (Sprint 5: 繝舌ぜ逎ｨ縺崎ｾｼ縺ｿ ・・LFM2.5蜷梧｢ｱ)

### 螳御ｺ・- [x] 屏・・**11.3 谿ｵ髫取ｼ泌・繧ｨ繝ｳ繧ｸ繝ｳ縺ｮ霆ｽ驥丞喧繝ｻ繧ｹ繧ｭ繝・・險ｭ螳・* (`web_pet/easter_eggs.js`, `web_pet/pet.js`):
  - 貍泌・繝｢繝ｼ繝・谿ｵ髫趣ｼ域ｨ呎ｺ・霆ｽ驥・OFF・峨ｒlocalStorage豌ｸ邯壼喧縲りｨｭ螳壹Δ繝ｼ繝繝ｫ縲娯惠 繧､繝ｼ繧ｹ繧ｿ繝ｼ繧ｨ繝・げ貍泌・繝｢繝ｼ繝峨阪°繧牙ｾｪ迺ｰ蛻・崛
  - 蛻晏屓繧｢繧ｯ繧ｻ繧ｹ譎ゅ～prefers-reduced-motion`繝ｻ`deviceMemory竕､2`繝ｻ`hardwareConcurrency竕､4` 縺ｮ遶ｯ譛ｫ縺ｯ閾ｪ蜍輔〒縲瑚ｻｽ驥上阪↓險ｭ螳・  - 霆ｽ驥上Δ繝ｼ繝・ 驥阪＞繧ｨ繝輔ぉ繧ｯ繝茨ｼ域険蜍・繝代Ν繧ｹ/繧ｰ繝ｪ繝・メ/蜈ｨ逕ｻ髱｢Canvas邊貞ｭ撰ｼ峨ｒ逵∫払縺礼洒縺・ヵ繧ｧ繝ｼ繝峨〒莉｣譖ｿ縲０FF繝｢繝ｼ繝峨〒繧・*隗｣謾ｾ繝舌ャ繧ｸ轤ｹ轣ｯ縺ｪ縺ｩ縺ｮ螳溘Ο繧ｸ繝・け縺ｯ蠢・★邯ｭ謖・*
- [x] 洞 **LFM2.5 蛻晏屓襍ｷ蜍疋L譁ｹ蠑上・螳溯｣・* (`tools/setup_local_model.py` 譁ｰ隕・:
  - 繝｢繝・Ν繧ｫ繧ｿ繝ｭ繧ｰ2谿ｵ讒区・: **350m・域耳螂ｨ繝ｻ雜・ｻｽ驥上Δ繝ｼ繝・邏・30MB・・* ・・**1.2b・磯ｫ伜刀雉ｪ繝｢繝ｼ繝・邏・70MB・・*縲∝・蠑秀GUF縺ｮ **QAD-Q4_0**・磯㍼蟄仙喧隱崎ｭ倩頂逡咏沿・峨ｒ謗｡逕ｨ
  - 蟇ｾ隧ｱ蠑城∈謚橸ｼ義--model` 髱槫ｯｾ隧ｱ・義--list`縲るｲ謐励Ο繧ｰ繝ｻ繧ｵ繧､繧ｺ螯･蠖捺ｧ讀懆ｨｼ・域怙菴・00MB・九Μ繝｢繝ｼ繝医し繧､繧ｺ辣ｧ蜷茨ｼ峨・`.env` 閾ｪ蜍墓嶌縺崎ｾｼ縺ｿ・・LOCAL_GGUF_MODEL`・義DEFAULT_LLM_PROVIDER=local_gguf`・・  - `start.bat`: models/*.gguf 譛ｪ讀懷・譎ゅ・縺ｿ縲後そ繝・ヨ繧｢繝・・縺励∪縺吶°・歇Y/N]縲阪ｒ謠千､ｺ・医せ繧ｭ繝・・蜿ｯ・・  - `llm_factory.py`: LOCAL_GGUF 繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ荳隕ｧ縺ｨ譌｢螳壹Δ繝・Ν繧偵き繧ｿ繝ｭ繧ｰ縺ｨ謨ｴ蜷・  - **繝ｩ繧､繧ｻ繝ｳ繧ｹ遒ｺ隱肴ｸ医∩**: LFM Open License v1.0 窶・隨ｬ5譚｡縺ｫ繧医ｊ蟷ｴ髢灘庶蜈･$10M譛ｪ貅縺ｮ蝠・畑蛻ｩ逕ｨ蜿ｯ繝ｻ蜀埼・蟶・庄縲３EADME縺ｸ繧ｯ繝ｬ繧ｸ繝・ヨ險倩ｼ・- [x] ｧｪ **繝・せ繝・*: `tests/test_setup_local_model.py` 6莉ｶ・医き繧ｿ繝ｭ繧ｰ謨ｴ蜷・URL邨・ｫ・.env豌ｸ邯壼喧/荳肴ｭ｣繧ｭ繝ｼ諡貞凄・・*蜈ｨ繝代せ**
- [x] 塘 **README蛻ｷ譁ｰ**: 讖溯・荳隕ｧ縺ｫ譛昜ｼ・繧ｷ繝ｼ繧ｯ繝ｬ繝・ヨ/繧ｪ繝輔Λ繧､繝ｳAI繧定ｿｽ險倥√交沒ｴ 繧ｪ繝輔Λ繧､繝ｳAI蜷梧｢ｱ (LFM2.5)縲阪そ繧ｯ繧ｷ繝ｧ繝ｳ・記iquid AI繧ｯ繝ｬ繧ｸ繝・ヨ譁ｰ險ｭ
- [x] 汐 **繝・Δ蜍慕判繧ｷ繝翫Μ繧ｪ菴懈・** (`docs/temp/繝・Δ蜍慕判繧ｷ繝翫Μ繧ｪ_30sec.md`): Phase L 謌仙粥蝓ｺ貅問蔵逕ｨ縺ｮ30遘貞床譛ｬ
- [x] 成 **retro_dolphin 蛻､螳壹す繝ｼ繝育函謌・* (`docs/temp/retro_dolphin_review_20260829.png`, `tools/make_retro_dolphin_review_sheet.py`): 繝懊せ譛邨ょ愛螳壼ｾ・■
- [x] `version.py` 縺ｯ譌｢縺ｫ v1.0.0・亥､画峩荳崎ｦ∫｢ｺ隱肴ｸ医∩・・
### 繝懊せ謇句虚繧ｿ繧ｹ繧ｯ・医Μ繝ｪ繝ｼ繧ｹ蜑阪↓蠢・ｦ・ｼ・- [ ] 螳滓ｩ溽｢ｺ隱・ `python main.py` 竊・Pixel Defense蜍穂ｽ懊・貍泌・繝｢繝ｼ繝牙・譖ｿ繝ｻ`python tools/setup_local_model.py` 縺ｧ縺ｮDL
- [ ] README逕ｨ繧ｹ繧ｯ繝ｪ繝ｼ繝ｳ繧ｷ繝ｧ繝・ヨ3譫夲ｼ・C繝壹ャ繝・繧ｹ繝槭・PWA/謇句ｸｳ・峨ｒ `docs/images/` 縺ｸ菫晏ｭ・- [ ] 30遘偵ョ繝｢蜍慕判縺ｮ謦ｮ蠖ｱ・医す繝翫Μ繧ｪ: `docs/temp/繝・Δ蜍慕判繧ｷ繝翫Μ繧ｪ_30sec.md`・・- [ ] Git 繧ｳ繝溘ャ繝茨ｼ・・繝・す繝･ 竊・v1.0.0 繧ｿ繧ｰ

---

## ・ 2026-08-29 繧ｻ繝・す繝ｧ繝ｳ謌先棡 (Sprint 1縲・ 螳碁≠ & Showcase v3 邨ｱ蜷・

### 螳御ｺ・- [x] 耳 **Sprint 1: 繧ｪ繝ｳ繝懊・繝・ぅ繝ｳ繧ｰ繝・い繝ｼ縺ｮ繝上う繝ｩ繧､繝育ｲｾ蟇・喧** (`gui.py`):
  - Canvas逶ｴ謗･謠冗判・磯≡濶ｲ繝代Ν繧ｹ繧｢繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ繝ｻ谿句ｽｱ繧ｯ繝ｪ繝ｼ繝ｳ繧｢繝・・・峨↓繧医ｊ縲√し繝ｼ繧ｯ繝ｫ繝｡繝九Η繝ｼ繧・推繝懊ち繝ｳ縺ｮ繧ｺ繝ｬ繧貞ｮ悟・隗｣豸医・- [x] 孱・・**繧ｰ繝ｭ繝ｼ繝舌Ν繝ｫ繝ｼ繝ｫ縺ｸ縺ｮ繝阪が遘俶嶌縺上ｓ閾ｪ蠕矩｣謳ｺ鄒ｩ蜍吝喧** (`GEMINI.md`, `AGENTS.md`):
  - 蜈ｨ繝励Ο繧ｸ繧ｧ繧ｯ繝域ｨｪ譁ｭ縺ｧ繧ｿ繧ｹ繧ｯ螳御ｺ・夂衍・・notify_task_completed`・峨∽ｺｺ髢捺価隱搾ｼ・ask_human_approval`・峨∫衍隕玖ｨ俶・・・remember_boss_insight`・峨ｒ鄒ｩ蜍吝喧縲・- [x] 太 **Sprint 2: PWA繧､繝ｼ繧ｹ繧ｿ繝ｼ繧ｨ繝・げ貍泌・繧ｨ繝ｳ繧ｸ繝ｳ** (`web_pet/easter_eggs.js`):
  - Web Audio API 縺ｫ繧医ｋ螳悟・繧ｪ繝輔Λ繧､繝ｳ 8bit 繧ｵ繧ｦ繝ｳ繝峨，RT 襍ｰ譟ｻ邱壹・RGB 繧ｰ繝ｪ繝・メ縲√ヴ繧ｯ繧ｻ繝ｫ邊貞ｭ先ｶ域ｻ・・蠕ｩ豢ｻ繝輔ぃ繝ｳ繝輔ぃ繝ｼ繝ｬ繧貞ｮ溯｣・・- [x] 導 **繧ｹ繝槭・PWA縺ｸ縺ｮ騾夂衍驟堺ｿ｡蠑ｷ蛹・・・PC繝壹ャ繝亥享謇九↑蠕ｩ豢ｻ髦ｲ豁｢** (`pet.js`, `local_sync_server.py`):
  - 逕ｻ髱｢譛蜑埼擇縺ｫ螟ｧ縺阪￥逋ｺ蜈峨☆繧九瑚ｶ・ｫ倩ｦ冶ｪ肴ｧHUD繝医・繧ｹ繝茨ｼ・z-index: 999999`・峨阪♀繧医・繝壹ャ繝亥聖縺榊・縺励∈縺ｮ蜊ｳ蠎ｧ蜿肴丐縲・  - 繝舌ャ繧ｯ繧ｰ繝ｩ繧ｦ繝ｳ繝蛾夂衍譎ゅ・ `gui.show_pc_pet` 蠑ｷ蛻ｶ蜀崎｡ｨ遉ｺ繧呈賜髯､縺励・撼陦ｨ遉ｺ繝｢繝ｼ繝峨ｒ邯ｭ謖√・- [x] 笘・・**Sprint 3: Phase L3 譛昜ｼ・邨ら､ｼ繝悶Μ繝ｼ繝輔ぅ繝ｳ繧ｰ ・・蝨ｰ蝓溯ｨｭ螳・* (`briefing_engine.py`, `local_sync_server.py`, `web_pet/pet.js`, `weather_tools.py`, `gui.py`):
  - `briefing_engine.py`: 莉頑律縺ｮ莠亥ｮ壹・驥崎ｦゝODO繝ｻ螟ｩ豌励・鄙呈・驕疲・迥ｶ豕√ｒ髮・ｴ・＠縲∵凾髢灘ｸｯ縺ｫ蠢懊§縺溽嶌譽貞床隧槭・隕∫ｴ・Ξ繝昴・繝医ｒ逕滓・縺吶ｋ Deep Module 繧呈眠險ｭ縲・  - `weather_tools.py` ・・`local_sync_server.py`: 縺贋ｽ上∪縺・・蝨ｰ蝓滂ｼ磯・驕灘ｺ懃恁繝ｻ蟶ら伴譚大錐・峨・謇句虚險ｭ螳壹・繧ｸ繧ｪ繧ｳ繝ｼ繝・ぅ繝ｳ繧ｰ繝ｻ`.env`豌ｸ邯壼喧繝ｻPWA險ｭ螳壹Δ繝ｼ繝繝ｫ騾｣謳ｺ繧貞ｮ悟ｙ縲・  - 繧ｹ繝槭・PWA: 縲娯・・・譛昜ｼ壹ヶ繝ｪ繝ｼ繝輔ぅ繝ｳ繧ｰ繧定◇縺・/ 嫌 邨ら､ｼ譌･蝣ｱ縲阪け繧､繝・け繝舌リ繝ｼ ・・Glass Bottom Sheet 繝ｪ繝・メ陦ｨ遉ｺ ・・Web Speech API (TTS) 髻ｳ螢ｰ隱ｭ縺ｿ荳翫￡騾｣蜍輔・  - PC GUI: 蜿ｳ繧ｯ繝ｪ繝・け繝｡繝九Η繝ｼ縺九ｉ繝ｯ繝ｳ繧ｯ繝ｪ繝・け縺ｧ蜷ｹ縺榊・縺励∈隕∫ｴ・｡ｨ遉ｺ縲・  - `tests/test_briefing_engine.py` 繝ｦ繝九ャ繝医ユ繧ｹ繝井ｽ懈・繝ｻ繝代せ遒ｺ隱阪・- [x] 鋤・・**Product Showcase v3 ・・fireworks-open-eli5 譌･譛ｬ隱槫ｮ悟・邨ｱ蜷・* (`render_ja.mjs`, `neo-secretary-showcase.html`):
  - PO隕也せ・芋沁ｯ蛹玲･ｵ譏溘・虫3螟ｧ謠蝉ｾ帑ｾ｡蛟､・峨→縲∝虚逧・す繧ｰ繝翫Ν繝医Ξ繝ｼ繧ｹ・医ョ繝ｼ繧ｿ縺ｮ豬∝虚繧｢繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ・峨、rchify蜈ｨ菴薙Λ繝ｳ繧ｿ繧､繝魑･迸ｰ蝗ｳ・・ignal Flow / 繧ｬ繧､繝峨ヤ繧｢繝ｼ螳悟・蜍穂ｽ懶ｼ峨∝承繧ｹ繝ｩ繧､繝画ｦりｦ∬ｪｬ譏弱ラ繝ｭ繝ｯ繝ｼ・・hat/霄ｫ霑代↑萓九∴/Why/繧ｳ繝ｼ繝会ｼ峨ｒ1譛ｬ縺ｮ鄒弱＠縺・せ繝医・繝ｪ繝ｼ縺ｫ螳悟・邨ｱ蜷医・  - `fireworks-open-eli5` 繧ｹ繧ｭ繝ｫ縺ｮ螳悟・譌･譛ｬ隱櫁ｾ樊嶌縺ｨ繝ｬ繝ｳ繝繝ｩ繝ｼ繧呈ｧ狗ｯ峨＠縲√げ繝ｭ繝ｼ繝舌Ν謇区惆縺ｨ縺励※豌ｸ邯壼喧縲・- [x] **谺｡譛溘ち繧ｹ繧ｯ (Sprint 4)**: Phase L5 繧ｷ繝ｼ繧ｯ繝ｬ繝・ヨ繝溘ル繧ｲ繝ｼ繝縲訓ixel Defense縲阪ｒ螳溯｣・ｮ御ｺ・ｼ・026-08-29 22:00・・
  - `database.py`: `MinigameScore` 繝｢繝・Ν ・・`minigame_scores` 繝・・繝悶Ν・医ワ繧､繧ｹ繧ｳ繧｢讀懃ｴ｢繧､繝ｳ繝・ャ繧ｯ繧ｹ莉倥″・会ｼ・`record_minigame_score` / `get_high_score` / `get_recent_minigame_scores` CRUD 繧呈眠險ｭ
  - `local_sync_server.py`: `POST /api/action` 縺ｫ `record_minigame_score` 繧｢繧ｯ繧ｷ繝ｧ繝ｳ繧定ｿｽ蜉・・ame_id繝ｻscore蜿嶺ｿ｡ 竊・SQLite豌ｸ邯壼喧 竊・high_score霑泌唆・・  - `web_pet/pixel_defense.js`: Canvas 8bit繧ｲ繝ｼ繝繝ｫ繝ｼ繝暦ｼ郁・讖溘・繧､繝ｳ繝吶・繝繝ｼ邱ｨ髫企剄荳九・謨ｵ蠑ｾ繝ｻ辷・匱繝代・繝・ぅ繧ｯ繝ｫ繝ｻ谿区ｩ溘・繝ｬ繝吶Ν蜉騾滂ｼ会ｼ・Web Audio 遏ｩ蠖｢豕｢繝斐さ繝斐さ髻ｳ ・・繧ｿ繝・メ/繧ｭ繝ｼ繝懊・繝我ｸ｡蟇ｾ蠢懊Ａwindow.PixelDefense.show()/hide()` 縺ｮ逍守ｵ仙粋API
  - `web_pet/index.html`: 繝溘ル繧ｲ繝ｼ繝Canvas繝｢繝ｼ繝繝ｫ・・-index:100000繝ｻpixelated謠冗判・会ｼ・`secret-game-badge`・芋汨ｾ 遘伜ｯ・・驛ｨ螻具ｼ峨け繝ｪ繝・け縺ｧ襍ｷ蜍輔ヵ繝・け
  - `tests/test_minigame_score.py`: 繝ｦ繝九ャ繝医ユ繧ｹ繝・莉ｶ・郁ｨ倬鹸/繝上う繧ｹ繧ｳ繧｢/game_id蛻・屬/螻･豁ｴ/荳肴ｭ｣蜈･蜉帶拠蜷ｦ・・*蜈ｨ繝代せ**
- [x] `docs/specs/讖溯・繝ｭ繝ｼ繝峨・繝・・.md` 縺ｸ Phase L・・1.1縲・1.8・会ｼ句ｰ・擂繝舌ャ繧ｯ繝ｭ繧ｰ B01縲廝22 繧貞渚譏
- [x] 譌｢蟄倥さ繝ｼ繝峨→縺ｮ謨ｴ蜷育｢ｺ隱肴ｸ医∩: `character_manager.py`・・HARACTERS_DATA / set_character / get_character_system_prompt縲√く繝｣繝ｩID hisho繝ｻkinoko繝ｻseal・峨～web_pet/pet.js`・・HARACTERS / switch_character・峨～local_sync_server.py`・・witch_character 繧｢繧ｯ繧ｷ繝ｧ繝ｳ・・
### 屏・・螳溯｣・・譫懶ｼ亥酔譌･蜊亥ｾ後・2譎る俣繧ｹ繝励Μ繝ｳ繝茨ｼ・- [x] 肌 **MCP謇ｿ隱阪ヶ繝ｪ繝・ず3荳榊・蜷井ｿｮ豁｣** (hisho_mcp_server.py / database.py):
  - `execute_create_task` 竊・`database.Task` 繝｢繝・Ν邨檎罰縺ｫ菫ｮ豁｣・・riority譁・ｭ怜・竊・-3謨ｴ謨ｰ繝槭ャ繝斐Φ繧ｰ縲［emo竊壇escription・・  - `execute_get_pending_tasks` 竊・`get_tasks(limit=)` 蜻ｼ縺ｳ蜃ｺ縺嶺ｿｮ豁｣ + memo竊壇escription + status 霑ｽ蜉
  - `database.add_user_insight()` 繧呈眠險ｭ + 繧ｫ繝・ざ繝ｪ豁｣隕丞喧繝倥Ν繝代・ `_normalize_insight_category`・亥宛邏・・Constraint 遲会ｼ峨ｒ菫晏ｭ倥・蜿門ｾ嶺ｸ｡髱｢縺ｫ驕ｩ逕ｨ
  - 螳櫂B縺ｧ蜈ｨexecute髢｢謨ｰ繝・せ繝域ｸ医∩・・LL-MCP-EXEC-TESTS-PASS縲√ユ繧ｹ繝育畑繧ｿ繧ｹ繧ｯ縺ｯ謗・勁貂医∩・・- [x] 肌 **謇ｿ隱阪ち繧､繝繧｢繧ｦ繝亥ｯｾ遲・*: `cline_mcp_settings.json` 縺ｮ neo_hisho_bridge 縺ｫ `timeout: 300` 遘偵ｒ險ｭ螳夲ｼ・SON螯･蠖捺ｧ讀懆ｨｼ貂医∩・・  - 笞・・蜿肴丐縺ｫ縺ｯ Cline 縺ｮ MCP繧ｵ繝ｼ繝舌・蜀肴磁邯夲ｼ・S Code蜀崎ｵｷ蜍慕ｭ会ｼ峨′蠢・ｦ・- [x] 耳 **L0: retro_dolphin 繧ｹ繝励Λ繧､繝育函謌・*: `tools/generate_retro_dolphin_assets.py` 譁ｰ隕丈ｽ懈・ 竊・`assets/retro_dolphin/` 縺ｫ4迥ｶ諷具ｼ・44x144 騾城℃PNG・峨ｒ逕滓・
  - v1・域ｭ｣髱｢隕厄ｼ俄・ 繝懊せ蛻､螳壹後う繝ｫ繧ｫ縺ｫ隕九∴縺ｪ縺・坂・ **v2・域ｨｪ縺九ｉ縺ｮ繧ｷ繝ｫ繧ｨ繝・ヨ: 蜿｣蜷ｻ繝ｻ閭後・繧後・閭ｸ縺ｳ繧後・豌ｴ蟷ｳ蟆ｾ縺ｳ繧鯉ｼ峨↓蜈ｨ髱｢繝ｪ繝・じ繧､繝ｳ** 竊・繝懊せ譛邨ょ愛螳・pending
  - 蟄ｦ縺ｳ: 48px繝峨ャ繝育ｵｵ縺ｧ縺ｯ蜍慕黄縺ｮ繧ｷ繝ｫ繧ｨ繝・ヨ隱崎ｭ倥・縲梧ｭ｣髱｢縲阪ｈ繧翫悟・髱｢縲阪′蝨ｧ蛟堤噪縺ｫ蠑ｷ縺・- [ ] 谺｡蝗・ L1 繧ｭ繝｣繝ｩ邨ｱ蜷・竊・L2 繧､繝ｼ繧ｹ繧ｿ繝ｼ繧ｨ繝・げ・医ヨ繝ｪ繧ｬ繝ｼ讀懃衍縺ｯ繝輔Ξ繝ｼ繧ｺ荳ｻ蛻､螳・繝帙Ρ繧､繝医Μ繧ｹ繝医〒螳溯｣・ｼ・竊・繝ｪ繝ｪ繝ｼ繧ｹ鬆・ｺ丞愛譁ｭ・域｡・/B・・
### 噫 螳溯｣・・譫懶ｼ亥酔譌･繝ｻ霑ｽ蜉2譎る俣繧ｹ繝励Μ繝ｳ繝・ L1繧ｭ繝｣繝ｩ邨ｱ蜷・+ L2讀懃衍繧ｨ繝ｳ繧ｸ繝ｳ・・- [x] **L1: retro_dolphin 繧ｭ繝｣繝ｩ邨ｱ蜷茨ｼ・繝輔ぃ繧､繝ｫ・・*:
  - `character_manager.py`: CHARACTERS_DATA 縺ｫ retro_dolphin・医Ξ繝医Ο譯亥・邊ｾ髴翫・闃晏ｱ・′縺九▲縺滉ｸ∝ｯｧ蜿｣隱ｿ繝ｻ縲梧｡亥・讌ｭ蜍吶・邯咏ｶ壹＠縺ｾ縺吶堺ｺｺ譬ｼ・芽ｿｽ蜉
  - `tools/generate_retro_dolphin_assets.py`: 諡｡蠑ｵ 竊・assets/dot/retro_dolphin/ 縺ｸ **29遞ｮ縺ｮ繧ｹ繝励Λ繧､繝亥錐繝舌Μ繧｢繝ｳ繝・*閾ｪ蜍募ｱ暮幕・・ui.py 縺ｮ dot/{char}/ 譛蜆ｪ蜈郁ｪｭ縺ｿ霎ｼ縺ｿ隕冗ｴ・↓驕ｩ蜷医∵悴螳溯｣・憾諷九・霑代＞迥ｶ諷九〒莉｣逕ｨ・・  - `gui.py`: 繧ｭ繝｣繝ｩ蛻・崛繧ｵ繧､繧ｯ繝ｫ鬆・ｺ上↓ retro_dolphin 霑ｽ蜉
  - `web_pet/pet.js`: CHARACTERS 驟榊・縺ｫ retro_dolphin・芋汾ｬ・芽ｿｽ蜉 竊・PC繝ｻ繧ｹ繝槭・荳｡譁ｹ縺ｧ蛻・崛蜿ｯ閭ｽ
- [x] **L2: easter_egg_engine.py 譁ｰ隕丞ｮ溯｣・ｼ医Ξ繝薙Η繝ｼ豎ｺ螳壻ｺ矩・.7貅匁侠・・*:
  - 繝医Μ繧ｬ繝ｼ讀懃衍: 繝輔Ξ繝ｼ繧ｺ荳ｻ蛻､螳・3遞ｮ + 莠ｺ遘ｰ霑第磁豁｣隕剰｡ｨ迴ｾ + 陬懷勧繝ｯ繝ｼ繝・隱樔ｻ･荳・+ **謫堺ｽ懈э蝗ｳ繝帙Ρ繧､繝医Μ繧ｹ繝・*・医ち繧ｹ繧ｯ/莠亥ｮ夂ｭ峨・蜑企勁繧ｳ繝槭Φ繝峨ｒ隱､辷・勁螟厄ｼ・  - 逋ｺ轣ｫ繧ｫ繧ｦ繝ｳ繧ｿ2譛ｬ遶九※: 邏ｯ遨・attempt_count・・蝗槭〒 secret_game_unlocked・・ 譌･谺｡ daily_count・・-2蝗・縺ｨ縺ｼ縺・3=蜊ｴ荳・4=繧ｰ繝ｪ繝・メ/5=隗｣謾ｾ・峨～easter_egg_state.json` 縺ｫ豌ｸ邯壼喧繝ｻ譌･霍ｨ縺手・蜍輔Μ繧ｻ繝・ヨ
  - `main.py` `_process_message` 縺ｫ繝輔ャ繧ｯ: 繝医Μ繧ｬ繝ｼ譎ゅ・LLM謗ｨ隲悶ｒ繧ｹ繧ｭ繝・・縺励※蟆ら畑蜿ｰ隧槭ｒ霑斐☆
  - `tests/test_easter_egg_engine.py`: **7繝・せ繝亥・繝代せ**・医・繝ｯ繧､繝医Μ繧ｹ繝・繝輔Ξ繝ｼ繧ｺ/莠ｺ遘ｰ霑第磁/陬懷勧繧ｹ繧ｳ繧｢/隱､辷・亟豁｢/谿ｵ髫弱お繧ｹ繧ｫ繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ/譌･谺｡繝ｪ繧ｻ繝・ヨ・・- [ ] 谿九ち繧ｹ繧ｯ: L2蠕悟濠・・WA蛛ｴ easter_eggs.js 貍泌・繝ｻ蠕ｩ豢ｻ蜿ｰ隧槭・LLM騾｣謳ｺ・峨´3 譛昜ｼ・邨ら､ｼ縲√Μ繝ｪ繝ｼ繧ｹ鬆・ｺ丞愛譁ｭ・域｡・/B・峨√ヤ繧｢繝ｼUI蜍穂ｽ懃｢ｺ隱阪｀CP繧ｵ繝ｼ繝舌・蜀肴磁邯壼ｾ後・謇ｿ隱阪・繧ｿ繝ｳ蜀阪ユ繧ｹ繝・
### 肌 螳溯｣・・譫懶ｼ亥酔譌･繝ｻ隨ｬ3繧ｹ繝励Μ繝ｳ繝・ 繧､繝ｼ繧ｹ繧ｿ繝ｼ繧ｨ繝・げLLM蛹・+ QR謗･邯壽隼菫ｮ・・- [x] **繧､繝ｼ繧ｹ繧ｿ繝ｼ繧ｨ繝・げ LLM 譁・ц蠢懃ｭ泌喧**・医・繧ｹ繝輔ぅ繝ｼ繝峨ヰ繝・け縲悟崋螳壽枚險縺ｯ繧､繝槭う繝√榊ｯｾ蠢懶ｼ・
  - `easter_egg_engine.py` 縺ｫ `observe_message()` 霑ｽ蜉: stage蛻･縺ｮ**LLM譁・ц謖・､ｺ**・・irective・峨ｒ逕滓・
  - `main.py` 繝輔ャ繧ｯ蛻ｷ譁ｰ: 繝医Μ繧ｬ繝ｼ譎ゅ・ LLM 謗ｨ隲悶↓譁・ц謖・､ｺ繧呈ｳｨ蜈･縺励※繧ｭ繝｣繝ｩ縺瑚・繧牙渚蠢懶ｼ・tage 1-4縺ｮ貍疲橿謖・､ｺ莉倥″・峨・*蝗ｺ螳壼床隧槭・ LLM 螟ｱ謨玲凾縺ｮ繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ縺ｫ髯肴ｼ**・郁ｿ皮ｭ斐↑縺・萓句､匁凾繧る←逕ｨ・・  - `handle_message()` 縺ｯ蠕梧婿莠呈鋤繧ｨ繧､繝ｪ繧｢繧ｹ縺ｨ縺励※邯ｭ謖・ｼ医ユ繧ｹ繝・莉ｶ蜈ｨ繝代せ邯咏ｶ夲ｼ・- [x] **QR謗･邯壹ム繧､繧｢繝ｭ繧ｰ Tailscale HTTPS/HTTP 荳｡蟇ｾ蠢・*・育､ｾ蜀・が繝輔ぅ繧ｹ縺ｧ繧ｹ繝槭・謗･邯壻ｸ榊庄縺ｮ蝠城｡悟ｯｾ蠢懶ｼ・
  - `ui/qr_dialog.py` 蜈ｨ髱｢謾ｹ菫ｮ: 謗･邯壼・繧ｻ繝ｬ繧ｯ繧ｿ繧偵交沍・Tailscale (HTTPS繝ｻ蜈ｨ讖溯・蟇ｾ蠢・縲阪交沍・Tailscale (HTTP繝ｻ險ｭ螳壻ｸ崎ｦ√〒謇玖ｻｽ)縲阪交沛 LAN縲阪交沍・Tailscale IP (100.x)縲阪・隍・焚蛟呵｣懊↓蟇ｾ蠢・  - `tailscale serve --bg 8765` 縺ｮ**繝ｯ繝ｳ繧ｯ繝ｪ繝・け繧ｳ繝斐・繝懊ち繝ｳ**・九ヲ繝ｳ繝郁｡ｨ遉ｺ・郁ｦ∽ｻｶ2・・  - Tailscale IP (100.64.0.0/10) 繧・ipconfig 縺九ｉ讀懷・・・*CP932繝・さ蟇ｾ蠢・*: 譌･譛ｬ隱杆indows縺ｮUTF-8繝・さ繝ｼ繝峨け繝ｩ繝・す繝･繧定ｧ｣豸茨ｼ会ｼ郁ｦ∽ｻｶ3・・  - URL逕滓・繝ｻIP蛻､螳壹ｒ邏秘未謨ｰ蛹悶＠ `tests/test_qr_dialog.py` **5繝・せ繝亥・繝代せ**・郁ｦ∽ｻｶ4・・- [ ] 谿九ち繧ｹ繧ｯ: 遉ｾ蜀・が繝輔ぅ繧ｹ縺ｧ縺ｮ螳滓ｩ溷・繝・せ繝茨ｼ・ailscale serve 譛ｪ螳溯｡檎憾諷九〒 HTTP 繝｢繝ｼ繝画磁邯壹ｒ遒ｺ隱搾ｼ峨￣WA蛛ｴ貍泌・縲∵悃莨・邨ら､ｼ縲√Μ繝ｪ繝ｼ繧ｹ鬆・ｺ丞愛譁ｭ

### 垳 螳溯｣・・譫懶ｼ亥酔譌･繝ｻ隨ｬ4繧ｹ繝励Μ繝ｳ繝・ 繝壹ャ繝育函蜻ｽ諢溷ｼｷ蛹悶ヱ繝・け・・- [x] **PWA豁ｩ陦窟I・九ヵ繝ｬ繝ｼ繝繧｢繝九Γ** (`web_pet/pet.js` + `index.html`):
  - idle_1/idle_2 繝輔Ξ繝ｼ繝蛻・崛・・00ms蜻ｨ譛滂ｼ峨〒蜻ｼ蜷ｸ諢溘い繝・・
  - 豁ｩ陦窟I: 蝨ｰ髱｢繝ｩ繧､繝ｳ荳翫ｒ繝ｩ繝ｳ繝繝豁ｩ陦鯉ｼ・-4.5遘抵ｼ俄・莨第・・・-10遘抵ｼ峨Ν繝ｼ繝励るｲ陦梧婿蜷代∈ scaleX(-1) 蜿崎ｻ｢縲∵ｭｩ陦御ｸｭ縺ｯ walk_1/walk_2 繝輔Ξ繝ｼ繝+遐ら・繧ｨ繝輔ぉ繧ｯ繝・  - 髮・ｸｭ荳ｭ繝ｻ迚ｹ蛻･迥ｶ諷九〒縺ｯ豁ｩ陦御ｸｭ譁ｭ・・etStateNow 繧ｬ繝ｼ繝会ｼ・- [x] **繧ｹ繝槭・蜿ｰ隧槭・蜍慕噪蛹・* (`gui.py` + `local_sync_server.py`):
  - gui.update_message 縺・current_message 繧剃ｿ晄戟 竊・/api/status 縺・**PC繝壹ャ繝医・譛譁ｰ繧ｻ繝ｪ繝輔ｒ繝溘Λ繝ｼ**
  - 繝上・繝峨さ繝ｼ繝牙崋螳壽枚險蟒・ｭ｢ 竊・謇ｿ隱崎ｦ∬ｫ・> 髮・ｸｭ > PC逋ｺ隧ｱ繝溘Λ繝ｼ > **繧ｭ繝｣繝ｩ蛻･謖ｨ諡ｶﾃ玲凾髢灘ｸｯﾃ・0遘偵Ο繝ｼ繝・・繧ｷ繝ｧ繝ｳ**
- [x] **繧ｫ繧､繝ｫ蠑ｷ蟇・○繧ｹ繧ｭ繝ｳ (id: kyle)** (繝懊せ譁ｹ驥戡謇ｿ隱・:
  - 繧ｸ繧ｧ繝阪Ξ繝ｼ繧ｿ繝ｼv3: PALETTES 2繧ｹ繧ｿ繧､繝ｫ蛹・豁ｩ陦後ヵ繝ｬ繝ｼ繝(walk_1/2)+**繝帙ち繝・ｲ晏梛繝弱・繝・C繧｢繧ｯ繧ｻ繧ｵ繝ｪ繝ｼ**・医き繧､繝ｫ縺ｮ繧ｷ繧ｰ繝阪メ繝｣繝ｼ・・  - 蜃ｺ蜉・ assets/kyle/ 6迥ｶ諷・+ assets/dot/kyle/ 31遞ｮ・・etro_dolphin 縺ｯ貂ｩ蟄假ｼ・  - character_manager/pet.js/gui 縺ｫ縲後き繧､繝ｫ鬚ｨ邊ｾ髴翫咲匳骭ｲ・亥・蠑冗判蜒上・隍・｣ｽ縺ｯ縺帙★閾ｪ蜑阪ラ繝・ヨ邨ｵ縺ｧ蠑ｷ蟇・○・・- [x] **PC蠕伜ｾ翫Δ繝ｼ繝・* (`pet_animator.py` + `gui.py`):
  - PetAnimator 縺ｮ繝ｩ繝ｳ繝繝Idle陦悟虚縺ｫ縲梧淵豁ｩ縲崎ｿｽ蜉・・andering_enabled 譎ゅ・縺ｿ・・  - walk 迥ｶ諷倶ｸｭ縺ｯ繧ｦ繧｣繝ｳ繝峨え縺檎判髱｢荳狗ｫｯ繧呈ｨｪ遘ｻ蜍包ｼ・px/tick・峨・遶ｯ縺ｧ譁ｹ蜷題ｻ｢謠帙・逕ｻ蜒丞ｷｦ蜿ｳ蜿崎ｻ｢・・IL FLIP_LEFT_RIGHT 繧ｭ繝｣繝・す繝･・・  - 笞吶Γ繝九Η繝ｼ縺ｫ縲交泅ｶ 蠕伜ｾ翫Δ繝ｼ繝峨阪ヨ繧ｰ繝ｫ霑ｽ蜉・医ョ繝輔か繝ｫ繝・FF繝ｻcharacter_config.json 縺ｫ豌ｸ邯壼喧・・- [x] 蜈ｨ10繝輔ぃ繧､繝ｫ py_compile 繝代せ繝ｻ繝・せ繝・2莉ｶ蜈ｨ繝代せ繝ｻ譁・ｭ怜喧縺代ぞ繝ｭ
- [x] 繝懊せ繝輔ぅ繝ｼ繝峨ヰ繝・け蟇ｾ蠢・(2026-08-29): 雋晏梛PC蜑企勁・郁ｦ冶ｪ肴ｧ荳崎憶・会ｼ乗ｭｩ陦御ｸ榊・蜷・莉ｶ菫ｮ豁｣・・W繧ｭ繝｣繝・す繝･ v4.5 繝舌Φ繝励・petStateNow TDZ 隗｣豸医・walk 繝輔Ξ繝ｼ繝譛ｪ菫晄怏繧ｭ繝｣繝ｩ縺ｮ idle 莉｣逕ｨ・会ｼ熟ode --check 繝代せ
- [ ] 谿九ち繧ｹ繧ｯ: 繧ｹ繝槭・螳滓ｩ溘〒豁ｩ陦梧嫌蜍慕｢ｺ隱搾ｼ・*PWA蜀崎ｪｭ霎ｼ2蝗・*縺ｧ SW v4.5 驕ｩ逕ｨ・峨￣C蠕伜ｾ翫・螳滓ｩ溽｢ｺ隱搾ｼ遺囮繝｡繝九Η繝ｼ竊貞ｾ伜ｾ翫Δ繝ｼ繝碓N・峨￣WA蛛ｴ貍泌・縲∵悃莨・邨ら､ｼ縲√Μ繝ｪ繝ｼ繧ｹ鬆・ｺ丞愛譁ｭ

### 繝励Ο繝繧ｯ繝亥次蜑・ｼ亥・繧ｨ繝ｼ繧ｸ繧ｧ繝ｳ繝亥・譛・/ 繝槭せ繧ｿ繝ｼ繝峨く繝･繝｡繝ｳ繝医ｈ繧奇ｼ・1. **PC譛ｬ諡蝨ｰ荳ｻ鄒ｩ**: 驥阪＞蜃ｦ逅・・遘伜ｯ・ュ蝣ｱ繝ｻOAuth繝ｻWhisper縺ｯPC蛛ｴ縲ゅせ繝槭・PWA縺ｯ阮・＞遯・2. **逶ｸ譽偵〒縺ゅ▲縺ｦ蜈ｨ驛ｨ蜈･繧翫ヤ繝ｼ繝ｫ縺ｧ縺ｯ縺ｪ縺・*: 莠ｺ譬ｼ縺ｨ逅・罰縺後≠繧区ｩ溯・縺縺醍ｩ阪・
3. **繝輔ぅ繝ｼ繝√Ε繝ｼ隗｣謾ｾ諤晄Φ**: 驥阪＞讖溯・縺ｯ蠢・ｦ√↑莠ｺ縺縺題ｧ｣謾ｾ縲よｨ呎ｺ紋ｽ馴ｨ薙・霆ｽ驥上・蜿ｯ諢帙＞縺ｾ縺ｾ
4. **PWA荳ｭ蠢・*: 繝阪う繝・ぅ繝門喧縺ｯPWA縺ｮ髯千阜縺瑚ｦ九∴縺ｦ縺九ｉ蜀肴､懆ｨ・5. **蛻､譁ｭ蝓ｺ貅・*: 縲悟・隕・遘偵〒螂ｽ縺阪↓縺ｪ繧九°縲阪・譌･蠕後ｂ譛ｺ縺ｮ荳翫↓谿九ｋ縺九阪・2霆ｸ

### 谺｡繝輔ぉ繝ｼ繧ｺ: Phase L 繝舌ぜ繝ｻ逶ｸ譽樽VP・亥━蜈磯・ｼ・- [ ] L1 (譛蜆ｪ蜈・: retro_dolphin・医Ξ繝医Ο譯亥・邊ｾ髴奇ｼ峨く繝｣繝ｩ莉墓ｧ俶ｱｺ繧・ｼ九せ繝励Λ繧､繝・迥ｶ諷・idle/appear/offended/revive)逕滓・ 竊・`character_manager.py` CHARACTERS_DATA霑ｽ蜉
- [ ] L2 (譛蜆ｪ蜈・: 縲後♀蜑阪ｒ豸医☆譁ｹ豕輔阪ヨ繝ｪ繧ｬ繝ｼ讀懃衍・九Ξ繝吶Ν1(縺ｨ縺ｼ縺・繝ｻ繝ｬ繝吶Ν2(證苓ｻ｢繝ｻ繝代・繝・ぅ繧ｯ繝ｫ)貍泌・ 竊・`web_pet/easter_eggs.js` 譁ｰ隕・- [ ] L3 (譛蜆ｪ蜈・: 譛昜ｼ・邨ら､ｼ繝｢繝ｼ繝・竊・繝ｭ繝ｼ繝峨・繝・・7.8 譌･谺｡繝悶Μ繝ｼ繝輔ぅ繝ｳ繧ｰ縺ｨ邨ｱ蜷・- [ ] L4 (谺｡轤ｹ): 繧ｰ繝ｪ繝・メ蠕ｩ豢ｻ貍泌・(繝ｬ繝吶Ν3)・狗匱轣ｫ蝗樊焚縺ｮ豌ｸ邯壼喧・・database.py` or `character_config.json`・・- [ ] L5 (谺｡轤ｹ): pixel_defense 繝溘ル繧ｲ繝ｼ繝 竊・`web_pet/minigame_pixel_defense.js` 譁ｰ隕擾ｼ育鮪邨仙粋繝ｻ蜑企勁蜿ｯ閭ｽ・・- [ ] L6 (谺｡轤ｹ): 髻ｳ螢ｰ蜈･蜉帛ｰ守ｷ壹・繧ｿ繝ｳ・倶ｺ亥ｮ夊ｿｽ蜉繝ｭ繝・け陦ｨ遉ｺ・亥慍縺ｪ繧峨＠・・
### 蛻ｶ邏・ｼ・ust / 繝槭せ繧ｿ繝ｼ繝峨く繝･繝｡繝ｳ繝医ｈ繧奇ｼ・- Microsoft繧ｭ繝｣繝ｩ縺ｮ隍・｣ｽ遖∵ｭ｢・亥錐蜑阪・霈ｪ驛ｭ繝ｻ蟆冗黄繝ｻ蜿ｰ隧槭・逕ｻ蜒上・繧ｪ繝ｪ繧ｸ繝翫Ν・・- 貍泌・縺ｯ菴弱せ繝夂ｫｯ譛ｫ縺ｧ繧りｻｽ驥擾ｼ九せ繧ｭ繝・・險ｭ螳壹ｒ逕ｨ諢・- 譌｢蟄倩ｪ崎ｨｼ繝ｻ蜷梧悄繝ｻ謇ｿ隱阪ヶ繝ｪ繝・ず縺ｮ謖吝虚繧貞｣翫＆縺ｪ縺・
### 蠑輔″邯吶℃谿九ち繧ｹ繧ｯ・・hase K縺九ｉ邯咏ｶ夲ｼ・- [ ] 繝・い繝ｼUI蜍穂ｽ懃｢ｺ隱搾ｼ医Θ繝ｼ繧ｶ繝ｼ謇句虚・・ `Remove-Item .\backups\.tour_completed -Force; python main.py`
- [ ] 肌 謇ｿ隱阪ヶ繝ｪ繝・ず荳榊・蜷郁ｪｿ譟ｻ: 謇ｿ隱阪・繧ｿ繝ｳ陦ｨ遉ｺ縺輔ｌ繧九′繧ｿ繝・・辟｡蜿榊ｿ懊・PC蛛ｴ60s繧ｿ繧､繝繧｢繧ｦ繝茨ｼ・026-08-28逋ｺ逕溘Ｏeo_hisho_bridge 縺ｮ繧ｿ繧､繝繧｢繧ｦ繝・0s < 謇ｿ隱榊ｾ・■譎る俣縺ｮ蜿ｯ閭ｽ諤ｧ縲Ｄline_mcp_settings.json 縺ｮ繧ｿ繧､繝繧｢繧ｦ繝亥ｻｶ髟ｷ・詰ocal_sync_server.py 縺ｮ蠢懃ｭ皮ｵ瑚ｷｯ遒ｺ隱搾ｼ・- [ ] K2: 髻ｳ螢ｰ繧ｦ繧ｧ繧､繧ｯ繝ｯ繝ｼ繝・/ K4-2: 繧ｬ繧､繝峨ち繝悶き繝・ざ繝ｪ蛹・/ K4-4: 迸ｬ縺阪せ繝励Λ繧､繝・- [ ] M: 繧ｳ繝溘ャ繝茨ｼ義build_exe.py` + v1.0.0繧ｿ繧ｰ/Releases

---
## ・ 2026-08-27 繧ｻ繝・す繝ｧ繝ｳ謌先棡 (繝・い繝ｼUI譬ｹ譛ｬ蜀崎ｨｭ險・

### 螳御ｺ・- [x] **K4-1逋ｺ螻・ 繝・い繝ｼUI縺ｮ譬ｹ譛ｬ蜀崎ｨｭ險・* 窶・蠕捺擂縺ｮ繝輔Ν繧ｹ繧ｯ繝ｪ繝ｼ繝ｳalpha繧ｪ繝ｼ繝舌・繝ｬ繧､(`-alpha 0.8`)繧貞ｻ・｣・＠縲・*荳埼乗・繧ｬ繧､繝峨き繝ｼ繝・380x300px Toplevel) + 繝槭ぞ繝ｳ繧ｿ騾城℃繝上う繝ｩ繧､繝医Μ繝ｳ繧ｰ**譁ｹ蠑上↓蜈ｨ髱｢蛻ｷ譁ｰ
  - `_get_tour_spotlight` 竊・`_get_tour_target_rect` (遏ｩ蠖｢繝吶・繧ｹ縺ｫ螟画峩)
  - `_place_tour_card_near` (static) 譁ｰ隕・窶・繧ｿ繝ｼ繧ｲ繝・ヨ遏ｩ蠖｢霑代￥縺ｫ繧ｫ繝ｼ繝峨ｒ繧ｹ繝槭・繝磯・鄂ｮ
  - `_update_tour_ring` 譁ｰ隕・窶・`-transparentcolor` 縺ｧ豕ｨ逶ｮUI繧帝≡濶ｲ譫縺ｧ蝗ｲ繧
  - `_update_tour_overlay` 蛻ｷ譁ｰ 窶・繧ｬ繧､繝峨き繝ｼ繝臥函謌・譖ｴ譁ｰ + 繝ｪ繝ｳ繧ｰ陦ｨ遉ｺ
  - `_destroy_tour_overlay` 蛻ｷ譁ｰ 窶・繧ｫ繝ｼ繝・繝ｪ繝ｳ繧ｰ荳｡譁ｹ縺ｮ繧ｯ繝ｪ繝ｼ繝ｳ繧｢繝・・
  - `_do_tour_action` 蠕ｮ隱ｿ謨ｴ (繝ｭ繧ｸ繝・け蜷御ｸ)
- [x] `py_compile` 讒区枚讀懆ｨｼ繝代せ
- [x] 譌ｧAPI (`_get_tour_spotlight`, `_tour_overlay`, `_tour_btn_*`) 譛ｪ蜿ら・遒ｺ隱・
### 繧｢繝ｼ繧ｭ繝・け繝√Ε荳翫・豎ｺ螳・- **alpha萓晏ｭ倥ぞ繝ｭ**: 繝輔Ν繧ｹ繧ｯ繝ｪ繝ｼ繝ｳ繝ｬ繧､繝､繝ｼ繝峨え繧｣繝ｳ繝峨え(Layered Window)縺ｮ蝠城｡後ｒ譬ｹ譛ｬ隗｣豎ｺ
- **繧ｬ繧､繝峨き繝ｼ繝・*: 荳埼乗・380x300px縲√・繝・ム繝ｼ(繧ｿ繧､繝医Ν+繧ｫ繧ｦ繝ｳ繧ｿ繝ｼ+笨輔せ繧ｭ繝・・)+繝・く繧ｹ繝・繝懊ち繝ｳ陦・- **繝上う繝ｩ繧､繝医Μ繝ｳ繧ｰ**: 繝槭ぞ繝ｳ繧ｿ騾城℃(`-transparentcolor`=螳溽ｸｾ謚豕・縺ｧ繧ｿ繝ｼ繧ｲ繝・ヨ繧帝≡濶ｲ/繧ｪ繝ｬ繝ｳ繧ｸ莠碁㍾邱壹〒蠑ｷ隱ｿ
- **tour_engine.py**: 繝・・繧ｿ螻､縺ｯ1陦後ｂ螟画峩縺励※縺・↑縺・
### 谿九ち繧ｹ繧ｯ
- [ ] **蜍穂ｽ懃｢ｺ隱・* (繝ｦ繝ｼ繧ｶ繝ｼ謇句虚): `Remove-Item .\backups\.tour_completed -Force; python main.py` 縺ｧ蜈ｨ7繧ｹ繝・ャ繝礼｢ｺ隱・- [ ] K2: 痔 髻ｳ螢ｰ繧ｦ繧ｧ繧､繧ｯ繝ｯ繝ｼ繝会ｼ域ｬ｡繝輔ぉ繝ｼ繧ｺ譛ｬ蜻ｽ・・- [ ] K4-2: 繧ｬ繧､繝峨ち繝悶き繝・ざ繝ｪ・九い繧､繧ｳ繝ｳ蛹・- [ ] K4-4: 繝壹ャ繝育椪縺阪せ繝励Λ繧､繝茨ｼ医い繧ｻ繝・ヨ逕滓・・・- [ ] M: 繧ｳ繝溘ャ繝茨ｼ誼uild_exe.py + v1.0.0繧ｿ繧ｰ/Releases

### 螳御ｺ・- [x] **K0: 繧ｻ繧ｭ繝･繝ｪ繝・ぅ繝ｻ螳牙ｮ壽ｧ** 窶・/api/action逶｣譟ｻ繝ｭ繧ｰ / respond()髱樊耳螂ｨ蛹・/ LLM繧ｭ繝ｼ譛ｪ險ｭ螳夊ｭｦ蜻・/ PWA fetchStatus繝舌ャ繧ｯ繧ｪ繝・- [x] **K1-2: HTTP POST蜈ｱ騾壼喧** 窶・`_post_to_hub()` 譁ｰ險ｭ縲∥gent_bridge_client/hisho_mcp_server 縺ｮDRY・・95陦鯉ｼ・- [x] **K1-3: 髢｢謨ｰ蜀・mport謗・ｨ・* 窶・local_sync_server/gui 蜈ｨ髯､蜴ｻ
- [x] **K1-4: 繝医・繧ｯ繝ｳ遶ｶ蜷亥ｯｾ遲・* 窶・繧｢繝医Α繝・け譖ｸ縺崎ｾｼ縺ｿ・狗ｩｺ繝医・繧ｯ繝ｳ繝ｪ繝医Λ繧､
- [x] **K1-5: 雉ｪ蝠乗悄髯仙・繧袈X** 窶・timeout_at讀懃衍竊単WA縺ｫ縲娯床 譛滄剞蛻・ｌ縲阪ヨ繝ｼ繧ｹ繝・- [x] **K1-6: print竊値ogging邨ｱ荳** 窶・agent_bridge_client/main/agent
- [x] **K3-1: SQLite WAL checkpoint** 窶・襍ｷ蜍墓凾PRAGMA wal_checkpoint(TRUNCATE)
- [x] **K3-2: mcp_installer --force** 窶・--force繝輔Λ繧ｰ霑ｽ蜉
- [x] **K4-1: 繝・い繝ｼ髢句ｧ狗洒邵ｮ** 窶・5遘停・1.5遘・- [x] **K4-3: PC蜷ｹ縺榊・縺励ヵ繧ｩ繝ｳ繝育ｵｱ荳** 窶・DotGothic16蜆ｪ蜈・- [x] **K4-5: PWA莠亥ｮ壹ぞ繝ｭCTA** 窶・縲瑚ｨｭ螳壹°繧蛾｣謳ｺ縺吶ｋ縲阪・繧ｿ繝ｳ霑ｽ蜉
- [x] **鹿 繧ｭ繝｣繝ｩ繧ｯ繧ｿ繝ｼ繝壹Ν繧ｽ繝雁ｮ溯｣・* 窶・system_prompt・育ｧ俶嶌縺上ｓ/繧ｭ繝弱さ蜷・繧｢繧ｶ繝ｩ繧ｷ・会ｼ蟻gent.py豕ｨ蜈･
- [x] **研・・螟ｩ豌苓｡ｨ遉ｺ繝舌げ菫ｮ豁｣** 窶・city蛻晄悄蛟､縲悟叙蠕嶺ｸｭ窶ｦ縲坂・""・育ｩｺ譁・ｭ玲凾縺ｯ髱櫁｡ｨ遉ｺ・・
### 谿九ち繧ｹ繧ｯ
- [ ] K1-1: tour_overlay.py 謚ｽ蜃ｺ・・ig refactor縲∝ｾ悟屓縺怜庄・・- [ ] K2: 痔 髻ｳ螢ｰ繧ｦ繧ｧ繧､繧ｯ繝ｯ繝ｼ繝会ｼ域ｬ｡繝輔ぉ繝ｼ繧ｺ譛ｬ蜻ｽ・・- [ ] K4-2: 繧ｬ繧､繝峨ち繝悶き繝・ざ繝ｪ・九い繧､繧ｳ繝ｳ蛹厄ｼ郁ｻｽ蠕ｮ・・- [ ] K4-4: 繝壹ャ繝育椪縺阪せ繝励Λ繧､繝茨ｼ医い繧ｻ繝・ヨ逕滓・・・- [ ] M: build_exe.py + v1.0.0繧ｿ繧ｰ/Releases

---
---

## 識 驟榊ｸ・婿驥・(2026-08-26 豎ｺ螳・

### Phase J 蝓ｺ譛ｬ譁ｹ驥・- **譁ｹ蠑・*: 譁ｹ豕匹・医ワ繧､繝悶Μ繝・ラ・峨・itHub蜈ｬ髢・+ PyInstaller 繧ｷ繝ｳ繧ｰ繝ｫexe 繧貞酔譎ゅΜ繝ｪ繝ｼ繧ｹ縲・- **LLM繝｢繝・Ν**: 繝ｩ繝ｳ繧ｿ繧､繝縺ｫ縺ｯ**髱槫酔譴ｱ**縲りｨｭ螳夂判髱｢縺ｮ縲後Δ繝・Ν邂｡逅・阪°繧峨ム繧ｦ繝ｳ繝ｭ繝ｼ繝峨ぎ繧､繝峨↓蠕薙▲縺ｦ繝ｦ繝ｼ繧ｶ繝ｼ縺悟ｿ・ｦ√↓蠢懊§縺ｦ驟咲ｽｮ縺吶ｋ譁ｹ蠑上・- **README蜈・ｮ・*: 繧ｹ繧ｯ繝ｪ繝ｼ繝ｳ繧ｷ繝ｧ繝・ヨ・九ヰ繝・ず・区ｩ溯・荳隕ｧ・・itHub Pages/Wiki縺ｯ蠕梧律・峨・- **繝倥Ν繝・繝√Η繝ｼ繝医Μ繧｢繝ｫ**: 險ｭ螳夂判髱｢縺ｫ縲御ｽｿ縺・婿繧ｬ繧､繝峨阪ち繝冶ｿｽ蜉・亥・蝗櫁ｵｷ蜍輔が繝ｳ繝懊・繝・ぅ繝ｳ繧ｰ繝・い繝ｼ蜷ｫ繧・峨・- **繝昴・繝医ヵ繧ｩ繝ｪ繧ｪ**: 繝懊せ縺ｮ繝昴・繝医ヵ繧ｩ繝ｪ繧ｪ縺ｨ縺励※繧ゆｾ｡蛟､縺ゅｋ蜩∬ｳｪ繧堤岼謖・☆縲・
### 豎ｺ螳夂炊逕ｱ
1. 謚陦楢・ｼ・it繧ｯ繝ｭ繝ｼ繝ｳ・峨→髱樊橿陦楢・ｼ・xe DL・峨・荳｡譁ｹ繧偵き繝舌・
2. LLM繝｢繝・Ν繧貞酔譴ｱ縺励↑縺・％縺ｨ縺ｧexe繧ｵ繧､繧ｺ閧･螟ｧ蛹悶・繝ｩ繧､繧ｻ繝ｳ繧ｹ蝠城｡後ｒ蝗樣∩
3. 險ｭ螳夂判髱｢蜀・・繧ｬ繧､繝峨〒縲訓ython荳崎ｦ√搾ｼ九後Δ繝・Ν驟咲ｽｮ繧らｰ｡蜊倥阪ｒ螳溽樟
4. 繧ｳ繝ｼ繝牙・髢九↓繧医ｋ菫｡鬆ｼ諤ｧ・軌SS繧ｳ繝溘Η繝九ユ繧｣蠖｢謌舌・蜿ｯ閭ｽ諤ｧ

### 谺｡蝗樒捩謇九ち繧ｹ繧ｯ
1. **README.md 縺ｮ繧ｹ繧ｯ繝ｪ繝ｼ繝ｳ繧ｷ繝ｧ繝・ヨ霑ｽ蜉**・亥ｮ滄圀縺ｮ繝壹ャ繝育判髱｢繝ｻ謇句ｸｳ逕ｻ髱｢繧呈聴蠖ｱ縺励※謗ｲ霈会ｼ・2. **PyInstaller 繝薙Ν繝峨せ繧ｯ繝ｪ繝励ヨ菴懈・**・・build_exe.py` 縺ｾ縺溘・ `.spec` 繝輔ぃ繧､繝ｫ・・3. **險ｭ螳夂判髱｢縲御ｽｿ縺・婿繧ｬ繧､繝峨阪ち繝門ｮ溯｣・*・亥・蝗櫁ｵｷ蜍墓､懷・・九が繝ｳ繝懊・繝・ぅ繝ｳ繧ｰ繝・い繝ｼ・・4. **GitHub 繝ｪ繝昴ず繝医Μ蜈ｬ髢玖ｨｭ螳・*・磯撼蜈ｬ髢銀・蜈ｬ髢具ｼ・
1. **絹・・繝ｪ繧｢繝ｫ繧ｿ繧､繝螟ｩ豌礼ｵｱ蜷・* (`weather_tools.py` + `life_dreamer.py`):
   - Open-Meteo API (辟｡譁吶・繧ｭ繝ｼ荳崎ｦ・ 縺ｧ迴ｾ蝨ｨ蝨ｰ縺ｮ螟ｩ豌励・豌玲ｸｩ蜿門ｾ励・P閾ｪ蜍墓､懷・ or 謇句虚險ｭ螳・   - 繝峨Μ繝ｼ繝槭・LLM縺ｮ螟ｩ豌励ｒ繝ｪ繧｢繝ｫ蛟､縺ｧ蠑ｷ蛻ｶ荳頑嶌縺阪＠縲√・繝ｭ繝ｳ繝励ヨ縺ｫ縲檎樟蝨ｨ縺ｮ螳滄圀縺ｮ螟ｩ豌励阪ｒ豕ｨ蜈･ 竊・螟ｩ豌励↓蜷医≧逕滓ｴｻ謠丞・繧堤函謌・   - 螟ｩ豌励ヰ繝・ず縺ｫ貂ｩ蠎ｦ繧り｡ｨ遉ｺ・遺・・・25ﾂｰC / Tokyo・峨ょｵ舌・轤ｹ貊・い繝九Γ
2. **耳 繝峨ャ繝育ｵｵ閭梧勹繧ｷ繝ｼ繝ｳ 竊・蟒・ｭ｢**:
   - 繧ｯ繧ｪ繝ｪ繝・ぅ荳崎ｶｳ縺ｮ縺溘ａ `#bg-scene` 繧貞ｮ悟・蜑企勁縲ゅげ繝ｩ繝・・繧ｷ繝ｧ繝ｳ閭梧勹縺ｫ謌ｻ縺励◆
   - `tools/generate_dot_bg.py` 縺ｯ谿九☆・亥・蛻ｩ逕ｨ縺吶ｋ蝣ｴ蜷医↓蛯吶∴縺ｦ・・3. **導 繧ｹ繝槭・UI謨ｴ逅・*:
   - **荳企Κ繝舌・謨ｴ逅・*: 繧ｭ繝｣繝ｩ蛻・崛繝懊ち繝ｳ繧貞炎髯､・郁ｨｭ螳壹Δ繝ｼ繝繝ｫ蜀・〒謫堺ｽ懷庄閭ｽ・・   - **螟ｩ豌礼ｧｻ蜍・*: 荳企Κ繝舌・竊偵・繝・ヨ繧ｹ繝・・繧ｸ・亥聖縺榊・縺励・荳具ｼ峨∈遘ｻ蜍輔ゅさ繝ｳ繝代け繝医↓陦ｨ遉ｺ
4. **劫 繝昴Δ繝峨・繝ｭ髮・ｸｭ繝｢繝ｼ繧ｷ繝ｧ繝ｳ**: 繝昴Δ繝峨・繝ｭ髢句ｧ倶ｸｭ縲√・繝・ヨ繧ｹ繝励Λ繧､繝医′ `focus_1.png` 縺ｫ閾ｪ蜍募・譖ｿ
5. **肌 閭梧勹蟒・ｭ｢縺ｫ莨ｴ縺・ヤ繝ｼ繝ｫ**: `tools/generate_dot_bg.py` 谿狗ｽｮ・亥・蛻ｩ逕ｨ譎ら畑・・6. **SW繧ｭ繝｣繝・す繝･**: v3.4 竊・v3.5 譖ｴ譁ｰ
7. 讀懆ｨｼ: JS_OK / PY_COMPILE_OK / 蜈ｨ讀懆ｨｼ繝代せ

1. **絹・・繝ｪ繧｢繝ｫ繧ｿ繧､繝螟ｩ豌鈴｣謳ｺ** (`weather_tools.py` 譁ｰ險ｭ):
   - **Open-Meteo API**・育┌譁吶・API繧ｭ繝ｼ荳崎ｦ・ｼ峨〒迴ｾ蝨ｨ蝨ｰ縺ｮ螟ｩ豌励・豌玲ｸｩ繧貞叙蠕・   - **IP菴咲ｽｮ閾ｪ蜍墓､懷・**・・p-api.com・峨∪縺溘・**謇句虚險ｭ螳・*・磯・蟶ょ錐繝ｻ邱ｯ蠎ｦ邨悟ｺｦ・・   - WMO螟ｩ豌励さ繝ｼ繝俄・邁｡譏・遞ｮ・域匐/譖・髮ｨ/髮ｪ/蠏撰ｼ牙､画鋤
   - 1譎る俣繧ｭ繝｣繝・す繝･縺ｧ辟｡鬧・↑API蜻ｼ縺ｳ蜃ｺ縺玲椛蛻ｶ
   - 讀懆ｨｼ: WMO_TEST_OK・亥・5繝代ち繝ｼ繝ｳ・・2. **売 life_dreamer 縺ｮ繝ｪ繧｢繝ｫ螟ｩ豌怜渚譏** (`life_dreamer.py`):
   - 繝峨Μ繝ｼ繝槭・襍ｷ蜍墓凾繝ｻLLM逕滓・蜑阪↓ `_refresh_real_weather()` 縺ｧ繝ｪ繧｢繝ｫ螟ｩ豌励ｒ蜿門ｾ励＠ `life_state.weather` 繧剃ｸ頑嶌縺・   - LLM逕滓・蠕後ｂ `weather` 縺縺代・繝ｪ繧｢繝ｫ螟ｩ豌励ｒ蠑ｷ蛻ｶ驕ｩ逕ｨ・・LM縺ｮ螟ｩ豌励・辟｡隕厄ｼ・   - 繝励Ο繝ｳ繝励ヨ縺ｫ縲檎樟蝨ｨ縺ｮ螳滄圀縺ｮ螟ｩ豌・ 笘・・譎ｴ繧後阪ｒ霑ｽ蜉 竊・LLM縺悟､ｩ豌励↓蜷医≧逕滓ｴｻ謠丞・繧堤函謌・   - 螟ｩ豌怜､牙喧譎ゅ・螻･豁ｴ縺ｫ繧りｨ倬鹸
3. **耳 繝峨ャ繝育ｵｵ閭梧勹繧ｷ繝ｼ繝ｳ** (`tools/generate_dot_bg.py` 竊・`assets/dot/bg/`):
   - 繧ｭ繝｣繝ｩ縺ｨ蜷後§11濶ｲ繝ｬ繝医Ο繝代Ξ繝・ヨ縺ｧ5繝・・繝橸ｼ域嶌譁・繧ｫ繝輔ぉ/譽ｮ/豬ｷ/繧ｵ繧､繝舌・・峨・閭梧勹繧・8x48繝峨ャ繝遺・480x480px縺ｧ逕滓・
   - 譖ｸ譁・ 證也ｉ縺ｮ轤趣ｼ区悽譽夲ｼ区惻縲√き繝輔ぉ: 遯難ｼ九ユ繝ｼ繝悶Ν・九き繝・・縺ｮ貉ｯ豌励∵｣ｮ: 螟ｧ譛ｨ・九く繝弱さ・区惠貍上ｌ譌･縲∵ｵｷ: 豕｢・矩ｭ夲ｼ狗所迹壹√し繧､繝舌・: 繝阪が繝ｳ繝薙Ν鄒､・九げ繝ｪ繝・ラ
   - `#bg-scene` 縺ｨ縺励※ z-index 2 縺ｫ驟咲ｽｮ・・nv-backdrop縺ｨenv-canvas縺ｮ髢難ｼ峨｛pacity 0.6 縺ｧ繝峨ャ繝育ｵｵ縺後＞縺・─縺倥↓騾上￠繧・   - `cycleEnvTheme()` 縺ｧ繝・・繝槫・譖ｿ譎ゅ↓閾ｪ蜍募ｷｮ縺玲崛縺・4. **導 螟ｩ豌励ヰ繝・ず蠑ｷ蛹・*: 貂ｩ蠎ｦ・遺・・・25ﾂｰC / Tokyo・芽｡ｨ遉ｺ縺ｫ縲∝ｵ舌・轤ｹ貊・い繝九Γ
5. **肌 MCP險ｭ螳壻ｿｮ蠕ｩ**: BOM髯､蜴ｻ螳御ｺ・…odebase-memory-mcp豁｣蟶ｸ蜍穂ｽ懃｢ｺ隱肴ｸ医∩
6. 讀懆ｨｼ: PY_COMPILE_OK / JS_OK / WMO_TEST_OK / 閭梧勹5譫夂函謌先ｸ医∩

1. **決 閾ｪ蠕狗函豢ｻ繝峨Μ繝ｼ繝槭・繧ｨ繝ｳ繧ｸ繝ｳ譁ｰ險ｭ** (`life_dreamer.py`):
   - 繝壹ャ繝医′譎ょ綾縺ｫ蠢懊§縺ｦ閾ｪ蠕狗噪縺ｫ逕滓ｴｻ・磯｣滉ｺ九・蜈･豬ｴ繝ｻ逹｡逵繝ｻ莉穂ｺ九・隱ｭ譖ｸ繝ｻ莨第・遲会ｼ峨☆繧区ｧ倥ｒ **LLM・・emini・峨′5縲・5蛻・Λ繝ｳ繝繝髢馴囈縺ｧ逕滓・**・医・繝ｭ繝ｳ繝励ヨ縺ｫ譎ょ綾繝ｻ螟ｩ蛟吶・逶ｴ霑大ｱ･豁ｴ繧呈ｳｨ蜈･・・   - **繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ**: LLM螟ｱ謨励・JSON隗｣譫仙､ｱ謨玲凾縺ｯ**譎ょ綾繝吶・繧ｹ縺ｮ繝ｫ繝ｼ繝ｫ**・域悃=譛晞｣溘・9-21譎・蜈･豬ｴ縲・3譎ゆｻ･髯・逹｡逵遲会ｼ峨〒蠢・★迥ｶ諷区峩譁ｰ
   - 螟ｩ蛟吶ｂ逕滓・・域匐/譖・髮ｨ/髮ｪ/蠏撰ｼ峨よ律莉倥・繝ｼ繧ｹ縺ｮ豎ｺ螳夊ｫ也噪繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ莉倥″
   - 繧ｹ繝ｬ繝・ラ繧ｻ繝ｼ繝包ｼ・threading.Lock`・峨∝ｱ･豁ｴ縺ｯ譛螟ｧ20莉ｶ菫晏ｭ・   - **讀懆ｨｼ**: `test_life_dreamer_tmp` 蜈ｨ繝代せ・亥・譛溷喧/JSON繝代・繧ｹ/繧ｳ繝ｼ繝峨ヶ繝ｭ繝・け/荳肴ｭ｣蛟､/螻･豁ｴ驥崎､・賜髯､/繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ・・2. **藤 PCﾃ励せ繝槭・縺ｸ縺ｮ驟堺ｿ｡繝ｻ繝溘Λ繝ｼ**:
   - `local_sync_server.py`: `/api/status` 繝ｬ繧ｹ繝昴Φ繧ｹ縺ｫ `life_state` 繧堤ｵｱ蜷茨ｼ医せ繝槭・PWA縺ｮ2遘偵・繝ｼ繝ｪ繝ｳ繧ｰ縺後◎縺ｮ縺ｾ縺ｾ蛻ｩ逕ｨ・・   - 繧ｵ繝ｼ繝舌・襍ｷ蜍墓凾縺ｫ繝峨Μ繝ｼ繝槭・繧る幕蟋九・*PC繝・せ繧ｯ繝医ャ繝励・繝・ヨ縺ｸ縺ｮ繝溘Λ繝ｼ**・・_mirror_to_pc_pet`: 逕滓ｴｻ繧､繝吶Φ繝医ｒ `post_action` 邨檎罰縺ｧ蜷ｹ縺榊・縺暦ｼ九・繝・ヨ迥ｶ諷九↓蜿肴丐・・3. **導 繧ｹ繝槭・PWA縺ｮ蜿ｯ隕門喧** (`web_pet/pet.js` + `index.html`):
   - 繝倥ャ繝繝ｼ縺ｫ**螟ｩ蛟吶ヰ繝・ず**・遺・・・笘・ｸ・県・・笶・ｸ・笞｡縲∝､ｩ蛟吝挨繧ｫ繝ｩ繝ｼ・句ｵ舌・轤ｹ貊・い繝九Γ・・   - **螟ｩ蛟吶お繝輔ぉ繧ｯ繝・*: 髮ｨ邊偵・髮ｪ繝ｻ關ｽ縺｡闡峨・遞ｲ螯ｻ繝輔Λ繝・す繝･繧呈里蟄・canvas 繝代・繝・ぅ繧ｯ繝ｫ縺ｫ霑ｽ蜉・・spawnWeatherParticles()`・・   - 逕滓ｴｻ繧､繝吶Φ繝医′螻翫￥縺ｨ**繝医・繧ｹ繝茨ｼ九ヰ繧､繝・*縺ｧ騾夂衍縲∵ｴｻ蜍慕ｨｮ蛻･縺ｫ蠢懊§縺ｦ**繧ｹ繝励Λ繧､繝医ｂ蛻・崛**・磯｣滉ｺ・happy縲∫擅逵=sleepy縲∝・豬ｴ=care 遲峨ＡupdateLifeSprite()` 縺ｧ dot竊呈立繧｢繧ｻ繝・ヨ縺ｮ繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ莉倥″・・   - **SW繧ｭ繝｣繝・す繝･ v3.3**
4. **耳 繧ｹ繝槭・閭梧勹繝・じ繧､繝ｳ荳崎｡ｨ遉ｺ縺ｮ譬ｹ譛ｬ菫ｮ豁｣**:
   - 蜴溷屏遒ｺ螳・ `.screen` 縺ｮ `rgba(...,0.65)`・義blur(16px)` 縺・canvas・域囑轤峨・遯薙・譛ｨ縲・・豕｢繝ｻ繝阪が繝ｳ陦暦ｼ峨ｒ隕・＞髫縺励瑚牡縺悟､峨ｏ繧九□縺代阪↓縺ｪ縺｣縺ｦ縺・◆
   - `.screen` 繧・`rgba(20,14,10,0.18)`・義blur(2px)` 縺ｫ邱ｩ蜥・竊・閭梧勹繧ｷ繝ｼ繝ｳ縺瑚ｦ冶ｪ榊庄閭ｽ縺ｫ
5. **肌 Cline MCP險ｭ螳壹・菫ｮ蠕ｩ**:
   - `C:\Users\bonob\.cline\data\settings\cline_mcp_settings.json` 縺ｮ **UTF-8 BOM** 縺悟次蝗縺ｧMCP繧ｵ繝ｼ繝舌・隱ｭ縺ｿ霎ｼ縺ｿ螟ｱ謨・竊・BOM髯､蜴ｻ・徽SON蜀阪お繝ｳ繧ｳ繝ｼ繝峨〒菫ｮ蠕ｩ
   - 螳溯｡後ヵ繧｡繧､繝ｫ縺ｮ蟄伜惠繝ｻ`neo_hisho_bridge` 繝・・繝ｫ蜷阪・螳溷惠辣ｧ蜷医ｂ遒ｺ隱肴ｸ医∩・・繝・・繝ｫ荳閾ｴ・・6. **倹 Tailscale 螟門・蜈域磁邯・螳滓ｩ溽｢ｺ隱肴・蜉・*:
   - `tailscale serve 8765` 竊・`https://node.tail08a991.ts.net/` 縺ｧ謗･邯夂｢ｺ遶九ゅ・繧ｹ繝亥錐縺ｯ險ｭ螳夂判髱｢縺九ｉ蜈･蜉帙・菫晏ｭ伜庄閭ｽ
   - `main.py` 襍ｷ蜍墓凾縺ｫ `tailscale serve` 繧定・蜍募ｮ溯｡後☆繧倶ｻ慕ｵ・∩繧りｿｽ蜉貂医∩・域ｯ主屓縺ｮ謇句・蜉帑ｸ崎ｦ∝喧・・
---

## 識 譛ｬ譌･縺ｮ謌先棡 (2026-08-25 蜊亥ｾ・) 窶・謇句ｸｳ繧ｫ繝ｬ繝ｳ繝繝ｼUI ・・PWA騾夂衍蠑ｷ蛹・
1. **套 邨ｱ蜷域焔蟶ｳ縺ｮ莠亥ｮ壹ち繝悶ｒ繧ｫ繝ｬ繝ｳ繝繝ｼ謠冗判譁ｹ蠑上↓蜈ｨ髱｢蛻ｷ譁ｰ** (`ui/calendar_window.py`):
   - **譛磯俣**: 螳溘き繝ｬ繝ｳ繝繝ｼ繧ｰ繝ｪ繝・ラ・域律譖懷ｧ九∪繧翫・6騾ｱﾃ・蛻暦ｼ峨ょ推譌･縺ｫ莠亥ｮ壽ｦりｦ√ｒ譛螟ｧ3莉ｶ・医ヱ繧ｹ繝・Ν濶ｲ繝悶Ο繝・け・芽｡ｨ遉ｺ縲・N 縺ｧ莉ｶ謨ｰ陦ｨ遉ｺ縲ゆｻ頑律縺ｯ鮟・牡繝上う繝ｩ繧､繝医・驕主悉莠亥ｮ壹・繧ｰ繝ｬ繝ｼ
   - **騾ｱ髢・*: 7譌･ ﾃ・譎る俣霆ｸ(6:00-24:00)縺ｮ繧ｬ繝ｳ繝医メ繝｣繝ｼ繝亥梛繧ｿ繧､繝繝・・繝悶Ν縲ゆｺ亥ｮ壹・譎る俣蟷・↓蠢懊§縺溘ヶ繝ｭ繝・け縺ｧ謠冗判縲∫樟蝨ｨ譎ょ綾縺ｫ襍､邱・   - **譌･髢・*: 0-24譎ゅ・隧ｳ邏ｰ繧ｿ繧､繝繝・・繝悶Ν・医せ繧ｯ繝ｭ繝ｼ繝ｫ蜿ｯ繝ｻ繝帙う繝ｼ繝ｫ蟇ｾ蠢懶ｼ峨よ凾蛻ｻ遽・峇繝ｻ繧ｿ繧､繝医Ν繝ｻ隱ｬ譏・陦檎岼繧定｡ｨ遉ｺ縲∬ｵｷ逾ｨ譌･/驕主悉譌･縺ｯ閾ｪ蜍輔せ繧ｯ繝ｭ繝ｼ繝ｫ
   - 笳笆ｶ 縺ｧ譛滄俣遘ｻ蜍輔√御ｻ頑律縲阪〒蠕ｩ蟶ｰ縲よ律莉倥そ繝ｫ/莠亥ｮ壹ヶ繝ｭ繝・け縺ｮ繧ｿ繝・・縺ｧ譌･髢薙ン繝･繝ｼ縺ｸ繝峨Μ繝ｫ繝繧ｦ繝ｳ
   - **譬ｹ譛ｬ蜴溷屏縺ｮ隗｣豸・*: 蠕捺擂縺ｯ縲御ｻ頑律莉･髯阪・莠亥ｮ壹阪＠縺句叙蠕励＠縺ｪ縺・◆繧√（Cal蜷梧悄謌仙粥貂医∩縺ｧ繧よ悴譚･莠亥ｮ壹′0莉ｶ縺縺ｨ縲御ｺ亥ｮ壹・縺ゅｊ縺ｾ縺帙ｓ縲崎｡ｨ遉ｺ縺縺｣縺溘Ａdatabase.get_events_between()` 繧呈眠險ｭ縺励・℃蜴ｻ120譌･縲懈悴譚･200譌･繧貞叙蠕励＠縺ｦ謠冗判・・B蜀・62莉ｶ縺ｮ縺・■逶ｴ霑・7莉ｶ縺梧ｭ｣縺励￥陦ｨ遉ｺ縺輔ｌ繧九％縺ｨ繧堤｢ｺ隱搾ｼ・   - 讀懆ｨｼ: py_compile OK / unittest 5繝・せ繝・OK (`tests/test_calendar_ui_smoke.py` 譁ｰ險ｭ)
2. **粕 繧ｹ繝槭・PWA騾夂衍縺ｮ蜈ｨ髱｢蠑ｷ蛹・* (`web_pet/index.html` + `pet.js` + `sw.js`):
   - **隕冶ｪ肴ｧ**: 謇ｿ隱阪ヰ繝翫・繧剃ｸ埼乗・繝ｬ繝・ラ繧ｰ繝ｩ繝・・繧ｷ繝ｧ繝ｳ・狗區譁・ｭ暦ｼ句､ｧ繝輔か繝ｳ繝・繧ｿ繧､繝医Ν15px)・句ｼｷ繧ｰ繝ｭ繝ｼ縺ｫ蛻ｷ譁ｰ縲りｳｪ蝠・繧ｷ繧｢繝ｳ/螳御ｺ・繧ｰ繝ｪ繝ｼ繝ｳ縺ｮ繧ｰ繝ｩ繝・ｂ蜷梧ｧ倥↓鬮倩ｦ冶ｪ榊喧
   - **髻ｳ**: Web Audio 縺ｫ繧医ｋ縲後ヴ繝ｳ繝昴Φ縲・髻ｳ繝√Ε繧､繝・域価隱崎ｦ∬ｫ九・4騾｣謇薙・螳御ｺ・雉ｪ蝠上・2騾｣謇難ｼ会ｼ九ヰ繧､繝悶Ξ繝ｼ繧ｷ繝ｧ繝ｳ繝代ち繝ｼ繝ｳ縲６ser Gesture Policy 蟇ｾ蠢懊・ `unlockAudio()`・・ointerdown/touchstart/visibilitychange 縺ｧ隗｣骭・峨ｒ螳溯｣・   - **繧ｿ繝・・謇ｿ隱・*: 繝舌リ繝ｼ逶ｴ荳九↓縲娯怛謇ｿ隱・/ 尅蜊ｴ荳九榊､ｧ繝懊ち繝ｳ繧貞ｸｸ險ｭ・・onfirm繝繧､繧｢繝ｭ繧ｰ蟒・ｭ｢・峨ゅヰ繝翫・譛ｬ菴薙ち繝・・縺ｧ繧ｳ繝槭Φ繝牙・譁・ｼ句､ｧ繝懊ち繝ｳ莉倥″謇ｿ隱阪す繝ｼ繝郁｡ｨ遉ｺ
   - **繧､繝､繝帙Φ謇ｿ隱・*: MediaSession API 縺ｧ蜀咲函/荳譎ょ●豁｢/谺｡繝医Λ繝・け縺ｮ繝｡繝・ぅ繧｢繧ｭ繝ｼ繧偵梧価隱阪阪↓蜑ｲ繧雁ｽ薙※・・luetooth繧､繝､繝帙Φ縺ｮ蜀咲函繝懊ち繝ｳ縺ｧ繝弱・繝ｫ繝・け謇ｿ隱搾ｼ・   - PC縺九ｉ縺ｮ蜻ｼ縺ｳ蜃ｺ縺嶺ｿ｡蜿ｷ (buzz) 縺ｫ繧ゅメ繝｣繧､繝・九ヨ繝ｼ繧ｹ繝医〒蠢懃ｭ・   - SW繧ｭ繝｣繝・す繝･ **v3.0 竊・v3.1** 縺ｫ譖ｴ譁ｰ・亥ｮ滓ｩ溘∈譁ｰUI繧帝・菫｡・・3. **剥 holistic-code-review ・・Codebase險ｭ險亥・譫舌ｒ螳滓命** (`docs/temp/code_review_report_20260825.md`):
   - 5螟ｧ繝壹Ν繧ｽ繝奇ｼ医い繝ｼ繧ｭ繝・け繝・PM/繧ｫ繧ｪ繧ｹ/繧ｻ繧ｭ繝･繝ｪ繝・ぅ/繧ｲ繝ｼ繝繝・じ繧､繝翫・・会ｼ・Fowler繧ｳ繝ｼ繝芽・12遞ｮ ・・codebase-memory-mcp 繧ｰ繝ｩ繝募・譫舌〒譟ｻ隱ｭ
   - **P0縺ｪ縺・*・医け繝ｩ繝・す繝･繝ｻ繝・・繧ｿ遐ｴ謳阪・繧ｻ繧ｭ繝･繝ｪ繝・ぅ閼・ｼｱ諤ｧ繧ｼ繝ｭ・峨１1 3莉ｶ・遺蔵DB row竊脱vent螟画鋤縺ｮ驥崎､・竭｡蝙九ヲ繝ｳ繝医・primitive豎守畑蛹・竭｢萓句､匁升繧翫▽縺ｶ縺励・繝ｭ繧ｰ谺螯ゑｼ峨ｒ**蠖捺律菫ｮ豁｣貂医∩**・亥・讀懆ｨｼ: py_compile OK / node --check OK / unittest 5/5 繝代せ・・   - P2蛟呵｣・ 謇句ｸｳ繝輔ャ繧ｿ繝ｼ縺ｸ縺ｮ譛邨ょ酔譛滓凾蛻ｻ陦ｨ遉ｺ縲（Cal蜷梧悄蠕後・謇句ｸｳ閾ｪ蜍輔Μ繝輔Ξ繝・す繝･縲∝叙蠕礼ｪ薙・螳壽焚蛹悶∵律髢楢ｩｳ邏ｰ繝昴ャ繝励い繝・・縲∵価隱肴凾縺ｮ繝壹ャ繝・elebrate貍泌・
   - codebase-memory-mcp 繧､繝ｳ繝・ャ繧ｯ繧ｹ譛譁ｰ蛹厄ｼ・59繝弱・繝会ｼ会ｼ・ADR 譁ｰ隕丈ｽ懈・・郁ｨｭ險域ｱｺ螳壹・豌ｸ邯壼喧・・4. **泙 繝ｬ繝薙Η繝ｼP2蟇ｾ蠢懊ｒ螳御ｺ・*:
   - **謇句ｸｳ繝輔ャ繧ｿ繝ｼ**: 縲交沐・Google繧ｫ繝ｬ繝ｳ繝繝ｼ譛邨ょ酔譛・ XX:XX ・・謇句ｸｳ逋ｻ骭ｲ N 莉ｶ縲阪ｒ蟶ｸ譎り｡ｨ遉ｺ・亥酔譛溘・螳牙ｿ・─蜷台ｸ奇ｼ・   - **蜷梧悄蠕瑚・蜍輔Μ繝輔Ξ繝・す繝･**: 30蛻・ｮ壽悄蜷梧悄・・ain.py・会ｼ・ｨｭ螳夂判髱｢縺ｮ謇句虚蜷梧悄・・ettings_window.py・峨・謌仙粥蠕後∵焔蟶ｳ縺碁幕縺・※縺・ｌ縺ｰ `gui.refresh_calendar_if_open()` 繧・post_action 邨檎罰縺ｧ蜊ｳ譎ょ・謠冗判
   - **蜿門ｾ礼ｪ薙・螳壽焚蛹・*: `EVENT_RANGE_PAST_DAYS=120` / `EVENT_RANGE_FUTURE_DAYS=200`
   - **譌･髢楢ｩｳ邏ｰ繝昴ャ繝励い繝・・**: 譌･髢薙ン繝･繝ｼ縺ｮ莠亥ｮ壹ヶ繝ｭ繝・け繧偵ち繝・・ 竊・蜈ｨ譁・ち繧､繝医Ν繝ｻ譎ょ綾繝ｻ隱ｬ譏弱・隧ｳ邏ｰ繝繧､繧｢繝ｭ繧ｰ
   - **謇ｿ隱肴凾繝壹ャ繝域ｼ泌・**: 繧ｹ繝槭・縺ｧ謇ｿ隱・蜊ｴ荳九☆繧九→PC繝壹ャ繝医′ celebrate・域価隱搾ｼ・care・亥唆荳具ｼ峨Μ繧｢繧ｯ繧ｷ繝ｧ繝ｳ縲よ眠API繧｢繧ｯ繧ｷ繝ｧ繝ｳ `pet_reaction`・・ocal_sync_server.py・峨ｒ霑ｽ蜉
   - **髻ｳ濶ｲ蟾ｮ・・3・・*: 謇ｿ隱・荳頑・2髻ｳ・丞唆荳・荳矩剄2髻ｳ縲４W繧ｭ繝｣繝・す繝･ **v3.2**
   - 讀懆ｨｼ: py_compile 6繝輔ぃ繧､繝ｫ OK / node --check OK / unittest 5/5 繝代せ
5. **套 繧ｫ繝ｬ繝ｳ繝繝ｼ隍・焚繧｢繧ｫ繧ｦ繝ｳ繝郁ｳｼ隱ｭ蟇ｾ蠢懶ｼ井ｻ穂ｺ狗畑繝ｻ繝励Λ繧､繝吶・繝茨ｼ・*:
   - DB: `calendar_sources` 繝・・繝悶Ν譁ｰ險ｭ・義events.source_id` 繧ｫ繝ｩ繝霑ｽ蜉・・LTER TABLE繝槭う繧ｰ繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ閾ｪ蜍包ｼ・   - 蜷梧悄繧ｨ繝ｳ繧ｸ繝ｳ: 繧ｽ繝ｼ繧ｹ蜊倅ｽ阪・ `sync_calendar_source()` ・句・繧ｽ繝ｼ繧ｹ `sync_all_calendar_sources()`縲ょ叙繧願ｾｼ縺ｿ遯薙ヵ繧｣繝ｫ繧ｿ・磯℃蜴ｻ120譌･縲懈悴譚･730譌･・峨〒DB閧･螟ｧ蛹夜亟豁｢
   - 險ｭ螳啅I: 雉ｼ隱ｭ繧ｽ繝ｼ繧ｹ荳隕ｧ・郁ｿｽ蜉/濶ｲ蛻・崛/ON-OFF/蛟句挨蜷梧悄/蜑企勁・会ｼ亀ailscale繝帙せ繝井ｿ晏ｭ・   - 謇句ｸｳUI: 繧ｽ繝ｼ繧ｹ濶ｲ縺ｮ邵∝叙繧奇ｼ句・萓九ヵ繝・ち繝ｼ・狗┌蜉ｹ繧ｽ繝ｼ繧ｹ髯､螟・   - 繧ｹ繝槭・: 莠亥ｮ壻ｸ隕ｧ縺ｫ繧ｽ繝ｼ繧ｹ蜷崎｡ｨ遉ｺ
   - 讀懆ｨｼ: `tests/test_calendar_sources.py` 6/6 繝代せ
6. **倹 螟門・蜈域磁邯・(Tailscale VPN) 蟇ｾ蠢・*:
   - QR繝繧､繧｢繝ｭ繧ｰ縺ｫ螟門・蜈育畑URL陦ｨ遉ｺ縲∬ｨｭ螳夂判髱｢縺ｫTailscale繝帙せ繝亥錐菫晏ｭ倥き繝ｼ繝・   - `docs/guides/TAILSCALE_SETUP.md` 譁ｰ險ｭ・・ailscale繧､繝ｳ繧ｹ繝医・繝ｫ竊蛋tailscale serve 8765`竊偵・繧ｹ繝亥錐逋ｻ骭ｲ・・   - 螳滓ｩ溽｢ｺ隱阪・縲後き繝輔ぉ迺ｰ蠅・〒縺ｮE2E繝・せ繝医阪→縺励※蠕悟ｷ･遞九↓險倬鹸

---

## 識 譛ｬ譌･縺ｮ謌先棡 (2026-08-25 蜊亥ｾ・) 窶・iCal騾｣謳ｺ繝ｻ蜩∬ｳｪ謾ｹ蝟・
1. **套 Google 繧ｫ繝ｬ繝ｳ繝繝ｼ騾｣謳ｺ・育ｧ伜ｯ・Cal URL譁ｹ蠑上・OAuth螳悟・荳崎ｦ・ｼ・*:
   - `ics_tools.py` 縺ｫ `sync_calendar_from_ical_url()` 螳溯｣・ｼ郁ｻｽ驥終CS繝代・繧ｵ繝ｼ繝ｻ螟夜Κ萓晏ｭ倥ぞ繝ｭ繝ｻTZID/UTC/邨よ律蟇ｾ蠢懶ｼ・   - Google逕ｱ譚･莠亥ｮ壹・ `google_event_id` 莉倥″縺ｧ逋ｻ骭ｲ縺励∝酔譛溘・縺溘・縺ｫ鄂ｮ縺肴鋤縺茨ｼ磯㍾隍・↑縺暦ｼ・   - 險ｭ螳夂判髱｢縲悟､夜Κ繝・・繝ｫ縲阪ち繝悶↓騾｣謳ｺ繧ｫ繝ｼ繝芽ｿｽ蜉: **蜿門ｾ玲焔鬆・・隱ｬ譏・*繝ｻ**隱ｭ縺ｿ蜿悶ｊ蟆ら畑縺ｮ豕ｨ諢乗嶌縺・*繝ｻURL蜈･蜉帙・縲交沐・莉翫☆縺仙酔譛溘阪・譛邨ょ酔譛滓凾蛻ｻ陦ｨ遉ｺ
   - `main.py` 縺ｫ30蛻・俣髫斐・繝舌ャ繧ｯ繧ｰ繝ｩ繧ｦ繝ｳ繝牙ｮ壽悄蜷梧悄繧ｹ繝ｬ繝・ラ霑ｽ蜉
   - 讀懆ｨｼ: py_compile OK / ICS繝代・繧ｵ繝ｼ繝・せ繝・OK・・ZID繝ｻ邨よ律蠖｢蠑擾ｼ・2. **耳 繝・せ繧ｯ繝医ャ繝励・繝・ヨ縺ｮ繝・う繧ｹ繝域ｷｷ蝨ｨ隗｣豸茨ｼ・ix-1・・*:
   - `tools/generate_dot_hisho_extra.py` 譁ｰ險ｭ: idle_1 繝吶・繧ｹ縺ｫ13迥ｶ諷具ｼ医♀闌ｶ繝ｻ隱ｭ譖ｸ繝ｻ繧ｹ繝医Ξ繝・メ繝ｻ縺顔･昴＞繝ｻ蠢・・繝ｻ螟懶ｼ峨ｒ繧ｨ繝輔ぉ繧ｯ繝亥粋謌千函謌・   - `dot/hisho/` 縺・**16竊・9迥ｶ諷・* 縺ｨ縺ｪ繧翫∵立莠ｺ蝙九い繧ｻ繝・ヨ縺ｸ縺ｮ繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ縺悟ｮ悟・豸域ｻ・3. **償・・繧ｹ繝槭・閭梧勹繝・・繝櫁ｦ冶ｪ肴ｧ蜷台ｸ奇ｼ・ix-2・・*:
   - 5繝・・繝槭・繧ｰ繝ｩ繝・・繧ｷ繝ｧ繝ｳ繧呈・繧九￥迚ｹ蠕ｴ逧・↓蠑ｷ蛹悶～env-backdrop` opacity 0.85竊・.0
   - 蛻・崛譎ゅ・繝医・繧ｹ繝磯夂衍・医交沛橸ｸ・笳銀雷繝・・繝槭↓螟峨ｏ繧翫∪縺励◆縲搾ｼ峨ｒ霑ｽ蜉
4. **倹 AI繝九Η繝ｼ繧ｹ bottom-sheet 菫ｮ豁｣**: Google News RSS 縺九ｉ險倅ｺ・link 繧貞叙蠕励＠縲｜ottom-sheet 縺ｮ縲交沍・蜈・ｨ倅ｺ九ｒ髢九￥縲阪・繧ｿ繝ｳ縺ｧ螳溯ｨ倅ｺ矩夢隕ｧ縺悟庄閭ｽ縺ｫ・亥ｾ捺擂縺ｯ縲後ち繝・・縺励※窶ｦ縲阪・蝗ｺ螳壽｡亥・譁・・縺ｿ縺ｧ蜀・ｮｹ縺瑚ｦ九∴縺ｪ縺九▲縺滂ｼ峨ゅ≠繧上○縺ｦ `web_pet/sw.js` 縺ｮ繧ｭ繝｣繝・す繝･繝舌・繧ｸ繝ｧ繝ｳ繧・**v2.4竊致3.0** 縺ｫ譖ｴ譁ｰ縺励∵眠UI繧偵せ繝槭・縺ｸ遒ｺ螳溘↓驟堺ｿ｡縲・
---

## 識 譛ｬ譌･縺ｮ謌先棡 (2026-08-25 蜊亥ｾ・) 窶・繧ｭ繝｣繝ｩ蜀咲函謌撰ｼ・紛逅・
1. **卵・・譌ｧ繧ｭ繝｣繝ｩ繧｢繧ｻ繝・ヨ蜑企勁**・医Θ繝ｼ繧ｶ繝ｼ謖・､ｺ・・ kinoko/seal/wombat邉ｻ **204繝輔ぃ繧､繝ｫ蜑企勁**・・40竊・36・峨ゅえ繧ｩ繝ｳ繝舌ャ繝医・繧ｭ繝｣繝ｩ螳夂ｾｩ縺九ｉ繧ょ炎髯､・・haracter_manager.py / gui.py / pet.js・俄・ **3繧ｭ繝｣繝ｩ菴灘宛**・育ｧ俶嶌縺上ｓ繝ｻ繧｢繧ｶ繝ｩ繧ｷ繝ｻ繧ｭ繝弱さ蜷幢ｼ・2. **耳 繧｢繧ｶ繝ｩ繧ｷ・・く繝弱さ蜷帙ｒ8/15蜷後ユ繧､繧ｹ繝医〒蜀咲函謌・*:
   - 譁ｰ繝・・繝ｫ `tools/generate_dot_seal_kinoko.py`・・/15迚医→蜷御ｸ縺ｮ11濶ｲ繝ｬ繝医Ο繝代Ξ繝・ヨ繝ｻ128x128繝ｻ32x32繧ｰ繝ｪ繝・ラ謠冗判・・   - 繧｢繧ｶ繝ｩ繧ｷ: 繧ゅ■繧ゅ■螟ｧ遖上す繝ｫ繧ｨ繝・ヨ繝ｻ逋ｽ菴薙・鬆ｭ縺ｮ轣ｰ譁代・ﾏ牙哨
   - 繧ｭ繝弱さ蜷・ 襍､繧ｫ繧ｵ・医け繝ｪ繝ｼ繝逋ｽ轤ｹ縺､縺搾ｼ会ｼ・區闌・   - 16迥ｶ諷凝・繧ｭ繝｣繝ｩ = **32譫壹ｒ `assets/dot/seal/` `assets/dot/kinoko/` 縺ｸ逕滓・**
   - 迥ｶ諷九ヰ繝ｪ繧ｨ繝ｼ繧ｷ繝ｧ繝ｳ: 迸ｬ縺阪・隕也ｷ・譁ｹ蜷代・繝九さ繝九さ繝ｻ繝薙ャ繧ｯ繝ｪ繝ｻ閠・∴荳ｭ繝ｻZZZ繝ｻ繝上・繝医・譏溘・髮・ｸｭ繝槭・繧ｯ
   - 讀懆ｨｼ: py_compile OK / 逕ｻ蜒乗怏蜉ｹ諤ｧ OK・・28x128 RGBA・・ **3繧ｭ繝｣繝ｩﾃ・6迥ｶ諷・48譫壼ｮ悟ｙ**

---

## 識 譛ｬ譌･縺ｮ謌先棡 (2026-08-25 蜊亥ｾ・) 窶・Plan C 繝峨ャ繝育ｵｵ蜿悶ｊ霎ｼ縺ｿ

1. **耳 8/15繝ｬ繝医Ο繝峨ャ繝育ｵｵ縺ｮ豁｣蠑丞叙繧願ｾｼ縺ｿ**:
   - `restore_assets_20260815/assets/`・・6繧ｹ繝励Λ繧､繝・ idleﾃ・, lookﾃ・, thinkingﾃ・, happy, focusﾃ・, sleepyﾃ・, alarm_ask, pet_love, cheer・峨ｒ **`assets/dot/hisho/`** 縺ｸ驟咲ｽｮ・・28x128 RGBA・・   - **PC蛛ｴ**: `gui.py` 縺ｮ `_load_mascot_assets()` 蛟呵｣懊ヱ繧ｹ縺ｮ**譛蜆ｪ蜈・*縺ｫ `assets/dot/{char}/{name}.png` 繧定ｿｽ蜉縲ら┌縺・3繧ｹ繝励Λ繧､繝茨ｼ・ea/reading/stretch/celebrate/care/night邉ｻ・峨・譌｢蟄倥い繧ｻ繝・ヨ縺ｸ閾ｪ蜍輔ヵ繧ｩ繝ｼ繝ｫ繝舌ャ繧ｯ
   - **繧ｹ繝槭・蛛ｴ**: `web_pet/pet.js` 縺ｮ `preloadSprites()` 繧・`/assets/dot/{char}/idle_1.png` 譛蜆ｪ蜈医↓螟画峩
   - **繧ｻ繧ｭ繝･繝ｪ繝・ぅ蠑ｷ蛹・*: `local_sync_server.py` 縺ｮ `/assets/` 驟堺ｿ｡縺ｫ繝代せ繝医Λ繝舌・繧ｵ繝ｫ蟇ｾ遲厄ｼ・..`繝ｻ邨ｶ蟇ｾ繝代せ諡貞凄・峨ｒ霑ｽ蜉
   - 笞・・**繧ｭ繝弱さ蜷帙・繧｢繧ｶ繝ｩ繧ｷ縺ｯ蜷後ユ繧､繧ｹ繝亥・逕滓・縺ｾ縺ｧ譌｢蟄倥い繧ｻ繝・ヨ縺ｮ縺ｾ縺ｾ**・・dot/kinoko/` `dot/seal/` 繧剃ｽ懊ｌ縺ｰ閾ｪ蜍暮←逕ｨ縺輔ｌ繧玖ｨｭ險茨ｼ・   - 讀懆ｨｼ: py_compile OK / node --check OK / 逕ｻ蜒乗怏蜉ｹ諤ｧ OK (128x128 RGBA) / 繧ｻ繧ｭ繝･繝ｪ繝・ぅ繝・せ繝・8/8 繝代せ

---

## 識 譛ｬ譌･縺ｮ謌先棡 (2026-08-25 蜊亥ｾ・ 窶・Plan B 繧ｹ繝槭・UI菫ｮ蠕ｩ

1. **灯 謇句ｸｳ繝｢繝ｼ繝繝ｫ譛ｬ螳溯｣・*・・lert繧ｹ繧ｿ繝悶ｒ螳悟・鄂ｮ謠幢ｼ・
   - 套 莠亥ｮ壻ｸ隕ｧ・・eventsData` 陦ｨ遉ｺ・・ 統 TODO・医ち繝・・縺ｧ螳御ｺ・`complete_task`・・ 験 鄙呈・・医ち繝・・縺ｧ驕疲・ `toggle_habit`縲Å沐･繧ｹ繝医Μ繝ｼ繧ｯ陦ｨ遉ｺ・・ 笞呻ｸ・險ｭ螳夲ｼ医く繝｣繝ｩ繝ｻ繝・・繝槭・蜈ｨ逕ｻ髱｢繝ｻ蟶ｸ譎０N繝ｻPC繝壹ャ繝亥他縺ｳ蜃ｺ縺暦ｼ・   - `fetchStatus()` 縺ｫ tasks/events/habits 縺ｮ菫晏ｭ倥ｒ霑ｽ蜉・井ｻ･蜑阪・蜿門ｾ励＠縺ｦ縺吶ｉ縺・↑縺九▲縺滂ｼ・   - `openBottomSheet()` 繧偵Μ繧ｹ繝・TML陦ｨ遉ｺ蟇ｾ蠢懊↓諡｡蠑ｵ縲～escapeHtml()` 縺ｧXSS蟇ｾ遲・2. **笵ｶ 蜈ｨ逕ｻ髱｢繝懊ち繝ｳ蠕ｩ豢ｻ**: 繝倥ャ繝繝ｼ縺ｫ Fullscreen API 繝懊ち繝ｳ霑ｽ蜉
3. **庁 蟶ｸ譎ら判髱｢ON蠕ｩ豢ｻ**: Canvas `captureStream(10)` 竊・荳榊庄隕没ideo 縺ｮ辟｡髯千函驟堺ｿ｡譁ｹ蠑擾ｼ・026-08-16 隨ｬ荳蜴溽炊縺ｮ蜀榊ｮ溯｣・・TTP迺ｰ蠅・〒縺ｯ navigator.wakeLock 縺悟虚縺九↑縺・◆繧・ｼ峨ょ虚菴應ｸｭ縺ｯ繝倥ャ繝繝ｼ繧｢繧､繧ｳ繝ｳ縺交沐・↓
4. **導 讓ｪ逕ｻ髱｢繝ｬ繧､繧｢繧ｦ繝域眠險ｭ**: `@media (orientation: landscape)` 縺ｧ繝壹ャ繝亥ｷｦ・九し繧ｸ繧ｧ繧ｹ繝亥承縺ｮ2繧ｫ繝ｩ繝蛹悶‥esc陦ｨ遉ｺ4陦後↓諡｡螟ｧ
5. **dock 繝懊ち繝ｳ縲交洫遏･隕九坂・縲交沍ｱ鄙呈・縲・* 縺ｫ螟画峩・・entisDB遏･隕九・PC蛛ｴ讖溯・縺ｮ縺溘ａ縲√せ繝槭・縺ｧ縺ｯ螳溘ョ繝ｼ繧ｿ縺ｮ縺ゅｋ鄙呈・繝医Λ繝・き繝ｼ繧定｡ｨ遉ｺ・・
## 識 譛ｬ譌･縺ｮ謌先棡 (2026-08-25 蜊亥燕) 窶・繧ｻ繧ｭ繝･繝ｪ繝・ぅ繝ｻ謨ｴ逅・
1. **柏 Zero-Trust 3螻､髦ｲ蠕｡**: Bearer隱崎ｨｼ・九・繧｢繝ｪ繝ｳ繧ｰFail-Closed・詰ocalhost蛻ｶ髯撰ｼ玖・蟾ｱ謇ｿ隱咲ｦ∵ｭ｢・・est_sync_auth.py 8/8繝代せ・・2. **菅 /api/status UnboundLocalError 菫ｮ豁｣**・磯未謨ｰ蜀・mport database縺悟次蝗縺ｧ繧ｹ繝槭・蜷梧悄縺悟ｸｸ縺ｫ螟ｱ謨暦ｼ・3. **卵・・Git螻･豁ｴ蜈ｨ豸亥悉螳御ｺ・*・・6繧ｳ繝溘ャ繝遺・1繧ｳ繝溘ャ繝亥・蛻晄悄蛹厄ｼ鞠orce push・会ｼ・**繝ｪ繝昴ず繝医Μ髱槫・髢句喧**
4. **卵・・讖溷ｯ・ヨ繝ｼ繧ｯ繝ｳ貍乗ｴｩ蟇ｾ蠢・*: `.sync_token` 繧竪itHub縺九ｉ髯､蜴ｻ・九ヨ繝ｼ繧ｯ繝ｳ辟｡蜉ｹ蛹厄ｼ域ｬ｡蝗櫁ｵｷ蜍墓凾縺ｫ譁ｰ繝医・繧ｯ繝ｳ閾ｪ蜍慕函謌絶・繧ｹ繝槭・蜀阪・繧｢繝ｪ繝ｳ繧ｰ蠢・ｦ・ｼ・5. **唐 繝ｫ繝ｼ繝域紛逅・*: 蟄ｦ鄙偵Γ繝｢繧・`docs/learning-memos/` 縺ｫ邨ｱ荳縲・幕逋ｺ繝・・繝ｫ繧・`tools/`・・蛟具ｼ峨√ユ繧ｹ繝医ｒ `tests/`・・蛟具ｼ峨∈遘ｻ蜍輔～hisyokun-modern-source/`・・25繝輔ぃ繧､繝ｫ・牙炎髯､縲∝・繝代せ菫ｮ豁｣貂医∩・・/8讀懆ｨｼ繝代せ・・
---

## 搭 谺｡蝗槭お繝ｼ繧ｸ繧ｧ繝ｳ繝医∈縺ｮ蠑輔″邯吶℃繧ｿ繧ｹ繧ｯ (Next Actions)

1. **[P1] 繧ｹ繝槭・螳滓ｩ溘〒縺ｮ蜍穂ｽ懃｢ｺ隱・*: 謇句ｸｳ繝｢繝ｼ繝繝ｫ4遞ｮ繝ｻ蜈ｨ逕ｻ髱｢繝ｻ蟶ｸ譎０N繝ｻ讓ｪ逕ｻ髱｢繝ｬ繧､繧｢繧ｦ繝医・螳滓ｩ溽｢ｺ隱搾ｼ・C蛛ｴQR繝壹い繝ｪ繝ｳ繧ｰ縺九ｉ髢句ｧ具ｼ・2. **[P1] Plan C: 蠕ｩ蜈・ラ繝・ヨ邨ｵ縺ｮ豁｣蠑丞叙繧願ｾｼ縺ｿ**・・restore_assets_20260815/assets/` 竊・`assets/dot/hisho/`縲“ui.py 縺ｨ web_pet 縺ｫ蜆ｪ蜈亥盾辣ｧ霑ｽ蜉・俄ｻ繧ｭ繝弱さ繝ｻ繧｢繧ｶ繝ｩ繧ｷ縺ｯ蜷後ユ繧､繧ｹ繝亥・逕滓・
3. **[P2] 繝ｬ繝薙Η繝ｼP1/P2谿九ち繧ｹ繧ｯ**: keyring遘ｻ陦後￣ydantic讀懆ｨｼ縲ヾQL繝励Ξ繝ｼ繧ｹ繝帙Ν繝邨ｱ荳縲仝eb繝壹ャ繝医い繝九Γ迥ｶ諷区ｩ滓｢ｰ
4. **[B-1] DSpark GGUF 蜀好L蠕後・蜍穂ｽ懈､懆ｨｼ** / **驟榊ｸ・ヱ繝・こ繝ｼ繧ｸ讒区・縺ｮ譁・嶌蛹・*

---


1. **柏 蜷梧悄繧ｵ繝ｼ繝舌・ Zero-Trust 蛹・(local_sync_server.py)**:
   - `SyncTokenManager` 螳溯｣・ 襍ｷ蜍墓凾縺ｫ256bit荵ｱ謨ｰ繝医・繧ｯ繝ｳ逕滓・ 竊・`.sync_token` 菫晏ｭ倥∝ｮ壽焚譎る俣豈碑ｼ・(`hmac.compare_digest`) 讀懆ｨｼ縲・   - 蜈ｨGET/POST API 縺ｫ Bearer隱崎ｨｼ繧貞ｼｷ蛻ｶ (401諡貞凄)縲・   - **繝壹い繝ｪ繝ｳ繧ｰ繝｢繝ｼ繝・Fail-Closed**: `/api/auth/token` 縺ｯ QR謗･邯壹ム繧､繧｢繝ｭ繧ｰ陦ｨ遉ｺ荳ｭ(10蛻・縺ｮ縺ｿ蠢懃ｭ斐ょｸｸ譎る幕謾ｾ縺ｫ繧医ｋLAN隨ｬ荳芽・・繝医・繧ｯ繝ｳ蜿門ｾ励ｒ蟆√§縺溘・   - **繧ｨ繝ｼ繧ｸ繧ｧ繝ｳ繝・PI localhost蛻ｶ髯・*: `/api/agent/ask` / `ask_input` / `notify` 縺ｯ蜷御ｸPC縺九ｉ縺ｮ蜻ｼ縺ｳ蜃ｺ縺励・縺ｿ險ｱ蜿ｯ 竊・LAN謾ｻ謦・・′繝医・繧ｯ繝ｳ繧呈戟縺｣縺ｦ縺・※繧・ask 菴懈・荳榊庄 (RCE繝√ぉ繝ｼ繝ｳ驕ｮ譁ｭ)縲・   - **閾ｪ蟾ｱ謇ｿ隱・RCE)髦ｲ豁｢**: `BridgeHub.respond_checked()` 縺瑚ｦ∵ｱょ・IP縺ｨ蠢懃ｭ泌・IP縺ｮ荳閾ｴ繧呈､懃衍縺・03諡貞凄縲ゅ瑚・菴懊Μ繧ｯ繧ｨ繧ｹ繝遺・閾ｪ蟾ｱ謇ｿ隱阪阪・莠ｺ髢捺価隱阪ヰ繧､繝代せ繧剃ｸ榊庄閭ｽ蛹悶・
2. **泊 API繧ｭ繝ｼ貍乗ｴｩ蟇ｾ遲・(Git)**:
   - `.gitignore` 譁ｰ隕丈ｽ懈・ (.env / DB / GGUF / backups 遲峨ｒ髯､螟・縲・   - `git rm --cached` 縺ｧ `.env` / `neo_secretary.db` / `discovered_models.json` / `mcp_config.json` / `__pycache__` 繧定ｿｽ霍｡髯､螟匁ｸ医∩縲・   - 笞・・**譛ｪ螳・*: GitHub螻･豁ｴ縺ｫ縺ｯ螳溘く繝ｼ縺梧ｮ狗蕗荳ｭ縲・*荳｡API繧ｭ繝ｼ縺ｮ繝ｭ繝ｼ繝・・繧ｷ繝ｧ繝ｳ(螟ｱ蜉ｹ蛹・縺梧･蜍・* + 蠢・ｦ√↑繧・`git filter-repo` 螻･豁ｴ髯､蜴ｻ縲・
3. **菅 譌｢蟄倥ヰ繧ｰ菫ｮ豁｣**:
   - `/api/status` 縺ｮ UnboundLocalError (髢｢謨ｰ蜀・`import database` 縺後Ο繝ｼ繧ｫ繝ｫ螟画焚蛹悶＠繧ｹ繝槭・蜷梧悄縺悟ｸｸ縺ｫ螟ｱ謨・ 繧剃ｿｮ豁｣縲・   - `main.py` agent_watcher繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ縺ｮ Tkinter 繧ｹ繝ｬ繝・ラ蠅・阜驕募渚繧・`post_action` 邨檎罰縺ｫ邨ｱ荳縲Ａgui.py` post_action 縺・kwargs 騾城℃霆｢騾∝ｯｾ蠢懊・   - `llm_factory.py` 谿矩ｪｸ繝｡繧ｽ繝・ラ `_build_prompt` 蜑企勁縲・   - `backup_savepoint.py` 縺ｮ騾驕ｿ繝ｪ繧ｹ繝医ｒ螳溷惠繝輔ぃ繧､繝ｫ縺ｫ蜷梧悄縲・
4. **､・蠕梧婿莠呈鋤遒ｺ菫・(繝医・繧ｯ繝ｳ莉倅ｸ・**:
   - `agent_bridge_client.py`: `.sync_token` 隱ｭ縺ｿ霎ｼ縺ｿ繝倥Ν繝代・ `get_sync_token()` 霑ｽ蜉縲∝・3API縺ｫAuthorization繝倥ャ繝繝ｼ莉倅ｸ弱・   - `hisho_mcp_server.py`: `get_sync_token()` 繧貞溽畑縺柚CP邨檎罰縺ｮ謇ｿ隱崎ｦ∬ｫ九ｂ隱崎ｨｼ蟇ｾ蠢懊・   - `ui/qr_dialog.py`: Buzz繝・せ繝医↓繝医・繧ｯ繝ｳ莉倅ｸ弱Ａgui.py`: QR繝繧､繧｢繝ｭ繧ｰ陦ｨ遉ｺ譎ゅ↓ `unlock_pairing(600遘・`縲・
5. **笨・閾ｪ蜍墓､懆ｨｼ繝代せ (test_sync_auth.py / 8繧ｷ繝翫Μ繧ｪ)**:
   - T1 繝壹い繝ｪ繝ｳ繧ｰ髱樣幕謾ｾ譎ゅヨ繝ｼ繧ｯ繝ｳ驟榊ｸ・03 笨・/ T2 髢区叛蠕・00 笨・/ T3 辟｡繝医・繧ｯ繝ｳ401 笨・/ T4 譛牙柑繝医・繧ｯ繝ｳ200 笨・/ T5 localhost ask謌仙粥 笨・/ T7 LAN謾ｻ謦・・127.0.0.2)ask403 笨・/ T6 閾ｪ蟾ｱ謇ｿ隱肴拠蜷ｦ 笨・/ T8 蛻･遶ｯ譛ｫ豁｣蠖捺価隱肴・蜉・笨・
---

## 搭 谺｡蝗槭お繝ｼ繧ｸ繧ｧ繝ｳ繝医∈縺ｮ蠑輔″邯吶℃繧ｿ繧ｹ繧ｯ (Next Actions)

### 閥 P0 窶・莉翫☆縺撰ｼ亥ｿ・茨ｼ・1. **API繧ｭ繝ｼ繝ｭ繝ｼ繝・・繧ｷ繝ｧ繝ｳ**: Google Cloud Console / OpenCode 縺ｧ荳｡繧ｭ繝ｼ繧貞､ｱ蜉ｹ竊貞・逋ｺ陦後＠ `.env` 譖ｴ譁ｰ縲・2. **Git螻･豁ｴ繧ｯ繝ｪ繝ｼ繝ｳ**: `Remove-Item -Recurse -Force .git; git init; git checkout -b main; git add -A; git commit -m "feat: 繝阪が遘俶嶌縺上ｓ v1.0 (P0繧ｻ繧ｭ繝･繝ｪ繝・ぅ蟇ｾ蠢懈ｸ医∩)"; git remote add origin https://github.com/Siitake-man/hisho-kun.git; git push -f origin main`

### 泯 P1 窶・莉企ｱ荳ｭ・亥ｮ滓ｩ溽｢ｺ隱阪・蝣・欧諤ｧ・・1. **繧ｹ繝槭・螳滓ｩ檸2E遒ｺ隱・*: 繧ｫ繝輔ぉ迺ｰ蠅・〒縺ｮ蜈ｨ讖溯・繝・せ繝茨ｼ・ailscale 竊・螟ｩ豌苓｡ｨ遉ｺ繝ｻ騾夂衍髻ｳ繝ｻ謇ｿ隱阪ヵ繝ｭ繝ｼ繝ｻ繝昴Δ繝峨・繝ｭ繝｢繝ｼ繧ｷ繝ｧ繝ｳ繝ｻ謇句ｸｳ繧ｫ繝ｬ繝ｳ繝繝ｼ・・2. **OAuth繝医・繧ｯ繝ｳ縺ｮ keyring 遘ｻ陦・* (`google_workspace_tools.py`)
3. **MCP繝・・繝ｫ蠑墓焚縺ｮPydantic讀懆ｨｼ** (`hisho_mcp_server.py`)
4. **蠅・阜蛟､豁｣隕丞喧繝ｩ繝・ヱ繝ｼ邨ｱ荳** (`suggest_engine.py`, `proactive_engine.py`)
5. **after() 逋ｻ骭ｲ邂｡逅・・繝ｫ繝代・ `_schedule` 蟆主・** (`gui.py`)
6. **DB謗･邯壹・ with/closing 邨ｱ荳** (`database.py`, `db_tools.py`)
7. **險ｭ螳壹せ繧ｭ繝ｼ繝槭・蝙句ｮ夂ｾｩ・・ydantic/TypedDict・・* (`llm_factory.py` 縺ｻ縺・

### 泙 P2 窶・譚･騾ｱ莉･髯搾ｼ・X蜷台ｸ翫・讖溯・諡｡蜈・ｼ・1. **SQL蜈ｨ繧ｯ繧ｨ繝ｪ縺ｮ繝励Ξ繝ｼ繧ｹ繝帙Ν繝邨ｱ荳** (`db_tools.py`)
2. **Web繧ｳ繧ｯ繝斐ャ繝医↓繧｢繝九Γ迥ｶ諷区ｩ滓｢ｰ遘ｻ讀・* (`web_pet/pet.js`)
3. **繧ｨ繝ｩ繝ｼ鄙ｻ險ｳ繝上Φ繝峨Λ髮・ｴ・* (`task_narrator.py`)
4. **襍ｷ蜍輔・髱槫酔譛溷喧**・・UI蜊ｳ陦ｨ遉ｺ竊帝㍾縺・・譛溷喧繧貞ｾ後ｍ縺ｸ・・`main.py`)

### 笞ｪ P3 窶・諠・ｷ堤噪貍泌・繝ｻ繝ｪ繝輔ぃ繧ｯ繧ｿ繝ｪ繝ｳ繧ｰ
1. 迸ｬ縺阪・荵ｱ謨ｰ謠ｺ繧峨℃螳溯｣・(`pet_animator.py`)
2. 繧ｹ繝・・繝亥挨繝輔Ξ繝ｼ繝繝ｬ繝ｼ繝亥ｰ主・ (`pet_animator.py`)
3. 繧ｻ繝ｪ繝輔・蜿｣隱ｿ繝舌Μ繧ｨ繝ｼ繧ｷ繝ｧ繝ｳ逕滓・ (`task_narrator.py`)
4. 謦ｫ縺ｧ蜿榊ｿ懷ｼｷ蛹厄ｼ医Δ繝ｼ繧ｷ繝ｧ繝ｳ+繧ｻ繝ｪ繝・蜉ｹ譫憺浹・・`gui.py`, `web_pet/pet.js`)
5. God Constructor 縺ｮ composition root 蛹・(`main.py`)
6. llm_factory 谿矩ｪｸ繝｡繧ｽ繝・ラ蜑企勁・・_build_prompt` 縺ｯ蜑企勁貂医∩・・`llm_factory.py`)

### 統 縺昴・莉・- **DSpark GGUF 蜀好L蠕後・蜍穂ｽ懈､懆ｨｼ**
- **驟榊ｸ・ヱ繝・こ繝ｼ繧ｸ讒区・縺ｮ譁・嶌蛹・*
- **繧ｭ繝弱さ蜷帙・繧｢繧ｶ繝ｩ繧ｷ縺ｮ蜷後ユ繧､繧ｹ繝亥・逕滓・・・tools/generate_dot_seal_kinoko.py` 縺ｧ逕滓・貂医∩縲～assets/dot/` 縺ｫ驟咲ｽｮ貂医∩・・*
- **3繧ｭ繝｣繝ｩ蛻・崛UI邨ｱ蜷茨ｼ郁ｨｭ螳壹Δ繝ｼ繝繝ｫ蜀・〒螳溽樟貂医∩・・*

### 識 谺｡蝗・蛻・ヵ繧｡繝ｼ繧ｹ繝医ち繧ｹ繧ｯ
**README.md 縺ｫ繧ｹ繧ｯ繝ｪ繝ｼ繝ｳ繧ｷ繝ｧ繝・ヨ繧定ｿｽ蜉縺吶ｋ縲１C繝壹ャ繝育判髱｢繝ｻ繧ｹ繝槭・PWA逕ｻ髱｢繝ｻ謇句ｸｳ逕ｻ髱｢縺ｮ3譫壹ｒ謦ｮ蠖ｱ縺励～docs/images/` 縺ｫ菫晏ｭ倥＠縺ｦREADME縺九ｉ蜿ら・縺吶ｋ縲・*

---


## 識 譛ｬ譌･縺ｮ繧｢繝ｼ繧ｭ繝・け繝√Ε豎ｺ螳壻ｺ矩・・・螳溯｣・・譫・(2026-08-23)

1. **剥 蝠・畑繝ｪ繝ｪ繝ｼ繧ｹ蛻､螳壹ヨ繝ｪ繝励Ν繝ｬ繝薙Η繝ｼ縺ｮ螳滓命**:
   - **隨ｬ1谺｡繝ｬ繝薙Η繝ｼ (UI/UX)**: 繝昴Δ繝峨・繝ｭ蜀・ｽ｢繧ｲ繝ｼ繧ｸ縺後く繝｣繝ｩ鬘秘擇縺ｫ陲ｫ繧九ヰ繧ｰ繧堤音螳壹ょ濠蠕・ｒ `r=94` 縺ｫ諡｡螟ｧ縺励√く繝｣繝ｩ閭悟ｾ後・螟門捉繝阪が繝ｳ繧ｪ繝ｼ繝ｩ繝ｪ繝ｳ繧ｰ縺ｸ菫ｮ豁｣縲・   - **隨ｬ2谺｡繝ｬ繝薙Η繝ｼ (螟夜Κ騾｣謳ｺ/MCP)**: `mcp_config.json` 蜀・・蜿､縺・悴遞ｼ蜒拘SE `agent-bridge-mcp` 繧貞ｮ悟・蜑企勁縺励ヾtdio蝙・`neo_hisho_bridge` 縺ｮ縺ｿ繧偵け繝ｪ繝ｼ繝ｳ縺ｫ譛牙柑蛹悶ゅ＆繧峨↓ Windows stdout 縺ｮ UTF-8 蠑ｷ蛻ｶ・・reconfigure`・峨↓繧医ｊ `invalid escape sequence "\x92"` 繧ｨ繝ｩ繝ｼ繧貞ｮ悟・譬ｹ邨ｶ縲・   - **隨ｬ3谺｡繝ｬ繝薙Η繝ｼ (Google/GitHub)**: 蜊倥↑繧区枚蟄怜・蜈･蜉帙ｄ荳ｭ騾泌濠遶ｯ縺ｪiCal騾｣謳ｺ繧帝縺代・*縲隈mail譛ｪ隱ｭ繝ｻGoogle繧ｫ繝ｬ繝ｳ繝繝ｼ繝ｻGoogle Tasks縲阪ｒ邯ｲ鄒・☆繧狗悄縺ｮGoogle OAuth 2.0 邨ｱ蜷亥渕逶､**縺ｮ螳溯｣・ｒ豎ｺ螳壹・
2. **倹 Google OAuth 2.0 & GitHub PAT邨ｱ蜷亥渕逶､**:
   - `google_workspace_tools.py` 縺ｫ `get_google_auth_status()`, `run_google_oauth_flow()`, `revoke_google_auth()` 繧貞ｮ溯｣・・   - `ui/settings_window.py` 縺ｫ Google 隱崎ｨｼ繧ｹ繝・・繧ｿ繧ｹ・芋沺｢ 騾｣謳ｺ貂医∩ / 笞ｪ 譛ｪ隱崎ｨｼ・峨∬ｪ崎ｨｼ繝ｭ繧ｰ繧､繝ｳ繝懊ち繝ｳ縲∝酔譛溘ユ繧ｹ繝医・繧ｿ繝ｳ縲√Ο繧ｰ繧｢繧ｦ繝医・繧ｿ繝ｳ繧帝・蛯吶・   - GitHub Personal Access Token (PAT) 蜈･蜉帶ｬ・∝ｯｾ雎｡繝ｪ繝昴ず繝医Μ險ｭ螳壹√♀繧医・縲交沐・GitHub謗･邯壹ユ繧ｹ繝茨ｼ・PI `/user` 逍朱壽､懆ｨｼ・峨阪ｒ螳溯｣・・
3. **孱・・繧ｻ繝ｼ繝悶・繧､繝ｳ繝亥ｮ悟・繝舌ャ繧ｯ繧｢繝・・菴懈・**:
   - `backup_savepoint.py` 繧貞ｮ溯｡後＠縲∝・繧ｳ繝ｼ繝峨・繧｢繧ｻ繝・ヨ繝ｻDB繧・`backups/savepoint_20260823_122325/` 縺ｸ螳悟・騾驕ｿ縲・
4. **耳 UI/UX 0繝吶・繧ｹ蛻ｷ譁ｰ 繧ｰ繝ｩ繝ｳ繝峨ョ繧ｶ繧､繝ｳ蜷域э**:
   - 譌ｧUI縺ｮ隱ｲ鬘鯉ｼ医・繧ｹ繧ｳ繝・ヨ繝ｻ蜷ｹ縺榊・縺励・繝｡繝九Η繝ｼ縺ｮ謨｣荵ｱ繝ｻ繝代・繝・｢ｫ繧奇ｼ峨ｒ謚懈悽逧・↓隗｣豎ｺ縺吶ｋ縺溘ａ縲・*縲訓C蜿ｳ荳九・邵ｦ蝙倶ｸ菴灘梛繧ｹ繝槭・繝医ラ繝・け・・ocket Cyber-Assistant・峨・*縺ｸ0縺九ｉ蜀崎ｨｭ險医☆繧九％縺ｨ繧貞粋諢上・   - 荳雁ｱ､・医・繧ｹ繧ｳ繝・ヨ・九が繝ｼ繝ｩ・峨∽ｸｭ螻､・・mail/莠亥ｮ・繧ｻ繝ｪ繝輔・繝繧､繝翫Α繝・け繧ｵ繧ｸ繧ｧ繧ｹ繝医き繝ｼ繝会ｼ峨∽ｸ句ｱ､・医ラ繝・く繝ｳ繧ｰ繧｢繧ｯ繧ｷ繝ｧ繝ｳ繝舌・・峨・3螻､讒矩縺ｸ蛻ｷ譁ｰ縺吶ｋ險育判繧堤ｭ門ｮ壹・
---

## 搭 谺｡蝗槭お繝ｼ繧ｸ繧ｧ繝ｳ繝医∈縺ｮ蠑輔″邯吶℃繧ｿ繧ｹ繧ｯ (Next Actions)

1. **[P0] UI/UX 0繝吶・繧ｹ蛻ｷ譁ｰ縺ｮ螳溯｣・(`gui.py` / `ui/`)**:
   - 荳菴灘梛繧ｹ繝槭・繝医ラ繝・け遲蝉ｽ薙・讒狗ｯ会ｼ医・繧ｹ繧ｳ繝・ヨ・九ム繧､繝翫Α繝・け繧ｫ繝ｼ繝会ｼ九け繧､繝・け繝舌・縺ｮ邨ｱ蜷茨ｼ峨・2. **[P0] Google Workspace 繧ｵ繧ｸ繧ｧ繧ｹ繝磯｣謳ｺ (`suggestion_engine.py`)**:
   - 隱崎ｨｼ貂医∩ Google OAuth 繝医・繧ｯ繝ｳ縺九ｉ Gmail 驥崎ｦ∵悴隱ｭ繝｡繝ｼ繝ｫ繝ｻ繧ｫ繝ｬ繝ｳ繝繝ｼ逶ｴ蜑堺ｺ亥ｮ壹ｒ閾ｪ蜍募叙蠕励＠縲∽ｸｭ螻､繧ｫ繝ｼ繝峨∈閾ｪ蜍輔せ繝ｩ繧､繝芽｡ｨ遉ｺ縲・3. **[P1] 繝・せ繧ｯ繝医ャ繝礼畑 PKCE / Client ID 繧ｬ繧､繝峨・螳溯｣・*:
   - 蛻晏屓繝ｦ繝ｼ繧ｶ繝ｼ蜷代￠ Client ID/Secret 蜈･蜉帙ぎ繧､繝峨∪縺溘・ PKCE 隱崎ｨｼ縺ｮ邁｡邏蛹悶

## EDIT-PLAN 2026-08-31 (午後) TODO編集UI・完了取消
- **あるべき姿確定**: 登録=自然言語クイック(PC/スマホ共通・「明日18時に」等の期日解析済み) / 編集=タスクタップで詳細編集シート(期日・優先度・※重要※緊急・タグ・削除) / 完了=明示完了ボタン+再タップ取り消し
- 実装: database.update_task (ホワイトリスト更新) / local_sync_server update_task+delete_task アクション / スマホ編集シート (pet.js) / タップ完了→再タップで復活 (reopen_task)
- キャッシュバス 5.18 / テスト 142件全OK

## 🟢 2026-09-06 17:30 残り2割仕上げ完了 (Cline実装: Phase H ライブバッジ ＆ 付箋座標永続化 ＆ テスト緑化)
- **web_pet/pet.js & index.html & sw.js**: /api/status の `agent_activity` を受けるネオン調ライブバッジ (`#agent-live-badge`) を新設 (coding=緑パルス / thinking=黄点滅 / waiting_approval=紫点滅 / success=シアン)。`currentAgentBadgeState` への一元宣言で TDZ 地雷回避。SWキャッシュを v5.25 に更新。
- **ui/sticky_note.py & character_manager.py**: 付箋ドラッグ位置を `character_config.json` (`sticky_note_pos` キー) へ永続化。アトミック書込 (os.replace) + Lock + 画面外クランプ実装。`save_config()` を未知キー保護マージ方式に改修 (付箋キーが bond_xp 保存で消える潜在バグを修正)。`tests/test_sticky_note_position.py` 8件新設。
- **tests/test_auth_rate_limiter.py**: 外部攻撃者シミュレーション (`_is_private_ip` をテスト期間中のみ差し替え → tearDownClass で復元) により 11回目 429 を検証可能化。プロダクションコード無変更。
- **ファクト開示**: タスクトレイ常駐機能は実装・配線済み (gui.py:72-78)。venv に pystray 未導入が「表示されない」真因 → `pip install pystray==0.19.5` で解消 (ボス手動実行)。
- **検証**: py_compile / node --check / unittest discover / scan_git_secrets をボスへ手動実行依頼。
## 🟢 2026-09-06 17:45 (追記) gui.post_action 重複定義バグ修正 (Cline)
- `gui.py:995` の post_action を `(callback, *args, **kwargs)` に拡張 (引数ありは lambda 転送)。89行目の旧キュー版が後定義により上書きされていたため、LifeDreamerミラー (local_sync_server.py:1558) と neo_hisho_bridge 通知 (notify_task_completed 等) が TypeError で無言故障していた問題を修正。test_ui_notify.py のfake契約と一致。**アプリ再起動後にスマホ通知が復活**。旧定義削除は次スプリント候補。
## 🟢 2026-09-06 17:35 (追記2) 検証結果: コア全GREEN ＆ テスト実行は venv python に統一 (Cline)
- ボス手動検証: py_compile/node --check 全OK、**test_auth_rate_limiter 8/8** (429境界を実ログ確認)、test_agent_fsm 5/5、機密スキャン CLEAN、pystray venv導入成功。
- 22件の ModuleNotFoundError は **グローバル Python 3.13 で実行したことが起因の環境問題** (実測: venv には customtkinter/langchain_core 存在、グローバルには無し)。**テストは `venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` で統一**すること。
## 🟢 2026-09-06 18:00 (追記3) 付箋3連バグ根本解決 ＆ post_action 二重定義削除 ＆ Pydantic V2 移行 (Cline)
- **ui/sticky_note.py**: ①_on_quick_add を Task モデル生成方式へ修正 (旧: キーワード引数で TypeError→追加無反応) ②refresh_tasks を実在の get_tasks(limit=50) へ接続 (旧: 幻の get_active_tasks→AttributeError→リスト空白) ③バッジ/優先判定を importance_flag/urgency_flag へ統一 ④show() 時のフォーカス強化。tests/test_sticky_quick_add.py 8件新設。
- **gui.py**: 旧 post_action (アクションキュー版) の二重定義を削除し契約を root.after 版へ一元化 (_action_queue は process_action_queue ドレイン整合のため温存)。
- **database.py**: Event.end_after_start を @validator(V1)→@field_validator+ValidationInfo(V2) へ移行 (非推奨警告解消)。
- **残課題**: LAN信頼IPの認証失敗もカウントするレートリミット強化は、テスト横汚染対策 (ループバック累積失敗の隔離設計) が必要なため次スプリントへ持ち越し。
## 🟢 2026-09-06 18:30 レビュー相互検証 ＆ トークンハッシュ Deep Module 化 (Cline)
- **相互検証結果**: 最終監査の P2「WAL未強制」は `database.py:51-58` で **9/1実装済み** (TRUNCATE廃止含む) → 重複実装せず清項化。P1「God Class」は実測1,459行・ディスパッチテーブル化済み (一部指摘が陳腐化)。P2「トークンハッシュ漏洩」は指摘正解。
- **database.py**: `sync_device_session()` (認証済みセッションの台帳同期を照会+last_seen+自動登録に統合・SHA-256隠蔽・失効端末のtouchスキップ) と `register_device_from_bearer()` を新設。
- **local_sync_server.py**: サーバー側 `hashlib.sha256` 使用を **0箇所化** (`import hashlib` 削除含む)。既存 `get_device_by_token_hash` はテスト互換で温存。
- **tests/test_device_bearer_seam.py**: 5件新設 (ハッシュ化登録/未登録自動登録/touch更新/失効touchスキップ/契約違反伝播)。
- **ロードマップ改訂**: `docs/specs/機能ロードマップ.md` 末尾に改訂節 (P1-A 露出制御=引き算/ API残学分離/TLS) 追記。
## 🟢 2026-09-06 18:40 タスクトレイ＆スマホ遠隔呼び出し不能バグ解決 (Antigravity実装)
- **真因**: 18:00の post_action 一元化で `_action_queue` への投入が消え、別スレッド (pystray/HTTP) から Tkinter の `root.after()` を直接呼ぶ設計になっていたため、Tkinter のスレッドセーフ違反により Windows メッセージがドロップされ、タスクトレイ・スマホからの呼び出し要求が無反応になっていた。
- **改修内容 (`gui.py`)**:
  1. `post_action`: `hasattr(self, "_action_queue")` 時にスレッドセーフな `_action_queue.put((callback, args, kwargs))` へ投入する構造を復元。`main.py` のメインループ (`process_action_queue`) で 10ms ごとに確実にメインスレッド実行される。
  2. `show_pc_pet`: `deiconify()` 直後に `state('normal')`、`lift()`、`attributes("-topmost", True)`、`update_idletasks()` を明示実行し、Windows の DWM による枠なしウィンドウ（`overrideredirect`）の再描画落ちを防止。

## 🟢 2026-09-14 13:25 PWAフロントエンド Seam分割 第3弾 (pet_particles.js) 完了 ＆ レビューP0-P3完全反映 (Antigravity)
- **成果**:
  1. `web_pet/pet_particles.js` 新設（約600行）：5大背景テーマ、Canvas初期化・リサイズ同期、5大シーン描画、天候パーティクル、なでなでパーティクル、歓喜セレブレーション紙吹雪の物理ループを完全独立化。
  2. 独立検証者 (`quality-reviewer`) 指摘のP0〜P3（双方向状態同期、NoSleep Canvas参照保証、不滅アニメーションループ、放物線スプリング重力）を完全反映。
  3. `web_pet/pet.js` から重複描画コード（約816行）を削除・委譲化（3,335行 ➔ 2,519行に大幅スリム化）。
  4. 回帰防止テスト `tests/test_pet_seam_particles.py` 完備。ドキュメント4点セット完全同期。
## 🟢 2026-09-06 18:50 P1-C 内包ローカルLLM爆速常駐化 ＆ GPU加速バトン起票 (Antigravity設計 ➔ Cline委譲)
- **背景**: ボスから「LM Studio 同等の応答速度（80 tok/s）を秘書くん単体で実現したい」との強い製品方針受領。
- **真因特定**: 会話ごとの `create_model()` ➔ `Llama(model_path=...)` 再ロード（ディスクI/O遅延）および `n_gpu_layers` 未指定（CPU 4スレッド固定）がボトルネック。
- **設計書・ロードマップ反映**: `docs/specs/機能ロードマップ.md` に P1-C として追記。
- **バトン指示書作成**: `docs/handover/prompt_for_cline_20260906_local_llm_cache.md` 作成済み (シングルトンキャッシュ、`n_gpu_layers=-1`、スレッド数動的最適化、`test_device_bearer_seam.py` 1件バグ修正指示を同梱)。
## 🟢 2026-09-06 19:10 P1-C 内包ローカルLLM爆速常駐化 完成 (Cline実装)
- **llm_factory.py**: `_local_llm_cache` (key=str(gguf_path)) 常駐キャッシュ導入 → 会話ごとの GGUF 再ロードを廃止 (ロード待機 0 秒化 / 旧インスタンスは切替時に解放)。`clear_local_model_cache()` 公開メソッド新設。`LlamaCppChatModel.__init__` に `llama_instance` 注入経路を追加 (温度替えの新しいラッパを軽量生成し重いテンソルを共有)。`Llama(...)` に `n_gpu_layers` (HISHO_GPU_LAYERS, 既定 -1=全層GPU, 非対応時は自動CPUフォールバック) と `n_threads` (HISHO_CPU_THREADS, 既定 cpu_count-2 を1..8にクランプ) を導入 (旧 n_threads=4 固定を廃止)。
- **tests/test_local_llm_cache.py**: 3件新設 (同一モデル2回→Llama初期化1回 &温度は個別反映 / 切替で旧常駐解放+新ロード1回 / clear再ロード)。MODELS_DIR を一時dirへ差し替え、実models/を絶対に触らない。
- **database.py (バグ修正)**: sync_device_session の返却 Device が touch 前の古い ip/UA を持つ欠陥を修正 (touch 後に再照合)。Antigravity手動テストで検知された1件失敗 (192.168.1.5 != 10.0.0.9) の根治。

## 🟢 2026-09-14 13:35 PWAフロントエンド Seam分割 第4弾 (pet_motion.js) ＆ 第5弾 (pet_ui.js) 完了 ＆ 品質レビューAPPROVED (Antigravity)
- **成果**:
  1. `web_pet/pet_motion.js` 新設（約430行）：キャラクター定義・プリロード、生活リズム・睡眠サイクル、大歓喜ジャンプ演出、自律歩行物理（地面歩行・吹き出し追従）、なでなでインタラクションを完全独立化。
  2. `web_pet/pet_ui.js` 新設（約730行）：HUDトースト、Glass Bottom Sheet、サジェストカード、エージェント承認バナー（スワイプ・MediaSessionノールック承認）、時計・ポモドーロUI、エージェント稼働ライブバッジ、XSS防御を完全独立化。
  3. 独立検証者 (`quality-reviewer`) 指摘のP1〜P3（サジェストスワイプ初期化、`_hideBanner` 重複排除・完全統合、イベント状態同期、`setPetSprite` エイリアス）を即座に修正反映し、満点 **APPROVED** を獲得。
  4. `web_pet/pet.js` から重複コード（約915行）を削除・委譲化（2,519行 ➔ **1,604行** に激減、当初3,335行から通算約1,731行スリム化）。
  5. 回帰防止テスト `tests/test_pet_seam_motion_ui.py` 完備。ドキュメント4点セット完全同期。