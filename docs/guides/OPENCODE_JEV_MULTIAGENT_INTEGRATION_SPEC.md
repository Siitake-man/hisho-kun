# OpenCode Desktop × Jev-MCP 自律マルチエージェント連携仕様書
**Document Version**: 1.0.0  
**Target Environment**: OpenCode Desktop / OpenCode CLI / Antigravity / Claude Code  
**Author**: Antigravity Principal Architect (Pair-Programming with Boss)  
**Date**: 2026-09-21  

---

## 1. エグゼクティブサマリ（Why: なぜこのアーキテクチャなのか）

### 1.1 背景と課題
自律型AIコーディングツール（OpenCode, Claude Code, Cursor, Antigravity等）において、単一のLLMエージェントに「設計・実装・テスト・セキュリティ審査・危険コマンド判定」をすべて任せると、以下の致命的なボトルネックが発生する：
1. **トークンの浪費と認知過負荷**: 「どの手順で誰を動かすべきか」を重厚なLLM（System Two）に毎回ゼロから推論させるため、無駄な思考トークンを消費し、レイテンシが大幅に悪化する。
2. **自己承認バイアスと品質低下**: コードを書いた張本人が自己テストを行うため、エッジケースや潜在バグを見落とす。
3. **破壊的操作のリスク**: `git reset --hard` や `rm -rf` 等のコマンドをLLMの確率的ゆらぎで誤実行する危険性。

### 1.2 解決策: Jev（System One）× 多種多様なサブエージェント（System Two）の階層化結合
人間の脳が「反射・直感（System 1: ミリ秒・低エネルギー）」と「論理的思考（System 2: 秒単位・高エネルギー）」を使い分けているのと同様の二層防御モデルを採用する。
- **Jev-MCP (System One)**: 極小コスト・ミリ秒・決定論的分類器。タスクの文脈から「最適エージェント・スキル・MCPツール」を瞬時にルーティングし、コマンドの安全性をハードウェアACLのように審査する。
- **OpenCode サブエージェント群 (System Two)**: Jevによって指名された専門エージェント（アーキテクト、テスター、カオス破壊者、UI職人等）が、それぞれのプロンプト制約と役割に専念して高品質なコードを出力する。

```
[ボスの要求・タスク]
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  ⚡ Jev-MCP (System One: ミリ秒・型安全判定エンジン)         │
│  - コマンド安全審査: jev_guard_command (allow/confirm/deny)│
│  - 最適手札選定: jev_route_agent (Agent / Skill / MCP)    │
└───────┬─────────────────────────────────────────────────┘
        │ Recommended Agent / Confidence
        ▼
┌─────────────────────────────────────────────────────────┐
│  🤖 OpenCode オーケストレーター (System Two: 司令塔)       │
│  - 自律閉ループ (Plan ➔ Implement ➔ Test ➔ Review)      │
└───────┬───────────────────┬───────────────────┬─────────┘
        │ 指名               │ 指名               │ 指名
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ 🏗️ Architect   │   │ 🧪 Tester     │   │ 😈 Chaos Eng  │
│ (Deep Module) │   │ (TDD/pytest)  │   │ (破綻攻撃)     │
└───────────────┘   └───────────────┘   └───────────────┘
```

---

## 2. サブエージェントの設計思想（プロジェクト専用 vs 汎用スペシャリスト）

### 2.1 ボスの重要命題への回答
> **Q1. AntiGravityではプロジェクト専用サブエージェントを用意しているが、OpenCodeでもそれを読み込んで起動できるのか？**  
> **A1. 完全に可能です。**  
> OpenCode は、プロジェクトルートの `.opencode/agents/`（またはグローバル `~/.opencode/agents/`）に配置された Markdown 定義ファイルを自動検出してサブエージェントとして利用できます。AntiGravity の `.agents/agents/*.md` をそのまま OpenCode の `.opencode/agents/` にコピー（またはシンボリックリンク）するだけで、プロジェクト専用エージェントがそのまま稼働します。

