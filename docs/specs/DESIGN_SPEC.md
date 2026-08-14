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
1. **Desktop Pet Window**: 透過ウィンドウ上のドット絵ペット
2. **Speech Bubble (吹き出し)**: レトロ枠線の会話バルーン ＋ 右上「⚙」設定メニュー
3. **Calendar/Task Window**: 手帳風の呼出式ウィンドウ
4. **Settings Dialog (設定画面)**: APIキー・モデルプリセット・Base URLの編集・保存ダイアログ

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

古いスマートフォン（Android / iOS）を机の傍らに置き、**「外付けスマートディスプレイ／相棒端末」** として活用するアーキテクチャ。
- **PWAフロントエンド (`web_pet/`)**:
  - GameBoy風レトロ筐体デザイン、32x32ドット絵アニメーション（待機/瞬き/思考中/笑顔）。
  - ワンタップTODO完了チェック、つつきリアクション。
  - スマホのブラウザから「ホーム画面に追加」するだけでネイティブアプリ化。
  - **動的接続設定**: 画面右上「⚙」からPCのIPアドレス（例: `http://192.168.1.15:8765`）をいつでも変更可能。
- **PC側 ローカル同期サーバー (`local_sync_server.py`)**:
  - ポート `8765` で静的ファイル配信 ＆ `/api/status`, `/api/action` を軽量提供。
  - Web Bluetooth (BLE) および ローカルWi-Fi の両対応。

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
7. **Phase 7: ポモドーロタイマー ＆ 習慣トラッカー ＆ 音声入出力 (Whisper/TTS) [🚧 次期着手]**


