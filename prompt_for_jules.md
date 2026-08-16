# 🤖 Jules / Codex への開発引き継ぎ指示書 (2026-08-16)

## 📌 プロジェクト概要
- **プロジェクト**: ネオ秘書くん (Neo-Secretary)
- **現在のステータス**: Phase 8.0 完了（DeskPet PWA 安定化 ＆ 常時画面ON ＆ Bluetooth承認 ＆ 期間別手帳 ＆ スレッドセーフ化 完了）
- **技術スタック**: Python 3.13 / CustomTkinter / LangGraph / Asyncio / HTML5 Canvas PWA

---

## 🎯 Julesにお願いしたいタスク（夜間/非同期開発）

### タスク 1: キャラクタースキンシステムのドット絵アセット追加 (Phase 9 準備)
- **対象ディレクトリ**: `assets/`
- **内容**:
  - 新規キャラクター（キノコ君 `kinoko_*`、棒人間 `stickman_*`、アザラシ `seal_*`、ウォンバット `wombat_*`）のスプライト画像（64x64 PNG）を `generate_mascot_assets.py` を拡張して自動生成可能にする。
  - 各キャラクターに `idle_1`, `idle_2`, `thinking_1`, `thinking_2`, `happy` の基本5フレームを用意する。

### タスク 2: `database.py` の SQLite WAL モード有効化 ＆ トランザクション保護
- **対象ファイル**: `database.py`
- **内容**:
  - コネクション初期化時に `PRAGMA journal_mode=WAL;` および `PRAGMA busy_timeout=5000;` を設定し、マルチスレッド/非同期エージェントからの同時書き込み時の耐障害性を向上させる。

---

## ⚠️ コーディング規約・制約
- **型ヒント**: すべての関数・メソッドに厳格な型ヒント（Type Hinting）を付与すること。
- **省略禁止**: `// TODO` や `# ...省略` などの手抜きコメントは一切禁止。そのまま動くプロダクション品質を出力すること。
- **スレッド安全**: GUI関連の操作は必ず `gui.post_action(func, *args)` を使用すること。
