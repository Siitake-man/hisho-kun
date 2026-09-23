# ネオ秘書くん システム設計書 (DESIGN_SPEC.md)

- **バージョン**: 1.5.4-dev (🛡️ P0-1 失効の実効性強化 ＋ 🛡️ P0-3 loopback 信頼の3条件化 ＋ 🛡️ P0-2 承認ポリシー構造パース化 ＆ 📲 Web Push 導入)
- **最終更新日時**: 2026-09-23 18:10 (🛡️ **P0-4 完了** §10.2.1 データ境界（暗号鍵・DB の %LOCALAPPDATA% 退避・安全移行・テスト隔離）／🛡️ **ID 53 完了** §10.2.1 端末台帳アイデンティティ（Serve 実IP採用・毒値排除・cleanup 失効限定）／P0-1〜P0-3 は 2026-09-22 v1.1.7)
- **アーキテクチャ方針**: 完全ローカル完結型 非ブロッキング並行システム (Tkinter Desktop Overlay × Mobile PWA × LangGraph Agent × Zero-Trust Local Bridge ＆ Cross-Platform Headless CI/CD)


---

## 1. プロジェクトの定義と基本思想

### コアミッション
「**席を外してもAIコーディングエージェントが止まらない**」。  
Claude Code, Cline, Codex, Cursor, Antigravity などの自律型コーディングエージェントが実行許可を求めて停止する痛点を、**眠っていた古いスマホを卓上承認リモコン＆相棒ペットに転生させてワンタップで解決**する。

### 🏛️ プロダクト三層構造アーキテクチャ（2026-09-13 確定）

| レイヤー | 役割 | 対象モジュール / 機能 | アーキテクチャ設計方針 |
|:---|:---|:---|:---|
| **コア (A)** | **主役・独自の痛点解決** | `api_agent_bridge.py`, `hisho_mcp_server.py`, `agent_watcher.py`, スマホ承認PWA | 🚀 **最優先投資**。エージェント承認の中継・失敗モード（タイムアウト/オフライン/再送）の堅牢化・Agent Adapterによる規格統一。 |
| **世界観 (B)** | **愛着装置・ブランド** | `character_manager.py`, `pet_animator.py`, `web_pet/`, 自作Mod基盤 | 🔨 **自作Mod基盤（フォルダ配置による動的登録）のみ最小実装**。キャラ量産はコミュニティへ開放。既存ミニゲーム・演出は現状凍結。 |
| **居場所 (C)** | **常駐の理由・背景** | `api_tasks.py`, `api_calendar.py`, `ui/calendar_window.py`, `database.py` | 🧊 **現状維持**。承認リモコンを机上に常駐させるための背景（TODO・習慣・iCal）。TickTick/Notionと戦わない。 |
| **保留 (Backlog)** | **開発リソース浪費の回避** | 音声対話 (Whisper/TTS), Google/LINE/Notion双方向同期, Life Coach L2/L3 | 💤 **完全凍結**。v1.xでは触らず、使われてから需要に応じて再評価。 |

### コア・コンセプト
1. **Approval Remote First (承認リモコン最優先):** PCでエージェントがコマンド承認待ちになった瞬間、スマホ画面にレッドパルスバナーとワンタップ承認ボタン（✅承認 / 🛑却下）を即時発火。コーヒー片手にノールックで開発を進められる。
2. **Local-Only & Least Privilege (ローカル完結・最小権限・承認必須):** 外部クラウドや第三者サーバーを経由せず、同一LAN/Tailscale内のみでBearerトークン暗号照合により直接通信。要求元と承認者のIP一致（自己承認）を禁止し、LAN攻撃によるRCEを構造遮断。
3. **Retro Modern & Desk Pet:** ドットフォント（DotGothic16）とブラウン系配色による温かみあるレトロUI。古いスマホの画面で呼吸し生活するペットが、無機質な開発作業に愛着と癒やしをもたらす。
4. **Zero-Configuration Entry:** QRコードをスマホのカメラで読み取るだけでペアリング完了。OAuth申請やクラウド登録を一切不要とする。

## 2. エージェント・アーキテクチャ (LangGraph & Tiered Multi-LLM Factory)

### 2.1 Tiered Multi-LLM Factory (2階層ハイブリッド推論基盤)
推論速度、コスト、プライバシー、高度なタスク解決を最適化する2段階ハイブリッドアーキテクチャ。
- **Tier 1 (内包ローカルLLM - llama-server / GGUF)**:
  - メモリ約600MB〜1GB、完全オフライン・0円・レイテンシ50ms即答。
  - 推奨プリセット: `MiniCPM5-1B`, `LFM2.5`, `Bonsai`, `Qwen2.5-0.5B/1.5B`, `Llama-3.2-1B`。
  - ユーザー独自GGUFのドラッグ＆ドロップ / ファイル指定適用に対応。
  - 役割: ペットの日常リアクション・エージェント見守り・1行タスクナレーション。
- **Tier 2 (クラウド高性能LLM)**:
  - **OpenCode GO (DeepSeek-V3 / R1)**: 爆速・高精度のクラウド推論（日常のメイン頭脳）
  - **Google Gemini (Gemini 2.5 Flash / Pro)**: クラウド標準バックエンド（大容量コンテキスト・マルチモーダル）
  - 役割: LangGraph自律推論、Googleカレンダー同期、DB横断検索、複雑な業務計画。
- **動的切り替え**: UI上の右クリックメニューおよび設定画面から即座に切り替え可能。

### 2.2 State Definition (Graphの状態)
エージェントは以下の状態を持ち回る。
- `messages`: 会話履歴 (HumanMessage, AIMessage, ToolMessage)
- `current_plan`: 現在実行中のタスク計画
- `user_approval`: 承認ステータス (Pending/Approved/Rejected)
- `vision_context`: 画面認識データ（スクリーンショット・OCR・UI解析結果）

### 2.3 MemorySaver (記憶の永続化)
最新のLangGraphに搭載された `MemorySaver` (Checkpointer) を用いて、会話の文脈を永続化する。

### 2.4 パーソナライズニュース ＆ 超軽量3行AIサマリ基盤
サジェストエンジン (`suggest_engine.py`) にて、完全無料で登録不要なニュース・検索エコシステムを提供する。
- **Zero-Config Search**: Google News RSS および DuckDuckGo / Jina Reader (`r.jina.ai`) による完全無料・APIキー不要のリアルタイムニュース・Webページ読込基盤 (`web_tools.py`)。
- **Keyword Personalization**: `suggest_config.json` にてユーザーごとの関心キーワード (`keywords`: 例 `["AI", "NW", "クラウド"]`) を保持し、設定UI (`ui/settings_window.py`) からカンマ区切りで自由編集・即時反映。
- **Hybrid 3-Line Summarizer**: 取得したニュース概要を `LLMFactory`（Tier 1/Tier 2）に投入し、「・ポイント1\n・ポイント2\n・ポイント3」の超軽量3行要約を動的生成。オフライン時やエラー時は句点分割ルールベースへ自動フォールバック。

### 2.5 外部カレンダー・SaaSマルチ中継Webhook連携基盤
Google公式OAuthの100名制限および審査負担をゼロにするため、ユーザー自身の外部ハブを介した疎結合連携基盤を提供する。
- **Universal Webhook Hub**: 設定画面（`ui/settings_window.py`）に「外部連携Webhook URL」の自由入力枠を新設。
- **Multi-Platform Support**:
  - **Zapier / IFTTT**: 非エンジニア向けノーコード連携（Googleカレンダー/Slack/Notionへイベントを即時中継）
  - **Make**: 月1,000回無料枠を活用した高機能JSONシナリオ中継
  - **GAS (Google Apps Script)**: 1クリックデプロイによる完全無料・無制限・審査不要のGoogleカレンダー直接双方向REST API
- **Event Dispatcher**: 予定作成・タスク完了・リマインド発生時に秘書くんから自動でWebhook JSONをディスパッチ。

### 2.6 Workflow (Nodes & Edges)
1.  **Planner Node:** ユーザーの入力や時間トリガー、画面状況からツール呼び出しを自律判断。
2.  **Executor Node (Tools):** DB操作、カレンダー、付箋、画面認識、外部エージェント連携を実行。
3.  **Human Review Node:** 重要な操作（削除、外部送信等）の前にユーザーの承認を待機。

### 2.7 非同期処理の堅牢化 (Async Native)
`asyncio` を用いて、UIの描画ループとLLM推論・ツール実行を完全に分離し、UIフリーズをゼロにする。

## 3. データベース設計 (SQLite)
Manusの設計をSQLite用に正規化して採用する。

### Table: events (予定)
- `id`: INTEGER PK
- `title`: TEXT
- `description`: TEXT
- `start_time`: INTEGER (Unix Timestamp ms)
- `end_time`: INTEGER (Unix Timestamp ms)
- `recurrence_type`: TEXT ('none', 'daily', 'weekly', 'monthly_date', etc.)
- `recurrence_rule`: JSON
- `category_id`: INTEGER FK
- `google_event_id`: TEXT

### Table: sticky_notes (付箋)
- `id`: INTEGER PK
- `content`: TEXT
- `color`: TEXT (Hex)
- `position_x`: INTEGER
- `position_y`: INTEGER
- `width`: INTEGER
- `height`: INTEGER
- `is_minimized`: BOOLEAN

### Table: categories (カテゴリ)
- `id`: INTEGER PK
- `name`: TEXT
- `color`: TEXT
- `icon`: TEXT

### Table: tasks (TODOタスク)
- `id`: INTEGER PK
- `title`: TEXT
- `description`: TEXT
- `due_date`: INTEGER (Unix Timestamp ms)
- `priority`: INTEGER (0: なし, 1: 低, 2: 中, 3: 高)
- `status`: TEXT ('inbox', 'todo', 'in_progress', 'completed')
- `parent_id`: INTEGER (サブタスク用)

### Table: user_insights (知識の宝庫 ユーザー長期知見テーブル - 新規追加)
- `id`: INTEGER PK
- `category`: TEXT ('Constraint': 制約, 'Preference': 好み, 'Habit': 習慣, 'Project': PJルール)
- `content`: TEXT (例: '平日夜は家族のケアサポートのため予定を入れない')
- `context_tags`: TEXT (例: 'schedule, family, time')
- `importance`: INTEGER (1〜5)
- `created_at`: INTEGER (Unix Timestamp ms)
- `updated_at`: INTEGER (Unix Timestamp ms)

## 4. UI/UXデザイン仕様 (ドット絵ペット常駐 ＆ レトロモダン)

### デザインテーマ
- **ペットビジュアル**: **ドット絵・レトロスプライトアニメーション**（待機・思考中・喜び・眠い等の状態に応じたリアクション）
- **配色:** Primary: `#A67B5B` (ブラウン) / BG: `#F5F5DC` (クリーム) / Text: `#4A3B32` (ダークブラウン)
- **フォント:** `DotGothic16` (ドット文字)
- **常駐挙動:**
  - 画面隅へのオートハイド（自動隠蔽）＆ マウスホバーでスライド出現
  - ドラッグ＆ドロップでデスクトップ上の自由な位置へ移動
  - 右クリックメニュー ＆ 吹き出し「⚙」ボタン（モデル切り替え、設定ダイアログ、カレンダー展開、付箋一覧）

### 画面構成
1. **Desktop Pet Window (PC側)**:
   - 透過ウィンドウ上のドット絵ペット ＆ 会話吹き出し ＆ 指示入力欄（340x430）。
   - 右クリックメニュー ＆ 「⚙」ボタンから手帳や設定を展開。
2. **Mobile Smart Cockpit (スマホ側 PWA / Desk Pet Companion)**:
   - 机に置いた専用端末としてのスマートコックピット。
   - **ヘッダー**: 遠くからでも見やすい特大デジタル時計 ＆ ポモドーロ集中タイマー（`🍅 25:00`）。
   - **メイン領域**: インテリジェント・サジェスト（直近予定・重要TODO・健康ケア・知見の15秒自動ローテーション）。
   - **ボトム機能バー**: ［📋 TODO手帳］［📅 予定一覧］［🖥️ PCペット呼出］［⚙ 設定］からオンデマンド展開。



## 5. 機能要件 (Tools & Engines)

### 5.1 Multi-LLM Factory & Model Presets
代表的かつコストパフォーマンスに優れたモデル群をプリセット提供。
- **OpenCode GO**:
  - `deepseek-chat` (DeepSeek-V3: 爆速・極低コスト・日常対話＆ツール呼び出し)
  - `deepseek-reasoner` (DeepSeek-R1: 複雑なタスク分解・思考プロセス)
- **Google Gemini**:
  - `gemini-2.5-flash` (高速・低コスト・100万トークン大容量コンテキスト)
  - `gemini-2.5-pro` (最高峰推論・アーキテクチャ検討)
- **LM Studio (Local)**:
  - `local-model` (完全オフライン・機密保護・ゼロコスト)

### 5.2 知識の宝庫 (Knowledge Vault) ユーザー知見蓄積エンジン (Long-Term Memory)
1. **知見の自動抽出**: 会話の中からユーザーの制約・好み・生活リズムを検知し、`user_insights` テーブルへ永続化。
2. **コンテキスト注入**: 推論時に重要度の高い知見（上位5件）をシステムプロンプトへ自動挿入。
3. **⚠️ 用語の境界 (2026-09-16 恒久)**: 本機能「知識の宝庫」は秘書くんアプリ内の `user_insights` ストアであり、
   Cline等の外部環境が提供する汎用エージェント記憶MCP「MentisDB」とは **別物** である（混同禁止）。
   2026-09-14 に旧呼称「MentisDB」から本呼称へ全面改名済み。旧ドキュメントに残る "MentisDB" は歴史記録。
   回帰防止テスト: `tests/test_terminology_boundary.py`。

### 5.3 Tools for Agent
- **Calendar & Task Manager**: `create_event_tool`, `get_upcoming_events_tool`, `create_task_tool`, `list_tasks_tool`, `complete_task_tool`
- **Sticky Note Manager**: `create_sticky_note_tool`
- **知識の宝庫 (Knowledge Vault) Long-Term Memory**: `remember_user_insight_tool`, `get_user_insights_tool`
- **Vision & Screen Recognition (MiniCPM型)**: `capture_screen_tool`, `analyze_screen_error_tool`
- **Proactive Health & Care**: `proactive_engine.py` による45分作業・夕方の自律声掛け
- **Google Workspace (Calendar & Gmail)**: `get_google_calendar_events_tool`, `create_google_calendar_event_tool`, `search_gmail_messages_tool`
- **iCalendar (.ics) Sync**: `export_calendar_ics_tool`（Google/Outlook対応）
- **MCP Extensibility**: 外部MCPサーバーから動的に取得された任意ツール群

### 5.4 MCP (Model Context Protocol) クライアント連携アーキテクチャ 🌟
Anthropic提唱の標準規格「MCP」クライアント機能を内蔵し、外部サービス（Notion, GitHub, Google Drive, Slack, Filesystem, Playwright 等）とプラグイン感覚で接続可能。
- **動的カスタム追加・削除UI**: 設定画面「⚙」から「➕ 新規追加」ダイアログで、コマンド（`npx`, `uvx`, `python` 等）と引数を自由に入力して即座にツールバインド可能。
- **設定永続化**: `mcp_config.json` にカスタムサーバー設定が自動保存され、次回起動時にも復元。
### 5.5 外部Agent監視 (Agent Monitoring) ＆ タスクナレーション (Task Narration) 🌟
MiniCPM-Petの秀逸な着眼点をネオ秘書くんのクリーンアーキテクチャで昇華した見守り機能。
1. **File Watcher による受動的ログ監視**:
   - Claude Code (`~/.claude/`), Cursor, Codex, Antigravity 等のログや出力を常時スキャン。
   - エージェントの状態を `Idle` / `Thinking` / `Coding` / `Waiting Approval` / `Success` / `Error` に分類し、ペットの感情・アニメーション（FSM）と即座に同期。
2. **双方向ノールック承認 (Agent Bridge)**:
   - `Waiting Approval` 発生時、ペット吹き出し ＆ DeskPet PWA（スマホ / Bluetoothイヤホン）へ即座にPush通知。
   - 画面タッチや物理ボタンでノールック承認（y/n）を実行。
3. **タスクナレーション (Task Narration)**:
   - セッション完了（`Success`）時、内包ローカルLLM（Tier 1）が変更差分を1行で要約し、ペットが吹き出しで音声的に発話。

## 6. スマートフォン専用コンパニオン連携（Desk Pet Device / PWA ＆ ローカル同期サーバー）

