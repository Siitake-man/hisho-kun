<!--
  Cline 引き継ぎ指示書 (prompt_for_cline_20260902.md)
  更新日時: 2026-09-01 23:55
  更新内容: タスク6 P2①第一/第二段・P2②完了を記録。次回は P2③分割リファクタの専用スプリント
-->

# 🤖 Cline 引き継ぎ指示書 (2026-09-02 セッション用)

## 📌 現在のステータス
- **タスク6 進捗**: P2①Pydantic DTO移行 (第一段 sync_dtos.py ＋ 第二段 DB戻り値モデル化) ✅ / P2②ProactiveScheduler共通化 (全エンジン移管) ✅ / **P2③分割リファクタ のみ未着手**
- **テスト基準**: 全 **221テスト OK** (基準線。作業後はこの数以上で全パス必須)
- **実バグ修正済**: briefing_engine の is_done 誤参照 (朝会の習慣達成数が常に0) → _build_habit_summary() で修正済み
- **⚠️ コミット未実施** (ボス手動): 前セッション変更分がワーキングツリーに残っている可能性あり。開始時に git status で確認し、未コミットならボスに確認

## 🎯 次回タスク: P2③ コード肥大化解消 (Divergent Change)

### 対象1: local_sync_server.py (約1800行)
- **最大ホットスポット**: do_POST (L1036〜 / 約700行・循環的複雑度127) の God Function
- **改修方針**: アクションディスパッチテーブル (action_name → handler_func の辞書) へ抽出し Seam 化 → 機能別モジュール (api_calendar / api_tasks / api_agent_bridge) へ分離
- **手順 (1モジュールずつ厳守)**:
  1. 対象アクション群の振る舞いを固定する characterization テスト追加 (既存: tests/test_sync_lan_selfheal.py 10件 / tests/test_webhook_integration.py を活用)
  2. ハンドラをメソッド→モジュール関数へ移動し、ディスパッチテーブルで結線
  3. 全221テスト実行 → Green 確認 → 次のモジュールへ

### 対象2: gui.py (約1600行)
- tour_engine 連携 / ポモドーロ / サークルメニュー / サウンド に Seam 分割
- 同じく「テスト追加 → 移動 → 全テスト」の3ステップ。Tkinter × asyncio 分離規約 (gui.post_action 徹底) は死守

### 注意事項 (前セッションの教訓)
- **UTF-8ファイルの読み書きは必ず Python io.open で encoding=utf-8 指定** (PowerShell 5.1 は日本語ファイルを破壊する / 恒久ルール7)
- **python -c 引数内のダブルクォートは PowerShell に剥がされる** → ファイル書き込みは「$OutputEncoding=UTF-8 ＋ $env:PYTHONUTF8=1 ＋ ヒア文字列 stdin パイプ」方式を使う
- **run_commands の複数コマンドは並行実行され得る** → patch→test のような依存操作は別コールで逐次実行
- メソッド名・属性名は search_graph で実在確認してから参照 (推測禁止)
- TDD: 失敗するテスト (Red) を先に作り、Green へ持ち込む

## 🛠️ 検証コマンド (PowerShell)
```powershell
# 全テスト実行 (基準: 221件全パス)
& .\venv\Scripts\python.exe -m unittest discover -s tests -p test_*.py | Select-Object -Last 5

# 構文検証
& .\venv\Scripts\python.exe -m py_compile <対象ファイル>
```

## 📚 参照ドキュメント
- active_context.md (次回再開タスク・23:30更新)
- docs/learning-memos/学習メモ_20260901.md (本セッションの教訓・環境地雷帳)
- docs/handover/prompt_for_cline_20260901.md (P2①②の実装詳細)
- AGENTS.md (開発規約・4大弱み克服)
