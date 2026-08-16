# システム設計書: Neo-Secretary (秘書くん3) Python Agent Edition

**Based on**: 秘書くん Modern 設計書 (by Manus AI) v1.0.0
**Architecture**: Python Desktop App with LangGraph

## 1. プロジェクトの定義
Manusが設計した「秘書くん Modern (Web版)」の機能とデザイン美学を、Python/TkinterおよびLangGraphを用いた「自律型デスクトップエージェント」として再実装（ポーティング）する。

### コア・コンセプト
1.  **Retro Modern UI:** ドットフォント(DotGothic16)とブラウン系配色を用いた「懐かしくも新しい」デザイン。
2.  **Local First & Agentic:** クラウド（Web）ではなくローカルPCに常駐し、ユーザーのコンテキストを理解して自律的に動く。
3.  **Educational:** AIラボでの学習用教材として、LangGraphによるステートマシン制御を実装の中心に据える。

## 2. エージェント・アーキテクチャ (LangGraph & Multi-LLM Factory)

### 2.1 Multi-LLM Factory (動的モデル切り替え)
OpenAI互換プロトコルを活用し、用途に応じてLLMバックエンドを動的に切り替えるファクトリ層を導入する。
- **OpenCode GO (DeepSeek-Flash / V3 / R1)**: 爆速・高精度のクラウド推論（日常のメイン頭脳）
- **LM Studio (Local LLM)**: ローカル完結・完全オフライン・機密保護
- **Google Gemini (Gemini 2.5 Flash)**: クラウド標準バックエンド
- **動的切り替え**: UI上の右クリックメニューから即座に切り替え可能。

### 2.2 State Definition (Graphの状態)
エージェントは以下の状態を持ち回る。
- `messages`: 会話履歴 (HumanMessage, AIMessage, ToolMessage)
- `current_plan`: 現在実行中のタスク計画
- `user_approval`: 承認ステータス (Pending/Approved/Rejected)
- `vision_context`: 画面認識データ（スクリーンショット・OCR・UI解析結果）

### 2.3 MemorySaver (記憶の永続化)
最新のLangGraphに搭載された `MemorySaver` (Checkpointer) を用いて、会話の文脈を永続化する。

### 2.4 Workflow (Nodes & Edges)
1.  **Planner Node:** ユーザーの入力や時間トリガー、画面状況からツール呼び出しを自律判断。
2.  **Executor Node (Tools):** DB操作、カレンダー、付箋、画面認識、外部エージェント連携を実行。
3.  **Human Review Node:** 重要な操作（削除、外部送信等）の前にユーザーの承認を待機。

### 2.5 非同期処理の堅牢化 (Async Native)
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
  - **多彩なキャラクタースキンシステム（将来展望）**:
    - 🍄 **かわいらしいキノコ君**（胞子を飛ばしてひらめく）
    - 🐛 **ニャッキ風3本毛の棒人間**（元祖秘書くんリスペクト・手足をパタパタ）
    - 🦭 **もちもちアザラシ**（ゴロゴロ転がって癒やす）
    - 🐻 **まるまるころころウォンバット**（四角いうんち？ではなくドット絵でトコトコ歩く）
  - **縦置き・横置きレスポンシブ**:
    - 縦置き (Portrait): ヘッダー（時計・ポモドーロ）＋状況カード＋ドット絵ペット＋親指特大承認ボタン。
    - 横置き (Landscape): 左ペイン（ペット・時計・ポモドーロ）＋右ペイン（状況ログ・承認/拒否/説明ボタン）。
  - **ウィジェット切替**: デジタル時計、ポモドーロタイマー、ログ展開、常時画面ON (Wake Lock)。
  - **双方向リンク死活監視 ＆ 呼び出しテスト**:
    - リアルタイムPing表示（`LINKED 15ms`）、PCからの遠隔呼び出し（Buzz振動）、スマホからのPingテスト。
- **PC側 ローカル同期サーバー (`local_sync_server.py`)**:
  - ポート `8765` で静的ファイル配信 ＆ `/api/status`, `/api/action`, `/api/link_status`, `/api/test_buzz` を提供。
  - **Agent Bridge Hub**:
    - Claude Code, Codex, Antigravity, Cursor, Aider 等のコーディングエージェントからのコマンド実行許可要請を受け付け、スマホへリアルタイム中継。
    - スマホ側での「承認 (Approve)」「拒否 (Reject)」「説明 (Explain)」の判定を即時レスポンス。
  - **オフライン完結**: Wi-Fiなし・外出先でもBluetooth PAN / PCモバイルホットスポットで100%動作。

## 7. Google Workspace (Googleカレンダー ＆ Gmail) ダイレクト連携 🌟
- **モジュール**: `google_workspace_tools.py`
- **OAuth2 Token Flow**: `google_credentials.json` をプロジェクト直下に配置するだけで、Google公式APIを通じたスケジュール参照・登録、および未読メール検索・要約が可能。
- **セーフフォールバック**: 認証ファイル未配置時はローカル手帳およびiCalendarエクスポートへ自動フォールバック。

## 8. 将来ロードマップ
1. **Phase 1: デスクトップ常駐MVP [✅ 完了]**
2. **Phase 2: Multi-LLM Factory ＆ 代表的モデル動的選択 [✅ 完了]**
3. **Phase 3: MentisDB型・長期記憶エンジン ＆ ドット絵ペット化 [✅ 完了]**
4. **Phase 4: TODOタスク手帳統合 ＆ MCP動的管理設定UI [✅ 完了]**
5. **Phase 5: MiniCPM型 画面見守り (Vision) ＆ 自律プロアクティブ健康ケア ＆ スマホDesk Pet PWA [✅ 完了]**
6. **Phase 6: Google Workspace Direct連携 ＆ iCalendar (.ics) 同期 [✅ 完了]**
7. **Phase 7: MiniCPM級ペット体験 ＆ スマホDesk Pet 承認コクピット (Agent Bridge Hub) [✅ 完了]**
8. **Phase 7.5: スマホDesk Pet 最適化 (画面占有ゼロ化 / スリープ防止 / ポモドーロ同期 / 自律生活) ＆ Codex/Agent Bridge 実動連携 [✅ 完了]**
9. **Phase 8: キャラクタースキン（キノコ君・棒人間・アザラシ・ウォンバット） ＆ 社内配布用 1クリック起動パッケージ ＆ 習慣トラッカー ＆ 音声対話 (Whisper/TTS) [🔲 次期予定]**