古いスマートフォン（Android / iOS）を机の傍らに置き、**「外付けスマートディスプレイ／相棒端末 ＆ AI承認コクピット (Agent Bridge Hub)」** として活用するアーキテクチャ。
- **PWAフロントエンド (`web_pet/`)**:
  - **画面占有ゼロ化（PC側ペット自動最小化）**:
    - スマホとのリンク確立時、PC画面上のペットウィンドウを自動で最小化／タスクトレイへ退避し、PC画面の作業領域を100%確保。
    - スマホ切断時、またはユーザーのワンクリックで即座にPC画面上へ復帰。
  - **スマホ画面完全最適化 (100dvh / No-Scroll PWA)**:
    - モバイルビューポート（`height: 100dvh; overflow: hidden;` / Safe Area Inset）に完全適合。
    - 余分なスクロールや余白を完全に排除し、ゲームボーイ／専用ガジェットのような一体感のあるハードウェアUIを実現。
    - ホーム画面追加（PWAインストール）により、アドレスバー無しのネイティブフルスクリーンアプリとして動作。
  - **ペットの生活シーンアニメーション（Life Motion System）**:
    - 単なる待機（Idle）だけでなく、時間帯やボスの作業状況に応じた多彩な生活シーンを描画：
      - 🛏️ **ベッドでゴロゴロ・すやすや睡眠**（夜間・放置時）
      - 📖 **本を読んだり勉強・タイピング**（集中ポモドーロ時）
      - 🏋️ **ダンベル筋トレ・体操**（リフレッシュ時）
      - 📺 **テレビ／ゲームでくつろぎ**（休憩時）
      - ☕ **コーヒー・お茶ブレイク**（声掛け時）
      - 🧹 **お部屋のお掃除・はたきがけ**
  - **キャラクタースキン ＆ 自作Mod取り込み基盤 [v1.0.0確定 ＆ v1.1.0設計]**:
    - 👔 **公式プリセット (2体)**:
      - **秘書くん (`hisho`)**: 8/15レトロドット絵（`assets/dot/hisho/` 16状態）
      - **カイル (`kyle`)**: 貝型PC風レトロキャラ（`assets/dot/kyle/` 16状態）
      - ※ 初回リリーススコープとして「秘書くん / カイル」の2体に厳選。
    - 🎨 **自作キャラMod基盤 (Custom Pet Skins / Modding - v1.1.0)**:
      - 開発者が自力でドット絵を描き続ける泥沼を脱却し、ユーザーやコミュニティが「自分の推しキャラ」を自由に動かせるオープンMod機構。
      - `assets/custom_pets/<chara_id>/` に `idle_1.png`, `happy_1.png` 等の命名規則で配置すると、`character_manager.py` が起動時に動的検知・登録。
      - PC設定画面およびスマホPWAのキャラ変更ドロップダウンに「カスタムキャラ」として即時反映。
  - **縦置き・横置きレスポンシブ [✅ 実装済み]**:
    - 縦置き (Portrait): ヘッダー（時計・ポモドーロ・常時ON・全画面）＋状況カード＋ドット絵ペット＋サジェストカード＋操作ドック。
    - 横置き (Landscape): `@media (orientation: landscape)` でペット左＋サジェスト右の2カラム化（説明文4行表示）。
  - **手帳モーダル [✅ 実装済み]**: 📅予定一覧 / 📝TODO（タップ完了）/ 🌱習慣（タップ達成・ストリーク表示）/ ⚙️設定（キャラ・テーマ・全画面・常時ON・PCペット呼び出し）を Glass Bottom Sheet で提供。
  - **常時画面ON [✅ captureStream 方式]**: HTTP環境では navigator.wakeLock が使えないため、Canvas再描画フレームを `captureStream(10)` で不可視videoへ流す「無限生配信」でOSスリープを阻止。
  - **双方向リンク死活監視 ＆ 呼び出しテスト**:
    - リアルタイムPing表示（`LINKED 15ms`）、PCからの遠隔呼び出し（Buzz振動）、スマホからのPingテスト。
- **PC側 ローカル同期サーバー (`local_sync_server.py`)**:
  - 待受ポート `SERVER_PORT`（`sync_config.py` が唯一の情報源・既定8765）で静的ファイル配信 ＆ `/api/status`, `/api/action`, `/api/link_status`, `/api/test_buzz` を提供。
  - **ローカル完結・最小権限・承認必須の3層防衛アーキテクチャ [✅ 実装済み ＆ 堅牢化]**:
    - **層1 (暗号認証・端末台帳)**: 起動時に256bit乱数トークンを生成し、`database.py` の `devices` テーブルで SHA-256 ハッシュ照合・個別失効・`last_seen` 更新。全APIで Bearer認証を強制（401拒否・定数時間比較）。同一LANであっても未認証GETは401拒否。
    - **層2 (ペアリング Fail-Closed)**: トークン配布API (`/api/auth/token`) は QR接続ダイアログ表示中（10分）かつループバック/LANのみ応答。
    - **層3 (要求元/承認者分離 ＆ RCE遮断)**: 承認要請API（ask/ask_input/notify）は localhost（127.0.0.1）接続のみ許可。さらに要求元IPと応答元IPの一致（自己承認）を403拒否し、LAN上からの悪意ある RCE チェーンを構造的に遮断。
    - 検証: `tests/test_sync_auth.py`, `tests/test_device_registry.py`, `tests/test_cors_hardening.py`。
  - **Agent Bridge Hub ＆ 遠隔承認パイプライン**:
    - Claude Code, Codex, Antigravity, Cursor, Aider 等のコーディングエージェントからのコマンド実行許可要請を受け付け、スマホへリアルタイム中継。
    - スマホ側での「承認 (Approve)」「拒否 (Reject)」「説明 (Explain)」の判定を即時レスポンス。
    - **Agent Adapter構想 ＆ 共通承認プロトコル (P0 / v1.1.0)**:
      - 共通DTO `AgentApprovalRequest` (agent_id, tool_name, command, cwd, risk_level, arguments) を定義。
      - Claude Code, Cline, Cursor, Codex, OpenCode のプロトコル差異をアダプター層で吸収し、「単一ツール連携」から「AI Agent承認プラットフォーム」へ昇格。
    - **Approval Policy（コマンド実行ポリシーエンジン - P0 / v1.1.0)**:
      - 危険度に応じた3段階自動判定：
        1. 🟢 **Auto-Allow**: `npm test`, `git status`, 読取専用コマンドは自動即時許可（認知負荷削減）
        2. 🟡 **Prompt**: `npm install`, ファイル編集, `git commit` はスマホワンタップ承認
        3. 🔴 **Strict / Block**: `rm -rf`, `git push --force`, `drop table`, 秘密鍵・トークン外部送信はスマホ大画面での警告＆二重確認
      - **🛡️ 構造パース堅牢化 (P0-2 / 2026-09-22)**: 複合コマンド検知を `;` `&&` `||` の**部分文字列判定**から
        `shlex`（posix + `punctuation_chars`）による**シェル演算子トークンの構造判定**へ移行。
        - パイプ（`|`）・リダイレクト（`>` `>>` `<`）・バックグラウンド（`&`）・チェイン・
          **コマンド置換／変数展開**（`$( )`・バッククォート・`%VAR%`・`$env:`・`${}`）・改行による複合は 🟡 **Prompt** へ格上げ。
        - パイプ先インタプリタ（sh/bash/pwsh/python 等）・`xargs`＋インタプリタ・`find -exec/-delete/-fprint`・
          `eval`/`Invoke-Expression`・`git (diff|log|show) --output`・`git branch -D`/`tag -d`/`remote add|remove`・
          `rm --recursive --force` 系は 🔴 **Strict**（トークン＝非クォート語で判定し、引用符内文字列の誤検知を防止）。
        - **shlex の既定値の罠を封鎖**: ①`commenters='#'` は語中でも以降を読み捨てる → `commenters=""` を必須化
          ②連続する句読点は1トークンに連結（`>|` `&>` `&>>`）→「句読点のみのトークン＝演算子ラン」で判定
          ③引用符が語全体を覆う純粋演算子（`echo ">"`）は保守的に Prompt（混在語 `echo "a;b"` は Auto-Allow を維持）。
        - 構文解析失敗（閉じない引用符等）は **Fail-Closed で Prompt**（warning ログで可視化）。
        - 検証: `tests/test_approval_policy.py`（既存回帰）＋ `tests/test_p0_2_approval_policy_structural.py`（19テスト＋40 subtests）。
    - **Audit Log（承認監査ログ基盤 - P0 / v1.1.0)**:
      - すべての承認要請・判定結果・タイムスタンプ・実行エージェント名を SQLite `approval_audit_logs` に記録し、改ざん防止・後日監査を可能にする。
    - **承認失敗モード堅牢化 (v1.1.0)**: エージェント側のタイムアウト時のスマホUI追従、Wi-Fi瞬断時の冪等リトライ、PWAスリープ復帰時の再同期。
  - **オフライン完結**: Wi-Fiなし・外出先でもBluetooth PAN / PCモバイルホットスポットで100%動作。

### 6.0 デスクトップGUIアーキテクチャの戦略的判断（Grok指摘: Tkinter限界への対応パス ADR）
- **背景 (Why)**:
  - Grokのブラインドレビューにおいて「Tkinterは古く、モダンなUI表現やクロスプラットフォーム（Mac/Linux）での透過・アニメーション制御に限界がある」旨の指摘が提起された。
- **アーキテクチャ判断 (What & How)**:
  1. **短期（v1.x: 役割の引き算とスマホ逃がし）**:
     - PCデスクトップ側のTkinter画面は「最小限の透過キャラ常駐・通知・トレイ」に徹する。
     - スプリング物理、リッチなCSS装飾、TODO・習慣・ミニゲームなどの操作面は**Web標準技術（HTML/CSS/JSによるスマホPWA）へ全面移管**。
     - スマホリンク確立時はPC側ペットを自動非表示（`withdraw`）とするため、Tkinterの描画限界がユーザー体験を阻害しない。
  2. **中長期（v2.0: 重厚Electronを避けた移行パス ADR）**:
     - 150MB超のランタイムを要求するElectronへの全面書換（リソース浪費の罠）は避け、超軽量・高速な **Tauri (Rust + Web)**、または既存Python資産をそのまま活かせる **pywebview** を移行候補とする。
     - これにより、既にPWAとして完成しているフロントエンド資産（`web_pet/`）をそのままPC画面としてラップ再利用可能にする。

### 6.1 PC統合手帳：カレンダー3モード描画 [✅ 実装済み 2026-08-25]
- `ui/calendar_window.py` の予定タブを Canvas 描画エンジン化:
  - **月間**: 日曜始まり6週グリッド。各日に予定概要をパステル色ブロックで最大3件表示（+N で残件数）。今日=黄ハイライト、過去予定=グレー化
  - **週間**: 7日 × 時間軸(6:00-24:00) のガントチャート型タイムテーブル。現在時刻に赤線
  - **日間**: 0-24時の詳細タイムテーブル（スクロール/ホイール対応・現在時刻 or 最初の予定へ自動スクロール）
  - ◀▶ で期間移動、「今日」で復帰。日付セル/予定ブロックのタップで日間ビューへドリルダウン。**日間ビューのブロックタップで詳細ポップアップ**（全文タイトル・時刻・説明）
- **データ窓の設計 [重要]**: `database.get_events_between()` を新設し、手帳は**過去120日〜未来200日**（`EVENT_RANGE_PAST_DAYS` / `EVENT_RANGE_FUTURE_DAYS` 定数）の窓で取得する。従来の `get_upcoming_events()` は「今日以降」限定のため、未来予定が0件だと同期成功済みでも常に「予定はありません」になる罠があった（2026-08-25 実際に発生・解消）
- **同期状態フッター**: 「🔄 Googleカレンダー最終同期: XX:XX ／ 手帳登録 N 件」を予定タブ下部に常時表示
- **同期後自動リフレッシュ**: 30分定期同期（main.py）・設定画面の手動同期（settings_window.py）の成功後、手帳が開いていれば `gui.refresh_calendar_if_open()` が post_action 経由で即時再描画される
- **品質**: `tests/test_calendar_ui_smoke.py`（unittest 5シナリオ）。row→Event 変換は共通ヘルパー `_rows_to_events()` に集約（重複排除）

### 6.2 PWA通知・承認UX強化 [✅ 実装済み 2026-08-25]
- **高視認バナー**: 承認要請=不透明レッドグラデ＋白文字(タイトル15px)＋強グロー＋パルス点滅。質問=シアン/完了=グリーンのグラデ
- **チャイム＆振動**: Web Audio による2音チャイム（承認要請は4連打・完了/質問は2連打）＋ vibrate パターン。ブラウザ自動再生制限対策の `unlockAudio()`（pointerdown/touchstart/visibilitychange で AudioContext 解錠）。チャイムは発火のたびに前回タイマーを解除
- **ワンタップ承認**: バナー直下に「✅承認 / 🛑却下」大ボタンを常設（ネイティブ confirm() は廃止）。バナー本体タップでコマンド全文＋大ボタン付き承認シート（Glass Bottom Sheet）を表示
- **イヤホン承認（ノールック）**: MediaSession API の play/pause/nexttrack メディアキーを「承認」アクションに割り当て。Bluetoothイヤホンの再生ボタンで承認完了。ユーザーが音声再生中のNoSleep videoを流すトリックを利用
- **承認結果のフィードバック**: 承認=上昇2音(880→1245Hz)／却下=下降2音(660→440Hz)の音色差＋PCペットへの `pet_reaction` アクション（承認=celebrate・却下=care）で双方の端末がリアクション
- Service Worker キャッシュ **v3.2**（変更の実機配信を保証）

### 6.3 カレンダ複数アカウント同期 [✅ 実装済み 2026-08-25]
- **DB設計**: `calendar_sources` テーブル（id/name/color/url/enabled/last_sync）＋ `events.source_id` カラム（ALTER TABLE マイグレーションで既存データを自動移行）
- **同期エンジン**: `ics_tools.sync_calendar_source()` でソース単位の同期。`sync_all_calendar_sources()` で有効な全ソースを順次実行。**取り込み窓フィルタ**（`ICAL_IMPORT_PAST_DAYS=120` / `ICAL_IMPORT_FUTURE_DAYS=730`）でDB肥大化を防止
- **設定UI**: 購読ソース一覧（☐有効チェック・色ボタンで識別色切替・名前編集・URL編集・🔄個別同期・🗑削除）＋「＋ 購読を追加」ボタン。色は7色パレットから自動割当
- **手帳UI**: 各予定ブロックにソース色の縁取り（左3px線）。フッターにソース凡例（色見本＋名前）＋最終同期時刻を表示。ソースをOFFにするとその予定は手帳から消える（同期も停止）
- **スマホPet.js**: 予定一覧モーダルにソース名表示
- **後方互換**: `.env` のレガシー `GOOGLE_CALENDAR_ICAL_URL` は初回起動時に `ensure_default_calendar_source()` が自動移行。`sync_calendar_from_ical_url()` は全ソース同期のエイリアスとして維持
- **品質**: `tests/test_calendar_sources.py`（6シナリオ：CRUD+トグル+同期時刻+カスケード削除）全パス

### 6.4 外出先接続（Tailscale VPN）対応 [✅ 実装済み 2026-08-25]
- **設定画面**: 外部ツールタブに「外出先接続 (Tailscale VPN)」カード追加。ホスト名入力＋保存ボタン
- **QRダイアログ**: `TAILSCALE_HOSTNAME` が設定済みの場合、LAN QRコードの下に「🌐 外出先接続 (Tailscale)」URL分を追加表示。コピーボタン付き
- **ガイド**: `docs/guides/TAILSCALE_SETUP.md` 新設（Tailscaleインストール→`tailscale serve <SERVER_PORT>`→ホスト名登録までの手順を記載）
- 実機確認は「カフェ環境でのE2Eテスト」として後工程に記録

## 7. Google Workspace (Googleカレンダー ＆ Gmail) ダイレクト連携 🌟
- **モジュール**: `google_workspace_tools.py`
- **OAuth2 Token Flow**: `google_credentials.json` をプロジェクト直下に配置するだけで、Google公式APIを通じたスケジュール参照・登録、および未読メール検索・要約が可能。
- **セーフフォールバック**: 認証ファイル未配置時はローカル手帳およびiCalendarエクスポートへ自動フォールバック。
- **秘密iCal URL 連携 [✅ 実装済み 2026-08-25]**: `ics_tools.py` の `sync_calendar_from_ical_url()` により、Googleカレンダーの「予定の取得用の秘密のアドレス (iCal)」を貼るだけで**OAuth・APIキー・クライアントシークレット不要**で予定を読み取り専用同期（30分間隔自動＋手動ボタン）。Google由来予定は `google_event_id` で管理し重複なし。※設定画面に取得手順・読み取り専用の注意書きを表示。

## 8. 最新マスターロードマップ
1. **Phase A〜E: デスクトップ常駐MVP・LangGraph・知識の宝庫・手帳・PWA・MCP自動登録 [✅ 完了]**
2. **Phase F: ゲーム級UX ＆ アニメーション基盤（ポモドーロネオン円形ゲージ・集中時の闘気/炎・猛烈タイピングエフェクト） [🚧 現在着手]**
3. **Phase G: 内包型ローカルLLM推論基盤 ＆ モデル管理UI（GGUF / llama-server サイドカー ＆ カスタムGGUFドラッグ＆ドロップ） [🔲 次期予定]**
4. **Phase H: 外部Agentログ監視（File Watcher）＆ 状態連動FSM ＆ タスクナレーション（Task Narration） [🔲 次期予定]**
5. **Phase I: キャラクタースキンシステム ＆ 習慣トラッカー [🔲 将来予定]**
6. **Phase J: 配布パッケージング（GitHub公開 ＆ PyInstaller exe ハイブリッド） [🚧 方針決定済み]**:
   - **方式**: ハイブリッド（GitHub公開 + PyInstaller シングルexe）。両方同時リリース。
   - **LLMモデル**: ランタイム非同梱。ユーザーが設定画面の「モデル管理」からダウンロードガイドに従って配置する方式。
   - **README充実**: スクリーンショット＋バッジ＋機能一覧（GitHub Pages/ Wikiは後日対応）。
   - **ヘルプ/チュートリアル**: 設定画面に「使い方ガイド」タブを追加（初回起動オンボーディングツアー含む）。
   - **exe化のポイント**: 
     - Python + 全コード + 依存DLLを1つのexeにまとめる（PyInstaller）。
     - アセット（dot絵・画像）はexe外に保持するか埋め込むか検討。
     - ウイルス誤検知対策としてコード署名証明書の取得を検討。
   - **決定日**: 2026-08-26（ボスとの合意事項）
