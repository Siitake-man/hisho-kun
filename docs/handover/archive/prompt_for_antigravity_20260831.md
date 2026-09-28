# 📝 Antigravity 引き継ぎ指示書 (2026-08-31)

**宛先**: Antigravity（⚡ 0 ➔ 0.85 爆速プロトタイピング担当）
**発行元**: Cline（🛡️ 0.85 ➔ 1.0 リファイン・品質ゲート担当）
**分業体制**: Antigravity が骨格を一括実装 ➔ Cline が構文修正・テスト・エッジケース補完でプロダクション品質へ仕上げる
**プロジェクト**: ネオ秘書くん (`c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん`)

---

## 1.【今回完了したこと (Done & Current Status)】

### ✅ タスク2「11.9 新生5大キャラクタースイート実装」— **完全完了**

| 成果物 | 内容 | 検証結果 |
|---|---|---|
| `tools/generate_kawaii_sprites_v2.py` | 新規作成。マーモット35状態／アザラシ33状態（tea_pillar茶柱追加）／キノコ33状態（メガネ👓＋羽ペン＋writing）の全面改修スプライトジェネレーター | venv実行で **101スプライト生成成功** |
| `assets/dot/{marmot,seal,kinoko}/` | 404 PNG（128px 本体 ＋ _32/_24/_20 縮小版）。全状態で十分な描画ピクセル数を確認 | 全PNG開封検証 **ALL_OK** |
| `character_manager.py` | `CHARACTERS_DATA` に marmot（🦫 絶叫＆悟り系「ア゛ーッ！」）登録済み。5キャラ体制（hisho/kinoko/seal/marmot/kyle） | import検証＋py_compile **パス** |
| `web_pet/pet.js` | `CHARACTERS` 配列に marmot 追加（スマホ側切替UI） | `node --check` **パス** |
| `pet_animator.py` | ①`ANIMATION_FRAMES` に `screaming`/`petting`/`tea_pillar` 追加 ②`_character_has_frames()` ガード新設（未搭載キャラは汎用ステートへ安全フォールバック） ③`trigger_reaction` 拡張: `deadline`/`reminder` イベント新設 | キャラ切替統合テスト **全シナリオ期待通り** |

**統合テスト結果（キャラ別フォールバック動作）**:
```
[marmot] deadline=screaming reminder=screaming love=petting care_tea=care  ← 固有ステート発火
[seal]   deadline=alarm_ask reminder=alarm_ask love=pet_love care_tea=tea_pillar  ← 茶柱発火
[hisho]  全イベント → 既存汎用ステート（alarm_ask/pet_love/care）へフォールバック
```

### ⏸ 未着手（次期ミッション）
- **タスク1「Block 2 (B20) PC Whisper本実装①」** → 本書の §3 で Antigravity に委譲

---

## 2.【発見したGotcha・技術的制約 (Invariants)】

### 🔴 恒久ルール（必ず遵守）
1. **UTF-8ファイルの読み書きは必ず Python `io.open(encoding='utf-8')` を使うこと**
   PowerShell 5.1 の `Get-Content`/`Set-Content`（CP932 既定）は日本語ファイルを破壊する（2026-08-31 実障害）。
   一時スクリプト経由の処理は `[System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))`（BOMなし）で書き出すこと。
