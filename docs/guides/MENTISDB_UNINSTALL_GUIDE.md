# MentisDB 完全アンインストール手順ガイド (MENTISDB_UNINSTALL_GUIDE.md)

**最終更新**: 2026-09-23  
**目的**: 「引き算の美学」に基づき、形骸化・過剰設計となった MentisDB のバイナリおよび関連設定を完全消去し、開発環境を軽量化する。

---

## 1. 完了済みの自動設定解除（AI側で実施済み）
以下の設定ファイルから `mentisdb` の起動定義を完全に削除しました：
- ✅ `~/.gemini/antigravity/mcp_config.json`
- ✅ `~/.gemini/config/mcp_config.json`
- ✅ `~/.gemini/tools/jev_router/agent_scanner.py`（Jev候補からの除外）
- ✅ `AGENTS.md` ＆ `GEMINI.md`（記憶の3本柱体制への移行）

---

## 2. ユーザー手動実行手順（バイナリ・データの完全削除）

PowerShellを開き、以下のワンライナーまたは手順を実行してください。

### ステップ 2.1: バイナリ実行ファイル（mentisdb.exe）の削除
```powershell
# Cargoでインストールした場合のアンインストール
cargo uninstall mentisdb

# または直接 mentisdb.exe を削除
Remove-Item -Path "$HOME\.cargo\bin\mentisdb.exe" -Force -ErrorAction SilentlyContinue
```

### ステップ 2.2: ローカルデータ・キャッシュの削除（存在する場合）
```powershell
# MentisDB のローカルデータディレクトリを削除
Remove-Item -Path "$HOME\.mentisdb" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$HOME\AppData\Local\mentisdb" -Recurse -Force -ErrorAction SilentlyContinue
```

### ステップ 2.3: 削除確認
```powershell
Get-Command mentisdb -ErrorAction SilentlyContinue
```
何も出力されなければ、アンインストール完了です！

---

## 3. これからの記憶体制（3本柱）
1. **コード構造・依存関係**: `codebase-memory-mcp` (AST解析・Neo4j)
2. **ボスの恒久ルール・思考**: 秘書くんの「知識の宝庫 (Knowledge Vault)」(`neo_secretary.db`)
3. **作業引き継ぎ・成長ログ**: Git (`active_context.md`, `growth_log_YYYY-MM.md`)