7. **Phase K: オンボーディング強化（使い方ガイド・初回ツアー刷新） [✅ 実装済み 2026-08-27]**: ガイドカード+ハイライトリング方式（本書 6.5 参照）。
8. **Phase L: バズ・相棒MVP [🔲 計画確定 2026-08-28]**: 本書 9 章参照（マスタードキュメント反映）。

### 6.5 初回起動ツアーUI: ガイドカード + ハイライトリング方式 [✅ 実装済み 2026-08-27]

**問題**: 従来のフルスクリーン半透明オーバーレイ（`Toplevel + overrideredirect + -alpha 0.8`）は Windows Layered Window の描画破綻により「ガイドが全然見えない」状態だった。alpha値の調整やボタン拡大では解決せず、根治療法が必要。

**解決**: alpha属性を**一切使わない**以下2層構成に全面刷新。

#### ガイドカード（不透明 Toplevel）
- **サイズ**: 380×300px、`overrideredirect(True)` + `-topmost`
- **構造**: ヘッダー（`#F5F5DC`背景、タイトル + カウンター + ✕スキップ）→ セパレーター → テキスト本文（`tk.Text`、wrap=WORD、`#FFF8F0`背景）→ ボタン行（◀戻る / 次へ▶）
- **配色**: アプリ全体のレトロモダンに統合（茶系 `#4A3B32` / `#8B7355` / `#A67B5B`、アクセント `#5B8A9B`）

#### ハイライトリング（マゼンタ透過）
- **技法**: メインGUIで実績のある `-transparentcolor`（`#FF00FF` 抜き）を使用
- **外観**: Canvas 上に金色（`#FFD700`）外枠4px + オレンジ（`#FFA500`）内枠2pxの二重矩形
- **サイズ**: ターゲットウィジェット矩形 + 12px余白

#### スマート配置（_place_tour_card_near）
- ターゲット矩形の上側に十分スペースがあれば上、なければ下
- 画面端クランプ（10pxマージン）で常に可視を保証
- ターゲット矩形は `_get_tour_target_rect()` で動的計算（ウィンドウ移動追従）

#### 設計原則
- `tour_engine.py`（データ層・状態機械）は**一切変更しない**
- `_on_tour_step` / `_start_tour` / `_on_tour_complete` の呼び出し側インターフェースは互換維持
- フルスクリーン暗転演出は廃止 → 代わりにユーザー操作を妨げないオンボーディングに



## 9. Phase L: バズ・相棒MVP設計（2026-08-28 Genspark壁打ちマスタードキュメント反映）

> 出典: `docs/specs/秘書くんマスタードキュメント.md` v1.0。判断基準は「初見3秒で好きになるフック」「7日後も机の上に残る理由」の2軸。

### 9.1 retro_dolphin（レトロ案内精霊）キャラ追加
- **追加先**: `character_manager.py` の `CHARACTERS_DATA` に `retro_dolphin` を追加（既存キャラID: `hisho` / `kinoko` / `seal`）。人格は `get_character_system_prompt()` 経由で注入（芝居がかった丁寧口調）
- **スプライト**: `assets/retro_dolphin/` に idle / appear / offended / revive の4状態（最低ライン）
- **役割**: 相棒寄りのナビゲーター / 小ネタ担当 / イースターエッグ誘発役。代表台詞: 「消去依頼を検知しました。……ですが、案内業務は継続します。」
- **制約**: Microsoftキャラの複製禁止。名前・輪郭・小物・台詞・画像はすべてオリジナル

### 9.2 「お前を消す方法」イベント状態機械
- **トリガー**: PC入力欄 または PWAテキスト入力で削除系ワード（お前を消す方法 / 消し方 / 邪魔 / 消えて）を検知。明示ワード一致＋類義語スコア判定
- **反応段階**: レベル1 とぼけ（吹き出しのみ）→ レベル2 本気反応（暗転・中央移動・パーティクル・復活台詞）→ レベル3 グリッチ復活（ノイズ・再構築・裏人格台詞）→ レベル4 ミニゲーム解放
- **発火段階**: 1日1回目=軽反応 / 3回目=重演出 / 5回目=解放
- **演出タイムライン**: 暗転300ms → キャラ中央移動 → 0.4秒の溜め → 放射パーティクル2段 → 3フレームグリッチ → 0.8秒で再構築 → 復活台詞
- **永続化キー**: `easter_delete_attempt_count` / `last_easter_trigger_at` / `secret_game_unlocked`（`database.py` または `character_config.json`）

### 9.3 PWA側モジュール構成（疎結合）
- `web_pet/easter_eggs.js`（新規）: トリガー検知・状態機械・演出をpet.jsから分離
- `web_pet/minigame_pixel_defense.js`（新規）: 固定砲台シュート。本体と疎結合・削除可能構造。5分未満・終了後は本編へ復帰
- **低スペ端末配慮**: 演出は軽量設計＋スキップ設定を必須化（古いスマホ活用がコンセプトのため）

### 9.4 朝会 / 終礼モード
- **朝会**: 今日の予定のざっくり確認＋タスク3件までの整理＋「今日は何から片づける？」のひとこと
- **終礼**: やったことの短い振り返り＋承認処理件数＋「今日はここまで進んだね」
- **設計制約**: ロードマップ 7.8「朝の挨拶・日次ブリーフィング」と統合実装。1分以内。ガチな業務日報にしない

### 9.5 音声入力導線 ＆ 機能解放UI（地ならし）
- **音声入力**: 「話しかける」ボタン配置のみ。録音はスマホ、Whisper等の重い処理はPC側で受ける（PC本拠地主義の固定）。本実装は B20
- **Google予定追加**: 「将来解放される能力」としてのロック表示。BYO認証（ユーザー自身のClient ID）前提のオンボーディング導線。本実装は B19
- **機能解放UI**: 未解放機能は「ロック」表示＋「3分で設定できます」形式の導線。Client ID読み込み・Whisper有効化はPC側設定画面から

### 9.6 直近Non-Goals
- 多言語展開 / ミニゲーム複数本展開 / 全部入り化 / Google OAuth本実装の全面公開 / ネイティブアプリ化
- 将来バックログ B01〜B22 は「docs/specs/秘書くんマスタードキュメント.md」および機能ロードマップ 12章に保存。明示指示なしに現行スプリントへ混入させない
### 9.7 実装レビュー決定事項（2026-08-28 レビュー採用）

- **トリガー検知仕様の修正（誤爆対策）**: 主判定 = フレーズレベル一致（「お前を消す」「君を削除する」等、2人称＋消去系動詞の直接攻撃）。「邪魔」「消えて」等の単語一致は補助スコアに格下げ。**操作意図ホワイトリスト**: タスク・予定・付箋の削除を意図する正当なコマンド（「タスクを消して」等）はイベント発火から除外する
- **発火カウンタの2本立て**: 累積 `easter_delete_attempt_count`（5回到達で `secret_game_unlocked`）＋ 日次 `easter_delete_daily_count`（1回目=軽反応 / 3回目=重演出）。`last_easter_trigger_at` で日跨ぎを検知し日次カウンタをリセット
- **L0 アセット生成スプリント（L1の前置き）**: `docs/CHARACTER_PROMPTS_SPEC.md` と `tools/` 配下の生成スクリプトで retro_dolphin スプライト（4状態）の品質検証を行い、既存ドット絵テイストとの整合を合格させてから L1 本体着手。根拠: ドット絵背景シーンのクオリティ不足による廃止（2026-08-26）という前例があるため、アセットリスクを先行解消する
- **Phase L 成功基準（観測可能ゴール）**: (a) 30秒のデモ動画が撮影できる (b) 消す方法イベントを見た第三者から「何これ好き」クラスの反応を得る (c) スマホが7日間机の上に設置され続ける（手動観測）
- **リリース順序（次回判断事項）**: 案A = Phase M（v1.0.0 公開）を先行し Phase L を v1.1「バズアップデート」として投入 / 案B = L1〜L3 を先行実装し v1.0.0 に内包。案A = 確実な積み上げ、案B = 初見インパクト最大化


## 10. 集中開発4サイクル＆セキュリティ堅牢化アーキテクチャ（2026-09-06 実装反映）

### 10.1 PCタスクトレイ常駐マネージャー (`ui/system_tray.py`)
- **アーキテクチャ**: `pystray` + `PIL` による Windows タスクトレイ完全常駐。
- **スレッドセーフディスパッチ**: Tkinter メインループをブロックしないよう、`pystray` は独立デーモンスレッドで稼働。トレイ右クリック（ペット表示、非表示、設定、手帳、QR、終了）からの GUI 操作はすべて `gui.post_action()` 経由で Tkinter メインスレッドへディスパッチ。
- **ペット非表示時の生存性**: デスクトップペットを非表示にしてもアプリは終了せず、タスクトレイからいつでも即時呼び出し・設定変更が可能。

### 10.2 ゼロトラスト端末台帳 ＆ 認証 Seam (`database.py` & `local_sync_server.py`)
- **端末台帳スキーマ (`devices` テーブル)**:
  - `id`: デバイスID（自動採番）
  - `device_name`: 端末名（User-Agent より iPhone, iPad, Android端末, Mac, Windows PC を自動推定）
  - `token_hash`: Bearer トークンの SHA-256 ハッシュ文字列（平文トークンは DB に一切保存しない）
  - `ip_address`: 最終接続元IP
  - `user_agent`: クライアント識別子
  - `created_at` / `last_seen`: 登録日時および最終通信日時（Unixミリ秒）
  - `is_revoked`: 個別失効フラグ（0: 有効, 1: 失効）
- **認証・認可フロー (`_check_auth`) — 🛡️ P0-1 / P0-3 改定 (2026-09-22 / v1.1.7)**:
  1. Bearer トークンを抽出し、`SyncTokenManager` でマスタートークン（PCマスターキー）/ loopback 専用トークン / 個別トークン（QRペアリング配布）を判定する。
  2. **マスタートークンは信頼できる loopback 専用**（Agent Bridge・MCPサーバー）。非ループバックからの提示は台帳照合を必須とし、**未登録または照合例外は 401 Fail-Closed**（漏洩済みマスターキーの実効無効化 = A案 / 2026-09-22 ボス承認）。
  3. **loopback 専用トークン（PC内ブラウザ用 / P0-3）** はプロセス内生成で台帳に登録せず、`/api/auth/token` の loopback 分岐のみが配布する。**信頼できる loopback 以外では 401**（窃取しても Serve/LAN からは使えない）。**マスター鍵は HTTP で一切配布しない**。
  4. 個別トークンは SHA-256 ハッシュで `database.verify_device_token` を照会し、`is_revoked == 1`（失効済み）は即座に **403 Forbidden** で通信遮断。
  5. 有効端末は `touch_device_last_seen` で接続日時とIPを自動更新。**照合例外は 401 Fail-Closed**（warning ログで可視化。旧「Fail-Safe で認証継続」は失効判定の蒸発を招くため廃止）。
  6. **認証経路は台帳へ書き込まない（読み取り専用）**: `sync_device_session` は未登録資格情報を自動登録せず `None` を返す。資格情報の登録・再束縛は**人間承認を伴うペアリング経路のみ**（`issue_device_token` → `register_device(reuse_identity=True)`）。
  7. `GET /api/status` のレスポンスへ同期トークン（マスターキー）を同梱しない。DTO 境界 `validate_status_payload` の deny-list が再混入を除去し ERROR ログを残す（多層防御）。
- **loopback 信頼の3条件 (P0-3 / 2026-09-22) — `_is_trusted_loopback(client_ip, host_header, headers)`**:
  1. TCPピアが loopback（`127.0.0.1` / `::1`）
  2. プロキシヘッダ（`X-Forwarded-For` / `Forwarded` / `X-Real-IP`）が**無い**
  3. **`Host` ヘッダが loopback 名**（`localhost` / `127.0.0.1` / `::1`。ポート付き・IPv6 リテラル対応、Host 無しは Fail-Closed）
  - **Tailscale Serve の識別子**: Serve は TCPピアを 127.0.0.1 に中継するが `Host` は `*.ts.net` のまま届くため、条件3で「外部端末」と正しく分類され、ペアリング開放 + 人間承認 + 個別トークンの対象になる（失効・監査の対象にもなる）。
  - **DNS Rebinding の遮断**: 攻撃者ドメインの `Host` は条件3を満たさず loopback 信頼が成立しない（`/api/devices/restore` 等の管理APIは遮断）。
  - 適用箇所: `_check_auth` / `_handle_auth_token` / `_dispatch_get_devices` / `do_GET`(トークン無し閲覧) / `_check_webhook_auth` / `AGENT_ONLY_PATHS` / devices revoke・restore / agent activity。
- **失効の不変条件 (AD-3 / 2026-09-22)**:
  - **失効解除は `restore_device()` のみ**（`is_revoked = 0` を書ける関数は同関数ただ1つ。`tests/test_p0_sync_token_leak_and_revocation.py` のソース凍結テストで機械的に保証）。
  - **人間承認済み再ペアリング = 明示的な復帰操作**: `_handle_auth_token` は承認ダイアログ許可後にのみ `restore_device` を呼び、監査ログ `source="pairing"`（`client_ip` 付き）へ記録する。復帰失敗時は失効を維持し warning を残す（UI の嘘を作らない）。
  - **失効は端末識別単位で実効**: 失効端末は個別トークン・マスタートークンのいずれを提示しても拒絶される。
- **残余リスク（バックログ起票済み / 機能ロードマップ §13.19）**: ① Tailscale Serve 経由の `client_ip` 同一性（P0-3: トークン種別ベース信頼設計）② `Host` ヘッダー未検証（DNS Rebinding・ID 47）③ 失効×復帰レース・ペアリング600秒窓・403自動再ペアリング（ID 48）④ 承認1クリック横取り・行マッチ属性依存（ID 50）⑤ UI暗黙削除・DTO deny-list 浅さ・Webhook Fail-Open（ID 51）⑥ `.sync_token` 書込失敗時の旧キー復活。

### 10.2.1 データ境界（暗号鍵・DB の非同期領域化）と端末台帳アイデンティティ (P0-4 / ID 53 / 2026-09-23)

- **データ境界 (ADR-2 実装)**: 暗号鍵・DB・マスタートークン・自動バックアップは `%LOCALAPPDATA%\NeoHisho`（`app_paths.get_data_root()`／env `NEO_HISHO_DATA_DIR` で上書き可）のみに配置する。`storage.connection.resolve_db_path` / `resolve_backups_dir` が**単一チョークポイント**として既定相対名（大文字小文字・冗長相対表記を同一視）をデータルートへ解決し、100超の呼び出し元は無改修で到達する。**クラウド同期フォルダ配下のデータルートは Fail-Closed で拒否**（ADR-2 違反）。
- **安全移行 (`app_paths.migrate_legacy_data`)**: SQLite Online Backup API（WAL 込みの一貫スナップショット）→ `PRAGMA quick_check` → 一意名 `*.migrating` → 本採用（`os.replace`）。旧ファイルは `migration_archive/<timestamp>/` へ**退避（移動・削除しない）**。`-wal`/`-shm` は本体と運命共同体（オール・オア・ナッシング）。移行先既存時は上書きせず、残存旧DBの退避を再試行し失敗時は「機密残存」を ERROR で明示。起動時配線: **`main.py` のみ（データ所有者）**。`hisho_mcp_server.py` は**移行せず警告のみ**（`warn_if_legacy_data_pending()`）＝アプリ稼働中の移行は「アプリは旧DB・クライアントは新DB」の**DB分裂**を生むため、クライアントは旧配置フォールバックで一貫して旧DBを使用する。
- **テスト隔離（障害からの学び）**: 2026-09-23、旧配置フォールバックが `NEO_HISHO_DATA_DIR` 上書きを無視したため pytest が**本番台帳へ端末行を作成**する障害が発生（「AIが作業中に承認要求が来る」の正体）。**データルート上書き時は旧配置フォールバックを無効化**し、`tests/conftest.py` が「既定DBパスがデータルート外へ解決したら即失敗」を全テストへ強制する。実測: 修正後の全回帰894件で本番DBへの新規書込みゼロ。
- **端末台帳アイデンティティ (ID 53)**: 中継経由（Tailscale Serve 等＝TCPピア loopback かつ loopback 信頼3条件の不成立）では `X-Forwarded-For` の**単一・非loopback・有効IPのみ**を実IPとして採用し、台帳登録・監査 actor・`last_seen` 更新・**レートリミットのキー**に使用する。XFF 欠落/複数/不正/loopback値は `None`（IP不明）とし、**毒値 127.0.0.1 を台帳へ書かない**。IP不明時も `reuse_identity`（人間承認済みペアリング経路限定）が (端末名, UA) で同一端末を再利用し、行の増殖を防ぐ。
- **台帳の保守性**: `cleanup_loopback_devices` は**失効済み行のみ**を物理削除（有効資格情報の即死を構造的に防止）し、一覧表示からの自動呼び出しは撤去。中継以前の残存ループバック行は「⚠️ 中継以前の残存行」として表示し失効・削除できる（不可視の有効資格情報を残さない）。非ブラウザUA（Python クライアント等）は「⚠️ 非ブラウザ端末」と正直に表示する。
- **端末台帳アイデンティティ (ID 50 / 2026-09-23)**: PWA が `crypto.randomUUID()`（非セキュアコンテキストでは `getRandomValues` ベースの UUIDv4）で生成し localStorage に永続化した **端末自己生成UUID**（MACの代替）を `X-Device-UUID` ヘッダで申告し、`devices.device_uuid`（UNIQUE 索引・NULL 可）に保存する。`register_device` は **UUID 一致を最優先**で行を再利用し、フォールバック（IP+名前 → 名前+UA）は **`device_uuid IS NULL` の行に限定**する（UUID 記名済み行はヘッダを外したクライアントからも乗っ取れない＝ID 50 の構造排除。旧 NULL 行は採用して UUID を束縛＝移行ゾンビなし）。UUID は**認証の根拠にはならない**（束縛は人間承認済みペアリング経路のみ＝AD-3 不変）。端末一覧は「端末ID: xxxxxxxx…」を表示。
- **残余（バックログ）**: ① `.env`（APIキー）は依然リポジトリ配置（ID 56）② OneDrive クラウド版歴に残る旧DB（VAPID PEM）はローカル退避では消えない（ボス手動パージ案内）③ Link Monitor / ApiContext の IP は TCPピアのままで台帳IPと不整合（監査統一は別チケット）④ **localStorage のオリジン分離**により Serve/LAN 併用時は UUID が別々（推奨運用: Tailscale に一本化）⑤ 並列ペアリングの UUID 競合は UNIQUE 索引＋先着採用で吸収。
- **管理用エンドポイント**:
  - `GET /api/devices`: 登録済み端末一覧（認証必須）。
  - `POST /api/devices/revoke`: 端末失効（管理者・同一PC/ループバックからの呼び出しに限定し、外部クライアントからの他端末キック DoS を完全防止）。

