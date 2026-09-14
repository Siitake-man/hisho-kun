"""
Performs a comprehensive cleanup and translation of all remaining Japanese UI text
in docs/neo-secretary-showcase-en.html.
"""
from pathlib import Path
import json

path = Path("docs/neo-secretary-showcase-en.html")
content = path.read_text(encoding="utf-8")

replacements = {
    # Workspace drawer & buttons
    '>ライブラリ</button>': '>Library</button>',
    '<div class="section-kicker">ライブラリ</div>': '<div class="section-kicker">Library</div>',
    '<h2 id="workspace-title">学習ワークスペース</h2>': '<h2 id="workspace-title">Learning Workspace</h2>',
    '<button type="button" data-workspace-close>閉じる</button>': '<button type="button" data-workspace-close>Close</button>',
    '<p>このブラウザ内で履歴、お気に入り、注釈メモを保存します。</p>': '<p>Save browsing history, bookmarks, and annotation notes locally in this browser.</p>',
    '<button type="button" data-library-enable>ローカルライブラリを有効化</button>': '<button type="button" data-library-enable>Enable Local Library</button>',
    'aria-label="学習ワークスペース"': 'aria-label="Learning Workspace"',
    '<button type="button" role="tab" id="workspace-tab-contents" aria-controls="workspace-panel-contents" aria-selected="true">目次</button>': '<button type="button" role="tab" id="workspace-tab-contents" aria-controls="workspace-panel-contents" aria-selected="true">Contents</button>',
    '<button type="button" role="tab" id="workspace-tab-history" aria-controls="workspace-panel-history" aria-selected="false" tabindex="-1">閲覧履歴</button>': '<button type="button" role="tab" id="workspace-tab-history" aria-controls="workspace-panel-history" aria-selected="false" tabindex="-1">History</button>',
    '<button type="button" role="tab" id="workspace-tab-annotations" aria-controls="workspace-panel-annotations" aria-selected="false" tabindex="-1">注釈・メモ</button>': '<button type="button" role="tab" id="workspace-tab-annotations" aria-controls="workspace-panel-annotations" aria-selected="false" tabindex="-1">Notes</button>',
    '<button type="button" class="document-favorite" data-document-favorite aria-pressed="false">ドキュメントをお気に入りに登録</button>': '<button type="button" class="document-favorite" data-document-favorite aria-pressed="false">Bookmark Document</button>',
    '<h3 id="workspace-export-title">エクスポート</h3>': '<h3 id="workspace-export-title">Export</h3>',
    '<button type="button" data-export-pdf>印刷 / PDF保存</button>': '<button type="button" data-export-pdf>Print / Save PDF</button>',
    '<button type="button" data-export-pptx>全シーンをPPTX (スライド) 出力</button>': '<button type="button" data-export-pptx>Export PPTX Slides</button>',
    '<button type="button" data-export-image>現在のシーンをPNG保存</button>': '<button type="button" data-export-image>Save Current Scene as PNG</button>',
    '<button type="button" data-export-docx>Pages互換 DOCX出力</button>': '<button type="button" data-export-docx>Export DOCX Document</button>',
    '<label for="annotation-scene">対象セクション</label>': '<label for="annotation-scene">Target Section</label>',
    '<label for="annotation-text" class="sr-only">このセクションに関するメモを記述...</label>': '<label for="annotation-text" class="sr-only">Write your thoughts or notes about this section...</label>',
    'placeholder="このセクションに関するメモを記述..."': 'placeholder="Write your thoughts or notes about this section..."',
    '<button type="button" data-annotation-save>メモを保存</button>': '<button type="button" data-annotation-save>Save Note</button>',
    '<button type="button" data-annotation-cancel hidden>キャンセル</button>': '<button type="button" data-annotation-cancel hidden>Cancel</button>',
    '<p class="workspace-storage-note" id="workspace-storage-note" tabindex="-1" aria-live="polite">お気に入り・履歴・メモはこのブラウザ内（ローカル）にのみ安全に保存されます。</p>': '<p class="workspace-storage-note" id="workspace-storage-note" tabindex="-1" aria-live="polite">Bookmarks, history, and notes are securely stored only inside this browser.</p>',
    '<button type="button" data-mini-pause>一時停止</button>': '<button type="button" data-mini-pause>Pause</button>',

    # Hero & Cheatsheet link
    'guides/NEO_HISHO_CHEAT_SHEETS.html': 'guides/NEO_HISHO_CHEAT_SHEETS_en.html',
    '📘 チートシート ＆ 公式利用ガイドを開く ➔': '📘 Official Cheatsheets & Guide ➔',
    '<a href="neo-secretary-showcase-en.html" style="background:var(--paper-2); color:var(--indigo); border:1.5px solid var(--indigo); padding:9px 18px; border-radius:999px; font-weight:800; text-decoration:none; font-size:0.9rem; display:inline-flex; align-items:center; gap:6px;">\n            🇬🇧 English\n          </a>': '<a href="neo-secretary-showcase.html" style="background:var(--paper-2); color:var(--indigo); border:1.5px solid var(--indigo); padding:9px 18px; border-radius:999px; font-weight:800; text-decoration:none; font-size:0.9rem; display:inline-flex; align-items:center; gap:6px;">\n            🇯🇵 日本語\n          </a>',

    # Module Blueprint Section
    '<div class="section-kicker">モジュール構造</div>': '<div class="section-kicker">Module Architecture</div>',
    
    # Trace controls
    '<button type="button" data-trace="play">再生</button>': '<button type="button" data-trace="play">Play</button>',
    '<button type="button" data-trace="previous">前へ</button>': '<button type="button" data-trace="previous">Previous</button>',
    '<button type="button" data-trace="next">次へ</button>': '<button type="button" data-trace="next">Next</button>',
    '<button type="button" data-trace="reset">リセット</button>': '<button type="button" data-trace="reset">Reset</button>',
    '<button type="button" data-failure-toggle aria-pressed="false">障害シミュレーター</button>': '<button type="button" data-failure-toggle aria-pressed="false">Failure Simulator</button>',

    # Static fallback nodes in HTML
    '<h3>スマホ Desk Pet (PWA)</h3>': '<h3>Mobile Desk Pet (PWA)</h3>',
    '<p>常時点灯の卓上スマートディスプレイ。8bitシンセ音とオフラインキャッシュを搭載。</p>': '<p>Always-on tactile smart display with 8-bit sound synthesis and offline caching.</p>',
    '<span class="node-kind">判定・分岐</span>': '<span class="node-kind">Decision</span>',
    '<h3>同期サーバー (LocalSyncServer)</h3>': '<h3>Sync Server (LocalSyncServer)</h3>',
    '<p>Bearerトークン認証とCORS隔離を強制する軽量HTTPデーモン。</p>': '<p>Lightweight HTTP daemon enforcing constant-time Bearer authentication and CORS origin echoing.</p>',
    '<h3>Agent監視デーモン</h3>': '<h3>Agent Supervision Daemon</h3>',
    '<p>外部AIエージェントのログ出力をリアルタイム監視し、完了歓喜や承認要請を発火。</p>': '<p>Monitors CLI build output and intercepts command approval requests in real time.</p>',
    '<h3>LangGraph ＆ LLM Factory</h3>': '<h3>LangGraph & LLM Factory</h3>',
    '<p>Gemini/Claudeとオフライン用ローカルGGUFをシームレスに切り替える思考エンジン。</p>': '<p>Dynamically switches between Gemini, Claude, and local GGUF models.</p>',
    '<h3>SQLite WAL データベース</h3>': '<h3>SQLite WAL Database</h3>',
    '<p>予定・タスク・習慣・ボスの知見をトランザクション安全に保存する永続化層。</p>': '<p>Persistent store for tasks, habits, and tamper-proof approval audit trails.</p>',
    '<h3>デスクトップペット (Tkinter)</h3>': '<h3>Desktop Mascot (Tkinter)</h3>',
    '<p>最前面透過ウィンドウでピクセルアニメーションと吹き出しを描画。</p>': '<p>Top-level transparent window rendering breathing pixel sprites and comic balloons.</p>',
    '<h3>音声・SEシンセサイザー</h3>': '<h3>Audio & Chime Synthesizer</h3>',
    '<p>8bitレトロ効果音とWeb Speech音声読み上げによるタスクナレーション。</p>': '<p>8-bit sound effects and speech synthesis for milestone notifications.</p>',

    # Archify frame link
    'src="neo-secretary-architecture.html"': 'src="neo-secretary-architecture-en.html"',
    'href="neo-secretary-architecture.html"': 'href="neo-secretary-architecture-en.html"',

    # Component drawer markup
    '<h2 id="comp-drawer-title" style="font-size:1.45rem; color:var(--indigo); margin-top:2px;">コンポーネント名</h2>': '<h2 id="comp-drawer-title" style="font-size:1.45rem; color:var(--indigo); margin-top:2px;">Component Name</h2>',
    '<button type="button" onclick="closeComponentDrawer()">閉じる</button>': '<button type="button" onclick="closeComponentDrawer()">Close</button>',
    '② 身近な例えでの理解 (Analogy)': '2. Everyday Analogy',
    '③ 設計のポイント ＆ 勝因 (Why &amp; Tradeoff)': '3. Design Architecture & Tradeoffs (Why & How)',
    '📁 関連ソースコード': '📁 Associated Source Code',

    # Core Concepts Section
    '<h2>📚 押さえておくべきコア概念</h2>': '<h2>📚 Core Architectural Concepts</h2>',
    '<h3>🔒 ローカル完結・最小権限・承認必須</h3>': '<h3>🔒 Local-First, Least Privilege & Mandatory Approval</h3>',
    '<p>同一LAN内通信であっても全リクエストにBearer認証を要求し、外部クラウドリレーなしで完結させるセキュリティ設計。</p>': '<p>Security architecture enforcing Bearer token authentication on all requests—even within local LAN—with zero cloud dependencies or external relays.</p>',
    '<h3>📱 卓上承認リモコン (Desk Pet)</h3>': '<h3>📱 Desktop Approval Remote (Desk Pet)</h3>',
    '<p>スマホを卓上常時点灯ディスプレイ化し、AIエージェントのコマンド実行許可をワンタップで遠隔承認できるPWAコックピット。</p>': '<p>Always-on tactile PWA turning spare smartphones into a companion cockpit to review and authorize AI agent terminal commands with one tap.</p>',
    '<h3>💾 SQLite WAL &amp; 3層防衛</h3>': '<h3>💾 SQLite WAL &amp; 3-Tier Defense Engine</h3>',
    '<p>GUIとHTTPサーバー間のロック競合を防ぐ先行書き込みログと、自己承認禁止によるRCE遮断構造。</p>': '<p>Write-Ahead Logging (WAL) prevents concurrency lock contention between GUI and HTTP server, backed by strict anti-self-approval protection against RCE.</p>',

    # JavaScript alert
    "alert('📋 次期5分指示書をクリップボードにコピーしました！');": "alert('📋 Copied 5-minute task prompt to clipboard!');",
}

