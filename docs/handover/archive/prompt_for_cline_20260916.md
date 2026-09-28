# Cline Desktop への超詳細引き継ぎ指示書 (prompt_for_cline_20260916.md)

- **作成日時**: 2026-09-16 12:55
- **作成元エージェント**: Antigravity (Google DeepMind)
- **引き継ぎ先エージェント**: Cline Desktop
- **作業リポジトリ**: `ネオ秘書くん` (https://github.com/Siitake-man/hisho-kun)
- **最新コミット状態**: PR #5 (chore: repo-hygiene) マージ完了直後
- **現在のテスト状態**: 全474テスト完全合格（`474 passed, 2 skipped, 0 failed in 31.7s` - 100% All Green）
- **知識基盤**: `codebase-memory-mcp 0.11.0` 稼働中 (ADR登録済み, 2777 nodes, 11750 edges)

---

## 🧭 1. プロジェクトの背景・アーキテクチャ設計規約 (Codebase Design)

本プロジェクトは、人間と自律型AIエージェント（Cline, Antigravity, Claude Code等）をつなぐ、リアルタイム感情的秘書ハブ ＆ デスクペット（Desk Pet）です。

Cline Desktop は作業着手にあたり、以下の **Codebase Design 規約（アーキテクチャ原則）** を厳格に遵守してください：

1. **Deep Module の原則**:
   - インターフェースは小さく（少数のメソッド・型安全な引数）、内部実装に複雑さを隠蔽（Leverage）すること。
   - 神ファイル（`web_pet/pet.js`）や巨大メソッド（`local_sync_server.py:do_GET`）にこれ以上処理をベタ書きで追加しないこと。必ず独立したモジュール/クラス（例: `storage/device_repo.py`, `ui/settings_window.py` 内の独立フレーム）に責務を分離すること。
2. **Seam (接合部) と テスト容易性**:
   - UI（Tkinter/CustomTkinter）とビジネスロジックは必ず Seam（接合部関数・DTO）で分離し、GUIを表示せずにテスト可能な設計を維持すること。
3. **ハードコードの絶対禁止**:
   - ポート番号（8765）やURLは直接文字列でハードコードせず、`SERVER_PORT` 定数や設定値・ヘルパー関数を参照すること。
   - 個人絶対パス（`C:/Users/...`）のコミットは厳禁（すべて相対パスまたは設定から解決）。
4. **ゼロトラスト ＆ 安全性**:
   - ローカル通信であってもトークン認証（`Sync-Token`）と入力バリデーションを徹底すること。

---

## 📋 2. 実装タスク一覧 ＆ 詳細仕様書

以下の5つのタスクを、**1タスクずつ TDD（テスト作成 ➔ 実装 ➔ テスト合格）のステップ** で確実に遂行してください。

---

### 【タスク0: 🌟 秘書くんアイコン化 ＆ キャラ着せ替え連動】(最優先・ボスご要望)

#### 目的
デフォルトの青い羽ペンアイコンを廃止し、ボスの誇る「初代秘書くん」ドット絵をアプリ全体・タスクトレイ・EXEに適用する。

#### 詳細仕様
1. **タスクトレイアイコン (`ui/system_tray.py`)**:
   - `_ASSET_CANDIDATES` リストの最優先候補に `assets/dot/hisho/idle_1.png` を追加。
   - `NeoSecretaryTray` クラスに `update_character_icon(character_id: str) -> bool` メソッドを新設。
   - `character_manager.py` でキャラクターが変更された際（例: `hisho` ⇄ `seal` ⇄ `mushroom` ⇄ `kyle`）、該当キャラクターの `idle_1.png` を動的にロードしてトレイアイコン画像を切り替える。
2. **デスクトップウィンドウアイコン (`gui.py`, `ui/*.py`)**:
   - `gui.py` (`NeoSecretaryGUI.__init__`) および各ダイアログ（`calendar_window.py`, `settings_window.py`, `qr_dialog.py`）で、ウィンドウアイコンを設定する。
   - Windows環境では `self.root.iconbitmap("assets/icon.ico")` を試行し、失敗時は `iconphoto(False, ...)` にフォールバックする例外安全設計とする。
3. **EXE実行ファイルアイコン (`neo_hisho.spec`)**:
   - `neo_hisho.spec` の 110行目付近にある `icon=None` を `icon=str(PROJECT_ROOT / 'assets' / 'icon.ico')` に変更。

---

### 【タスク1: 🧹 ハードコード解消 ＆ 衛生クリーンアップ】

#### 目的
Grokbot PR #5 のマージに伴い、リポジトリ内に残存するハードコードURLとGit除外設定を完璧にする。

#### 詳細仕様
1. **`ui/qr_dialog.py` のハードコードURL解消**:
   - 396行目にある `"http://localhost:8765/api/test_buzz"` のベタ書きを修正。
   - `local_sync_server.py` の `SERVER_PORT`（または `TAILSCALE_HTTP_PORT`）定数を用いた動的URL生成（`f"http://localhost:{SERVER_PORT}/api/test_buzz"`）に変更。
2. **`.gitignore` のバックアップ除外確認**:
   - `*.bak`, `*.md.bak`, `*.html.bak` が確実に除外されていることを維持。

---

### 【タスク2: ⚡ 省電力スプリント完遂 (P1-2 ＆ P1-3)】

#### 目的
スマホPWA（0fps完全スリープ達成済み）に続き、SQLiteクエリ負荷とPC側CPU使用率を最小化する。

#### 詳細仕様
1. **P1-2: SQLite 頻出カラムの明示的インデックス作成 (`storage/connection.py`)**:
   - `init_db()` 関数内に、以下のインデックス作成文を追加：
     ```sql
     CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status, due_date);
     CREATE INDEX IF NOT EXISTS idx_events_start_end ON events(start_time, end_time);
     ```
   - 目的: `/api/status` の定期ポーリングや手帳画面表示時における、TODOテーブル・予定テーブルのフルスキャン（O(N)）を排除し、インデックススキャン（O(log N)）へ高速化。
2. **P1-3: PC側メインループの適応型スリープ (`main.py`)**:
   - `main.py` の `async_mainloop` において、ユーザー無操作（アイドル）状態の待機時間を `await asyncio.sleep(0.01)` から `await asyncio.sleep(0.03)`（約30Hz）に緩和。
   - 目的: UIの滑らかな応答性を維持しながら、PC側メインスレッドのCPU常時占有率を約50%削減。

---

### 【タスク3: 📱 スマホPWAホーム画面アイコンの最適化】

#### 目的
スマホのホーム画面にPWAを追加（「ホーム画面に追加」）した際、美しい高解像度ドット絵アイコンが表示されるようにする。

#### 詳細仕様
1. **マニフェスト整合 (`web_pet/manifest.json`)**:
   - `icons` 配列内のパスを確認し、`assets/dot/hisho/happy.png` または正方形アイコン（192x192, 512x512）が正しく配信・指定されていることを確認。
2. **HTMLメタタグ (`web_pet/index.html`)**:
   - `<link rel="apple-touch-icon" href="...">` を追加・確認し、iOS Safari でのホーム画面追加時にも秘書くんアイコンが正しく適用されるようにする。
3. **Service Worker キャッシュ整合 (`web_pet/sw.js`)**:
   - 追加したアセットがオフラインキャッシュに含まれるよう、`STATIC_ASSETS` リストとキャッシュバスターの整合性を確認。

---

### 【タスク4: 🛡️ 設定画面のゼロトラスト接続端末一覧UI】(Sprint C 先取り)

#### 目的
バックエンドですでに実装済みの「端末認証・台帳管理機能」を、PC設定画面から視覚的に確認・管理（Revoke）できるようにする。

#### 詳細仕様
1. **バックエンド連携の確認**:
   - `storage/device_repo.py`: `get_devices()`, `revoke_device(device_id)` が既に利用可能。
   - `api_devices.py`: `/api/devices` (GET), `/api/devices/revoke` (POST) が実装済み。
2. **設定画面UIの実装 (`ui/settings_window.py`)**:
   - 設定ウィンドウ内に「📱 接続端末管理（ゼロトラスト）」セクションを新設。
   - 登録済み端末の一覧を表示するスクロールフレームを配置：
     - 表示項目: 端末名（User-Agent解析名 / IP）、初回接続日時、最終アクセス日時、認証ステータス（有効 / 拒否済み）。
     - 各端末の横に「接続解除（Revoke）」ボタン（赤系ボタンスタイル）を配置。
   - 「接続解除」クリック時:
     - 確認ダイアログを表示し、承認されたら `device_repo.revoke_device(device_id)` を実行。
     - 一覧を即座に再描画し、該当端末のステータスを「拒否済み」に更新。次回のスマホからのリクエストを401 Unauthorizedで即座に遮断。

---

## 🧪 3. テスト実行 ＆ 品質検証手順

タスク実装後は、**必ず以下の手順でテストを実行し、1件の失敗もないこと（All Green）を確認** してください。

### ① 単体・統合テストの実行コマンド (PowerShell)
```powershell
.\venv\Scripts\python.exe -m unittest discover tests
```
または pytest:
```powershell
.\venv\Scripts\pytest.exe -q
```
> **合格基準**: 全474件以上のテストが PASS すること。

### ② 新規追加するテスト
- タスク0用: `tests/test_tray_character_icon.py`（キャラ切り替え時のアイコン更新確認）
- タスク2用: `tests/test_db_indexes.py`（インデックスの存在とクエリプラン確認）
- タスク4用: `tests/test_device_ui_seam.py`（端末一覧の取得とRevoke処理のSeamテスト）

---

## 📝 4. 完了後のドキュメント更新義務 (必須4点セット)

すべての実装とテストが完了したら、必ず以下のドキュメントを更新してください：

1. **`docs/00_ドキュメント一覧.md`**: 更新日時と概要の同期。
2. **`docs/specs/DESIGN_SPEC.md`**: アイコン設定仕様、DBインデックス、端末管理UIの追記。
3. **`docs/specs/機能ロードマップ.md`**: タスク0〜4の進捗ステータスを「✅ 完了」に更新。
4. **`active_context.md`**: 現在地、完了事項、次のステップを同期。
5. **学習メモの作成**:
   - `docs/learning-memos/学習メモ_Cline_20260916.md` を作成し、【習得した技術】【身近な例えでの理解】【進捗と次ステップ】を記録すること。

以上、よろしくお願いいたします！🚀