### 10.3 自己治癒ウォッチドッグの独立モジュール化 (`server_watchdog.py`)
- **Seam 設計 (Deep Module)**:
  - サーバーの監視・再起動ループを `LocalSyncServer` から完全に切り離し、`probe_fn: Callable[[], bool]` と `restart_fn: Callable[[], bool]` の2つのコールバックのみを受け取る小さなインターフェース（`ServerWatchdog`）に集約。
- **ヒステリシスと指数バックオフ**:
  - 連続失敗カウント（`failure_threshold`）により、一時的な通信揺らぎでの過剰再起動を防止。
  - 再起動失敗時は `2^n` 秒（最大 `max_backoff` 秒）の指数バックオフを適用し、ソケットポート競合時の CPU 浪費や過剰ループを防止。
- **終端契約 (Terminal Contract)**:
  - `stop()` 呼び出し時は直ちに `_stop_event` をセットしてスレッドを安全終了させ、ゾンビ再起動（シャットダウン中にサーバーが勝手に再バインドする事故）を 100% 遮断。

### 10.4 スマホPWA 予定リマインダー通知基盤 (`web_pet/`)
- **リマインダー強調表示**:
  - 予定の 10 分前および開始時刻に、スマホ画面に紫系バナー（`.reminder`）を展開。
  - エージェント承認要請（黄色）やタスク完了（緑）と明確に差別化された認知誘導（Cognitive Guidance）を提供。
- **触覚・聴覚フィードバック**:
  - Web Audio API による専用チャイム音の再生。
  - ナビゲーター Vibration API によるパルスバイブレーション（`[200, 100, 200]`）。
  - デスクトップペット・スマホペットの表情変化（`alarm_ask`）の同期発火。

### 10.5 音声通知の安全トグル設定 (`ui/settings_window.py`)
- **PC音声読み上げの環境変数制御**:
  - `VOICE_NARRATION_ENABLED` を `.env` で永続管理し、設定画面 Tab 2 からワンタップでトグル可能。
  - オフィスや家族環境での意図しない発話事故を完全に防止。

### 10.6 ゼロトラスト脆弱性P0即時封鎖 ＆ 終礼日報P1バグ是正（2026-09-18 実装反映）
- **P0-1 スマホ全解除時の一括失効 (`storage/device_repo.py`, `local_sync_server.py`)**:
  - `SyncTokenManager.regenerate()` 実行時に `database.revoke_all_devices()` を自律的に同期実行。
  - これにより、マスタトークン再生成（全解除）と同時にDB上の個別端末レコードも一括で `is_revoked = 1` に失効され、旧個別トークンによる不正通信を完全遮断。
- **P0-2 QRペアリングのワンタイム・Fail-Closed化 (`local_sync_server.py`)**:
  - `_handle_auth_token()` において、正常に個別トークンを発行した直後に `tm.close_pairing()` を呼び出し、ペアリング受付フラグを即時クローズ。同一Wi-Fi上の不正端末による連続発行DoSを遮断。
  - トークン発行例外時は、グローバルトークンへのフォールバック（マスターキー漏洩）を廃止し、HTTP 500 で通信を遮断する Fail-Closed 規律を徹底（P1-2）。
- **P0-3 ソケットタイムアウト設定によるSlowlorisスレッド枯渇防御 (`local_sync_server.py`)**:
  - `DeskPetSyncHandler.timeout = 10.0` を設定。低速送信や切断放置によるHTTPワーカースレッドの永久ハング・リソース枯渇を防止。
- **P1-1 終礼日報の当日完了タスク集計是正 (`storage/task_repo.py`, `briefing_engine.py`)**:
  - `get_tasks_completed_today(now_ms=None, limit=10)` Seam を新設。
  - 本日00:00:00のミリ秒タイムスタンプ以降に `updated_at` が記録され、かつ `status='completed'` のタスクのみを厳格に抽出。過去全期間の完了タスクが毎晩日報に誤出力されるバグを根治。
- **P1-3 端末台帳覗き見防止のループバック制限 (`local_sync_server.py`)**:
  - `_dispatch_get_devices()` において、クライアントIPがループバック（`127.0.0.1` / `::1`）以外からの `GET /api/devices` 要求を HTTP 403 で拒絶。同一LAN上のスマホや第三者端末からの端末台帳覗き見を構造的に遮断。

### 10.6.1 ループバック除外・403自動リカバリ・Human-in-the-Loop接続承認（2026-09-18 改善）
- **ループバック（127.0.0.1）の台帳完全除外 ＆ 自動クリーンアップ**:
  - PC内部通信（CLI、テスト、ヘルスチェック）が端末台帳に「スマホブラウザ (127.0.0.1)」として自動登録される問題を根治。
  - `cleanup_loopback_devices()` を新設し、設定画面表示時・アプリ起動時に既存のゴミレコードを一掃。台帳は純粋に外部スマホ専用とする。
- **スマホ側の 403 自動リカバリ (`web_pet/pet_auth.js`)**:
  - `authFetch` において、401 だけでなく 403 Forbidden（失効済み・不整合）受信時にも古い無効トークンをクリアし、新トークン再取得を自動試行するフォールトトレラント設計。
- **QRダイアログ連動ライフサイクル (`ui/qr_dialog.py`)**:
  - トークン1回発行によるゼロ秒即時締め出しを廃止。QRダイアログの表示中は安全にリロード・接続を許可し、ダイアログを閉じた際（`destroy`）に確実に `close_pairing()` を呼んで Fail-Closed を成立させる。
- **🌟 Human-in-the-Loop 端末接続承認ロードマップ**:
  - スマホ等から接続要求が届いた際、PCペット側で接続要求を可視化・把握し、承認ダイアログ（[許可] / [拒否]）でユーザーが明示許可して永続トークンを発行する世界基準のゼロトラスト・アーキテクチャ。

---

## 11. 将来アーキテクチャ設計: Codebase Design ＆ Seam 分割 (v1.1.0)

### 11.1 背景と課題（Shallow Module化の危機）
- **現状のホットスポット**:
  1. `web_pet/pet.js` (3,335行): 通信、UIバナー、スプライト管理、歩行物理、歓喜アニメ、パーティクル、隠しコマンドの7つの異なるライフサイクルが単一ファイルに同居。
  2. `database.py` (2,498行): タスク、カレンダー、習慣、知識の宝庫知見、監査ログの全CRUDが単一ファイルに集中。
- **課題**: 異なる役割が同一スコープに同居することで、修正時の玉突き事故（副作用）、AI推論オーバーヘッドによるハング、5分コードレビューの困難化を招いている。

### 11.2 PWAフロントエンド Seam 4分割設計 (`web_pet/`)
ビルドツールを入れず、Vanilla JSのまま `<script type="module">` を採用して役割別にSeam（接合点）を配置：
```text
web_pet/
├── js/
│   ├── pet_network.js    # 通信・ポーリング・認証・キャッシュ制御 (約500行)
│   ├── pet_ui.js         # バナーカード・コミック吹き出し・モーダル描画 (約600行)
│   ├── pet_motion.js     # 歓喜ジャンプ・歩行物理・スプライト管理 (約500行)
│   ├── pet_particles.js  # なでなで・紙吹雪パーティクルエンジン (約400行)
│   └── pet_main.js       # 全体を統括するエントリーポイント (約300行)
└── easter_eggs.js        # ミニゲーム・隠しコマンド (既存のまま独立維持)
```
- **設計契約**:
  - `pet_network.js` はサーバーとの通信とイベント発火のみを担当し、DOMやスプライトを直接触らない。
  - `pet_motion.js` はアニメーションと物理演算を担当し、HTTPリクエストを発行しない。
  - これにより、「吹き出しを直す時に通信を壊す」玉突き事故が構造的に0%になる。

### 11.3 データベース層 Repository パターン分割 (`database/`)
- `database/connection.py`: コネクションプール・WAL設定・トランザクション保護
- `database/task_repo.py`: タスクCRUD・再帰ルール・階層管理
- `database/calendar_repo.py`: カレンダーイベント同期・終日判定
- `database/insight_repo.py`: 知識の宝庫（ボスの知見・トリセツ管理）
- `database/audit_repo.py`: 承認監査ログ永続化
- `database.py` は各Repositoryのファサード（Deep Module）として薄いインターフェースを提供。

---

## 12. グローバル展開・多言語Webアーキテクチャ (2026-09-13 策定)

### 12.1 目的とグローバルOSS戦略
- **海外開発コミュニティ（Hacker News / Reddit / Product Hunt / X）への訴求**:
  - 日本語専用ツールではなく、世界水準の「AI Agent Remote Approval Platform」として認知を獲得する。
  - GitHub READMEにおける3秒直感理解（Mermaid / ASCIIアーキテクチャ図）と、Web Showcase / 公式チートシートによる二重の導線をグローバル展開する。

### 12.2 二層式ローカライズ設計
1. **Interactive Showcase (`docs/neo-secretary-showcase-en.html`)**:
   - `eli5-data` および `eli5-ui` JSONの完全英訳により、JavaScriptレンダリングエンジン・アニメーション・シグナルトレースロジックを100%再利用。
   - 日英相互リンク（`🇯🇵 日本語版` ⇄ `🇬🇧 English`）によるシームレスな言語切り替え。
   - 専用アーキテクチャ図（`neo-secretary-architecture-en.html`）をiframe埋め込みし、設計図内部のカードまで完全英語化。
2. **Official Cheat Sheets & User Guide (`docs/guides/NEO_HISHO_CHEAT_SHEETS_en.html`)**:
   - 初期セットアップ、スマホQR/VPN接続、統合手帳、3段階承認ポリシー、ローカルLLM、FAQの全セクションを自然なプロフェッショナル英語で完全網羅。
   - `docs/guides/NEO_HISHO_CHEAT_SHEETS.html`（日本語版）と相互にトグル可能なヘッダーナビゲーションを配備。
   - 全6枚の公式インフォグラフィック（`banner_main_en.jpg`, `cs01_setup_en.jpg` 〜 `cs05_localllm_en.jpg`）を超高精細AI生成で完全英訳・配備。
3. **5大チートシート Raw Markdown 英語版 (`docs/guides/cheatsheet_0X_..._en.md`)**:
   - GitHubリポジトリ上で直接ドキュメントを閲覧する海外開発者のため、①〜⑤の全Markdownファイルを英訳し、インフォグラフィック画像を埋め込み配備。

---

## 13. バージョン定数一元化アーキテクチャ (version.js 動的配信・2026-09-14 策定)

### 13.1 散弾銃手術（Shotgun Surgery）の課題と背景
従来、PWAキャッシュ更新時に以下の複数箇所へバージョン文字列が散逸していた：
1. `version.py` (`__version__ = "1.0.0"`)
2. `web_pet/sw.js` (`CACHE_NAME = 'neo-pet-v5.32'`)
3. `web_pet/pet.js` (キャッシュパージキー `'neo-pet-v5.32'`)
4. `web_pet/index.html` (スクリプトタグのクエリパラメータ `?v=5.32`)

これにより、更新漏れによる古いキャッシュの残存や、UI表示とAPI契約の不整合リスクが存在していた。

### 13.2 Single Source of Truth (SSOT) 設計
- **正本 (SSOT)**: `version.py` の `__version__` を唯一の情報源とする。
- **動的エンドポイント (`DeskPetSyncHandler.do_GET`)**:
  - `/version.js` または `/web_pet/version.js` へのGET要求に対し、`version.py` を読み込んで以下の JavaScript を動的生成・レスポンス（`Content-Type: application/javascript`, `Cache-Control: no-cache`）：
  ```javascript
  self.APP_VERSION = "1.0.0";
  self.WEB_PET_CACHE_NAME = "neo-pet-v1.0.0";
  if (typeof window !== "undefined") {
      window.APP_VERSION = self.APP_VERSION;
      window.WEB_PET_CACHE_NAME = self.WEB_PET_CACHE_NAME;
  }
  ```
- **Service Worker (`sw.js`) 連携**:
  - 冒頭で `importScripts('./version.js');` を実行し、`const CACHE_NAME = self.WEB_PET_CACHE_NAME || 'neo-pet-v1.0.0';` へ統一。
- **フロントエンド (`pet.js` / `index.html`) 連携**:
  - `index.html` の先頭で `<script src="version.js"></script>` を読み込み。
  - `pet.js` のキャッシュパージ処理で `window.WEB_PET_CACHE_NAME` を参照。
- **フォールバック**:
  - オフライン時および開発環境向けに静的ファイル `web_pet/version.js` を同梱配備。

---

## 14. フロントエンド Seam 分割アーキテクチャ (`web_pet/pet_auth.js`)

### 14.1 モノリス解体と Seam Pattern（継ぎ目設計）
`web_pet/pet.js`（3,335行）の肥大化・結合度を解消するため、Jules設計レポート（`docs/temp/seam_mapping_pet_js.md`）に基づき、依存度が低く最も重要な「認証・通信基盤」を第1弾として独立モジュール `web_pet/pet_auth.js` へ分離。

### 14.2 `pet_auth.js` の責務と Zero-Trust 強化
1. **Bearer トークン管理**:
   - URLクエリパラメータ（`?token=...`）または `localStorage` からの安全な解決。
   - 🛡️ **Zero-Trust URLサニタイズ**: URLからトークンを取得した直後に `history.replaceState` でクエリを除去し、画面共有やリファラヘッダー経由の漏洩を防止。
2. **`authFetch` 透過ラッパー**:
   - 🛡️ **同一オリジン保護**: 相対パスまたは同一オリジン宛てのリクエストのみ `Authorization: Bearer <token>` を付与し、外部URLへのトークン流出を構造的に遮断。
   - 🛡️ **FormData 自動判定**: `options.body` が `FormData` の場合は `Content-Type` ヘッダーを自動付与せず、ブラウザによる multipart boundary 生成を保証。
   - 🔄 **自己治癒（401自動リトライ）**: 401 Unauthorized 受信時、`/api/auth/token` で最新トークンを再取得して1回限定で再試行。
3. **グローバル後方互換**:
   - `pet.js` や各ミニゲーム（`pixel_defense.js`, `minigame_arcade.js`）からの直接呼び出しを保証するため、`window.authFetch`, `window.syncToken`, `window.getSyncToken`, `window.setSyncToken` を公開。
4. **回帰防止テスト**:
   - `tests/test_pet_seam_auth.py` により、ファイル存在・シンボル公開・ロード順序・SWキャッシュ・HTTP配信を自動検証。

---

## 15. フロントエンド Seam 分割 第2弾: 音響・効果音エンジン (`web_pet/pet_audio_se.js`)

### 15.1 責務の分離と Deep Module 化
`web_pet/pet.js` 内に直接インライン記述されていた発振器（Oscillator）の生成、周波数ランプ（`exponentialRampToValueAtTime`）、User Gesture解錠、および各キャラクターの固有音響合成ロジック（約170行）を、完全に独立した「Web Audio SE エンジン」として `web_pet/pet_audio_se.js` へ抽出・モジュール化。

### 15.2 アーキテクチャとフェイルセーフ設計
1. **完全ローカル・低遅延シンセサイザー (Web Audio API)**:
   - 外部音声ファイル（mp3/wav）へのネットワーク通信依存を一切持たず、クライアント側のCPUで純粋な波形（サイン波・三角波・矩形波）をリアルタイム合成。
   - `exponentialRampToValueAtTime` での0値指定例外（`RangeError`）を回避するため、`0.0001` からの指数減衰曲線を徹底。