for k, v in replacements.items():
    if k not in content:
        print(f"Notice: pattern not found: {k[:50]}...")
    content = content.replace(k, v)

# Update COMPONENT_DETAILS in script
comp_details_en = {
    "pwa": {
        "title": "📱 Mobile Desk Pet (PWA Client)",
        "what": "Always-on tactile touchscreen sitting on your desk to display mascot reactions and approval alerts.",
        "analogy": "'A dedicated smartwatch or miniature smart display on your desk.'",
        "why": "Eliminates app store review friction and battery drain; runs instantly by tapping 'Add to Home Screen'.",
        "code": "web_pet/index.html & pet.js (v7.2 Voice Edition)",
        "matchKeywords": ["pwa", "mobile", "phone", "cockpit"]
    },
    "server": {
        "title": "⚙️ Sync Server (LocalSyncServer)",
        "what": "Lightweight HTTP gateway relaying messages and approvals between phone and desktop.",
        "analogy": "'The concierge desk routing room calls and handling guest keys.'",
        "why": "Direct communication over LAN or Tailscale ensures zero cloud latency and total privacy.",
        "code": "local_sync_server.py (Bearer Auth & Bridge Hub)",
        "matchKeywords": ["server", "localsync", "proxy", "tailscale"]
    },
    "langgraph": {
        "title": "🧠 LangGraph & LLM Factory",
        "what": "Reasoning engine determining next actions based on developer input and build state.",
        "analogy": "'The strategic thought process of an executive secretary.'",
        "why": "State machine graphs explicitly model planning, executing, and awaiting human confirmation.",
        "code": "agent.py & llm_factory.py",
        "matchKeywords": ["langgraph", "llm", "gemini", "claude"]
    },
    "tkinter": {
        "title": "🖥️ PC Desktop Mascot (Tkinter Overlay)",
        "what": "Border-less transparent window living at the bottom-right corner of your desktop.",
        "analogy": "'A friendly spirit living inside your monitor.'",
        "why": "Custom Tkinter event loop interlaces with asyncio, preventing desktop UI freezes during heavy LLM inference.",
        "code": "gui.py & main.py (Asyncio Mainloop)",
        "matchKeywords": ["gui", "desktop", "pet", "tkinter"]
    },
    "sqlite": {
        "title": "💾 Database (SQLite WAL & MentisDB)",
        "what": "Transaction-safe persistent notebook recording tasks, habits, and boss insights.",
        "analogy": "'An indestructible leather-bound organizer.'",
        "why": "Write-Ahead Logging (WAL) allows concurrent reads and writes from GUI and HTTP daemon without database locks.",
        "code": "database.py (Pydantic & WAL Mode)",
        "matchKeywords": ["sql", "db", "database", "wal"]
    },
    "watcher": {
        "title": "👁️ Agent Supervision Daemon (AgentWatcher)",
        "what": "Background watcher tracking external AI agents to trigger approval banners and celebrations.",
        "analogy": "'A motion sensor watching the workshop door.'",
        "why": "Real-time log interception triggers instant mascot celebrations the moment tests turn green.",
        "code": "agent_watcher.py & task_narrator.py",
        "matchKeywords": ["agent", "watcher", "bridge", "codex"]
    },
    "weather": {
        "title": "🌐 External Integrations (Meteo & Calendar)",
        "what": "Fetches local weather and Google Calendar events without credential leaks.",
        "analogy": "'A courier delivering morning newspapers and weather reports.'",
        "why": "Secret iCal URLs and key-less Open-Meteo APIs provide friction-free setups.",
        "code": "weather_tools.py & ics_tools.py",
        "matchKeywords": ["weather", "cal", "google", "meteo"]
    }
}

