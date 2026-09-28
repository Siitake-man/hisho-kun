# Cline 指示書: 内包ローカルLLM爆速常駐化 ＆ GPU加速 (P1-C)

- **作成日時**: 2026-09-06 18:45
- **対象機能**: `llm_factory.py` (内包ローカルLLM `LOCAL_GGUF`)
- **優先度**: 🔴 **P1-C (最優先コア改善)**
- **背景とボスの意志**:
  - ボスからの強い製品要件: **「外部のLM Studioを起動させるのではなく、ネオ秘書くん単体でローカルLLMを爆速体験できることに真の価値がある」**。
  - 現状の課題: LM Studio では 80 tok/s で即答する同一モデル（Bonsai等）が、秘書くんだと話しかけるたびに数秒待たされる。
  - **ボトルネック真因①**: 会話するたびに `agent.py` が `factory.create_model()` ➔ `Llama(model_path=...)` を実行し、**会話のたびに毎回 GGUF ファイルをディスクから再ロードしてテンソル初期化を行っている**。
  - **ボトルネック真因②**: `llm_factory.py:734` の `Llama(...)` インスタンス化時に `n_gpu_layers` が未指定（デフォルト0＝CPUのみ動作）。GPUが一切使われていない。

---

## 🎯 実装要件 (Specification)

### 1. モデルのメモリ常駐シングルトン化 (`llm_factory.py`)
- `LLMFactory` クラスに、ローカル GGUF インスタンスのキャッシュ機構を実装せよ。
- キャッシュキーは `str(gguf_path)`。
- **動作契約**:
  - 同一モデル（同じGGUFファイル）に対する `create_model()` 呼び出し時は、**ディスクロードをスキップし、すでにメモリに展開済みの `_llm` インスタンスを再利用（ロード時間0秒）** すること。
  - ユーザーが設定画面等で別の GGUF モデルに切り替えた場合は、古いインスタンスを解放（リソースクリーンアップ）し、新しいモデルを1度だけロードすること。
  - キャッシュクリア用の公開メソッド `clear_local_model_cache()` を提供すること。

### 2. GPU自動オフロード ＆ スレッド最適化 (`llm_factory.py`)
- `Llama(...)` 初期化引数に以下を設定せよ：
  ```python
  # GPU オフロード: -1 (全レイヤーオフロード)。環境変数 HISHO_GPU_LAYERS で上書き可能
  gpu_layers = int(os.getenv("HISHO_GPU_LAYERS", "-1"))
  # スレッド数: CPUコア数 - 2 (UIと非同期ループ用に余力を残す。最低1、最大8)
  cpu_threads = max(1, min(8, (os.cpu_count() or 4) - 2))
  n_threads = int(os.getenv("HISHO_CPU_THREADS", str(cpu_threads)))

  self._llm = Llama(
      model_path=model_path,
      n_ctx=n_ctx,
      n_threads=n_threads,
      n_gpu_layers=gpu_layers,
      verbose=False,
  )
  ```
- ※ `llama-cpp-python` は CUDA / Metal / DirectML がビルドされている環境では全レイヤーを VRAM に載せ、GPU非対応ビルドやVRAM不足時は安全にCPUへフォールバックするため、`-1` 指定が最も堅牢かつ高速である。

### 3. 【ついでに修正】`tests/test_device_bearer_seam.py` の 1件の失敗解消
- `test_sync_device_session_touches_last_seen` で `AssertionError: '192.168.1.5' != '10.0.0.9'` が発生している。
- **原因**: `database.sync_device_session()` 内で、既存端末に対して `touch_device_last_seen()` を呼んだ後、更新後の値が呼び出し元に返す `dev` オブジェクトに反映されていない（または古いオブジェクトを返している）。
- **対策**: `touch_device_last_seen()` 実行後、最新のレコードを再取得するか、`dev` オブジェクトの `ip_address` / `user_agent` を更新して返却せよ。

---

## 🧪 TDD ＆ 検証手順

1. **テスト先行作成 (`tests/test_local_llm_cache.py`)**:
   - `Llama` をモック化し、同一モデル名で2回 `create_model()` を呼んだ際に `Llama.__init__` が1回しか呼ばれないこと（2回目はキャッシュが返ること）を検証するテストを作成せよ。
2. **実装 ＆ 全テスト合格**:
   ```powershell
   venv\Scripts\python.exe -m unittest tests/test_local_llm_cache.py -v
   venv\Scripts\python.exe -m unittest tests/test_device_bearer_seam.py -v
   venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
   ```
   **全326+テストが完全 GREEN になることを確認せよ。**

---

## 🚫 禁止事項
- `run_command` によるコマンド自律実行の禁止（必ずユーザーへPowerShellコマンドを提示して手動実行を促すこと）。
- 既存の LangChain 互換性（`bind_tools`, `invoke`, `_stream`）を壊す変更の禁止。
