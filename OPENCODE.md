# OpenCode 自律オーケストレーション規約 (Jev Multi-Agent Protocol)

**最終更新**: 2026-09-21
**対象**: OpenCode Desktop / CLI (v2.x)
**正本規約**: `AGENTS.md`（AntiGravity 側と共通のプロジェクト規約）／ `~/.gemini/GEMINI.md`（ボスの開発哲学）

このファイルは **OpenCode 環境における実務マスタールール**です。`AGENTS.md` から参照され、タスク着手前に必ず読まれます。
Antigravity で運用している「System One (Jev) × System Two (専門エージェント陣形)」を、OpenCode 上で**同一の体験**として再現するための規約を定めます。

---

## 1. 環境構成（3層アーキテクチャ）

```
[ボスの要求]
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│ ⚡ System One: jev-mcp (ミリ秒・1回約0.05円)                   │
│   jev_route_agent   : 最適エージェント/スキル/MCPの高速選定     │
│   jev_guard_command : 破壊的コマンド審査 (allow/confirm/deny)  │
└──────┬───────────────────────────────────────────────────────┘
       │ 指名
       ▼
┌──────────────────────────────────────────────────────────────┐
│ 🤖 System Two: OpenCode サブエージェント 11体 (.opencode/agents)│
│   閉ループ: Plan ➔ Implement ➔ Test ➔ Error Analyze ➔ Review  │
└──────┬───────────────────────────────────────────────────────┘
       │ 補助
       ▼
┌──────────────────────────────────────────────────────────────┐
│ 📊 codebase-memory-mcp (知識グラフ/ADR)                        │
│ 🐬 neo_hisho_bridge (Desk Pet 承認・通知・知識の宝庫)           │
└──────────────────────────────────────────────────────────────┘
```

| サーバー | 登録場所 | 役割 |
|:---|:---|:---|
| `jev-mcp` | `~/.config/opencode/opencode.jsonc`（全プロジェクト共通） | System One 意思決定・Tool Guard |
| `codebase-memory-mcp` | `~/.config/opencode/opencode.jsonc`（全プロジェクト共通） | コード構造グラフ・ADR（grep より優先） |
| `neo_hisho_bridge` | `~/.config/opencode/opencode.jsonc`（全プロジェクト共通 / 2026-09-21 ボス判断で移設） | スマホ承認・完了通知・知識の宝庫 |

---

## 2. 必須プロトコル（4本柱）

### 2.1 Jev Pre-flight ルーティング義務
タスク・要望を受け取ったら、**いきなりコードを書き始めることを固く禁ずる**。

1. `jev_route_agent(task_description=..., workspace_dir="<repo絶対パス>")` を呼び出す。
2. 返却された `primary_agent` / `selected_agents` / `recommended_skills` / `recommended_mcp` を確認する。
3. 対話の冒頭で `🤖 [Agent: <primary_agent>] <作業方針>` と名乗る（**実際にツールを呼んだエビデンスとして**）。
4. `.opencode/agents/<primary_agent>.md` の規約に従って作業する。

> ⚠️ **偽装名乗りの絶対禁止**: `jev_route_agent` も `subagent` ツールも呼ばずに `🤖 [Agent: ...]` と名乗る行為は、AGENTS.md 2.8 により固く禁じられる。**ツール実行結果（会話ID・出力）を必ずエビデンスとして示すこと。**

### 2.2 Jev Tool Guard 義務（対象を絞る）
**Jev Guard を呼ぶのは「Hard ACL が `ask` または `deny` とする操作」の前だけ**とする。

| 対象 | Jev Guard | 理由 |
|:---|:---:|:---|
| 破壊的コマンド（Hard ACL が `deny`） | **不要** | 決定論的ハード層が即座に阻止する（Jev の確率判定を待つ必要がない） |
| 安全コマンド（Hard ACL が `allow`）<br/>例: `git status` / `git diff` / `git log` / `pytest` / `python -m py_compile` | **不要** | ハード層が無承認で許可済み。二重審査はコストと摩擦の無駄 |
| **上記以外（Hard ACL が `ask`）** | **必須** | 人間ゲートの前段として Jev の高速審査を挟む |
| 不可逆・大規模な操作<br/>（ファイル削除・大量置換・外部ネットワーク通信・DBスキーマ変更・Git操作） | **必須** | `jev-brain` スキルが本来対象と定めている領域 |

