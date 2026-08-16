# ネオ秘書くん MCP サーバー連携仕様書 (MCP_INTEGRATION.md)

- **最終更新日時**: 2026-08-16 18:28 (横置き3大リッチカードUI ＆ 双方向質問回答 ＆ タブ型MCP設定完全対応)
- **準拠規格**: Model Context Protocol (2026-07-28 Specification / FastMCP / stdio JSON-RPC 2.0)

---

## 1. 概要 (Overview)

ネオ秘書くんは、**外部のあらゆるコーディングAI（Antigravity, Codex, Claude Code, Cursor, Windsurf 等）と「机上のスマホDesk Pet」を直結する MCP サーバー (`hisho_mcp_server.py`)** です。

机の上に置いたスマホ（横置き推奨）が、AIからの「承認要請」「選択肢付き質問」「作業完了通知」をリアルタイムに受け止める **インテリジェント・コックピット** に進化します。

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 🤖 外部AI (Codex / Claude Code / Antigravity / Cursor)                 │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (MCP: stdio JSON-RPC 2.0)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ ⚡ hisho_mcp_server.py (ネオ秘書くん MCP Bridge Hub)                   │
│  ├── 🛡️ ask_human_approval       : コマンド実行前のスマホワンタップ承認  │
│  ├── 🔔 notify_user_input_needed  : 選択肢付き質問の送信 ＆ スマホ回答待機│
│  ├── 🎉 notify_task_completed    : 作業完了通知＆成果物サマリリッチカード│
│  ├── 📋 create_task              : TODO手帳へのタスク自動登録           │
│  └── 🧠 remember_boss_insight    : ボスの制約・知見 (MentisDB) 永続化    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Local HTTP: Port 8765)
                                   ▼
┌──────────────────────────────────┴─────────────────────────────────────┐
│ 📱 机の上のスマホ Desk Pet (横置き 3大リッチカードUI)                   │
│  ・1️⃣ 🛡️ コマンド承認カード : コマンド/リスク ＋ ［✓承認］［✕拒否］    │
│  ・2️⃣ 🔔 質問回答カード     : 質問文 ＋ 動的選択肢ボタン ＋ クイック返信│
│  ・3️⃣ 🎉 作業完了カード     : 成果物詳細サマリ ＋ ［✓確認］            │
│  ・4️⃣ 💡 サジェストカード   : 普段の先回り予定・タスク案内             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 提供する MCP ツール一覧 (Tools)

| ツール名 | 役割・用途 | 引数 | 動作とリアクション |
| :--- | :--- | :--- | :--- |
| **`ask_human_approval`** | 破壊的コマンドの**事前承認要請** | `command` (必須), `summary`, `details`, `timeout_sec`, `agent_name` | スマホに **① 🛡️ 承認カード** が表示され、ワンタップ承認されるまでAIが安全に待機。 |
| **`notify_user_input_needed`** | 質問・確認・選択肢の**入力待ち要請** | `question` (必須), `choices` (カンマ区切りまたは配列), `agent_name`, `timeout_sec` | スマホに **② 🔔 質問回答カード** が表示され、選択肢ボタンをタップすると回答がAIへ即時返却。 |
| **`notify_task_completed`** | タスク終了・ターン完了の**作業完了通知** | `title`, `message`, `details`, `agent_name` | スマホに **③ 🎉 作業完了カード**（成果物サマリ）が表示され、ペットが大喜び。 |
| **`create_task`** | 気づいた課題の**TODO手帳登録** | `title` (必須), `priority`, `memo` | ネオ秘書くんのTODO手帳へ即時登録。 |
| **`remember_boss_insight`** | ボスの制約・好みの**MentisDB記憶** | `category` (必須), `content` (必須), `importance` | 次回以降のセッションでも参照可能な長期記憶として永続化。 |

---

## 3. 各エージェントへの登録設定（設定画面から1クリックコピー可能）

### ① Claude Desktop / Cursor / Antigravity (`mcp_config.json`)
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

### ② Codex (`config.toml`)
```toml
[mcp_servers.neo_hisho_bridge]
command = "python"
args = ["c:/Users/bonob/OneDrive/ドキュメント/AntiGlavity/ネオ秘書くん/hisho_mcp_server.py"]
```

### ③ Claude Code (CLI Command)
```bash
claude mcp add neo_hisho_bridge python c:/Users/bonob/OneDrive/ドキュメント/AntiGlavity/ネオ秘書くん/hisho_mcp_server.py
```