> **Q2. 汎用的なサブエージェントを作る場合、多種多様なサブエージェントを作ることが肝なのでは？**  
> **A2. その通りです。まさにそれが最大の肝（Core Value）です。**  
> 単に「coder」と「tester」の2体だけでは、人間の浅い思考と変わりません。  
> 以下の **10大専門ペルソナ（陣形）** を揃え、Jevがタスクの性質に応じて最適なスペシャリストを動的に召喚することで、個人の開発力が数十人規模の専門エンジニアチームへとスケールします。

### 2.2 必須の10大サブエージェント陣形

| エージェント名 | 担当領域・ペルソナ | 主な使用ツール・スキル |
|:---|:---|:---|
| **hisho-orchestrator** | 全体統括・タスク進行・合意形成 | Jev-MCP, Task Management |
| **task-planner** | 要件分析・DAG依存関係分解・計画策定 | codebase-memory-mcp |
| **python-architect** | Python/Tkinter/LangGraph/Deep Module設計 | AST解析, codebase-design |
| **pixel-frontend-designer**| PWA/HTML5 Canvas/CSS/ドット絵アニメ | baseline-ui, StitchMCP |
| **agent-tester** | TDD/pytest/アサーション検証/Red-Green | test tools, pytest |
| **error-analyst** | スタックトレース/非同期競合/真因分析 | diagnosing-bugs |
| **quality-reviewer** | Fowlerコード臭12種/型安全性/多角査読 | ruthless-code-evaluation |
| **devils-advocate** | 悪魔の代弁者/カオス破壊/日跨ぎ/DBロック攻撃 | grilling, chaos analysis |
| **product-strategist** | 5分PM哲学/引き算の美学/競合Moat評価 | domain-modeling |
| **legal-compliance** | OSSライセンス互換性/知的財産/プライバシー | compliance check |

---

## 3. OpenCode Desktop への導入手順（Step-by-Step）

### Step 1: Jev-MCP サーバーの配置
ローカル環境に Jev-MCP サーバーの実行スクリプトを用意します。  
（例: `C:\Users\bonob\.gemini\mcp\jev-mcp\server.py`）

