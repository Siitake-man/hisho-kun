---
name: graph-engineering
description: ネオ秘書くんにおける開発タスクをグラフ構造（DAG）として分解し、偽の依存関係を削ぎ落として並列処理（Fan-out）と独立検証者（Verifier）による多角レビュー・成果統合（Fan-in）を実行するスキル。
---

# スキル：グラフエンジニアリング実行器 (graph-engineering)

このスキルは、「ネオ秘書くん（Neo-Secretary）」における複雑な機能追加・改修タスクを「グラフ構造（DAG）」に分解し、モジュールごとの独立並列処理、厳格な独立検証（Verifier）、および成果の統合（Synthesize）を実行する。

---

## 実行フェーズ

### Step 0: コンテキスト同期 ＆ 前提条件の自動確認

1. **セーブポイント作成**: 大きな改修前にバックアップや Git コミットを確認する。
2. **`codebase-memory-mcp` インデックス同期**: `index_repository` を呼び出して最新化。
3. **仕様・規約の確認**: `DESIGN_SPEC.md`, `AI_RULES.md`, `機能ロードマップ.md` を参照。

### Phase 1: 依存関係グラフ（DAG）の構築と「偽のエッジ」排除

タスク依頼を受けた際、単一ループでの直列試行錯誤を禁止し、以下の「ノード」と「エッジ」を定義する。

1. **入出力契約（Contract）の明示**: 各モジュール（GUI / Agent / Tools / DB / LLM Factory）のインターフェース契約を定義。
2. **偽のエッジ（Fake Edges）の削除**: 例えば「DBスキーマ変更とGUIデザイン調整」など独立したタスクは並列（Fan-out）ノードとして分離。
3. **DAG構造の宣言**: 実行前に以下のフォーマットでユーザーに提示し合意を得る：
   ```
   [Task Input]
       ├── 🔵 Node A: DB / Data Layer (Contract: Pydanticモデル & CRUD関数)
       ├── 🔵 Node B: LLM Factory / Agent Layer (Contract: LangGraph State & Tools)
       └── 🔵 Node C: GUI / Pet UI Layer (Contract: CustomTkinter Event & Window)
   [Verification Tier]
       ├── 🛡️ Verifier 1 (Contract & Spec Audit): 独立検証
       ├── 🛡️ Verifier 2 (Type & Import Execution): python -m py_compile *.py
       └── 🛡️ Verifier 3 (Side-effect & Threading Audit): asyncio / Tkinter競合検証
   [Synthesize Tier]
       └── 🟣 Node Reduce: 成果物の統合・main.py結合確認
   ```

### Phase 2: 並列ノード（Fan-out）の実行

- 各並列ノードは「5分でコミット・確認可能なサイズ」にマイクロタスク化して実行する。
- コード検索には `codebase-memory-mcp` (`search_graph`, `trace_path`) を優先使用する。

### Phase 3: 独立検証者（Verifier Nodes）による多角検証

1. **Verifier 1 (仕様適合・契約検証)**: 各モジュールの成果物が `DESIGN_SPEC.md` および `AI_RULES.md` を満たしているかチェック。
2. **Verifier 2 (構文・型・インポート検証)**: Python構文チェック・インポート検証。
3. **Verifier 3 (副作用・非同期競合スキャン)**: `asyncio` メインループと Tkinter GUI スレッドのデッドロックやブロッキングがないか検証。

### Phase 4: 成果物統合（Synthesize / Reduce）

全 Verifier のパスを確認後、成果物を統合する。

1. 最終結合確認（モジュール間疎通）
2. ユーザーへ「日本語結論ファースト」で成果報告と習得スキルの提示。

---

## 留意事項
- **PowerShell互換**: コマンド連結時は必ずセミコロン `;` を使用すること。
- **5分粒度ルール**: タスクは隙間時間の5分で確認できる粒度に保つこと。
- **完全なコード出力**: 省略コメント (`# TODO`, `# ...`) を排除し、完全なプロダクションコードを出力すること。