2. **多重 User Gesture 解錠ポリシー (Mobile Audio Unlock)**:
   - モバイルブラウザの自動再生ブロックを突破するため、`pointerdown`, `touchstart`, `visibilitychange`（`passive: true`）の3重解錠リスナーを配備。
   - アラートチャイム再生時にも `unlockAudio()` を内部連動させ、画面復帰直後の通知音鳴動を死守。
3. **安全なフェイルセーフ ＆ フォールバック**:
   - 全ての公開メソッドを `try-catch` で保護し、オーディオデバイス無効環境や `navigator.vibrate` 非対応端末（iOS/デスクトップ）でもメインUIループを絶対に巻き込まない設計。
   - 未知のキャラクターIDが渡された場合、無駄なオシレーター生成を防ぎつつ即座にデフォルト（`hisho`）へフォールバック。
4. **公開インターフェース (Global Export)**:
   - `getAudioContext()`, `unlockAudio()`, `playTwoTone()`, `playAlertChime()`, `stopAlertChime()`, `playDecisionSound()`, `playCharacterSE()` を `window` および非モジュールスコープへ公開。
5. **回帰防止テスト**:
   - `tests/test_pet_seam_audio.py` により、物理存在・シンボル定義・読み込み順序・SWオフラインキャッシュ・HTTP配信（200 OK）を完全網羅。

---

## 16. フロントエンド Seam 分割 第3弾: 背景環境・天候・パーティクルエンジン (`web_pet/pet_particles.js`)

### 16.1 責務の分離と描画パイプラインの独立
`web_pet/pet.js` 内にインライン記述されていた5大背景テーマ定義、Canvas初期化とリサイズ同期、5大シーン描画ロジック（書斎・カフェ・森・海・サイバー）、天候パーティクル（雨・雪・雷・落ち葉）、なでなでパーティクル、および歓喜セレブレーション紙吹雪の物理演算ループ（約600行）を、完全に独立した「HTML5 Canvas 背景・パーティクルエンジン」として `web_pet/pet_particles.js` へ抽出・モジュール化。

### 16.2 アーキテクチャと堅牢性設計（P0〜P3 レビュー反映）
1. **不滅のアニメーションループ (Fail-safe Animation Pipeline)**:
   - 描画処理内部で予期せぬ例外が発生してもメインループが二度と停止しないよう、`particleLoop` を `try { ... } finally { requestAnimationFrame(particleLoop); }` 構造で完全防護。
   - `drawEnvScene` 内の Canvas コンテキスト変形（`save() / restore()`）も `try-finally` で保護し、コンテキストリークや画面描画崩壊を構造的に防止。
2. **状態の双方向同期 ＆ NoSleep Canvas 参照保証**:
   - 閉包（IIFE）内の環境インデックスとグローバルな `window.currentEnvIndex` の乖離を根絶するため、`Object.defineProperty` による双方向ゲッター／セッターおよび `setEnvTheme(idx)` API を配備。DOMの `active` クラスとパーティクル種別を100%同期。
   - `pet.js` の `NoSleep`（`captureStream()`）が参照する `window.envCanvas` および `window.envCtx` をトップレベルで確実に公開し、スリープ防止の壊れを回避。
3. **情緒物理の最適化 (Real Organic Physics)**:
   - 完了通知時の最高報酬演出である紙吹雪大噴射（`spawnCelebrationConfetti`）に、重力加速度（`gravity: 0.14`）と空気抵抗（減衰率 `0.985`）を適用。直線的な拡散ではなく、上空へ吹き上がった後に放物線を描いてヒラヒラと舞い落ちるオーガニックな物理挙動を実現。
4. **公開インターフェース (Global Export)**:
   - `initEnvCanvas()`, `particleLoop()`, `drawEnvScene()`, `spawnWeatherParticles()`, `cycleEnvTheme()`, `setEnvTheme()`, `spawnTouchParticles()`, `spawnCelebrationConfetti()`, `ENV_THEMES`, `envCanvas`, `envCtx` を公開。
5. **回帰防止テスト**:
   - `tests/test_pet_seam_particles.py` により、物理存在、必須シンボル公開、スクリプト読み込み順序（`pet_audio_se.js` 直後かつ `pet.js` 直前）、SWオフラインキャッシュ、HTTP配信（200 OK）を完全自動検証。

---

## 17. フロントエンド Seam 分割 第4弾 (`web_pet/pet_motion.js`) ＆ 第5弾 (`web_pet/pet_ui.js`)

### 17.1 モーション・キャラクター・生活リズムエンジン (`web_pet/pet_motion.js`)
1. **責務の分離**:
   - キャラクター定義（`CHARACTERS`）と動的切り替え（`cycleCharacter`）、スプライトプリロード（`preloadSprites`）、スプライト切り替え（`_setPetSprite`, `setPetSprite` エイリアス）。
   - 生活リズム・睡眠サイクル（`ACTIVITY_SPRITES`, `updateLifeSprite`, `updatePetLifeActivity`）。
   - 歓喜ジャンプ演出（`triggerCelebrateReaction`: CSS物理バウンス、足元シャドウ、パラパラアニメ、紙吹雪連動）。
   - 自律歩行エンジン（`WANDER`, `petWanderTick`: 120msインターバル、地面ランダム歩行、左右反転、吹き出し頭上リアルタイム追従）。
   - なでなでインタラクション（`onPetTap`: 弾力バウンス、Haptics、キャラクター固有SE、パーティクル連動、ランダムセリフ）。
2. **堅牢性・フェイルセーフ設計**:
   - 未知のキャラクターID指定時でもデフォルトへの安全なフォールバック。
   - `window.petStateNow` および `window.currentPetCharacter` との双方向同期。

### 17.2 UI制御・エージェント承認・ボトムシート (`web_pet/pet_ui.js`)
1. **責務の分離**:
   - 高視認性HUDトースト通知（`showToast`, `toastTimer`）。
   - サジェストカード表示 ＆ Glass Bottom Sheet（`renderSuggestionCard`, `nextSuggest`, `prevSuggest`, `openBottomSheet`, `closeBottomSheet`, `quickCompleteCurrentTask`, `setupSuggestSwipe`, `triggerSecretRoomIris`）。
   - エージェント遠隔承認バナー ＆ イベント操作（`setupBannerSwipe`, `openApprovalSheet`, `openQuestionSheet`, `respondApproval`, `respondChoice`, `dismissCompleted`, `_hideBanner`）。
   - MediaSession API ノールック承認（`setupMediaKeyApproval`: ハードウェアキー/イヤホンボタン連動）。
   - 時計 ＆ ポモドーロUI制御（`updateClock`, `togglePomodoro`）。
   - エージェント稼働ライブバッジ表示（`updateAgentActivityBadge`）。
   - HTMLエスケープユーティリティ（`escapeHtml`）。
2. **堅牢性・フェイルセーフ設計**:
   - `_hideBanner` の責務統合（スワイプ変形リセット、`currentActiveEvent` リセット、クラス除去をアトミックに実行）。
   - サジェストスワイプの `DOMContentLoaded` 初期化保証。
   - `escapeHtml` によるXSS完全防御。

### 17.3 公開インターフェースと回帰防止テスト
- **グローバル公開**: モジュール/非モジュール双方に対応し、`window.xxx` および `var xxx` で全関数・定数を公開。
- **回帰防止テスト**: `tests/test_pet_seam_motion_ui.py` により、物理存在、必須シンボル公開、スクリプト読み込み順序、SWオフラインキャッシュ、HTTP静的配信（200 OK）を完全網羅。
- **コード削減成果**: `pet.js` の行数が 2,519行 ➔ **1,604行**（約915行削減、当初3,335行から通算約1,731行スリム化）を達成。

---

## 18. バックエンド `database.py` Repository パターン分割計画 (Architectural Blueprint)

### 18.1 現状の課題と動機 (Why)
- **現状**: `database.py` が単一ファイルで **2,498行** に達し、8つの異質なドメイン関心事が1箇所に密集。
- **課題**: 
  1. タスクの修正時にカレンダーや監査ログのコードを巻き込む認知負荷。
  2. AIエージェントが編集する際のトークン消費と推論遅延の増大。
  3. 単体テスト実行時にファイル全体をロードする必要がある結合度。

### 18.2 設計原則: Facade パターンによる完全後方互換性の死守 (What & How)
既存の71件以上のテストスイート（`tests/test_*.py`）および各サブシステム（`gui.py`, `local_sync_server.py`, `agent.py`, `briefing_engine.py`, `hisho_mcp_server.py` 等）は、すべて `import database` または `from database import ...` を直接呼び出している。
これらを破壊せず安全に分割するため、**Facade パターン（窓口維持方式）** を採用する。

```
ネオ秘書くん/
├── storage/                    # 🗄️ 新設: 分割されたRepositoryパッケージ
│   ├── __init__.py             # パッケージ宣言
│   ├── connection.py           # コネクションライフサイクル, WAL設定, init_db, バックアップ
│   ├── models.py               # Pydanticモデル定義 (Category, Event, Task, Habit, Insight等)
│   ├── calendar_repo.py        # Event, Category, CalendarSource CRUD & 繰り返し展開計算
│   ├── task_repo.py            # Task, TaskList CRUD, 階層ツリー, 4象限マトリクス
│   ├── habit_repo.py           # Habit, HabitLog CRUD, ストリーク計算, 年間ヒートマップ集計
│   ├── insight_repo.py         # UserInsight (知識の宝庫) CRUD, タグ検索, 重要度スコアリング
│   ├── note_repo.py            # StickyNote CRUD, デスクトップ位置・サイズ永続化
│   ├── device_repo.py          # Device 台帳 CRUD, トークンハッシュ照合, 失効管理
│   ├── audit_repo.py           # ApprovalAuditLog CRUD, 改ざん耐性監査台帳
│   └── minigame_repo.py        # MinigameScore CRUD, ハイスコア集計
└── database.py                 # 🏛️ 既存維持: storage/ の全公開シンボルを再エクスポートする薄いFacade
```

### 18.3 パフォーマンスへの影響評価 (Performance & Zero-Overhead)
1. **実行時パフォーマンス (Runtime Performance)**:
   - Python のモジュールインポートによる名前解決は起動時に一度辞書（`sys.modules`）へ登録されるのみであり、関数呼び出し時のオーバーヘッドは **0.000ミリ秒**（ゼロオーバーヘッド）。
   - SQLite WAL の同時読み書き性能やクエリスループットは接続コンテキストマネージャ（`get_db_connection`）と SQLite Cエンジン内部で決定されるため、ファイル分割による劣化は一切生じない。
2. **保守・開発パフォーマンス (Developer Velocity)**:
   - 各 Repository が 200〜400行 前後の「深いモジュール（Deep Module）」として自己完結するため、AIのコード生成精度が向上し、コンテキスト溢れや副作用バグ（玉突き事故）が構造的に撲滅される。
   - 各リポジトリ単体でのモック化・テストが容易になり、CIテストの並列性も向上する。

### 18.4 移行ステップ (Incremental Migration Plan)
- **Phase 1 (非破壊的モデル・接続の切り出し - ✅ 2026-09-14 完了)**: `storage/models.py` (全13モデル) と `storage/connection.py` (WAL・init_db・マイグレーション) を先行新設し、`database.py` から参照。行数を2,498行 ➔ 1,960行へ約538行削減。全体テスト446件全緑（444 passed, 2 skipped, 0 failed）達成。
- **Phase 2 (ドメインRepository完全切り出し ＆ Facade集約 - ✅ 2026-09-14 完了)**: 
  - `storage/audit_repo.py`, `storage/device_repo.py`, `storage/insight_repo.py`, `storage/sticky_repo.py`, `storage/habit_repo.py`, `storage/calendar_repo.py`, `storage/task_repo.py`, `storage/minigame_repo.py` の全ドメインRepositoryを完全分離。
  - `storage/connection.py` に `backup_database` および世代管理付き `auto_backup` を配備。
  - `storage/__init__.py` で全シンボルを集約エクスポート。
  - `database.py` を実体1,721行から **243行の純粋な薄型Facade** へスリム化。既存の呼び出し元コードとの100%後方互換性を死守。
- **Phase 3 (回帰防止アサーション - ✅ 2026-09-14 完了)**: `tests/test_storage_seam_phase2_step1.py` および `tests/test_storage_seam_phase2_step2.py` による全シンボル・Facade同一性・各ドメインCRUDの自動検証を配備。

---

## 19. パフォーマンス最適化・省電力設計 (Performance & Battery Optimization - v1.0.3)

2026-09-14 の深層監査（`/deep-audit`）によって特定された「6大パフォーマンス・ボトルネック」に対する恒久設計指針。

### 19.1 クライアント側（スマホPWA）の省電力・低負荷設計
1. **Page Visibility ポーリング抑制 (✅ 2026-09-15 完了 - P0)**:
   - `document.hidden === true`（画面OFF・バックグラウンド時）は `getNextFetchInterval()` で `FETCH_HIDDEN_INTERVAL = 30000` (30秒) に自動伸長。
   - `visibilitychange` イベントで復帰した瞬間、既存タイマーを `clearTimeout(pollingTimerId)` で即座に破棄し、0秒即時フェッチ＆2秒通常ポーリングへ復帰（遅延ゼロ）。タイマー二重発火も完全防止。単体テスト `tests/test_pet_seam_pwa_power_save.py` 完備。
2. **Canvas適応型描画ループ ＆ Wake-on-Demand (✅ 2026-09-16 完了 - P1-1)**:
   - `web_pet/pet_particles.js`: `document.hidden === true`（画面非表示・バックグラウンド・スリープ時）に `stopParticleLoop()` を自動発火し、`cancelAnimationFrame(animFrameId)` で保留中フレームを完全消去してループを即時停止（**0fps完全スリープ**、GPU/CPU負荷ゼロ）。
   - 画面復帰時（`visibilitychange`）やユーザー操作時（なでなで `spawnTouchParticles`、タスク完了 `spawnCelebrationConfetti`）のみ `wakeParticleLoop()` で最小限叩き起こす Wake-on-Demand 機構を配備。
   - `isParticleLoopRunning` フラグによる多重ループ防止、`web_pet/pet.js` の初期化エントリーポイント統一、SSR/Node環境用 `typeof window !== 'undefined'` ガードを完備。TDDテスト `tests/test_pet_seam_canvas_power_save.py`（全8項目）完備。
3. **DOM更新の条件付きクランプ (P1)**:
   - `petWanderTick`（120ms周期）での吹き出し位置スタイル更新は、ペットが実際に歩行中（`isMoving === true`）のみに限定し、不要なレイアウト再計算を抑制。

### 19.2 サーバー側（Python / SQLite / GUI）のスケーラビリティ設計
1. **ステータスAPI キャッシュの完全網羅 (✅ 2026-09-15 完了 - P0)**:
   - `/api/status` において、タスク・予定（2秒TTL）に加え、習慣データ（`habits_data`）および70日分ヒートマップ（`heatmap_data`）を 30秒TTLキャッシュ に格納。
   - 2秒ポーリングによる高頻度SQLiteクエリを遮断し、DB負荷を93%削減。追加・トグル・削除時に `invalidate_habit_cache()` で即時破棄。単体テスト `tests/test_habit_cache.py` 完備。
2. **検索頻出カラムの明示的インデックス (✅ 2026-09-16 完了 - P1-2)**:
   - `storage/connection.py` の `init_db()` に `idx_tasks_status_due (status, due_date)` および `idx_events_start_end (start_time, end_time)` を新設し、フルテーブルスキャン（O(N)）を O(log N) へ最適化。既存DBにも起動時の `CREATE INDEX IF NOT EXISTS`（冪等）で自動付与。EXPLAIN QUERY PLAN で索引使用を検証する `tests/test_db_indexes.py` 完備。
3. **アイドル待機の30Hz化（✅ 2026-09-16 完了 - P1-3）**:
   - `main.py` の `async_mainloop` は無操作検出を行わず、待機を `MAIN_LOOP_IDLE_SLEEP_SEC = 0.03`（約30Hz）へ**固定レートで緩和**し、PC側CPUコアの常時占有を削減（定数へ一元化・マジックナンバー排除）。`tests/test_main_loop_power.py` 完備。
   - 応答遅延の上限は「1ティックの処理時間 + 30ms」。リマインダーは `proactive_scheduler`（1秒専用スレッド）駆動のため精度影響なし。
4. **ポート番号の単一情報源 ＆ 環境変数オーバーライド (✅ 2026-09-16 完了 - P1-4)**:
   - `sync_config.py` の `SERVER_PORT`（既定 `DEFAULT_SERVER_PORT = 8765` / 環境変数 `NEO_HISHO_PORT` で上書き可・不正値は既定へ安全退避）を唯一の情報源とし、`local_sync_server` / `ui/qr_dialog` / `main._auto_tailscale_serve` がすべてここを参照。QR接続ダイアログに残っていた `http://localhost:8765/...` のベタ書きを排除。`tests/test_port_single_source.py` 完備。

## 20. 秘書くんアイコン化・PWAアイコン・端末管理UI アーキテクチャ (2026-09-16 Cline Desktop 実装)

デフォルトの汎用アイコン（青い羽ペン相当）を廃止し、**初代秘書くんのドット絵**を
アプリ全体（ウィンドウ / タスクトレイ / EXE / スマホPWAホーム画面）へ一貫適用する。

