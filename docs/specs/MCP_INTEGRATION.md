# ネオ秘書くん MCP サーバー連携仕様書 (MCP_INTEGRATION.md)

**策定日**: 2026-08-16  
**準拠規格**: Model Context Protocol (2026-07-28 Specification / FastMCP / stdio)

---

## 1. 概要 (Overview)

ネオ秘書くんは、単体で動作するデスクトップAIにとどまらず、**外部のあらゆるコーディングAI（Antigravity, Claude Code, Cursor, Codex, Windsurf 等）に「机上のスマホDesk Pet承認」と「ボスの長期知見 (MentisDB)」を提供する MCP サーバー (`hisho_mcp_server.py`)** として動作します。

```
[ Antigravity / Claude Code / Cursor / Codex ]
                      │
                      │ (MCP: stdio JSON-RPC 2.0)
                      ▼
        [ hisho_mcp_server.py ]
         ├── Tools: ask_human_approval, create_task, remember_boss_insight
         ├── Resources: hisho://insights, hisho://tasks/pending
         └── Prompts: safety_check_workflow
                      │
                      │ (Local HTTP: Port 8765)
                      ▼
     [ 机の上の古いスマホ Desk Pet (PWA) ]
```

---

## 2. 提供する MCP インターフェース

### 🛠 Tools (ツール一覧)
| ツール名 | 説明 | 主要引数 |
|:---|:---|:---|
| **`ask_human_approval`** | コマンド実行前に机上のスマホDesk Petへ承認要請を送り、判定（承認/拒否）を待機 | `command` (必須), `summary`, `details`, `timeout_sec` (デフォルト180) |
| **`create_task`** | 作業中に見つけた課題を秘書くんのTODO手帳に登録 | `title` (必須), `priority` ('high'/'medium'/'low'), `memo` |
| **`remember_boss_insight`** | ボスの制約・好み・作業習慣・ルールを MentisDB (`user_insights`) に永続化 | `category` (必須), `content` (必須), `importance` (1-3) |
| **`get_boss_insights`** | MentisDBからボスの制約や好みを検索・取得 | `category`, `limit` (デフォルト10) |

### 📚 Resources (コンテキストリソース)
| URI | 説明 | MIME Type |
|:---|:---|:---|
| **`hisho://insights`** | ボスの制約条件（可処分時間・健康制約等）や好みの全知見 | `application/json` |
| **`hisho://tasks/pending`** | 現在未完了のTODOタスク一覧 | `application/json` |

---

## 3. 各エージェントへの登録設定（コピペ用設定例）

### ① Antigravity / Cursor (`mcp_config.json` または IDE MCP 設定)
```json
{
  "mcpServers": {
    "neo_hisho_bridge": {
      "command": "python",
      "args": [
        "c:/Users/bonob/OneDrive/ドキュメント/AntiGlavity/ネオ秘書くん/hisho_mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

### ② Claude Code (`~/.claude/config.json` または MCP 登録コマンド)
```bash
claude mcp add neo_hisho_bridge python c:/Users/bonob/OneDrive/ドキュメント/AntiGlavity/ネオ秘書くん/hisho_mcp_server.py
```

---

## 4. 動作確認テスト手順

1. **ネオ秘書くん本体の起動**:
   ```powershell
   python main.py
   ```
2. **MCPサーバーの単体疎通確認 (PowerShell)**:
   ```powershell
   # initialize リクエストのテスト
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2026-07-28"}}' | python hisho_mcp_server.py
   ```