2. **ClineにCode(JSON)で渡したコードは行継続 `\` が二重化される**: `if A \+\ B:` 形式は1行式 `(A)**2 + (B)**2 <= 1.0:` に書き直すこと（実障害あり）。
3. **冪等チェックの部分一致で置換が暴発する**: `COMMON_STATES` → `COMMON_COMMON_STATES` 二重置換事故が発生。置換対象は一意な文字列を使い、置換後は `py_compile` ＋実行で必ず確認。

### 🟡 コードベース不変条件（触ってはいけないもの／従うべきもの）
- **PC側スプライト読み込み命名規則**: `gui.py` `_load_mascot_assets()` が `assets/dot/{char_id}/{state}.png` を直接読む。状態名とファイル名は厳密一致させること。
- **pet_animator.py の `ANIMATION_FRAMES` が全アニメーションの単一情報源**: 新ステートはここに登録しないと発火しない（`set_state` は未登録名で早期リターン）。
- **`hisho`/`kyle` には `walk_1`/`walk_2` スプライトが欠落**（既存レガシー問題・新3キャラは完全カバー済み）。既存フォールバックを壊さないこと。
- **PC側キャラ切替UIは `gui.py` が `get_all_characters()` で動的列挙**: キャラ追加は `CHARACTERS_DATA` 登録だけで PC 側は自動対応。スマホ側のみ `web_pet/pet.js` の `CHARACTERS` 配列の手動追加が必要。
- **`local_sync_server.py` は `http.server` ベース（FastAPI/Flask 不使用）**: POST は `do_POST` 内の action 文字列分岐（例: `elif action == "quick_add_task":`）。認証は `SyncTokenManager.verify()`。
- **venv は `venv/Scripts/python.exe`**。重い依存は numpy 2.5.2 のみ（whisper/torch/fastapi/aiohttp は**未導入**）。
- コーディング規約: 厳格な型ヒント必須／Google Style 日本語Docstring／`print` デバッグ禁止（logging使用）／try-except 握りつぶし禁止。


---

## 3.【Antigravityへの依頼タスク (0 ➔ 0.85 爆速実装ミッション)】

### 🎯 ミッション: 「B20 スマホ音声 → PC Whisper 文字起こし → quick_add_task パイプライン」

多少荒削りで構わないので、以下を**一気に**書き上げてください（細部の品質は Cline が仕上げます）。

#### 成果物1: `whisper_transcriber.py`（プロジェクトルート新規）
- クラス `WhisperTranscriber`: 型ヒント必須、Google Style 日本語Docstring。
  - `__init__(self, model_size: str = "small", language: str = "ja") -> None`
  - `transcribe(self, audio_bytes: bytes, filename: str = "voice.webm") -> str`
    tempfile で一時ディレクトリに音声保存 → faster-whisper で文字起こし → テキスト返却。
  - `is_available(self) -> bool` — ライブラリ未インストール時に False を返す。
  - モデルは遅延ロード（初回 transcribe 時）＋クラス属性キャッシュ。
  - 推奨ライブラリ: `faster-whisper`（CTranslate2 製・CPU 高速）。import は try-except で守り、未導入時は logging 警告＋`is_available()==False` フォールバック（**握りつぶし禁止・ログ必須**）。

#### 成果物2: `local_sync_server.py` への追記
- `do_POST` の action 分岐に `transcribe_voice` アクションを追加:
  - リクエスト: `Content-Type: audio/webm`（または JSON+Base64 どちらでも可・スマホ側と統一）、`X-Sync-Token` ヘッダ認証（既存 `SyncTokenManager` を使用）。
  - 処理: `WhisperTranscriber.transcribe()` → 文字起こし結果を action `quick_add_task` の既存ハンドラへ**内部直接呼び出し**（HTTP 自己呼び出し禁止）→ 応答: `{"status": "ok", "transcript": "...", "task_created": true}`。
  - 空文字の際は `{"status": "empty_transcript"}`。

#### 成果物3: `web_pet/pet.js`（または `index.html`）への追記
- スマホ側録音UI: マイクボタン → `MediaRecorder` で録音（webm/opus、最大15秒・自動停止）→ `authFetch` で音声を PC へ送信 → 応答の `transcript` をトースト表示。録音中はボタン点滅等の軽いUXは自由。

#### 成果物4: `requirements_whisper.txt`（新規）
- `faster-whisper>=1.0` 等の依存を記載。**本体 venv へのインストールは不要**（Cline が検証段階で実施）。

#### 設計指針
- **既存パターン踏襲最優先**: `local_sync_server.py` の既存 `quick_add_task` ハンドラの構造を読んで、直下・同型式で書くこと。
- スレッド安全性: `http.server` ハンドラスレッドから Whisper を呼ぶため、モデルロードは `threading.Lock` で保護。
- ファイル書き込みは全て Python `io.open(encoding='utf-8')` または UTF-8 安全なエディタ機能で（§2 恒久ルール）。
- UI/アニメーション側（pet_animator.py）には**手を出さない**こと。

---

## 4.【後でClineが検証するための受け入れ基準 (Acceptance Criteria)】

Cline は以下をチェックして 0.85 ➔ 1.0 に引き上げます:

- [ ] `python -m py_compile whisper_transcriber.py local_sync_server.py` がパス
- [ ] `WhisperTranscriber().is_available()` がライブラリ有無を正しく報告（未導入時にクラッシュしない）
- [ ] `transcribe_voice` アクションが既存 `SyncTokenManager` 認証を通過（トークン無しで 401/403 系）
- [ ] `transcribe_voice` → `quick_add_task` が内部呼び出しで繋がり、HTTP 自己呼び出しが無い
- [ ] 全関数・クラスに型ヒント＋Google Style 日本語Docstring
- [ ] `print` デバッグ無し・logging 使用・except 箇所にログ出力あり
- [ ] `node --check web_pet/pet.js`（JS追記時）がパス
- [ ] UTF-8 破壊痕（文字化けコメント等）が無い
- [ ] スマホ実機 or curl での音声送信エンドツーエンド確認（Cline 側で実施）

---

## 5.【Antigravity再開用プロンプト (Magic Prompt)】

Antigravity のチャット冒頭に以下を貼ってください:

```
docs/handover/prompt_for_antigravity_20260831.md を読んで、§3のB20ミッション「スマホ音声 → PC Whisper文字起こし → quick_add_task パイプライン」を実装してください。whisper_transcriber.py 新規・local_sync_server.py に transcribe_voice アクション追加・web_pet 側に録音UI・requirements_whisper.txt を一気に作成。⚠️ ファイル読み書きは必ず Python io.open(encoding='utf-8') を使用（PowerShell は日本語ファイルを破壊します）。細部の荒削りはOK、Clineがリファインします。
```

---

*作成: 2026-08-31 Cline（🛡️）／元タスク: active_context.md 🎯次回再開タスク より*