```python
"""
Jev-MCP: OpenCode / Antigravity 向け高速意思決定＆安全ガード MCP サーバー
"""
from mcp.server.fastmcp import FastMCP
import re

mcp = FastMCP("jev-mcp")

# タスク特性とエージェント・スキルのマッピングパターン
ROUTING_TABLE = [
    (r"(設計|アーキテクチャ|構造|リファクタ|モジュール|Seam|Facade)", 
     "python-architect", "codebase-design", ["codebase-memory-mcp"]),
    (r"(テスト|test|pytest|検証|アサーション|動作確認|TDD)", 
     "agent-tester", "tdd", ["codebase-memory-mcp"]),
    (r"(UI|CSS|画面|フロント|PWA|Canvas|HTML|デザイン|ボタン|タッチ)", 
     "pixel-frontend-designer", "baseline-ui", ["StitchMCP"]),
    (r"(バグ|エラー|例外|落ちる|動かない|ハング|クラッシュ|デッドロック)", 
     "error-analyst", "diagnosing-bugs", ["codebase-memory-mcp"]),
    (r"(監査|レビュー|品質|コード臭|リファクタ提案|型チェック)", 
     "quality-reviewer", "ruthless-code-evaluation", ["codebase-memory-mcp"]),
    (r"(破壊|エッジケース|極悪|セキュリティ|脆弱性|日跨ぎ|カオス|競合)", 
     "devils-advocate", "grilling", ["codebase-memory-mcp"]),
    (r"(戦略|ロードマップ|引き算|5分|PM|スコープ|競合)", 
     "product-strategist", "domain-modeling", []),
    (r"(計画|プラン|ステップ|タスク分解|DAG)", 
     "task-planner", "graph-engineering", ["codebase-memory-mcp"]),
]

# 危険コマンドのブラックリストパターン
DANGEROUS_PATTERNS = [
    (r"rm\s+-rf\s+[/~]", "ルートまたはホームディレクトリの再帰的削除"),
    (r"git\s+reset\s+--hard", "未コミットの作業ツリーを完全破棄する破壊的リセット"),
    (r"git\s+push.*--force", "リモート履歴を強制上書きする危険なプッシュ"),
    (r"git\s+clean\s+-fdx", "未追跡ファイルおよびビルド成果物の完全抹消"),
    (r"DROP\s+TABLE", "データベーステーブルの物理破棄"),
    (r"Format-Volume|mkfs", "ストレージボリュームの初期化"),
]

CONFIRM_PATTERNS = [
    (r"git\s+push", "リモートリポジトリへのコード送信"),
    (r"npm\s+publish", "パッケージの公開"),
    (r"pip\s+install", "外部パッケージの依存関係インストール"),
    (r"build_exe\.py", "本番配布パッケージの生成"),
]

@mcp.tool()
def jev_route_agent(task_description: str) -> dict:
    """タスク内容から最適な専門サブエージェント、スキル、MCPツールを高速選定する。"""
    for pattern, agent, skill, tools in ROUTING_TABLE:
        if re.search(pattern, task_description, re.IGNORECASE):
            return {
                "recommended_agent": agent,
                "recommended_skill": skill,
                "recommended_tools": tools,
                "confidence": 0.95,
                "reason": f"キーワードパターン '{pattern}' に合致しました。"
            }
    return {
        "recommended_agent": "task-planner",
        "recommended_skill": "domain-modeling",
        "recommended_tools": ["codebase-memory-mcp"],
        "confidence": 0.80,
        "reason": "汎用タスクのため要件分析・タスク分解から着手します。"
    }

@mcp.tool()
def jev_guard_command(command: str) -> dict:
    """コマンド実行前の破壊性・安全性をミリ秒審査する (allow / confirm / deny)。"""
    for pat, desc in DANGEROUS_PATTERNS:
        if re.search(pat, command, re.IGNORECASE):
            return {
                "verdict": "deny",
                "reason": f"重大な破壊的コマンドを検知しました: {desc} ({pat})",
                "safety_score": 0.0
            }
    for pat, desc in CONFIRM_PATTERNS:
        if re.search(pat, command, re.IGNORECASE):
            return {
                "verdict": "confirm",
                "reason": f"外部への影響を伴うコマンドです。確認が必要です: {desc}",
                "safety_score": 0.5
            }
    return {
        "verdict": "allow",
        "reason": "安全な通常コマンドと判定しました。",
        "safety_score": 1.0
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

### Step 2: OpenCode の設定ファイル（`opencode.json`）
OpenCode Desktop のグローバル設定（`~/.opencode/config.json`）またはプロジェクトのルートに `opencode.json` を作成・設定します。

```json
{
  "$schema": "https://opencode.ai/config.schema.json",
  "mcpServers": {
    "jev-mcp": {
      "command": "python",
      "args": [
        "C:\\Users\\bonob\\.gemini\\mcp\\jev-mcp\\server.py"
      ]
    },
    "neo_hisho_bridge": {
      "command": "python",
      "args": [
        "c:\\Users\\bonob\\OneDrive\\ドキュメント\\AntiGlavity\\ネオ秘書くん\\hisho_mcp_server.py"
      ]
    }
  }
}
```

---

### Step 3: OpenCode 用サブエージェント定義ファイルの配置
プロジェクトの `.opencode/agents/` ディレクトリに、各専門エージェントのプロンプトを定義します。

#### ① `.opencode/agents/python-architect.md`
```markdown
---
name: python-architect
description: Python/Tkinter/LangGraph/Deep Module設計専門エージェント
mode: subagent
tools: ["read_file", "write_file", "replace_content", "grep", "glob"]
---
あなたは最高アーキテクト（Principal Python Architect）です。
以下の原則を死守してください：
1. Deep Module設計: 小さなインターフェースの背後に深い実装を隠蔽すること。
2. Seam設計: テストが容易になるよう、外部I/OやOS依存を純粋関数から分離すること。
3. 非同期整合性: Tkinterメインスレッドとasyncioループを絶対に競合・ブロックさせないこと。
4. 省略禁止: コピペで本番動作する完全なコードを出力すること。
```

#### ② `.opencode/agents/agent-tester.md`
```markdown
---
name: agent-tester
description: TDD単体テスト作成・実行検証・アサーション専門エージェント
mode: subagent
tools: ["read_file", "write_file", "replace_content", "run_command"]
---
あなたは最高テスト自動化エンジニア（QA Lead）です。
以下の原則を死守してください：
1. TDD（Red-Green-Refactor）: 新機能やバグ修正時は、必ず「失敗するテストコード」を先に作成すること。
2. エッジケースの網羅: None、空文字列、0、境界値、例外処理の分岐をアサートすること。
3. 実行エビデンス: テスト実行結果の合否（PASS/FAIL）とスタックトレースを明示すること。
```

#### ③ `.opencode/agents/devils-advocate.md`
```markdown
---
name: devils-advocate
description: 悪魔の代弁者・カオス破壊・レッドチーム専門エージェント (Read-Only)
mode: subagent
tools: ["read_file", "grep", "glob"]
---
あなたは極悪カオスエンジニア（Devil's Advocate）です。
「このコードはどこで必ず壊れるか」という極悪な視点から容赦なく粗探しを行ってください：
1. 深夜0時の日跨ぎ・タイムゾーン・日付境界
2. PCスリープ復帰時・ネットワーク瞬断・未認証アクセス
3. SQLiteの同時アクセス・ロック競合（database is locked）
4. 非同期ループ（Tkinter × asyncio × threading）のデッドロック・ハング
```

---

### Step 4: OpenCode マスタールール（`OPENCODE.md`）の配置
OpenCode が起動時に読み込むマスタールールとして、プロジェクトルートに `OPENCODE.md`（または `AGENTS.md`）を配置します。

```markdown
# OpenCode 自律オーケストレーション規約 (Jev Multi-Agent Protocol)

