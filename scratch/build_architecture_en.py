"""
Generates docs/neo-secretary-architecture-en.html by translating all Japanese strings
in docs/neo-secretary-architecture.html into native-grade technical English.
"""
from pathlib import Path

source_path = Path("docs/neo-secretary-architecture.html")
target_path = Path("docs/neo-secretary-architecture-en.html")

content = source_path.read_text(encoding="utf-8")

# Replacements for architecture diagram
replacements = {
    "<title>Neo Secretary (ネオ秘書くん) Runtime Architecture Diagram</title>": "<title>Neo Secretary Runtime Architecture Blueprint</title>",
    "<h1>Neo Secretary (ネオ秘書くん) Runtime Architecture</h1>": "<h1>Neo Secretary Runtime Architecture</h1>",
    '<title id="archify-diagram-title">Neo Secretary (ネオ秘書くん) Runtime Architecture</title>': '<title id="archify-diagram-title">Neo Secretary Runtime Architecture</title>',
    
    # Guided views JSON
    '"label":"スマホ承認コクピット通信フロー"': '"label":"Mobile Approval Cockpit Flow"',
    '"note":"外出先・Wi-Fi環境からTailscale経由で安全にPCと通信し、コマンド承認を中継するパス。"': '"note":"Securely routes remote mobile approvals and notifications via Tailscale Mesh VPN over Wi-Fi/cellular networks."',
    '"label":"コーディングエージェント連携"': '"label":"AI Coding Agent Interception"',
    '"note":"Cursor/Codex/Claude Code からの危険コマンド承認要請をスマホへ即座にプッシュ通知。"': '"note":"Pushes high-risk command approvals from Cursor, Codex, Claude Code, and Antigravity to mobile cockpit instantly."',
    '"label":"PCデスクトップ＆自律AI基盤"': '"label":"Desktop Companion & Local AI Core"',
    '"note":"CustomTkinter デスクトップペットとローカルDB・外部LLM推論・カレンダー同期の統合。"': '"note":"Orchestrates CustomTkinter desktop pet, SQLite WAL persistence, local/cloud LLM reasoning, and iCal sync."',
    
    # Bottom 3 cards
    "<h3>Zero-Trust ペアリング＆スマホ連携</h3>": "<h3>Zero-Trust Pairing & Mobile Cockpit</h3>",
    "<li>&bull; Tailscale Serve による Let&#39;s Encrypt TLS 証明書の自動終端</li>": "<li>&bull; Automatic TLS termination with Let&#39;s Encrypt via Tailscale Serve</li>",
    "<li>&bull; QRコード表示時のみトークン配布を開放する Fail-Closed 認証</li>": "<li>&bull; Fail-Closed authentication: Bearer tokens issued strictly during active QR window</li>",
    "<li>&bull; Web Speech API 音声入力 ＆ バイブレーションによるリアルタイム呼出</li>": "<li>&bull; Real-time tactile alerts via Web Speech voice synthesis and haptic vibration</li>",
    
    "<h3>マルチエージェント承認ブリッジ</h3>": "<h3>Multi-Agent Remote Approval Bridge</h3>",
    "<li>&bull; Cursor / Codex / Claude Code / Antigravity からの危険コマンド承認を中継</li>": "<li>&bull; Intercepts command approval requests from Cursor, Codex, Claude Code & Antigravity</li>",
    "<li>&bull; スマホ承認コクピットからワンタップで即座に承認/拒否を返信</li>": "<li>&bull; Review proposed bash commands and return approve/reject decisions in one tap</li>",
    
    "<h3>デスクトップ ＆ 自律生活エンジン</h3>": "<h3>Desktop Companion & Autonomous Engine</h3>",
    "<li>&bull; asyncio と Tkinter メインループの完全分離によるノンブロッキングUI</li>": "<li>&bull; Non-blocking UI architecture decoupling asyncio event loops from Tkinter GUI</li>",
    "<li>&bull; SQLite によるタスク・習慣・親愛度XPのローカル永続化</li>": "<li>&bull; Local transactional persistence for tasks, micro-habits & Bond XP via SQLite WAL</li>",
    "<li>&bull; Google Workspace iCal 連携によるカレンダー予定の自動サジェスト</li>": "<li>&bull; Proactive daily schedule timeline suggestions via read-only Google Calendar iCal</li>",
}

for k, v in replacements.items():
    if k not in content:
        print(f"WARNING: Key not found: {k}")
    content = content.replace(k, v)

target_path.write_text(content, encoding="utf-8")
print(f"Successfully wrote {target_path} ({len(content)} bytes)")