`jev_guard_command(command=...)` の判定に対する行動:

| 判定 | 行動 |
|:---|:---|
| `deny` | **即中止**。理由と安全な代替案をボスへ提示する。 |
| `confirm` | ボスへ承認を求める。`ask_human_approval` を使う場合は **summary に Jev スコアを明記**する（例: `【Jev審査: confirm / 0.87】`）。 |
| `allow` | 実行を進めてよい。 |

> **二層防御の原則**: Jev は確率的ソフト層（確信度が低い場合がある）、`opencode.json` の `permissions` は決定論的ハード層。**どちらも迂回しようとしないこと。**

> **設計判断（2026-09-21 ボス決定 / 引き算の美学）**: Antigravity 側は Lifecycle Hook（`PreToolUse` → `tool_guard_hook.py`）で grep/コマンドを物理遮断しているが、**OpenCode 側は同等の役割を Hard ACL（`permissions`）が担うため、プラグインによる自動強制（B案）は実装しない**。AIツールのためのツール作りにスコープを広げない。

### 2.3 独立検証者 (Verifier) ゲート
実装完了時、**メインエージェント単独で「完了」と宣言することを禁ずる**（AGENTS.md 2.7）。

- **テスト**: `agent-tester` を `subagent` ツールで**実際に起動**し、`pytest` を実行させ ALL GREEN を確認する。
- **査読**: 設計変更を伴う場合は `quality-reviewer`（多角査読）／ `devils-advocate`（カオス攻撃）を起動する。
- **報告**: 誰（どのエージェントID）がどう判定したかを、セッションID・実行結果と共に報告する。

### 2.4 Desk Pet 通知
マイクロタスク完了時は `notify_task_completed(title=..., agent_name="OpenCode")` を呼び、PCペットとスマホDesk Petを歓喜させる。
ユーザー入力待ちが発生したら `notify_user_input_needed` を呼ぶ。

### 2.5 モデル選択プロトコル（コスト最適化 / 2026-09-21 制定）

サブエージェントを起動する前に `jev_select_models` でモデルを選定し、**`subagent` ツールの `model` 引数**へ渡す。

**手順**:
1. `tools.opencode.models` で**ライブの実在モデル**を取得する（一次情報。キャッシュを使わない）
2. `jev_select_models(task_description, agent_names, candidates)` を呼ぶ
3. 返却された `selections[agent].model` を `subagent` の `model` 引数に渡す
4. **`requires_approval == true` の場合は、`ask_human_approval` でボスのワンタップ承認を得てから起動する**
   （summary に `【承認帯モデル: <model> / 推定 $x.xx】` を明記）

**コスト帯（`model_catalog.py` が判定）**:

| 帯 | 条件 | 扱い |
|:---|:---|:---|
| 🟢 **常用帯** | 出力 < $1.0 / 100万トークン | 自動で使用可（例: `mimo-v2.5` $0.28 / `glm-5.3-flash` $0.50 / `deepseek-v4.1-flash` $0.60） |
| 🟡 **承認帯** | 出力 ≥ $1.0 / 100万トークン | **スマホ承認必須**（例: `deepseek-v4-pro` $1.98 / `glm-5.3` $4.40 / `kimi-k3` $15.00） |

**既定の役割別モデル（低コスト優先）**:

| 用途 | 既定 |
|:---|:---|
| 実装（`python-architect` / `pixel-frontend-designer`） | `deepseek-v4.1-flash` / `glm-5.3-flash` |
| 検証（`agent-tester`） | `glm-5.3-flash` / `qwen3.8-flash` |
| 調査・整形 | `deepseek-v4.1-flash` / `glm-5.3-flash` |
| 重大監査（`quality-reviewer` / `devils-advocate`） | 🟡 `glm-5.3` / `grok-4.6` / `kimi-k3`（**承認必須**） |

> **⚠️ モデル一覧を陳腐化させないこと**: GO契約のモデルは頻繁に入れ替わる（2026-09-21 実測で、既存キャッシュ37件のうち**10件が既に廃止済み**だった）。必ず `tools.opencode.models` で**ライブ取得**し、`model_catalog.py` のスナップショットは**保険**としてのみ扱う。