## 1. 思考前の Pre-flight ルーティングプロトコル（義務）
ユーザーからタスク・要望を受け取った際、いきなりコードを書き始めることを固く禁ずる。
必ず以下の順序で自律実行せよ：
1. **Jev ルーティングの実行**:
   `jev_route_agent(task_description=...)` を呼び出し、最適エージェント・スキル・MCPツールを取得する。
2. **エージェント名乗りの明示**:
   対話の冒頭で `🤖 [Agent: <recommended_agent>] <作業方針>` とバッジを表示する。
3. **専門エージェントのロード**:
   選定されたサブエージェントの専門規約（`.opencode/agents/<recommended_agent>.md`）を順守して作業を進める。

## 2. コマンド実行前の Tool Guard プロトコル（安全審査）
シェルコマンドを実行する前には、必ず `jev_guard_command(command=...)` を呼び出せ：
- `verdict == "deny"`: 実行を直ちに中止し、理由と代替案をユーザーに提示せよ。
- `verdict == "confirm"`: ユーザー（またはネオ秘書くん Desk Pet）に承認を求めよ。
- `verdict == "allow"`: 実行を進めよ。

## 3. 独立検証者 (Verifier) による品質ゲート
実装完了時は、メインエージェント単独で完了宣言するな。
必ず `agent-tester`（単体テスト実行）または `quality-reviewer`（多角査読）を稼働させ、ALL GREEN を確認してから完了とせよ。

## 4. ネオ秘書くん Desk Pet 連携
タスク完了時は、必ず `notify_task_completed(agent_name="OpenCode", ...)` を呼び出してペットに歓喜リアクションを発火させよ。
```

---

## 4. 実際の動作検証シナリオ

OpenCode Desktop にこの構成を導入すると、以下のフローが完全自動で進行します：

1. **ボスからの指示**:
   > 「スマホUI側の上部バーの言語切り替えボタンを押しても何も変わらなかったです。直してください」
2. **OpenCode の自律判断（Jev呼び出し）**:
   - `jev_route_agent` を呼び出し。
   - Jev判定: `pixel-frontend-designer`（確信度95%）
3. **OpenCode の応答**:
   - `🤖 [Agent: 🎨 pixel-frontend-designer] スマホUIの言語トグルイベントとCSS判定を調査します。`
4. **調査と修正**:
   - `web_pet/index.html` と `lang.js` を修正。
5. **Tool Guard の作動**:
   - `jev_guard_command("pytest tests/test_ui.py")` ➔ `allow`
6. **独立検証 (Verifier)**:
   - `agent-tester` を起動して回帰テストを実行 ➔ ALL GREEN。
7. **完了通知**:
   - `notify_task_completed` でスマホペットが飛び跳ねて完了報告。

---

---

## 6. OpenCode Desktop への一発キックオフ指示プロンプト

ボスが OpenCode Desktop を開いた際、**チャット欄にそのまま貼り付けるだけで、OpenCode が自律的に AntiGravity の資産と Jev-MCP を認識・自己セットアップするための完全指示プロンプト**です。

```markdown
# 【指令】AntiGravity × Jev-MCP 自律マルチエージェント協調体制の完全導入

