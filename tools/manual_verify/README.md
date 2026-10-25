# 手動検証・動作確認スクリプト (tools/manual_verify/)

本ディレクトリには、CI や `pytest` の自動回帰テスト対象ではなく、開発者が実機・手動で直接起動して動作を確認するための検証スクリプトを格納しています。

---

## 含まれるスクリプト一覧

### 1. `test_local_llm.py`
- **目的**: 内包ローカルGGUFモデル（`models/` 内のモデル）を `LLMFactory` 経由で直接ロードし、同期推論およびストリーミング推論が正常に実行できるかを実機確認する。
- **実行方法**:
  ```powershell
  python tools/manual_verify/test_local_llm.py [モデル名.gguf]
  ```

### 2. `test_sync_auth.py`
- **目的**: 秘書くん本体（HTTP同期サーバー）に対する Bearer 認証、自己承認（RCE）防止、ペアリングモードの挙動を、GUI を立ち上げずに手動シナリオとして通し検証する。
- **実行方法**:
  ```powershell
  python tools/manual_verify/test_sync_auth.py
  ```
  ※ 秘書くんアプリ本体がポート8765で起動している場合は停止してから実行してください。
