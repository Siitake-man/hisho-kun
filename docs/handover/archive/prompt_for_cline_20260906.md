<!--
  Cline 引き継ぎ指示書 (prompt_for_cline_20260906.md)
  更新日時: 2026-09-06 16:20
  更新内容: Sprint A + 集中開発4サイクル + Phase H (AIエージェント稼働可視化シアター 8割) + 4.2 (デスクトップ半透明スマート付箋 8割) 完全達成。テスト基準 300+件全パス。
-->

# 🤖 Cline 引き継ぎ指示書 (2026-09-06 超詳細・最終仕上げ委譲用)

## 📌 現在のステータス (Antigravity にて 8割完成 ＆ コア配線完了！)

本日、Antigravity は「Sprint A」「集中開発4サイクル」に続き、ロードマップの最重要機能である **「Phase H: AIエージェント稼働可視化シアター」** と **「4.2 / B17: デスクトップ半透明スマート付箋」** のコア実装を完了し、**8割完成（プロダクション品質）** に到達しました。

### 🌟 本日の主要達成モジュール一覧
1. **Phase H: AIエージェント稼働可視化シアター (Agent FSM ＆ 連動)**:
   - `agent_fsm.py` (新設): 状態マシン（`idle`, `thinking`, `coding`, `waiting_approval`, `success`）、ハートビート退避（60秒TTLで自動IDLE復帰）、スレッドセーフ（`Lock`）。
   - `local_sync_server.py`: `POST /api/agent/activity` 新設（localhost限定）、`GET /api/status` のペイロードに `agent_activity` 同梱および `pet_state` 動的連動。
   - `gui.py`: `AgentFSM` リスナー登録。エージェントがコード書き込み・思考・承認待ちになると、ペットが `focus`（猛烈タイピング）や `think`、`alarm_ask` にリアルタイムで切り替わり、吹き出しでお知らせ。
   - `tests/test_agent_fsm.py` (新設): 5件の単体テスト完備。
2. **4.2 / B17: デスクトップ半透明スマート付箋 (`ui/sticky_note.py`)**:
   - `ui/sticky_note.py` (新設): 最前面（Topmost）・半透明（Alpha 88%）・枠なし（Overrideredirect）のモダン付箋。ドラッグ移動可能。
   - `database.py` 接合: 今日の最重要タスク（重要×緊急）を自動抽出表示。ワンクリック「◯」で即座に完了チェック。クイック追加入力欄完備。
   - `ui/system_tray.py` ＆ `gui.py`: タスクトレイメニューおよび右クリックメニュー（「📌 新しい付箋を貼る」）から瞬時に表示/非表示トグル可能。
3. **Sprint A ＆ 集中開発4サイクル (以前完了分・安定稼働中)**:
   - 遅延ヘッダー送出（`ApiContext`）、401失敗IPレートリミッター（`auth_rate_limiter.py`）。
   - 音声設定画面トグル化、Windows タスクトレイ常駐（`ui/system_tray.py`）、ゼロトラスト端末台帳（`devices` テーブル）、自己治癒ウォッチドッグ独立モジュール化（`server_watchdog.py`）。

---

## 🎯 Cline への委譲スコープ（残り2割の仕上げ ＆ 監査チェック）

Cline は以下の **3大仕上げタスク** を実施し、ネオ秘書くんを完成状態へ導いてください：

### 1. スマホDesk Pet (PWA) 側のエージェント稼働ライブバッジ演出 (`web_pet/pet.js` & `web_pet/index.html`)
- **What**: `/api/status` から送られてくる `payload.agent_activity` を受け取り、エージェントがアクティブ（`is_active: true`）の時に、スマホ画面上部（時計の下付近）にネオン調のミニライブバッジを表示する。
- **表示例**:
  - `coding`: 🟢 `[Antigravity] Coding... 🔥` (緑パルス)
  - `thinking`: 🟡 `[Claude Code] Thinking... 🤔` (黄点滅)
  - `waiting_approval`: 🟣 `[Codex] Waiting Approval 🚨` (紫点滅)
- **注意**: スクリプト冒頭と下部での `let` 重複宣言は厳禁（TDZ syntax error 防止）。

### 2. 付箋ウィンドウの座標永続化 (`ui/sticky_note.py` ＆ `character_config.json`)
- **What**: ボスがドラッグして配置した付箋の位置（`_pos_x`, `_pos_y`）を、非表示時や次回起動時にも復元できるよう、`character_config.json`（または `database.py`）に保存・読み込みする処理を追加する。

### 3. 見落としチェック・回帰テスト・機密スキャンの実行
- **テスト全件実行**: 単体テスト・結合テスト（300件以上）が一発でパスすることを確認。
- **機密スキャン**: `python tools/scan_git_secrets.py` を実行し、CLEAN（検出ゼロ）を確認。

---

## ⚠️ 注意事項 (環境地雷・教訓)

1. **コマンド自律実行の厳禁**: `run_command` によるビルド・テスト・サーバー起動は禁止。必ずPowerShell互換コマンドをボスに提示して手動実行を促すこと。
2. **Tkinter スレッドセーフ**: GUI操作はすべて `gui.post_action(callback)` 経由でメインスレッドに委譲すること。
3. **Tailscale CGNAT IP (100.64.0.0/10) 除外**: レートリミット誤遮断防止を死守すること。

---

## 🛠️ 検証コマンド (PowerShell)

```powershell
# 1. AgentFSM 単体テスト
python -m unittest tests/test_agent_fsm.py -v

# 2. デバイス台帳テスト
python -m unittest tests/test_device_registry.py -v

# 3. watchdog 単体テスト
python -m unittest tests/test_server_watchdog_standalone.py -v

# 4. 全体テストスイート実行 (全件パス確認)
python -m unittest discover -s tests -p "test_*.py"

# 5. 機密スキャン (CLEAN確認)
python tools/scan_git_secrets.py
```

## 📚 参照ファイル
- `agent_fsm.py` (新設: エージェント状態マシン)
- `ui/sticky_note.py` (新設: デスクトップ半透明スマート付箋)
- `ui/system_tray.py` (タスクトレイ常駐マネージャー)
- `local_sync_server.py` (同期サーバー ＆ Agent Activity API)
- `gui.py` (メインGUI ＆ マスコット連動)
- `docs/learning-memos/学習メモ_20260906.md` (詳細学習メモ)

