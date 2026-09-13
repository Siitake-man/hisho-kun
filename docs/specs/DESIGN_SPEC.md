# システム設計書: Neo-Secretary (ネオ秘書くん) Python Agent Edition

- **最終更新日時**: 2026-09-13 23:05 (🌐 **Section 12 Global Showcase ＆ Cheat Sheets 英語版配備 ＆ Qiita記事完全配備版**)
- **Architecture**: Python Desktop App with LangGraph & PWA Mobile Approval Remote

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

### Table: user_insights (MentisDB型 ユーザー長期知見テーブル - 新規追加)
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

### 5.2 MentisDB型 ユーザー知見蓄積エンジン (Long-Term Memory)
1. **知見の自動抽出**: 会話の中からユーザーの制約・好み・生活リズムを検知し、`user_insights` テーブルへ永続化。
2. **コンテキスト注入**: 推論時に重要度の高い知見（上位5件）をシステムプロンプトへ自動挿入。

### 5.3 Tools for Agent
- **Calendar & Task Manager**: `create_event_tool`, `get_upcoming_events_tool`, `create_task_tool`, `list_tasks_tool`, `complete_task_tool`
- **Sticky Note Manager**: `create_sticky_note_tool`
- **MentisDB Long-Term Memory**: `remember_user_insight_tool`, `get_user_insights_tool`
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
  - ポート `8765` で静的ファイル配信 ＆ `/api/status`, `/api/action`, `/api/link_status`, `/api/test_buzz` を提供。
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
- **ガイド**: `docs/guides/TAILSCALE_SETUP.md` 新設（Tailscaleインストール→`tailscale serve 8765`→ホスト名登録までの手順を記載）
- 実機確認は「カフェ環境でのE2Eテスト」として後工程に記録

## 7. Google Workspace (Googleカレンダー ＆ Gmail) ダイレクト連携 🌟
- **モジュール**: `google_workspace_tools.py`
- **OAuth2 Token Flow**: `google_credentials.json` をプロジェクト直下に配置するだけで、Google公式APIを通じたスケジュール参照・登録、および未読メール検索・要約が可能。
- **セーフフォールバック**: 認証ファイル未配置時はローカル手帳およびiCalendarエクスポートへ自動フォールバック。
- **秘密iCal URL 連携 [✅ 実装済み 2026-08-25]**: `ics_tools.py` の `sync_calendar_from_ical_url()` により、Googleカレンダーの「予定の取得用の秘密のアドレス (iCal)」を貼るだけで**OAuth・APIキー・クライアントシークレット不要**で予定を読み取り専用同期（30分間隔自動＋手動ボタン）。Google由来予定は `google_event_id` で管理し重複なし。※設定画面に取得手順・読み取り専用の注意書きを表示。

## 8. 最新マスターロードマップ
1. **Phase A〜E: デスクトップ常駐MVP・LangGraph・MentisDB・手帳・PWA・MCP自動登録 [✅ 完了]**
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
- **認証・認可フロー (`_check_auth`)**:
  1. Bearer トークンを抽出し、`SyncTokenManager` で署名照合。
  2. SHA-256 ハッシュを算出し、`database.get_device_by_token_hash` を照会。
  3. `is_revoked == 1`（失効済み）の場合は即座に **403 Forbidden** で通信遮断。
  4. 有効端末は `touch_device_last_seen` で接続日時とIPを自動更新（DBロック発生時も通信を巻き込まない Fail-Safe 例外防護）。
  5. 未登録端末は `register_device` で自動登録。
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

---

## 11. 将来アーキテクチャ設計: Codebase Design ＆ Seam 分割 (v1.1.0)

### 11.1 背景と課題（Shallow Module化の危機）
- **現状のホットスポット**:
  1. `web_pet/pet.js` (3,335行): 通信、UIバナー、スプライト管理、歩行物理、歓喜アニメ、パーティクル、隠しコマンドの7つの異なるライフサイクルが単一ファイルに同居。
  2. `database.py` (2,498行): タスク、カレンダー、習慣、MentisDB知見、監査ログの全CRUDが単一ファイルに集中。
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
- `database/insight_repo.py`: MentisDB（ボスの知見・トリセツ管理）
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