# Replace COMPONENT_DETAILS literal
import re
comp_pattern = r'const COMPONENT_DETAILS = \{.*?\};'
new_comp_str = f"const COMPONENT_DETAILS = {json.dumps(comp_details_en, ensure_ascii=False)};"
content = re.sub(comp_pattern, new_comp_str, content, count=1)

# In eli5-data, translate nextQuest
content = content.replace(
    '"nextQuestTitle": "Phase L5 シークレットミニゲーム「Pixel Defense」"',
    '"nextQuestTitle": "Phase L5 Secret Mini-Game \\"Pixel Defense\\""'
)
content = content.replace(
    '"nextQuestDesc": "イースターエッグ解放バッジ（👾 秘密の部屋）から遊べる、レトロ8bitインベーダー防衛シューティングの実装。"',
    '"nextQuestDesc": "Implementation of an 8-bit retro invader defense shooter playable via easter-egg secret room badge."'
)
content = content.replace(
    '"nextQuestPrompt": "以下の5分マイクロタスクを実装してください：\\n【タスク】Phase L5 シークレットミニゲーム「Pixel Defense」の実装\\n【ファイル】web_pet/pixel_defense.js\\n【要件】Canvas 8bitインベーダーゲーム、スコアをPOST /api/actionで保存"',
    '"nextQuestPrompt": "Please implement the following 5-minute microtask:\\n[Task] Phase L5 Secret Mini-Game \\"Pixel Defense\\" Implementation\\n[File] web_pet/pixel_defense.js\\n[Requirements] HTML5 Canvas 8-bit shooter; save high scores via POST /api/action"'
)

path.write_text(content, encoding="utf-8")
print(f"Successfully updated {path} ({len(content)} bytes)")