---

## 3. 専門エージェント陣形（11体）

`.opencode/agents/*.md` は **`tools/sync_opencode_agents.py` による自動生成物**である。直接編集してはならない。

| エージェント | 役割 | 権限 |
|:---|:---|:---|
| `hisho-orchestrator` | 全体統括・閉ループ制御（自らは書かない） | edit deny / subagent allow |
| `task-planner` | 要件分析・DAG分解・影響範囲分析 | Read-Only |
| `python-architect` | Python/Tkinter/LangGraph/Asyncio 実装 | 実装可 / shell 承認制 |
| `pixel-frontend-designer` | PWA/Canvas/CSS/ドット絵 実装 | 実装可 / shell 承認制 |
| `agent-tester` | TDD・pytest・独立検証 | 実装可 / pytest のみ無承認 |
| `error-analyst` | スタックトレース・真因分析 | Read-Only |
| `quality-reviewer` | 5大ペルソナ・Fowlerコード臭12種 査読 | Read-Only |
| `devils-advocate` | 悪魔の代弁者・カオス破壊・エッジケース攻撃 | Read-Only |
| `product-strategist` | 5分PM・Moat評価・引き算の美学 | Read-Only |
| `legal-compliance` | OSSライセンス・知財・プライバシー監査 | Read-Only |
| `visionary-dreamer` | 情緒的価値・レトロ触感・未来機能構想 | Read-Only |

---

## 4. Hard ACL（決定論的防壁）

`opencode.json` の `permissions` が最終防壁として機能する（**後勝ち**＝最後にマッチしたルールが有効）。

| 種別 | 内容 |
|:---|:---|
| 基本方針 | シェルは原則 `ask`（ボス承認待ち） |
| 無承認許可 | `git status/diff/log/show/branch`、`pytest`、`python -m py_compile` |
| 保護対象 | `.env` / `.env.*` / `*.db` の編集は必ず `ask` |
| **絶対拒否** | `rm -rf /`・`rm -rf ~`・`git reset --hard`・`git push --force`・`git clean -f`・`git filter-repo`・`DROP TABLE/DATABASE/SCHEMA`・`TRUNCATE TABLE`・`Format-Volume`・`mkfs` |

> シェルの `resource` は**生のコマンド文字列**として照合される（パス正規化なし・Windowsは大小文字無視）。`*` は任意文字にマッチする。

---

## 5. 同期運用（ドリフト防止）

```powershell
# 正本 (.agents/agents/*.md) → 生成物 (.opencode/agents/*.md) を再同期
.\venv\Scripts\python.exe tools\sync_opencode_agents.py

# 差分検知のみ（CI向け / 差分があれば終了コード1）
.\venv\Scripts\python.exe tools\sync_opencode_agents.py --check
```

**正本は常に `.agents/agents/*.md`（Antigravity 資産）**である。エージェントの人格・ミッションを変更したい場合は、
必ず正本を編集してから上記コマンドで再同期すること。

---

## 6. Antigravity ⇆ OpenCode ツール読み替え表

| Antigravity | OpenCode |
|:---|:---|
| `view_file` | `read` |
| `grep_search` | `grep` |
| `list_dir` | `glob` |
| `replace_file_content` / `multi_replace_file_content` / `write_to_file` | `edit` / `write` |
| `run_command` | `bash`（シェルツール） |
| `invoke_subagent` | `subagent` ツール |
| `search_web` | `websearch` |
| `read_url_content` | `webfetch` |

---

## 7. トラブルシューティング

| 症状 | 対処 |
|:---|:---|
| MCPツールが見えない | `opencode mcp list` で接続状態を確認 → `opencode service restart` |
| 新しいエージェントが起動候補に出ない | `.opencode/agents/` の配置を確認 → `opencode service restart` |
| Desk Pet に通知が届かない | ネオ秘書くん本体が起動しているか確認。`HISHO_AGENT_NAME=OpenCode` が設定されているか確認 |
| Jev が応答しない | `OPENROUTER_API_KEY`（User環境変数）を確認。`~/.gemini/tools/jev_router/.venv` の存在を確認 |
| `.opencode/agents/*.md` の中身が古い | `tools/sync_opencode_agents.py` を実行（正本と乖離している） |