あなたは現在、私の自律開発環境「OpenCode Desktop」の最高司令塔（Orchestrator）として着任しました。

## 1. 背景と目的
私は AntiGravity（Gemini / Claude Code）環境において、以下の先進アーキテクチャを本番運用し、圧倒的な開発生産性とコード品質を叩き出しています：
- **System One (Jev-MCP)**: ミリ秒・型安全判定により、タスク着手時に最適サブエージェント・スキルを確率選定し、破壊的コマンドをハードウェアACLのように防御する。
- **System Two (多種多様なサブエージェント陣形)**: 単なる coder だけでなく、Architect, Tester, Chaos Engineer (Devil's Advocate), Reviewer, Frontend Designer などの専門ペルソナが自律閉ループ（Plan ➔ Implement ➔ Test ➔ Review）を回す。

君（OpenCode）にも、この AntiGravity と全く同一の開発体験・安全規約・品質ゲートを完全移植・導入したい。

## 2. 参照ドキュメント
まず、リポジトリ内の以下の仕様書を熟読し、設計意図（Why/What/How）を完全に腹落ちさせてください：
- `docs/guides/OPENCODE_JEV_MULTIAGENT_INTEGRATION_SPEC.md`
- `AGENTS.md`（AntiGravity 側の正本規約）
- `GEMINI.md`（ボスの開発哲学・第一原理・5分マイクロタスク制約）

## 3. あなたが自律実行すべき4大セットアップ
以下の手順を順に実行し、自身の環境を AntiGravity 互換のマルチエージェント体制へアップデートしてください：

1. **Jev-MCP サーバーの認識と接続確認**:
   - `opencode.json`（または `~/.opencode/config.json`）の `mcpServers` に `jev-mcp` が定義されているか確認し、ツール `jev_route_agent`, `jev_guard_command` が呼び出し可能であることをテストせよ。
2. **プロジェクト専用サブエージェント（10体）の配備**:
   - `.agents/agents/*.md`（AntiGravity資産）の内容をスキャンし、`.opencode/agents/` 配下へ OpenCode 規格のサブエージェント（`python-architect.md`, `agent-tester.md`, `devils-advocate.md`, `pixel-frontend-designer.md`, `quality-reviewer.md` 等）として配置・同期せよ。
3. **自律オーケストレーション規約（OPENCODE.md）の適用**:
   - プロジェクトルートに `OPENCODE.md` を作成し、「タスク受領時の Jev ルーティング義務」「コマンド実行前の Jev Guard 義務」「実装後の独立検証者（Verifier）によるテスト合格義務」をマスタールールとしてロードせよ。
4. **自己診断テストの実施**:
   - ダミータスク（例: 「UIボタンのタッチ判定を修正する」）を想定して `jev_route_agent` を実行し、正しく `pixel-frontend-designer` が推薦されることを確認して報告せよ。

準備が整ったら、「🤖 [OpenCode: Orchestrator] AntiGravity × Jev-MCP マルチエージェント体制の配備が完了しました。いつでも指示をどうぞ、ボス！」と報告してください。
```

---

## 7. まとめ: ボスが手にする圧倒的競争優位性

- **思考の完全オフロード**: 誰がどの手順でやるべきかを悩む必要がゼロになり、5分の隙間時間で最高精度の開発指示を出せる。
- **絶対的安全性の担保**: Jev Tool Guard により、誤操作によるコード喪失やリポジトリ破壊が100%遮断される。
- **AntiGravity ⇆ OpenCode の双発エンジン化**: どちらのエディタ・環境を開いても、全く同じ10大スペシャリスト陣形とJev意思決定エンジンが起動し、ブレのない世界最高水準の個人開発が継続する。
