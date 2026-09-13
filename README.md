# ネオ秘書くん (Neo-Secretary)

[![CI](https://github.com/Siitake-man/hisho-kun/actions/workflows/ci.yml/badge.svg)](https://github.com/Siitake-man/hisho-kun/actions/workflows/ci.yml)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![English README](https://img.shields.io/badge/README-English-red.svg)](README_en.md)

> 🇬🇧 **English documentation is available!** ➔ Check out [README_en.md](README_en.md) for full English guide.  
> **"Approve your AI coding agent from your phone while taking a coffee break."** ☕

### 📱 引き出しで眠る古いスマホが、AI開発の「卓上スマート相棒」に化ける。

**ネオ秘書くん (Neo-Secretary)** は、使わなくなったスマートフォンをQRコード1発で**「Desk Pet（卓上スマート秘書）」**へと生まれ変わらせるデスクトップ常駐AIアシスタントです。

Claude Code や Cline などの自律AIコーディングを回しながら、**「離席中に『コマンド実行していい？』で停止して開発が進まない…」**という経験はありませんか？  
ネオ秘書くんなら、PC右下のドット絵ペットがAIの思考とリアルタイムに連動し、離席中でも**手元のスマホからワンタップで遠隔承認**。コーヒーを淹れている間も、トイレに行っている間も、開発が止まりません。

<p align="center">
  <img src="assets/dot/hisho_animated.gif" width="104" alt="ネオ秘書くん（ヒショ）— まばたきするドット絵ペット">
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/dot/kyle_animated.gif" width="104" alt="ネオカイル — 泳ぐドット絵ペット">
</p>

<p align="center"><sub>▲ デスクトップやスマホで表情豊かに呼吸し、あなたの仕事を応援します 👔🐬</sub></p>

<p align="center">
  <img src="assets/screenshots/pc_pet.png" width="320" alt="PCペット: 会話とTODO操作">
  &nbsp;&nbsp;
  <img src="assets/screenshots/phone_pet.png" width="180" alt="スマホ Desk Pet (PWA): 手帳・天気・ブリーフィング">
  &nbsp;&nbsp;
  <img src="assets/screenshots/phone_approval.png" width="180" alt="エージェント承認要請をスマホでワンタップ承認">
</p>

<p align="center"><b>🔔 エージェント（Cline / Claude Code 等）の「コマンド実行していい？」をスマホでワンタップ承認</b></p>

### 💡 こんなあなたのためのツールです
- ☕ **AIエージェント（Claude Code / Cline 等）を回しながら、気兼ねなく離席・休憩したい人**
- 📱 **使わなくなった古いスマホ（iPhone / Android）のカッコいい再利用先を探している人**
- 👾 **無機質なコマンドライン作業に、90年代のレトロゲームのような「愛着と生命感」が欲しい人**

<p align="center" style="margin: 24px 0;">
  <a href="https://siitake-man.github.io/hisho-kun/neo-secretary-showcase.html">
    <img src="https://img.shields.io/badge/🌟_Interactive_Showcase-全体俯瞰図を見る-40458f?style=for-the-badge&logo=google-cloud&logoColor=white" alt="Interactive Architecture Showcase">
  </a>
  &nbsp;&nbsp;
  <a href="https://siitake-man.github.io/hisho-kun/guides/NEO_HISHO_CHEAT_SHEETS.html">
    <img src="https://img.shields.io/badge/📘_Cheat_Sheets-公式利用ガイド完全版-8b5e3c?style=for-the-badge&logo=readthedocs&logoColor=white" alt="Official Cheat Sheets">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/Siitake-man/hisho-kun/releases/tag/v1.0.0">
    <img src="https://img.shields.io/badge/📦_Download_v1.0.0-最新ZIPを入手-10b981?style=for-the-badge&logo=windows&logoColor=white" alt="Download Release v1.0.0">
  </a>
</p>

---

## ✨ 機能一覧

| 機能 | 説明 |
|---|---|
| 🤖 **AI秘書ペット** | PC右下に常駐。ドット絵アニメーション（秘書くん＋案内精霊カイル、設定から切替可能） |
| 📱 **スマホ連携 (PWA)** | QRコードを読むだけでペアリング。タスク・手帳・習慣をスマホから操作 |
| 🔔 **承認ブリッジ** | Cline / Codex 等の「コマンド実行して良い？」をスマホに通知・ワンタップ承認 |
| 📅 **カレンダー連携** | Googleカレンダーの秘密iCal URLを読み取り（OAuth不要・読み取り専用） |
| ☀️ **リアル天気** | 現在地の天気を自動取得。雨の日は画面に雨粒エフェクト |
| 🌈 **生活ドリーマー** | AIがペットの生活（食事・お風呂・読書・睡眠）を自動生成 |
| 🍅 **ポモドーロタイマー** | 集中タイマー。ペットが集中モードに変化 |
| 📣 **朝会/終礼ブリーフィング** | 朝は今日の予定・TODO・天気を音声付きで報告。夜は日報 |
| 👾 **シークレット要素** | 「お前を消す方法」と話しかけると…グリッチ演出と隠しミニゲーム（Pixel Defense）が解放 |
| 📴 **オフラインAI同梱** | LFM2.5 (Liquid AI) をローカル推論。APIキー無し・完全オフラインで会話可能 |

---

## 🚀 クイックスタート

### 必要なもの
- **Windows PC**（Python 3.11以上）
- **スマートフォン**（iOS / Android。PWA対応ブラウザ）
- **Wi-Fi**（PCとスマホが同じネットワークに接続）

### 1. ダウンロード＆インストール

```bash
# リポジトリをクローン
git clone https://github.com/Siitake-man/hisho-kun.git
cd hisho-kun

# 仮想環境を作成
python -m venv venv

# 仮想環境を有効化
venv\\Scripts\\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 2. 環境設定

`.env.example` をコピーして `.env` を作成し、APIキーを設定します：

```bash
copy .env.example .env
# メモ帳などで .env を開き、使用するLLMのAPIキーを記入
```

**最低限必要なもの**: いずれか1つのAPIキー
- OpenCode GO（推奨・安価格）
- Google Gemini（無料枠あり）
- OpenAI / Anthropic / Groq 等

### 3. 起動

```bash
venv\\Scripts\\python.exe main.py
```

PC画面右下にペットが現れます 🎉

### 4. スマホとペアリング

1. PCのペットを **右クリック → 📱 スマホ接続**
2. QRコードが表示されます
3. **スマホでQRコードを読み取る**
4. スマホにペット画面が表示されれば完了！

---

## 📴 オフラインAI同梱 (LFM2.5)

APIキーがなくても、PC内で完結するローカルAIと会話できます。
`start.bat` 初回起動時にモデルが未ダウンロードなら、自動的にセットアップを案内します。

### モデルの選択

| モデル | サイズ | おすすめ環境 |
|---|---|---|
| ⭐ **超軽量モード** (LFM2.5-350M QAD-Q4_0) | 約230MB | 大体のPCでサクサク動く推奨サイズ |
| **高品質モード** (LFM2.5-1.2B-Instruct QAD-Q4_0) | 約770MB | 4GB RAM以上。より賢い応答 |

手動でセットアップする場合:

```bash
python tools/setup_local_model.py              # 対話式で選択
python tools/setup_local_model.py --model 1.2b # 高品質モードを直接指定
```

セットアップ後は `.env` に `DEFAULT_LLM_PROVIDER=local_gguf` が自動設定され、次回起動からオフラインAIが有効になります。
設定画面や `.env` でいつでもクラウドLLMへ切り替え可能です。

> 📄 **モデルクレジット**: 本プロダクトは [Liquid AI](https://liquid.ai) の **LFM2.5** を使用しています。
> モデルは **LFM Open License v1.0** の下で提供されています（[ライセンス全文](https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/blob/main/LICENSE)）。

---

## 📖 スマホの使い方

| 操作 | 方法 |
|---|---|
| キャラ切替 | ⚙️ 設定 → 🎭 キャラクター切り替え |
| 🎨 テーマ変更 | 書斎→カフェ→森→海→サイバー |
| 常時画面ON | ⚙️ 設定 → 💡 常時画面ON |
| 全画面表示 | ⛶ ボタン |
| 手帳（予定・TODO） | 📝 ボタン |
| ポモドーロ | 🍅 ボタン |

---

## 🔗 Google カレンダー連携（オプション）

1. PC版 Googleカレンダーを開く
2. 左のカレンダー名「⋮」→「設定と共有」
3. ページ下までスクロール→「秘密のiCalアドレス」のURLをコピー
4. ネオ秘書くん設定 → 外部ツールタブ → iCal URL欄に貼り付け
5. 「今すぐ同期」

> ⚠️ **読み取り専用**です。スマホからの予定追加はローカルのみで、Googleカレンダーへは反映されません。

---

## 🌐 外出先からの接続（Tailscale）

スマホが同じWi-Fiにいない場合も、Tailscale VPN で接続できます：

1. PCとスマホに **Tailscale** をインストール
2. 同じアカウントでサインイン
3. PC側で管理者PowerShellから `tailscale serve 8765` を実行（初回のみ）
4. `main.py` を起動 → QR接続ダイアログ →「Tailscale VPN経由」のQRをスマホで読取

> 設定画面の「外部ツール」タブでホスト名を保存すると、次回から自動設定されます。

---

## 🤖 AIエージェント連携（MCP）— 1コマンドでセットアップ

ネオ秘書くんは **MCP (Model Context Protocol) サーバー** を内蔵しており、Cline / Claude Desktop / Claude Code / Cursor / Antigravity / VS Code などから「スマホへの承認依頼」「TODO登録」「長期記憶の保存」などのツールを呼び出せます。

### おすすめの方法：AIエージェント自身に設定させる

インストール後、お使いのAIエージェント（Claude / Cline 等）に次の1文を伝えるだけでOKです：

> ネオ秘書くんをインストールしたので、プロジェクトフォルダでMCP設定コマンドを実行して、対応すべてのクライアントに登録してください

エージェントは本READMEの手順どおり、以下のコマンドを1発実行するだけです：

```bash
# プロジェクトルートで実行（対応全クライアントへ一括登録・既存設定はバックアップ付き）
venv\\Scripts\\python.exe mcp_installer.py --all

# 特定クライアントのみ登録する場合
venv\\Scripts\\python.exe mcp_installer.py --tool claude_desktop cursor cline

# 対応クライアントとパスの一覧表示
venv\\Scripts\\python.exe mcp_installer.py --list
```

- **対応クライアント**: Antigravity / Claude Desktop / Cursor / Cline / Claude Code / VS Code（ワークスペース）
- 既存の設定は上書きされず**マージ**されます。書き込み直前の状態は `<設定ファイル>.bak` に退避されるので安心
- 登録後、各クライアントを再起動すると `neo_hisho_bridge` のツール群（承認要請・TODO・知見保存等）が使えるようになります
- Codex（config.toml）のみTOML形式のため自動登録非対象です。手動で追加してください

### 手動設定（JSONをコピーしたい場合）

PCペット右クリック → ⚙ 設定 → 「🤖 外部AI・MCP連携」タブの「MCP設定JSONをコピー」ボタンからも取得できます。

---

## 🔔 アップデート確認について

ネオ秘書くんは起動時と約6時間ごとに **GitHub Releases** へアクセスし、新しいバージョンが公開されていないかを確認します（読み取り専用・テレメトリ送信ゼロ）。

- 新バージョン検知時はPCペットがセリフでお知らせし、スマホPWAにも通知が表示されます
- オフライン環境では静かにスキップされ、エラーや起動遅延は発生しません

---

## 🗂️ プロジェクト構成

```
ネオ秘書くん／
├── main.py                 # メイン起動ファイル
├── version.py              # バージョン定義 (Single Source of Truth)
├── update_checker.py       # 更新チェック (GitHub Releases・通知のみ)
├── gui.py                   # PCペットUI
├── agent.py                  # LangGraph エージェント
├── life_dreamer.py           # 自律生活生成エンジン
├── weather_tools.py          # リアルタイム天気取得
├── local_sync_server.py      # スマホ連携・同期サーバー
├── database.py               # データベース操作
├── ui／                      # Tkinter UI 部品
├── web_pet／                 # スマホPWA フロントエンド
├── assets／dot／              # ドット絵アセット（2キャラ: 秘書くん／カイル）
├── tools／                    # 開発ツール類
├── tests／                    # テストスイート
├── docs／                     # ドキュメント
└── .env.example               # 環境設定テンプレート
```

## 🔮 今後のアップデート予定 (Roadmap & Coming Soon)

ネオ秘書くんは、コミュニティと共に進化し続けます。以下の機能を近日順次リリース予定です：

- 🎨 **自作キャラクター・スキン取り込み機能 (Custom Pet Skins / Modding)**:
  - 自分の描いたオリジナルドット絵や推しキャラの画像をフォルダに置くだけで、デスクトップ＆スマホに召喚できるスキン拡張機能
- 🌐 **フル英語・多言語対応 (Full English Support)**:
  - 海外のAIギークに向けて、スマホPWA・PCペットのワンタップ日英切り替え
- 🎙️ **リアルタイム音声対話 (Voice Conversation)**:
  - スマホマイクから話しかけて、ペットが音声で答えてくれる完全ハンズフリー対話
- 🌧️ **ポモドーロ連動・集中ホワイトノイズ (Ambient Focus Sounds)**:
  - 集中タイマーに合わせた雨音、深夜のカフェ、サイバーパンクな環境BGM
- 🔗 **マルチSaaS Webhook連携**:
  - Notion / Slack / LINE への予定・タスク双方向同期

フィードバックや機能リクエストは、ぜひ [GitHub Issues](https://github.com/Siitake-man/hisho-kun/issues) へお寄せください！✨

---

## 🎮 開発者向け情報

詳細は `docs/` 配下のドキュメントを参照してください：

- `docs/specs/DESIGN_SPEC.md` — システム設計書
- `docs/specs/機能ロードマップ.md` — 機能一覧と進捗
- `docs/guides/` — 利用者向けガイド・チートシート集
- `docs/specs/MCP_INTEGRATION.md` — MCP (Model Context Protocol) 連携仕様

---

## 📄 ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。
（同梱の LFM2.5 モデルは [LFM Open License v1.0](https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/blob/main/LICENSE) の下で提供されます）

---

*ネオ秘書くん — あなたのデスクトップに住む AI 秘書ペット 🤖✨*