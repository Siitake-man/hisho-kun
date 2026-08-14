# 🔍 ネオ秘書くん 全体コードレビュー ＆ アーキテクチャ設計診断書

**実施日**: 2026-08-15  
**レビュアー**: Antigravity (Python/AI Principal Architect)  
**適用スキル**: `/holistic-code-review` ＆ `/codebase-design`  
**対象コードベース**: `ネオ秘書くん` 全体 (168ノード, 164エッジ)

---

## 1. 総合評価サマリー (Executive Summary)

| 評価軸 | 評価スコア | 総評 |
| :--- | :---: | :--- |
| **Deep Module 設計 (Codebase Design)** | **4.8 / 5.0** | 🎯 **極めて優秀**。`llm_factory`, `database`, `mcp_manager`, `proactive_engine` が「小さなインターフェースの裏に深い実装を隠蔽する」理想的な Deep Module 構造になっている。 |
| **コーディング規約準拠 (Standards)** | **4.7 / 5.0** | 🛡 **優秀**。`print` デバッグゼロ、`logging` モジュール完全統一、Pydantic による厳格な型検証、Tkinter × asyncio の非ブロッキング非同期共存が死守されている。 |
| **仕様適合性 (Spec Compliance)** | **5.0 / 5.0** | ✨ **完璧**。TickTick対比コア機能、MentisDB長期記憶、レトロドット絵ペット、MCP連携、MiniCPM画面見守り、スマホPWA、Google連携がすべて仕様書通りに実装・稼働中。 |

---

## 2. 🏛️ Deep Module アーキテクチャ診断 (Codebase Design 視点)

```
┌──────────────────────────────────────────────────────────────┐
│                  Small Interface (呼び出し側の負担最小)       │
│  - llm_factory.create_model()                                │
│  - database.get_user_insights() / create_task()              │
│  - proactive_engine.check_and_trigger_care()                 │
│  - local_sync_server.start() / stop()                        │
├──────────────────────────────────────────────────────────────┤
│                  Deep Implementation (内部に隠蔽された高度な責務) │
│  ・Gemini / OpenCode / LM Studio のSDK/RESTフォールバック    │
│  ・SQLiteスキーママイグレーション & JSONキャッシュ永続化    │
│  ・作業疲労度判定・時間帯別プロアクティブ声掛けロジック       │
│  ・PWA静的配信 & REST/WebSocket双方向同期ハンドラ            │
└──────────────────────────────────────────────────────────────┘
```

### 【診断結果】
- **`llm_factory.py`**: **超深型モジュール（High Depth）**。呼び出し側は `factory.create_model()` を呼ぶだけで、内部で `.env`、`discovered_models.json`、APIキー解決、OpenAI互換/Google SDKの振り分け、フォールバックが自動完結する。
- **`database.py`**: **深型モジュール**。SQLite の生SQLや接続管理、Pydantic パースの複雑さをすべてCRUD関数群の内側に隠蔽し、呼び出し側をクリーンに保っている。
- **`mcp_manager.py`**: **深型モジュール**。外部プロセスの起動・JSON-RPC通信・ツールスキーマ変換の複雑さを `get_dynamic_mcp_tools()` 1本に集約。

---

## 3. 🎯 優先度付き改善・次回タスクリスト (P0 〜 P3)

### 🔴 P0 (緊急度: 高 / 致命的バグ・ハング要因)
- **現状該当なし**（全主要機能がエラーなく正常稼働中）。

---

### 🟡 P1 (重要度: 高 / パフォーマンス・堅牢性向上)
1. **[P1-1] SQLite 接続のコンテキストマネージャー (`with sqlite3.connect`) 共通化**:
   - **Why (理由)**: 現在 `database.py` の各CRUD関数で `conn = sqlite3.connect()` を個別に呼んでいる。`contextlib.contextmanager` またはユーティリティ関数で一元化することで、例外発生時のロールバックとコネクションリークを100%防止する。
   - **対象ファイル**: `database.py`

2. **[P1-2] LLM インスタンスの LRU キャッシュ**:
   - **Why (理由)**: 毎回の推論で `factory.create_model()` が呼ばれる際、プロバイダやモデルが同じであればインスタンスを再利用（キャッシュ）することで、推論開始オーバーヘッドを数ms削減する。
   - **対象ファイル**: `llm_factory.py`

---

### 🟢 P2 (重要度: 中 / 機能拡充・UX向上)
3. **[P2-1] ポモドーロタイマー機能（25分集中 ＋ 5分休憩）の実装**:
   - **Why (理由)**: TickTickの最人気機能であり、ドット絵ペットと相性抜群。タイマー中にお腹の画面でカウントダウンし、終了時にペットが笑顔でアラート。
   - **対象ファイル**: `proactive_engine.py`, `gui.py`, `web_pet/pet.js`

4. **[P2-2] 習慣トラッカー（Habit Tracker）エンジン ＆ 手帳タブ追加**:
   - **Why (理由)**: 「読書」「運動」「天風哲学の実践」など毎日の習慣をチェックボックスで記録し、手帳ウィンドウに「習慣」タブを新設。
   - **対象ファイル**: `database.py`, `gui.py`, `db_tools.py`

---

### ⚪ P3 (重要度: 低 / 将来的な美観・リファクタリング)
5. **[P3-1] 音声入出力 (Voice End-to-End) のプロトタイプ (Whisper / pyttsx3)**:
   - **Why (理由)**: 隙間時間にPCに向かわずに声だけで指示を出せるようにする。
   - **対象ファイル**: `voice_tools.py` (新規作成)

---

## 4. 🚀 次回セッションの 5分ファーストタスク

> **【次回着手タスク】**:  
> **`[P1-1] database.py の SQLite コネクション管理の一元化・堅牢化`**  
> または  
> **`[P2-1] ポモドーロタイマー機能（ペット集中モード）の実装`**