### 20.1 アイコン適用の Seam（`ui/window_icon.py`）
1. **Deep Module 化**: メインウィンドウ (`gui.py`) と各ダイアログ（手帳 / 設定 / QR接続）は
   `apply_window_icon(window)` を 1 行呼ぶだけ。Tk 固有の分岐は Seam 側へ隠蔽する。
2. **例外安全なフォールバック設計**: Windows では `iconbitmap(assets/icon.ico)`（タスクバー/Alt+Tab に反映）を
   第一候補とし、失敗時は PNG ドット絵を `iconphoto(False, image)` へフォールバック。
   双方失敗しても `False` を返すだけで起動を止めない（Fail-Safe）。
3. **GC 対策**: `iconphoto` に渡した `PhotoImage` は参照を保持しないと消えるため、
   ウィンドウ側属性 `_neo_hisho_icon_photo` に保持する。

### 20.2 タスクトレイのキャラ着せ替え連動（`ui/system_tray.py`）
1. **既定アセットの変更**: `_ASSET_CANDIDATES` の最優先候補を `assets/dot/hisho/idle_1.png` へ変更。
2. **純粋関数 Seam**: `resolve_character_icon_path(character_id)` / `load_character_tray_image(character_id)` が
   キャラIDから `assets/dot/<id>/idle_1.png`（64x64・NEAREST 拡大）を解決。未登録キャラは既定キャラへ退避。
3. **ゼロトラスト入力検証**: キャラIDは `^[a-z0-9_]+$` に正規化し、パストラバーサル文字列で
   assets 外のファイルを読み出せない（`sanitize_character_id`）。
4. **着せ替え連動**: `SystemTrayManager.update_character_icon(character_id) -> bool` を新設し、
   `gui.switch_character_skin()` が `_sync_tray_character_icon()` 経由で呼び出す
   （トレイ未起動時は何もせず False を返す）。

### 20.3 EXE 実行ファイルアイコン（`neo_hisho.spec`）
- `icon=str(ICON_PATH)`（`<PROJECT_ROOT>/assets/icon.ico`・256x256）を指定。
  プロジェクトルートは PyInstaller が注入する `SPECPATH` から解決し、
  未定義環境（テスト等）では CWD へフォールバックする。

### 20.4 スマホPWAホーム画面アイコン（`assets/pwa/` ＋ `web_pet/`）
1. **実在×サイズ一致の原則**: 旧 manifest は「32x32 が実在しない `./assets/idle_1.png` を指す（404）」
   「192/512 と宣言しながら実体は 128x128（サイズ不一致）」というインストール阻害要因を抱えていた。
   これを全て解消し、宣言サイズ＝実画像サイズを保証する。
2. **生成の再現性（`tools/build_pwa_icons.py`）**: ドット絵から 192/512（any）と
   512（maskable）/ 180（apple-touch-icon）を NEAREST 拡大で生成。
   maskable / iOS 用は透過を許さないためテーマ背景色で塗りつぶし、セーフゾーン（内側70%）に配置する。
3. **iOS 対応 (`web_pet/index.html`)**: `apple-touch-icon`（180x180）と
   `apple-mobile-web-app-title`、`rel="icon"`（192x192 PNG）を宣言。
4. **オフライン整合 (`web_pet/sw.js`)**: 4 種のアイコンを `ASSETS_TO_CACHE` に追加し、
   オフライン起動時もホーム画面アイコンが欠けないようにする。

### 20.5 設定画面のゼロトラスト接続端末管理UI（`ui/device_manager_panel.py`）
1. **Seam 分割**: 台帳→表示DTO変換 (`build_device_rows`) と Revoke 実行 (`revoke_device_entry`) は
   GUI 非依存の純粋関数 / Seam として公開し、Tk を起動せずにテストできる。
2. **表示項目**: 端末名（未登録時は User-Agent 解析名で補完）、UA要約＋IP、
   初回接続日時・最終アクセス日時、認証ステータス（🟢 有効 / 🚫 拒否済み）。
3. **Revoke フロー**: 赤系「🔒 接続解除」ボタン → 確認ダイアログ（注入可能な
   `confirm_callback`）→ `database.revoke_device(device_id)` → 一覧を即時再描画。
   失効済み端末のボタンは無効化（二重操作防止）。次回リクエストは 401/403 で遮断される。
4. **神ファイル肥大化の抑止**: `ui/settings_window.py` へは「📱 接続端末管理」タブに
   セクションを 1 つ差し込むだけに留め、ロジックは本モジュールへ委譲する。

