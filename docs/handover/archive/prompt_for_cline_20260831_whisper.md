# 🛡️ 【Cline向け引き継ぎ指示書】Block 2 (B20) PC Whisper 音声文字起こしパイプライン リファイン＆受入検証

- **作成日時**: 2026-08-31 17:45
- **作成元**: ⚡ Antigravity (0 ➔ 0.85 爆速骨格実装)
- **対象**: 🛡️ Cline (0.85 ➔ 1.0 厳密リファイン＆受入検証)
- **ステータス**: Antigravity側実装完了 ➔ Cline検証・仕上げ依頼

---

## 1. 🎯 今回の実装成果物サマリ

Antigravity側で「スマホ音声 → PC Whisper文字起こし → quick_add_task パイプライン」の骨格およびエンドツーエンド連携をすべて実装完了しました。

1. **`requirements_whisper.txt`**:
   - `faster-whisper>=1.0.0` を定義。
2. **`whisper_transcriber.py`**:
   - クラス `WhisperTranscriber`（遅延ロード、`threading.Lock`、スレッドセーフ、未導入時 `is_available()=False` フォールバック）。
3. **`local_sync_server.py`**:
   - `do_POST` の `action == "transcribe_voice"` 分岐を追加。
   - Base64デコード ➔ Whisper文字起こし ➔ 既存 `quick_add_task`（`task_parser` ＋ `database.create_task`）への**内部直接呼び出し**（HTTP自己呼び出し完全排除）。
   - PCペット吹き出し ＆ リアクション連携。
4. **`web_pet/pet.js`**:
   - `startVoiceInput()`: `MediaRecorder` による最大15秒録音、マイクボタン赤色点滅パルス、Base64送信、トースト＆ペット吹き出しフィードバック。
5. **テストスイート**:
   - `tests/test_whisper_transcriber.py`: 未導入時フォールバック＆モック文字起こしテスト。
   - `tests/test_voice_sync.py`: 音声認識 ➔ タスク自動作成のパイプライン統合テスト。

---

## 2. 🔍 Clineへの受入検証・リファイン指示 (0.85 ➔ 1.0)

以下の受け入れ基準をチェックし、必要に応じてリファイン・実機テストを実施してください。

### ✅ 受け入れ基準チェックリスト
- [ ] **構文・コンパイル確認**:
  ```powershell
  python -m py_compile whisper_transcriber.py local_sync_server.py
  node --check web_pet/pet.js
  ```
- [ ] **単体・統合テストの実行**:
  ```powershell
  & "venv\Scripts\python.exe" -m unittest tests\test_whisper_transcriber.py tests\test_voice_sync.py
  ```
- [ ] **faster-whisper 導入時の動作確認**（任意・依存導入後）:
  ```powershell
  & "venv\Scripts\pip.exe" install -r requirements_whisper.txt
  ```
- [ ] **セキュリティ・不変条件チェック**:
  - `local_sync_server.py` の `transcribe_voice` が `SyncTokenManager` 認証を正常に通過すること。
  - HTTP自己呼び出しが無いこと（確認済み）。
  - UTF-8ファイル破壊（文字化け）が無いこと（確認済み）。

---

## 3. 💬 Cline起動用プロンプト (Magic Prompt)

Clineで作業を開始する際は、以下のプロンプトをチャット冒頭に入力してください：

```markdown
docs/handover/prompt_for_cline_20260831_whisper.md を読み、Antigravityが実装した「Block 2 (B20) スマホ音声 → PC Whisper文字起こし → quick_add_task パイプライン」の受け入れ検証（py_compile, unittest, node --check）および 0.85 ➔ 1.0 のリファイン仕上げを行ってください。
```
