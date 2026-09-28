<!--
  Cline 引き継ぎ指示書 (prompt_for_cline_20260901.md)
  更新日時: 2026-09-01 23:30
  更新内容: P2①第二段 (DB戻り値モデル化) も完了をマーク。タスク6の残は P2③分割リファクタのみ
-->

# 🤖 Cline 引き継ぎ指示書 (2026-09-01)

## 📌 現在のステータス ＆ 参照ドキュメント
- **ネオ秘書くん v1.0.0 社内配布パッケージング完了**:
  - `dist/NeoHisho_v1.0.0_win64.zip` (106.0 MB) ビルド完了・社内周知済み！
- **マルチペルソナ全体コードレビュー報告書（必読）**:
  - 📄 [`docs/code_review_report_20260901.md`](file:///c:/Users/bonob/OneDrive/ドキュメント/AntiGlavity/ネオ秘書くん/docs/code_review_report_20260901.md) （5大ペルソナ診断・スコア）
  - 📄 [`docs/code_review_report_20260901_3rounds.md`](file:///c:/Users/bonob/OneDrive/ドキュメント/AntiGlavity/ネオ秘書くん/docs/code_review_report_20260901_3rounds.md) （3周徹底解剖・詳細分析）
- **ボスの開発哲学・世界水準評価 対話録（背景コンテキスト）**:
  - 📄 [`docs/handover/conversation_review_and_philosophy_20260901.md`](file:///c:/Users/bonob/OneDrive/ドキュメント/AntiGlavity/ネオ秘書くん/docs/handover/conversation_review_and_philosophy_20260901.md) （ボスの問いかけとアーキテクト評価の全記録）

---

## 🎓 【必読】ボスの4大弱み克服 ＆ Cline開発規約
Clineはタスク実装にあたり、単にコードを自動修正するだけでなく、ボスが「自立した一流アーキテクト」へ進化できるよう、以下の4原則を徹底してください：

1. **コード審美眼・監査力の育成**:
   - 修正やリファクタリングを行った際は、「なぜその型にしたのか」「なぜその例外処理が必要なのか」のWhy（技術的根拠）をコミットログや報告で言語化し、ボスのコードリーディング筋力を鍛えること。
2. **TDD（テスト駆動開発）の徹底**:
   - P2〜P3の実装時は、必ず「先に失敗するテストコード（Red）」を作成・確認してから本体実装を行い、デグレを構造的に防ぐこと。
3. **引き算の美学（スコープ削減）**:
   - コアバリュー（Agent Bridge + Desk Pet）に関係のない不要な機能追加は一切行わず、コードのシンプル化・共通化・モジュール分離を最優先とすること。
4. **ゼロトラスト・セキュリティ**:
   - 「ローカル環境だから」という甘えを排し、APIエンドポイントの型バリデーション（Pydantic DTO）やサニタイズを厳格に実装すること。

---

## 🎯 レビュー指摘事項の対応タスク一覧（優先度順）

以下のタスクは、上記コードレビュー報告書の指摘事項をそのまま5分マイクロタスクに分解したものです。優先度順に実装・テストを進めてください。

---

### 🔴 【P0】即時対応（ランタイム安定性・データ保全）— ✅ **2026-09-01 完了（Cline実装・全177テストOK）**

#### 1. SQLiteの接続時TRUNCATEチェックポイント廃止 ＆ 自動化 — ✅ 完了
- **対象ファイル**: `database.py` (L54-58付近)
- **問題（Why）**: 接続ごとに `wal_checkpoint(TRUNCATE)` を呼んでいるため、スマホからの高頻度ポーリング時にI/O競合・ロック遅延を招く。
- **改修内容（How）**:
  - `conn.execute("PRAGMA wal_autocheckpoint=1000;")` を設定し、接続時の手動TRUNCATEチェックポイント呼び出しを削除する。
- **検証**: `pytest tests/test_packaging_support.py tests/test_task_lists.py` → 実環境は pytest 未導入のため `python -m unittest` で実施（26テストOK）

#### 2. 管理者権限フォルダ実行時の AppData 自動フォールバック — ✅ 完了
- **対象ファイル**: `app_paths.py`
- **問題（Why）**: `C:\Program Files` などの書き込み権限がないフォルダに解凍された場合、PermissionError でクラッシュする。
- **改修内容（How）**:
  - `get_app_root()` 内で書き込みテスト（一時ファイル作成）を行い、失敗した場合は `Path(os.environ.get("APPDATA", "~")) / "NeoHisho"` を返す安全フォールバックを実装する。
- **検証**: `pytest tests/test_packaging_support.py` → `python -m unittest tests.test_packaging_support` で実施（新規 `TestAppRootWritableFallback` 3ケース含む全13テストOK）

---

### 🟡 【P1】短期対応（セキュリティ ＆ 外部障害耐性）— ✅ **2026-09-01 完了（Cline実装・全182テストOK）**

#### 3. LLM API呼び出しのタイムアウト境界 ＆ 縮退通知の統一 — ✅ 完了
- **対象ファイル**: `llm_factory.py`, `agent.py`, `proactive_engine.py`
- **改修結果（ファクト）**:
  - `llm_factory.py`: `LLM_REQUEST_TIMEOUT_SEC=15.0` 定数新設。Gemini (`request_timeout`) / Claude・OpenAI互換 (`timeout` + `max_retries=1`) に適用。LOCAL_GGUFはプロセス内推論のため対象外
  - `is_llm_network_failure()` 新設（タイムアウト・429等を分類）＋ `LLM_NETWORK_FALLBACK_TEXT = "🌐 通信が途切れました。後ほど再試行します。"` で縮退通知を統一
  - `agent.py` planner_node / `main.py` `_process_message` の両exceptで分岐適用
  - **※ `proactive_engine.py` はLLMを呼び出していないことを実コードで確認**（プリセット台詞のみ。レビュー文書の対象指定誤りと判定）
- **検証**: py_compile OK / 全177テストOK（当時）＋ 分類関数の単体検証 OK

#### 4. 設定画面への「スマホ連携 全解除（トークン再生成）」ボタン追加 — ✅ 完了（※コミットは中核機能のみ）
- **対象ファイル**: `ui/settings_window.py`, `local_sync_server.py`
- **改修結果**:
  - `local_sync_server.py`: `SyncTokenManager.regenerate()` 新設 — 旧トークンの全セッションを即時無効化し新トークンを永続化
  - `ui/settings_window.py`: 外部ツールタブに赤系カード「🚫 スマホ連携をすべて解除（トークン再生成）」＋確認ダイアログ付きハンドラ `_revoke_sync_token()` 実装
  - `tests/test_sync_token_regenerate.py` 新設（5シナリオ・実トークン保護のためテンポラリ差し替え方式）
- **検証**: 全182テストOK / test_sync_auth + test_sync_lan_selfheal 10件OK
- **⚠️ コミット留意点**: `ui/settings_window.py` は本対応以前から未コミット変更（モデルDL GUI関連）が混在しているため、`local_sync_server.py` + 新規テストのみコミット済み (`67d4797`)。settings_window の取り込みはボス手動確認推奨

---

### 🟢 【P2】中期対応（アーキテクチャ深化 ＆ 型安全性）

#### 5. DB戻り値・データモデルの Pydantic DTO 完全移行 — ✅ 第一段完了 (2026-09-01)
- **対象ファイル**: `database.py`, `db_tools.py`, `local_sync_server.py`
- **問題（Why）**: 一部の関数で `dict` 生辞書を受け渡しているため（Primitive Obsession）、キー名ミスによる実行時エラーのリスクがある。
- **改修内容（How）**:
  - 全てのDB操作関数の戻り値を Pydantic モデル（`TaskResponse`, `EventResponse` 等）に厳格に統一する。
- **改修結果（第一段）**:
  - `sync_dtos.py` 新設: `/api/status` (`StatusResponse`) と `get_tasks_view` アクション (`TasksViewResponse`) のレスポンス契約を Pydantic v2 で型付け
  - 設計: 既知フィールド厳格検証 ＋ 未知フィールドは `extra=allow` 透過 (PWA契約保護) ＋ ValidationError時は生辞書フォールバック (可用性優先の縮退設計)
  - `local_sync_server.py` L951 (status) / L1560 (tasks_view) に組み込み
  - **ファクト更正**: 「`/api/tasks`」GETエンドポイントは実在しない。実在契約は `/api/status` と `get_tasks_view` アクション
  - **→ 第二段も完了 (2026-09-01 23:30)**: `database.py` の dict 返却は `get_habits_with_status` / `get_habit_heatmap_data` の2関数のみと特定し、`HabitWithStatus` / `HabitHeatmapPoint` モデル返却へ移行 (呼び出し元4ファイルを属性アクセス化・local_sync_server は JSON送信時に model_dump)
  - **実バグ修正**: briefing_engine が存在しない `is_done` キー参照 → 朝会の習慣達成数が常に0だった潜在バグを `_build_habit_summary()` 新設で修正 (Pydantic化の効果を実証)
  - ファクト: `get_recent_minigame_scores` は既に `MinigameScore` モデル返却のため対象外
  - 検証: `tests/test_habit_models.py` 8件新設 → 全221テスト OK
  - **残: P2③のみ** (gui.py / local_sync_server.py 分割 — 次セッション以降)
- **検証**: `tests/test_sync_dtos.py` 6件新設 → 全209テスト OK

#### 6. 自律通知エンジンのスケジューラー共通化 (Deep Module) — ✅ 第一段完了 (2026-09-01)
- **対象ファイル**: `proactive_engine.py`, `suggest_engine.py`, `briefing_engine.py`
- **実装結果**:
  - `proactive_scheduler.py` 新設: 複数エンジンに分散した周期タイマーを1本のデーモンスレッドへ集約する Deep Module（プラグイン例外隔離・スレッド安全な register/unregister・stop()）
  - `main.py`: asyncio ループ内 tick（`check_and_trigger_care` / `check_event_reminders`）をスケジューラへ移管 → UIループからDB I/Oを分離
  - `tests/test_proactive_scheduler.py` 6件新設
- **残（第二段）**: `suggest_engine` SuggestBgWorker / `life_coach_engine` 2h周期 / `reminder_engine` の個別スレッドを順次 register() へ置換
  - **→ 第二段一部完了 (2026-09-01)**: `proactive_scheduler.py` に `PeriodicThrottle` (初回tick即実行→interval間引き) と `register_periodic()` を新設。`reminder_engine` / `life_coach_engine` の専用スレッド (_loop/_thread) を廃止し共有デーモンスレッドへ移管 (start/stop/is_running 契約は後方互換維持)
  - **→ 第二段残も完了 (2026-09-01 21:20)**: `suggest_engine` SuggestBgWorker 専用スレッド (`_worker_thread`/`_background_worker_loop`) も廃止し `register()` プラグイン方式へ移管。強制更新 (request_refresh) は従来の「次の30秒周期」から **tick (1秒) 以内の即時反映** へ向上
  - `ProactiveScheduler.stop()` をプラグインクリア契約へ強化 (停止済みスケジューラへの幽霊プラグイン残留を構造的に防止)
  - **P2② 全エンジン移管完了** — 検証: `tests/test_perf_step2.py` 新契約刷新 + stop() 契約テスト追加 → 全213テスト OK

---

### ⚪ 【P3】体験向上（オンボーディング洗練）

#### 7. オンボーディングツアーの3ステップ最短化
- **対象ファイル**: `tour_engine.py`
- **改修内容（How）**: 初回起動時の認知摩擦を減らすため、ツアーを「①右クリックで設定」「②スマホQR連携」「③会話・手帳」の3ステップに凝縮する。

---

## 🛠️ 開発・検証コマンド（PowerShell）

```powershell
# 全テスト実行
& ".\venv\Scripts\python.exe" -m pytest tests/

# アプリ起動確認
& ".\venv\Scripts\python.exe" main.py
```