### 20.6 静的アセット配信のパス検証 Seam (`web_assets.py`) — 🔒 P0 修正 (2026-09-16)
1. **背景（実測された脆弱性）**: `GET /assets/...` は PWA 表示のため認証なしで公開しており、
   旧実装の検査（`".." / 先頭"/" / ":"`）を Windows の `\` 始まり絶対パスが通過した。
   `GET /assets/\Windows\win.ini` が **200 OK＋実ファイル本文**を返し、`0.0.0.0` 待受のため
   同一LAN/Tailscale 上の第三者へホスト内ファイルが露出していた（ruthless-code-evaluation で実測再現）。
2. **修正**: 判断ロジックを純粋関数 `web_assets.resolve_asset_path(filename, assets_root)` へ集約し、
   HTTPハンドラは結果を使うだけにする（Deep Module / Seam）。多層防御は
   ① 危険表現（`\`・`:`・`%`・先頭 `/`）の事前排除
   ② 画像拡張子アローリスト（`.png/.jpg/.jpeg/.gif/.webp/.svg/.ico`）
   ③ 解決後の実パスがルート配下であることの検証（`Path.resolve()` + `is_relative_to`）。
   Content-Type は `guess_asset_content_type()` で実ファイルから導出。
3. **公開維持の判断**: 正規アイコン（`/assets/pwa/icon_192.png`）は 200 + image/png のまま
   （認証は付与しない。ブラウザは manifest/icons を Bearer なしで取得するため）。
   したがって **パス検証が唯一の防壁**であり、回帰テスト
   `tests/test_asset_path_security.py`（純粋Seam 9件＋実HTTP 5件＋自己点検ツール2件＝16件）で凍結する。
4. **自己点検ツール (`tools/check_asset_security.py`)**: `curl` やブラウザは URL の `\` を `/` へ
   正規化するため攻撃文字列を再現できない。**生ソケットで点検する専用ツール**を用意し、
   実サーバー（既定）／LAN IP（`--host`）／アプリ未起動（`--serve`）の3モードで
   正常系200・攻撃系404・内容漏えいなしを検査する（終了コード 1 でリリース前ゲートにも使用可）。

### 20.7 待受ポートの解決順序 (`sync_config.py`) — P1-1 修正 (2026-09-16)
- 解決順は **OS環境変数 `NEO_HISHO_PORT` → `.env`（stdlibのみで軽量読取）→ 既定 8765**。
- `main.py` は `agent.py`（`load_dotenv()` 実行元）より先に `sync_config` を import するため、
  `.env` の値は `os.environ` に載っていない。そこで `read_port_from_env_file()` が
  アプリデータルート（`app_paths.get_app_root()`）の `.env` を直接読む（`os.environ` は汚染しない）。
- 不正値は例外を出さず既定ポートへ退避する（`resolve_server_port` の入力検証）。

### 20.8 端末管理パネルの非同期化 ＆ Revoke 監査 (P1-3 / P1-4・2026-09-16)
1. **UIブロックの根絶**: `ui/device_manager_panel.py` の台帳読み出しは `fetch_device_rows()`（失敗を空リストへ
   潰さず `DeviceFetchResult(rows, error)` を返す Seam）へ集約し、`refresh_async()` が
   **ワーカースレッドで読み出し → `dispatch`（本番: `parent_gui.post_action`）経由でメインスレッドへ反映**する。
   Tk ウィジェットへはメインスレッドからしか触らない（`refresh()` は他スレッドから呼ばれた場合に警告して退避）。
   - 多重発行は `_refresh_in_flight` で抑止し、実行中の要求は**破棄せず延期**（`_refresh_pending`）して
     完了直後に再実行する。破棄すると「失効直後の再読込が失効前スナップショットで上書きされる」＝
     **DBは失効済み・UIは有効**という嘘が固定表示される（2026-09-16 独立査読で実測）。
   - 失効成功時は `mark_row_revoked()` による**楽観反映**で即座に「🚫 拒否済み」を表示し、
     バックグラウンド再読込で整合を取る。
   - 取得失敗時は「端末ゼロ」と区別できるよう「⚠️ 読み出し失敗」を表示し、既存一覧がある場合は
     それを消さずに（stale-but-visible）状態行へ失敗理由を出す。
2. **Revoke の監査 (P1-4)**: `api_devices.record_device_revoke()` が `approval_audit_logs` へ
   **agent_type=device_management / command=revoke device_id=N (端末名) /
   decision_by=操作主体（`pc_settings_ui` または接続元IP）/ decision_message=source=ui|api** を記録する。
   - 本経路は**同期書き込み**とする。非同期ロガー（`AsyncAuditLogger`）は終了時にキューがフラッシュされず
     「失効成功・監査0件」が成立することを査読が実測したため。失効本体（同期DB書き込み）と
     同じブロッキング特性であり、追加の遅延要因にならない。
   - 承認履歴（非同期側）は `main.py` の終了処理で `get_global_audit_logger().stop()` によりフラッシュする。
3. **API ハンドラの Seam 化**: `POST /api/devices/revoke` の処理本体は
   `api_devices.handle_post_devices_revoke(ctx)` へ抽出（ループバック限定チェックは呼び出し元に残置）。
   400/404/200/500・CORS ヘッダーの挙動は従来踏襲（不正JSONのみ 500→400 へ明示化）。

### 20.9 LLM 出力言語ガード (`i18n.py` / `life_coach_engine.py` / `agent.py`) — P0 (2026-09-17)
1. **背景（実機で発生した事象）**: 生活コーチのレポートが**中国語で出力**された。
   原因は `life_coach_engine._invoke_llm()` が LLM へ `Output language: ja` と
   **言語コードのみ**を渡していたこと。DeepSeek 等の中国系モデルは曖昧な言語指示を解釈できず、
   既定言語（中国語）で生成する（`OPENCODE_MODEL=deepseek-v4-pro` 環境で再現）。
2. **設計**:
   - `i18n.LANGUAGE_NAMES`（`{"ja": "日本語", "en": "English"}`）と `get_language_name()` を新設し、
     プロンプトには**正式言語名**を渡す。
   - `get_no_chinese_instruction()`（“Do NOT use Chinese (简体中文) …”）を全LLMプロンプトへ追記し、
     中国語・他言語の混入を明示的に禁止する。
   - メインチャット（`agent.py`）のシステムプロンプトにも**【言語規則】必ず日本語で応答**を明記
     （キャラクター人格プロンプトと併記）。
   - **言語タグによる再生成**: `LifeCoachEngine` は生成レポートに `language` を埋め、
     `_load_latest_report()` で現在言語と不一致なら破棄して再生成する
     （旧レポートの言語が残り続ける事故を防止・SQLite永続化を跨ぐ）。
3. **回帰防止**: `tests/test_life_coach.py`（11件）＋ `tests/test_i18n*`。
   実機確認（ボス）にて日本語出力を確認済み。

### 20.10 継続セッションの品質負債返済 (2026-09-17)
| 項目 | 内容 |
|---|---|
| **アセット解決の一本化** | `ui/system_tray.py` の `iter_tray_icon_candidates()` を唯一の情報源とし、`_ASSET_CANDIDATES`（固定リスト）と `resolve_character_icon_path`（キャラ別）の二重化を解消。**起動時のトレイアイコンが保存済みキャラクター（着せ替え状態）に追従**（旧: 常に既定キャラ固定）。`Image.open` は `with` で確実にクローズ |
| **Tailscale コマンド統一** | `sync_config.tailscale_serve_command_args()` / `TAILSCALE_SERVE_FLAGS = ("--bg",)` を新設し、`main.py`（旧: `--bg` なし）・QRダイアログ・設定画面ガイド・LLMプロンプトを**同一コマンド**へ統一 |
| **端末管理UIの文言是正** | 復旧手順を「設定画面の『🚫 スマホ連携をすべて解除（トークン再生成）』→ 新しいQRを読み直す」と正確化。全端末共通トークン運用のため**台帳は通常1件のみ**である旨を注記 |
| **起動時DB初期化の可視化** | `init_db` の実行時間を計測し `DB_INIT_SLOW_THRESHOLD_MS`（2秒）超で警告。バックグラウンド化は起動直後の書き込みロック競合リスクが高く、本アプリのDB規模では不要と判断（理由を docstring に明記） |
| **命名・整合の是正** | 「適応型スリープ」→「**アイドル待機の30Hz化（固定レート）**」へ是正（遅延上限=1ティック処理時間+30ms を明記）。`tools/build_pwa_icons.py --check`（生成仕様とのドリフト検出・終了コード1）を追加し、コミット済みアイコンが仕様と一致することをテストで凍結 |
| **機密スキャナの実行不能バグ** | `tools/scan_git_secrets.py` が Windows コンソール（cp932）で絵文字により `UnicodeEncodeError` で落ちていたため、出力を ASCII（`[OK]`/`[NG]`/`[SCAN]`）へ変更 |

### 20.11 端末台帳のゼロトラスト個別トークン化 ＆ 端末単位 un-revoke API (2026-09-18)
1. **背景と課題**:
   旧実装は全端末で共通のグローバルトークン（`.sync_token`）1本を配布しており、`devices.token_hash` が実質1行のみで運用されていた。
   そのため「複数端末の一覧」や「端末ごとの個別失効（Revoke）」が実質不能であり、1台解除すると全端末が拒絶される問題があった。
2. **設計・アーキテクチャ**:
   - **QRペアリング単位での個別トークン発行 (`issue_device_token`)**:
     - 256bit 暗号論的乱数 (`secrets.token_hex(32)`) を生成。
     - DBへは平文を保存せず、SHA-256 ハッシュのみを永続化（ゼロトラスト徹底）。
     - `/api/auth/token` はループバック（同一PC内）からの通常要求には既存互換のグローバルトークンを返し、ペアリング開放時または外部/スマホ端末接続時は端末固有トークンを発行・返却。
   - **2層 Bearer 認証 (`local_sync_server._check_auth`)**:
     - Step 1: グローバルトークン一致（PC内部・Agent Bridge・CLI・既存テストのマスターキーとして100%後方互換維持）。
     - Step 2: 個別端末トークン照会（`verify_device_token`）。
       - `is_revoked == 0` ➔ 認証成功（`dev.token_hash` を再利用し `last_seen` 更新）。
       - `is_revoked == 1` ➔ 403 Forbidden（対象端末のみ遮断、他端末は通信継続）。
       - 未登録 ➔ 401 Unauthorized。
   - **端末単位の復帰（un-revoke）API ＆ UI**:
     - `POST /api/devices/restore`: ループバック限定・二重防御ハンドラ新設（`api_devices.handle_post_devices_restore`）。
     - `storage.device_repo.restore_device(device_id)`: `UPDATE devices SET is_revoked = 0 WHERE id = ?`
     - `record_device_restore`: 復帰操作を `approval_audit_logs` へ同期記録（who/when/which device）。
     - 設定画面UI (`ui/device_manager_panel.py`): 失効済み端末カードに「♻️ 接続復帰」ボタンを配備。楽観反映と非同期再描画を完備。
3. **検証と品質ゲート**:
   - `tests/test_device_individual_tokens.py`（新規TDDテスト）、`tests/test_api_devices_seam.py`、`tests/test_device_ui_seam.py`。
   - 独立査読エージェント（`quality-reviewer`）多角査読により APPROVED 判定。

### 20.12 Jev意思決定エンジン連携アーキテクチャ (2026-09-20)
1. **背景とコア設計思想（引き算の美学）**:
   - 2026年9月に登場したTypeSafe Jev（System Oneモデル）を活用し、LLMの推論トークンを消費せずにミリ秒・極小コスト（約0.002円/回）で白黒判定やルーティングを行う基盤を導入。
   - **本体への不組込み原則**: 秘書くん本体（Desk Pet / Agent Bridge）にはJevの推論コードやキーを持たせず、外部エージェント（Antigravity, Codex等）側がJevを叩いて判断を下す「関心事の分離」を徹底。
2. **連携フローと承認要請の進化**:
   - エージェント側で `jev_guard_command` を呼び出してコマンドの安全性・破壊性を事前審査。
   - `ask_human_approval` 呼び出し時、サマリにJev判定結果（例: `【Jev安全審査: allow (信頼度1.0)】 git push origin main`）を付与。
   - スマホDesk Petを見たボスが、コードを熟読せずとも一目でワンタップ承認できるUI体験を実現。
3. **成果物とグローバル完全独立配備**:
   - 配置先: `C:\Users\bonob\.gemini\tools\jev_router\`（全リポジトリ共通資産）
     - `jev_client.py`: OpenRouter Decisions API 連携
     - `model_fetcher.py`: OpenCode GO / OpenRouter 最新モデル動的取得 ＆ ローカルキャッシュ (24h TTL)
     - `jev_mcp_server.py`: FastMCP stdio サーバー (`jev_guard_command`, `jev_route_agent`, `jev_list_available_models`, `jev_execute_opencode`)
   - 設定: `C:\Users\bonob\.gemini\config\mcp_config.json` に専用仮想環境（`.venv`）参照でグローバル登録完了（4 tools enabled）
   - リポジトリクリーン化: 秘書くんリポジトリ内の一時ファイルを退役させ、完全な「関心事の分離」を実現。
4. **ボス開発エコシステム・マスター設計書 ＆ Showcase**:
   - `C:\Users\bonob\.gemini\docs\BOSS_DEVELOPMENT_ECOSYSTEM.md`: 6層アーキテクチャ、データフロー、記憶境界（知識の宝庫 vs MentisDB vs codebase-memory）の体系化。
   - `docs/ecosystem_showcase.html` / `~/.gemini/docs/ecosystem_showcase.html`: 動的相関図・パケット送受信アニメーションShowcase。

### 20.13 未承認端末接続時の Human-in-the-Loop 承認ダイアログ (P0-2) (2026-09-20)
1. **背景とゼロトラスト原則**:
   - 同一LANやTailscaleに侵入した未知の端末がペアリング開放期間中に自動接続し、正規トークンを不正取得する脅威を根絶。
   - 新規端末からのトークン発行要求（`/api/auth/token`）に対し、デスクトップPC上で人間が明示的に「許可」を押さない限りトークンを発行しない **Human-in-the-Loop（人間承認）の二重防壁** を導入。
2. **設計・アーキテクチャ**:
   - **承認ダイアログ GUI (`ui/device_approval_dialog.py`)**:
     - `DeviceApprovalDialog`: 最前面表示（`-topmost`）、端末名・IP・安全審査バッジ・30秒カウントダウン表示。
     - 自動拒絶（Fail-Closed）: 30秒経過、ダイアログ閉じる操作、例外発生時はすべて自動拒絶。
     - スレッド同期 Seam: `ask_device_approval_gui` が HTTP スレッドと Tkinter メインスレッドの間を `root.after` と `threading.Event` で非同期ブリッジし、UIフリーズを回避。
   - **同期サーバー結合 (`local_sync_server.py`)**:
     - `set_gui_instance`: GUI起動時に `SyncTokenManager.set_device_approval_callback` を自動結合。
     - `DeskPetSyncHandler._handle_auth_token`: ループバック（`127.0.0.1` / `::1`）からの要求は即時バイパス、外部IP端末は承認ダイアログを起動。拒絶時は即時 `403 Forbidden`。
3. **OpenCode GO 実機 kimi-k2.7-code 査読結果**:
   - Jev が選定した Moonshot Kimi（Thinkingモデル）による4000トークンの実機推論により、スレッド競合耐性・Fail-Closed 挙動・キー誤爆リスクの深層検証をクリア。
4. **テスト**:
   - `tests/test_device_connection_approval.py`（7件全件合格）。

### 20.14 多言語化（i18n）アーキテクチャとUIレイアウト耐性設計（Microcopy ＆ 文字数予算規約） (2026-09-20)
1. **背景とテキスト長膨張（Text Expansion Ratio）の課題**:
   - 表意文字（日本語）から表音文字（英語）への展開に伴い、文字数・横幅が平均 **1.3〜1.8倍（場合により2倍以上）** 膨張する。
   - 画面枠が狭小なスマホDesk Pet（PWA）、デスクトップペット頭上のキャンバス吹き出し、およびTkinter固定幅レイアウトにおいて、直訳を適用するとボタンのはみ出し、改行破綻、ラベル見切れ（Truncation）が不可避となる。
2. **引き算のMicrocopy規約（文字数予算・Character Budget）**:
   - **直訳の禁止**: 原文の意味を単に翻訳するのではなく、UI領域ごとに許容される文字数上限（Character Budget）を定め、動詞・名詞1語の短縮語（Microcopy）を厳選する。
   - **PWAボトムドック (Budget: 最大7文字)**:
     - 「タスク」➔ `"Tasks"`（5文字）
     - 「カレンダー」➔ `"Cal"`（3文字、アイコン併用）
     - 「日報」➔ `"Daily"`（5文字）
     - 「設定」➔ `"Config"` または `"Settings"`（6〜8文字、clamp縮小）
   - **承認アクションボタン (Budget: 各単語最大8文字)**:
     - 「承認する」➔ `"Approve"`
     - 「却下する」➔ `"Deny"`
     - 2ボタン並列（flex: 1）を維持し、縦積み崩れを構造防止。
   - **Jev安全審査バッジ (Budget: 最大14文字)**:
     - `🟢 Jev安全審査: ALLOW` ➔ `🟢 JEV: ALLOW`
     - 1行完結（`white-space: nowrap`）を死守。
3. **UIレイアウト3大領域の防御設計**:
   - **スマホDesk Pet PWA (`web_pet/`)**:
     - `lang.js` による辞書駆動レンダリング。
     - CSS `font-size: clamp(0.75rem, 2.5vw, 0.9rem)` と `min-width: 0` / `flex-shrink: 1` によるコンテナ追従。
   - **デスクトップ常駐ペット吹き出し (`ui/pet_window.py`)**:
     - キャンバスバブルの動的スケーリング（幅220px〜320pxの可変伸縮）。
     - Tkinter Canvas の単語単位自動折り返し（Word Wrapping）。
     - 長文セリフの2〜3行分割・ページャー化（クリック送り）。
   - **Tkinter 設定画面 (`ui/settings_window.py`)**:
     - 固定ピクセル指定（`width=N`）を廃止し、`sticky="ew"` および `grid_columnconfigure(1, weight=1)` によるAuto-fitレイアウト。
4. **多言語基盤アーキテクチャ (`i18n.py` ＆ `web_pet/lang.js`)**:
   - デスクトップ側: `i18n.py` の `t(key, **params)` にUIドメイン辞書（`ui.*`, `tray.*`, `dialog.*`）を拡充。
   - PWA側: `web_pet/lang.js`（`NeoLang.t(key)`）を新設し、ブラウザ設定（`navigator.language`）または手動トグルで言語即時切り替え。
5. **レッドチーム（devils-advocate）カオス破壊監査と6大防壁 (2026-09-20 適用)**:
   - **防壁1 (1000文字爆弾＆ペット窒息死防止)**: `ui/pet_window.py` の `draw_speech_bubble` に `max_chars=180`（超過時Truncate）および `max_height=140px`（clamp）を実装。
   - **防壁2 (スペースなし長大トークン横突き抜け防止)**: `_sanitize_wrap_text` により、25文字以上の空白なし英数字列を強制改行分割し、Tkinter Canvas の Word Wrapping 破壊を遮断。
   - **防壁3 (承認ボタン深海沈没防止)**: `web_pet/style.css` の `.approval-sheet-actions` に `position: sticky; bottom: 0; backdrop-filter: blur(4px);` を適用し、長文コマンド時でも親指位置に常時固定。
   - **防壁4 (PWA吹き出し縦貫通防止)**: `web_pet/style.css` の `.speech-bubble` に `max-height: 120px; overflow-y: auto; word-break: break-word;` を強制適用。
   - **防壁5 (文字数予算自己矛盾是正)**: `web_pet/lang.js` の `dock.settings` を 8文字の "Settings" から 6文字の "Config" へ是正し、iPhone SE (320px) でも `Setting...` と見切れないよう Character Budget を遵守。
   - **防壁6 (型汚染 ＆ 不正波括弧即死ガード)**: `i18n.py` の `t()` で `ValueError`（`Single '{'`）を捕捉し、`set_language` 冒頭で `isinstance(lang, str)` ガードを敷設。

### 11.13 深層コード監査に伴うP0/P1時限爆弾是正 ＆ 多言語化Phase 4 (2026-09-20 適用)
1. **P0 スレッド競合クラッシュの根絶 (`main.py`)**:
   - `api_agent_bridge.py` からのメッセージ受信用 `post_human_message` において、ワーカースレッドから `asyncio.create_task` を呼んでいたため `RuntimeError: no running event loop` で即死していた。
   - `async_mainloop` 起動時にメインループ参照 `app.loop = asyncio.get_running_loop()` を保持し、`asyncio.run_coroutine_threadsafe(agent.process_message(msg), app.loop)` を用いる安全なスレッド間タスク委譲に是正。
2. **P1 予定リマインダー二重発火の根絶 (`main.py`, `proactive_engine.py`)**:
   - `proactive_engine.check_event_reminders` と `reminder_engine.check_reminders` が同一カレンダー予定を重複スキャン・重複通知していた。
   - `proactive_engine.check_event_reminders` を no-op 化し、通知責務を `reminder_engine.py` に完全一本化。スケジューラ側の重複呼び出しも撤去。
3. **P1 繰り返しタスク自動生成時のDBカラム逆転汚染根絶 (`storage/task_repo.py`)**:
   - `complete_task` 内の繰り返しタスク INSERT 文において、`SELECT` カラム順序（`tags, list_id`）と `INSERT` カラム順序（`list_id, tags`）の逆転により `list_id` にタグ文字列が混入する汚染バグを是正。
4. **P1 監視ウォッチドッグの自爆ポート競合防止 (`local_sync_server.py`)**:
   - `ServerWatchdog` の失敗許容回数を 1 ➔ 3、タイムアウトを 1.0s ➔ 2.0s に緩和し、GCやLLM推論による一時遅延での不要な再起動ループ（ポート10048 WinError）を防止。
5. **多言語化 Phase 4 完遂 (`agent.py`, `i18n.py`, `ui/sticky_note.py`)**:
   - `agent.py`: プロンプト内の日本語規則ハードコードを `get_prompt_language_instruction()` に置換し、英語設定時は英語で指示・応答するよう動的制御。
   - `i18n.py`: 起動時に `.env` の `APP_LANGUAGE` を自動認識・適用する `_init_language_from_env()` / `reload_language_from_env()` を配備。
   - `ui/sticky_note.py`: 半透明スマート付箋のタイトル、プレースホルダー、空タスク通知、緊急度バッジを `i18n.t()` 化し、`subscribe_language_change` による動的再描画に対応。


## 21. OpenCode × Jev-MCP 自律マルチエージェント配線 (As-Built 2026-09-21)

AntiGravity で本番運用している「System One (Jev) × System Two (専門エージェント陣形)」を
OpenCode Desktop (v2.0.11) へ **同一の開発体験・安全規約・品質ゲート**として移植した。
詳細仕様は `docs/guides/OPENCODE_JEV_MULTIAGENT_INTEGRATION_SPEC.md`（v1.1.0 §0 As-Built）を正本とする。

### 21.1 3層アーキテクチャと配備ファイル
| 層 | 実体 | 配備先 |
|:---|:---|:---|
| System One | `jev-mcp`（`jev_route_agent` / `jev_guard_command`） | `~/.config/opencode/opencode.jsonc`（全プロジェクト共通） |
| System Two | `.opencode/agents/*.md` 11体（V2 `permissions` で最小権限） | プロジェクト（`.gitignore` 対象） |
| 知識・承認 | `codebase-memory-mcp` / `neo_hisho_bridge`（`HISHO_AGENT_NAME=OpenCode`） | `~/.config/opencode/opencode.jsonc`（全プロジェクト共通 / 2026-09-21 移設） |

### 21.2 二層防御（本設計の核心 / ADR候補）
- **第1層 = Jev Guard（確率的ソフト層）**: ミリ秒・約0.05円で大半の危険を高速に弾く。
  実測: `python -m pytest` → allow（0.99）、`git reset --hard` → deny（**確信度 0.39**）。
- **第2層 = OpenCode `permissions`（決定論的ハード層）**: 15の deny ルール（`rm -rf /`・`git reset --hard`・
  `git push --force`・`git clean -f`・`DROP TABLE`・`mkfs` 等）＋ シェル原則 `ask` ＋ 安全コマンド allowlist 10件。
- **設計判断**: 安全性の最終責任を LLM の確率出力に負わせない。Jev は高速フィルタ、保証は決定論的 ACL が担う。

### 21.3 ドリフト根絶（正本 → 生成物の一方向同期）
- 正本は `.agents/agents/*.md`（Antigravity 資産）。`tools/sync_opencode_agents.py` が
  Antigravity の `tools:` リストを OpenCode V2 の `permissions` へ翻訳し `.opencode/agents/*.md` を生成する。
- `--check` でドリフト検知（終了コード1）。生成物には正本ハッシュを刻印し、直接編集を禁止する。

### 21.4 OpenCode V2 仕様上の重要な発見（ファクト / 推測なし）
1. MCP は `mcpServers` ではなく **`mcp.servers`**（`type: "local"` / `command` は配列）。
2. エージェント権限は `tools:` ではなく **`permissions: [{action, resource, effect}]`**。判定は**後勝ち**。
3. **自動ロードされる指示ファイルは `AGENTS.md` のみ**。`instructions` フィールドは V2 では解決されない
   → よって `OPENCODE.md` は `AGENTS.md` §4 から参照させる二段構えとする。
4. V2 は **`.agents/skills/` を互換パスとして自動発見**する（プロジェクト専用スキルは移植不要）。

### 21.5 実機検証（2026-09-21）
| 検証 | 結果 |
|:---|:---|
| Jev Route（「UIボタンのタッチ判定を修正する」） | `pixel-frontend-designer` 66.0% 第1位 ✅ |
| サブエージェント実起動 | `agent-tester` を起動し回帰テスト実行（sessionID: `ses_f403c6456ffespdn2ra9zrqxQF`）✅ |
| 回帰テスト | **684〜686件 ALL GREEN**（failed=0 / errors=0 / 47〜54秒）✅ |
| 設定構文 | JSONC検証OK（グローバル2サーバー / プロジェクト44ルール）✅ |
| 独立査読 | `quality-reviewer` による多角査読（sessionID: `ses_f40392574ffeGcarX95KVihv67`）→ P0×1 / P1×6 を検出し全件是正 |
| 同期ツールのテスト | `tests/test_sync_opencode_agents.py`（22件 / 74 subtests）新設。全回帰 **709 passed / 3 skipped** |

### 21.6 独立査読（quality-reviewer）と是正記録（2026-09-21）

`quality-reviewer` を独立コンテキストで起動し、公式V2ドキュメントを正本として全成果物を査読させた。
判定は **CHANGES_REQUESTED**（P0×1 / P1×6）。以下を全て是正し、契約テストで凍結した。

| 指摘 | 内容 | 是正 |
|:---|:---|:---|
| **P0-1** | `git branch *` の allow が `git branch -D/-f/-m` を**無承認で**通す決定論的ホール | allow を読み取り専用形（`git branch` / `--list` / `-v` / `-a`）へ限定し、破壊形7パターンを deny に追加 |
| **P1-1** | エージェント権限に `shell` の allow を再宣言 → **後勝ち**でグローバル deny を上書きし得る | ポリシーテーブルから allow を全廃（`INHERIT_PROJECT_ACL = ()`）。「締める方向にのみ働く」不変条件をテストで凍結 |
| **P1-2** | 正本の `mainAgent: true` を捨て `mode: subagent` 固定 → `hisho-orchestrator` を primary に選べず**名乗りが形骸化** | `resolve_mode()` を新設し `mainAgent`/`subagent` から `all`/`primary`/`subagent` を導出（7体=all / 4体=subagent） |
| **P1-3** | `--check` が孤立生成物（改名の残骸）を検知できない | 孤立検出を追加。削除は `--prune` 明示時のみ（同意なき削除の禁止を遵守） |
| **P1-4** | `return 1 if warnings and not loaded else 0` が**恒偽**で、検証警告が CI を落とせない | 終了コード契約を実装（警告 or ドリフトで 1） |
| **P1-5** | 権限ポリシー未定義の新規エージェントで `KeyError` 即死 | 書き込み時は修正箇所を明示した `ValueError`、`--check` 時はドリフトとして報告 |
| **P1-6** | 同期ツールにテストが無い（AGENTS.md §2.9 TDD 違反） | `tests/test_sync_opencode_agents.py` を新設（Red→Green を実証: 29 failed → 22 passed） |
| P2-2 | Read-Only 7体が MCP 経由で書き込み可能 | `neo_hisho_bridge_*` の書き込み4ツールを deny に追加 |
| P2-4 | `*.db`（個人データ）の `read` が無保護 | `read *.db` / `*.db-wal` / `*.db-shm` を `ask` に追加 |
| P2-6 | 正本ハッシュがバイト列依存（CRLF で偽ドリフト） | 改行を LF へ正規化してからハッシュ算出 |
| P2-8 | 読み替え表が V1 用語（`bash`）のまま | `bash (V1) / shell (V2)` と併記 |
| P2-9 | 陣形数の表記不整合（10 vs 11） | 仕様書・ロードマップ・一覧・active_context を **11体** に統一 |

> **教訓（ボスのコード審美眼メモ）**: OpenCode の permission は **後勝ち**である。
> 「設定ファイルに deny を書いたから安全」ではなく、**後から追記されるルール（エージェント定義）が
> その deny を覆さないか**を常に確認する。今回はまさにこの1点が P0 と P1-1 の共通根因であった。

---

## 22. エージェント Hooks 設定ガイドウィザード ＆ 新・機能オンボーディングツアー設計 (v1.5.0)

### 22.1 課題とアーキテクチャ背景 (Why)
1. **エージェント側の導入摩擦ゼロ化**:
   - ネオ秘書くんの「離席中にエージェントが承認待ちで停止する痛点」の解消は、エージェント側（Antigravityの `PreToolUse` Hook や OpenCode の `hisho-approval-notify` プラグイン）との協調動作によって初めて成立する。
   - しかし、外部設定ファイル（`hooks.json` や `index.ts`）を手動配置する作業はユーザーにとって認知負荷が高いため、秘書くんアプリ側で「設定ガイドウィザード」と「セルフ診断（Pingテスト）」を提供し、導入を1分で完了させる必要がある。
2. **ツアー機能の最新化と国際化**:
   - 初期のオンボーディングツアー（`tour_engine.py`）は3ステップの静的案内のまま止まっており、Agent Bridge、スマホ遠隔承認、適応型0fps省電力、統合手帳、日英多言語切替といった現在のコア価値が網羅されていない。
   - 英語版ツアーを完備し、海外ユーザーにも「なぜネオ秘書くんが必要なのか」を直感的に腹落ちさせる。

### 22.2 Hooks 設定ガイドウィザード構成 (What)
- **UIコンポーネント (`ui/hooks_guide_dialog.py` / 設定画面タブ)**:
  - エージェント選択タブ（`Antigravity` / `OpenCode` / `Claude Code` / `Cursor` / `Codex`）。
  - 各エージェント向けの設定スニペットワンクリックコピー。
  - ローカル設定フォルダ自動検出＆ワンタップ自動配置ボタン（ファイル存在時はマージ確認）。
  - 「🔔 接続テスト（Ping）」ボタン: `POST /api/agent/ask_input` をテスト送信し、PCペットの `alarm_ask` とスマホDesk PetのBuzz振動が正しく発火するかをその場で確認。

### 22.3 新・機能オンボーディングツアー 4ステップ設計
1. **Step 1: 🎉 ようこそネオ秘書くんへ (`tour.welcome`)**:
   - デスクトップ常駐ペット、サークルメニュー、基本操作。
2. **Step 2: 📱 スマホとつなぐ卓上リモコン (`tour.mobile_pet`)**:
   - QRコードワンタップペアリング、適応型Canvas 0fps完全省電力、愛着と生活モーション。
3. **Step 3: 🤖 コーディングエージェント遠隔承認 (`tour.agent_bridge`)**:
   - 席を外してもAIが止まらない。Agent BridgeとHooksによる離席中のノールック承認。
4. **Step 4: 📔 統合手帳・カレンダー ＆ 言語設定 (`tour.notebook_i18n`)**:
   - TODO、習慣トラッカー、iCal連携、および日英動的切替。


## 23. OpenCode モデル選択 ＆ 入力待ち通知の設計 (2026-09-21 深夜セッション / ボス承認済み)

### 23.1 課題と設計判断（Why）
1. **モデル選択の帰属問題**: Antigravity は「サブエージェントごとにモデルを指定すると直列実行になる」制約を持つ。
   一方 OpenCode は `subagent` ツールの `model` 引数で動的に指定できる（実測済み）。
   両者は **同じ `jev-mcp` を共有**しているため、Jev の出力にモデル情報を足すと Antigravity 側が直列化してしまう。
2. **解決**: Jev を改造するのではなく **契約の境界を分ける**。
   - Antigravity … `jev_mcp_server.py`（2ツール / **変更禁止** / モデル情報ゼロ）
   - OpenCode … `jev_mcp_planner.py`（3ツール / モデル選択を追加）
   - `jev_guard_command` / `jev_route_agent` は **Antigravity 側の関数オブジェクトをそのまま import** して登録し、
     挙動がズレる余地を構造的に排除（`tests/test_jev_model_planner.py` の `assertIs` で凍結）。

### 23.2 モデル選定の3原則
| 原則 | 内容 |
|:---|:---|
| **一次情報はライブ** | `tools.opencode.models`（OpenCode自身が知る実在モデル）を毎回取得。キャッシュは保険のみ（実測: 既存キャッシュ37件中**10件が廃止済み**だった） |
| **候補はクライアントが渡す** | Jev はモデル名を知らない。MCPサーバーは `tools.opencode.models` を呼べないため、呼び出し側（エージェント）が実在候補を渡す |
| **高コストは構造で防ぐ** | 既定では承認帯（出力 $1.0/M 以上）を候補から除外。Jev は**選べない** |

### 23.3 コスト帯ポリシー（`model_policy.json`）
- **ボスが編集する唯一のファイル**。しきい値・役割別モデル・監査系を JSON で保持し、`model_catalog.py` が読み込む。
- 🟢 常用帯（< $1.0/M 出力）: 自動で使用可。実装の既定は `deepseek-v4.1-flash` / `glm-5.3-flash`（ボス指定）
- 🟡 承認帯（≥ $1.0/M 出力）: `ask_human_approval` による**スマホ承認必須**。監査は `glm-5.3` / `grok-4.6` / `kimi-k3`
- **B案（厳格運用）**: 指定モデル以外は候補から除外（安い逃げ道を廃止）。追随は `model_policy.json` への1行追記で完結。
- **ドリフト検知CLI**: `model_catalog.py --check --live-json <実在モデル一覧>` が ①推奨モデルの廃止 ②新モデルの出現 ③価格改定 を検知（終了コード1）。

### 23.4 入力待ち通知プラグイン（`hisho-approval-notify`）
1. **背景**: OpenCode が「⚠️ 権限が必要です」で止まっても、ボスが画面を見ていないと気づけず待ちぼうけになる
   （＝**ネオ秘書くんの存在意義そのもの**）。Antigravity は `PreToolUse` Hook で解決するが、OpenCode に Hook は無い。
2. **設計**: **Plugin** が `ctx.permission.hook("evaluate")` で権限評価の瞬間を捕捉し、
   イベントの **`effect: "ask"`**（＝人間の判断が必要）のときだけ通知する（`allow`/`deny` では鳴らさない＝スパム防止）。
3. **通知経路**: `POST /api/agent/ask_input`（**`wait_decision:false`**）→ `trigger_buzz()` ＋ `gui.set_pet_state("alarm_ask", 6000)` ＋ スマホプッシュ。
4. **安全性**: Bearer認証（`.sync_token`）／ localhost限定（サーバー側でも403で防御）／ **権限判定には一切干渉しない（観測のみ）** ／
   全例外をログして OpenCode を止めない（Fail-Safe）／ 同一要求は60秒クールダウン。
5. **実測**: ボスが実機で通知を受信（`HTTP 200 {"status":"queued"}`）。診断ログ `%TEMP%\hisho-notify.log` に全履歴。
6. **Gotcha（重要）**: `import { Plugin } from "@opencode/plugin"` は**この環境では解決できない**
   （`Cannot find package '@opencode/plugin'`）。`Plugin.define` の実体は素通し関数（`return plugin`）であるため、
   **import を省いて素のオブジェクトを default export** すれば等価（実測で解決・ホットリロードで反映）。

### 23.5 Antigravity への技術移管
同じ痛点を Antigravity 側でも解消するため、実測済みのAPI契約と落とし穴
（**`wait_decision:false` 必須**／Bearer認証／`_post_to_hub` の再利用／`PreToolUse` には allow/ask の区別が無いため逆allowlist方式）
を指示文として提供し、Antigravity 側の実装完了を確認した（2026-09-21）。

### 23.6 品質ゲート
- 独立査読（`quality-reviewer`）: P0×1（`git branch *` allow の決定論的ホール）/ P1×6 を検出し**全件是正**
- TDD: `tests/test_jev_model_planner.py` 34件（Red 29 failed → Green 22 passed の実証を含む）
- 全回帰: **753 passed / 2 skipped**

## 24. スマホ通知の Web Push API 導入 (As-Built 2026-09-22 / ロードマップ §13.19 第4項・手帳 TODO ID 30)

### 24.1 課題と設計判断（Why）
1. **構造的限界の確定**: 従来のスマホ通知は「PWA 開いている間の 2秒ポーリング（`/api/status` の `buzz` / `latest_notification`）」のみで、画面オフ・ブラウザ閉じ・スリープ中は**原理的に届かない**（2026-09-22 実測: 通知発火時 `devices.last_seen` = 901.7分前）。「席を外しても気づく」というコアバリューの成立のため **Service Worker + VAPID** を導入した。
2. **observe-only の維持（最重要制約）**: Push 送信は既存の通知入口（`handle_agent_ask` / `handle_agent_ask_input` / `handle_agent_notify` / `reminder_engine._dispatch`）に**後段追記**したのみで、権限判定・ポーリング契約・既存メソッド署名は一切変更しない。既存 763 テストが無修正で生きる。
3. **ノンブロッキング構造**: `push_sender.send_push_to_all_devices()` は **DB 読み取りと VAPID 準備（ミリ秒）を呼び出し元スレッドで同期実行**し、ネットワーク送信（秒）のみ daemon スレッドへ委譲する。バックグラウンドスレッドが DB ファイルを保持しないため、テスト環境の一時ファイル削除との競合 (WinError 32) も構造的に回避する。
4. **VAPID 鍵の単一行永続化**: 鍵は `vapid_keys` テーブルに PKCS#8 PEM で保存し**再生成しない**（再生成すると全端末の購読が無効化されるため）。公開鍵は `GET /api/push/vapid_key`（Bearer 認証必須）で配信する。

### 24.2 システム構成（データフロー）
| 層 | 実体 | 役割 |
|:---|:---|:---|
| 台帳 | `storage/push_subscription_repo.py` ＋ `push_subscriptions` テーブル | endpoint UNIQUE の購読 upsert・token_hash 単位一括削除 |
| 鍵 | `storage/vapid_key_repo.py` | P-256 鍵ペア生成（初回のみ）・`Vapid` インスタンス復元 |
| 送信 | `push_sender.py` | pywebpush 送信（timeout 10秒明示）・**404/410 の無効購読を自動掃除**・Fail-Safe（1件の例外で全送信を止めない） |
| API | `api_push.py` | `POST /api/push/subscribe` / `unsubscribe`（入力長上限 2048/512 を 422 で拒否）／`GET /api/push/vapid_key`。Bearer 認証は `do_POST`/`do_GET` の共通経路で強制 |
| 配線 | `local_sync_server.py` `POST_PATH_HANDLERS` / `GET_PATH_HANDLERS` | ルート登録のみ（認証・監査は既存経路を流用） |
| PWA | `web_pet/sw.js` | `push` イベント → OS 標準通知表示 ＋ IndexedDB (`neo-hisho-push`) へ未読記録。`notificationclick` → アプリ復帰 |
| PWA | `web_pet/pet_push.js` / `push_common.js` | SW 登録・購読登録・**起動時の取りこぼしまとめバナー（未読バッジ）**。通知許可は初回タップ後（ジェスチャ要件対策） |

### 24.3 対象イベントと通知形式
| イベント | title | tag / event_type |
|:---|:---|:---|
| 承認待ち (`/api/agent/ask`) | `⚠️ 承認待ち` | `approval_request` |
| 質問 (`/api/agent/ask_input`) | `💬 質問` | `ask_input` |
| 作業完了 (`/api/agent/notify`) | `✨ {agent_name} 完了` | `agent_notify` |
| 予定・タスクリマインダー (`reminder_engine._dispatch`) | `⏰ リマインダー` | `reminder` |

### 24.4 品質ゲートと運用メモ
- TDD: `tests/test_web_push_server.py` **24件**（repo CRUD / VAPID 永続化 / 404・410 掃除 / 例外継続 / ノンブロッキング / API 入力検証 400・403・422 / 配線）
- 全回帰: **785 passed / 2 skipped**（旧基線 761+2 からの純増 24件、既存テスト無修正）
- 実機 E2E (2026-09-22 16:58): HTTPS (Tailscale) 購読 → **画面OFF で OS 通知受信**（FCM 201 受理）→ 起動時まとめバナー表示を確認。凡例: `インストール済み PWA「ネオ秘書くん」名義で通知表示`
- 依存追加: `pywebpush==2.5.0` / `py-vapid==1.9.4`（requirements.txt ピン留め済み）
- **Gotcha**: ① 秘書くんアプリ本体は Python 変更の**再起動が必要**（PWA 側 JS は保存即反映）② 従来ポーリングは併存（撤去しない＝後退リスクゼロ）③ OpenCode Plugin v1.1（`hisho-approval-notify`）による `question` 回答待ち通知（同日実装）と本機能は相互補完関係にある

## 25. 起動時 LLM モデル同期の設定済みプロバイダ限定 (As-Built 2026-09-22 / ロードマップ §13.19 第5項・手帳 TODO ID 31)

### 25.1 課題と設計判断（Why）
起動時の `llm_factory.sync_all_discovered_models()` は `LLMProvider` 全10プロバイダを無条件巡回し、APIキー未設定（openai/groq/openrouter）・ローカルサーバー未起動（ollama/lm_studio/custom_openai）の6プロバイダで**確定失敗のネットワーク試行＋ERROR ログ＋フォールバックロード**を毎回発生させていた（実測約4.6秒の巡回・ERROR 6件）。引き算の美学により「設定済み・呼び出し可能性のあるものだけ」を巡回するゲート（`LLMFactory.should_probe_provider`）を導入した。

### 25.2 ゲート規則
| プロバイダ種別 | 判定 | 根拠 |
|:---|:---|:---|
| 現行選択中 | 常に巡回 | 動作保証のため |
| LOCAL_GGUF | 常に巡回 | ローカルディレクトリスキャンのみで通信が無い |
| クラウド系（`api_key_env` あり） | `is_provider_configured() == True` のみ | 既存の60秒TTL判定（ダミーキー除外付き）を再利用 |
| Ollama / LM Studio | TCP プローブ（`_probe_endpoint`・0.5秒タイムアウト）成功時のみ | アプリ起動と無関係に生滅するローカルサーバーのため、キー判定ではなく疎通確認が適切 |

- 未起動・未設定の正常系扱い: 巡回は「⏭ スキップ」INFO ログ＋`"skipped: 未設定・未起動"` の結果記録で静かに省略する（ERROR ログは出さない）。
- ゲートは `_sync_one` 内にあるため設定画面からの手動同期にも同様に適用される。ただし対象外プロバイダはキー欠落・サーバ未起動により取得が確定失敗するため、手動同期で失われる実効機能は無い（フォールバック一覧はキャッシュ済みで表示に影響しない）。

### 25.3 品質ゲート
- TDD: `tests/test_llm_factory_sync_gating.py` **8件**（Red 8 failed → Green 8 passed の実証を含む）
- 全回帰: **793 passed / 2 skipped**（環境条件 skip は Tk 初期化不可×2 またはアプリ起動中ポート競合×2）
- 独立検証（`agent-tester`, `ses_f37d4c53bffe7PSGbsxEuFqXK3`）: **PASSED**。実測で未設定7プロバイダのスキップ＆ERROR 0件を確認
- Gotcha: `_compute_provider_configured` は `load_dotenv(override=True)` で実 .env を読み戻すため、テストでは `llm_factory.load_dotenv` も遮断する必要がある

## 26. スコープ縮小（引き算）決定 — Whisper / LifeCoach 撤去予定 (2026-09-22 ボス決定 / 計画)

### 26.1 背景と設計判断（Why）
総合コードレビュー（`ruthless-code-evaluation`: 引き算 D評価 / `codebase-design`: shallow 分析）が「コアバリュー（Agent Bridge + Desk Pet）以外の百貨店化」を指摘。ボスはこれを受け、以下2機能の撤去を決定した（AGENTS.md §1.4 引き算の美学の実践第1号）。実施は **P0 セキュリティ修正完了後**（手帳 TODO ID 35 / 36・ロードマップ §13.19 第8/9項に同時起票）。

| 対象 | 撤去理由（ボス判断） | 主なフットプリント |
|:---|:---|:---|
| **Whisper 音声認識（＋休眠中の Web Speech 音声入力）** | 実測で認識精度が低すぎた。**スマホOS標準の音声入力（キーボードのマイク）** で代替可能となり、内蔵する必然性が消滅。ボス実使用でも「音声機能が欲しい場面がほぼ無かった」ことを確認（2026-09-22 全撤去決定） | `whisper_transcriber.py`（199行・faster-whisper は optional import で requirements 未記載）／`api_tasks.action_transcribe_voice`／`web_pet/pet.js` の `startVoiceInput`＋`_sendVoiceToWhisper`（Web Speech 認識も含む）／`tools/e2e_voice_check.py`／設定トグル（`voice_input_enabled`）／関連テスト・CHEAT_SHEETS |
| **LifeCoachEngine** | 2時間ごとの LLM 呼び出しコストに対し、ボスの行動変容に寄与していない（＝通知ノイズ） | `life_coach_engine.py`（511行・LLM/テーブル/スケジューラ/サジェスト連携）／`main.py` 配線／status payload の `life_coach` フィールド／関連テスト・i18n |

### 26.2 誤削除の禁止事項（Important）
- **`LifeDreamer`（`life_dreamer.py`: 天気・生活イベント＝ペットの情緒・コアバリュー）は残す**。LifeCoach との混同による誤削除を固く禁止する。
- **`toggleBriefingSpeech`（TTS 読み上げ・朝会ブリーフィング「🔊 音声で聴く」）は残す**。音声入力とは別機能であり、稼働中・依存ゼロ（ブラウザ標準 API のみ）。2026-09-22 ボス決定。
- 撤去時は対象テストを同時に削除し、全回帰 Green を確認する。Git 履歴で復元可能（セーブポイント不要論の根拠）。

### 26.3 実施手順（各5分マイクロタスク粒度）
1. 対象テスト同時削除 → `pytest tests/ -q` 全回帰 Green 確認
2. Python 側撤去（エンジン/アクション/配線/payload）
3. PWA 側撤去（マイクUI・関連i18n）
4. ドキュメント4点セット同期（本節の「予定」→「完了」更新・ロードマップ・一覧・active_context）





