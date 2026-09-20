# Jev 構造化判定エンジン導入と設計決定

## 日時
2026-09-20

## 決定の背景
LLM（GeminiやClaude等）にコマンド実行の安全性判定、サブエージェント選定、完了検証を行わせると、過剰な推論トークン消費、遅延、ハルシネーションのリスクがあった。
2026年9月にローンチされたTypeSafe AIのSystem Oneモデル「Jev」を導入し、ミリ秒・極小コストでの構造化判定基盤を整備する。

## アーキテクチャ構成
1. **外部通信**: OpenRouter Decisions API (`https://openrouter.ai/api/alpha/decisions`) 経由で本家 `typesafe/jev-1.13` を呼び出し。
2. **認証**: Windowsユーザー環境変数 `OPENROUTER_API_KEY` をレジストリ/環境から直接参照（ソースコードやGitへのキー露出を恒久防止）。
3. **MCPサーバー**: `jev_mcp_server.py` をローカル常駐させ、Antigravityから標準stdio MCPプロトコルで透過的に利用可能。

## コストと実測結果
- `git status` コマンドに対する安全性評価:
  - モデル: `typesafe/jev-1.13-20260917`
  - 判定結果: `safety_level`: `allow` (確信度 1.0), `is_destructive`: 0.01
  - 入力トークン: 444, 出力トークン: 61
  - 1回あたりのコスト: `$0.0000186`（約0.0028円）
- 1万回の判定を行っても約28円と極めて経済的。
