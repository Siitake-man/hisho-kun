# Tailscale セットアップガイド — 外出先Wi-FiからスマホDesk Pet接続

**最終更新日時**: 2026-08-25 19:00

カフェ・出張先等の「端末間通信が禁止された公衆Wi-Fi」でも、ネオ秘書くんのスマホDesk Petを動作させるための手順です。

## なぜ Tailscale が必要か
- カフェWi-Fiは多くの場合、**APアイソレーション（端末間通信禁止）** が有効で、PCとスマホが同じWi-Fiに繋がっていても相互に通信できません。
- Tailscale は WireGuard ベースのVPNメッシュで、インターネット越しにPCとスマホを仮想的な同一LANに接続します。
- 無料（個人利用・1ユーザー最大100端末まで）で、セットアップは3分で完了します。

## 手順

### 1. PCとスマホに Tailscale をインストール
- **PC (Windows)**: https://tailscale.com/download からインストーラをダウンロード、実行
- **スマホ (Android/iOS)**: Google Play / App Store で「Tailscale」を検索、インストール
- インストール後、両方で同じアカウント（Google アカウント等）にログイン

### 2. PC側で tailscale serve を有効化
1. **管理者として PowerShell を開く**（Windowsキー → "PowerShell" → 右クリック → 管理者として実行）
2. 以下のコマンドを実行：
   ```powershell
   tailscale serve 8765   # 8765 は既定ポート。NEO_HISHO_PORT で変更している場合はその値に読み替えてください
   ```
3. 出力例：
   ```
   Serve enabled:
   https://hisyo-pc.tailXXXX.ts.net/  →  http://127.0.0.1:8765/
   ```
   この `https://hisyo-pc.tailXXXX.ts.net/` の部分が「外出先接続URL」です。

### 3. ネオ秘書くん設定画面にホスト名を登録
1. `python main.py` で起動
2. 設定画面 → 「外部ツール」タブ → 「外出先接続 (Tailscale VPN)」カード
3. 上記のホスト名（例： `hisyo-pc.tailXXXX.ts.net`）を入力
4. 「💾 ホスト名を保存」

### 4. スマホで接続確認
1. スマホで Tailscale アプリを開き、**VPNがON**になっていることを確認
2. QR接続ダイアログ（PCペット右クリックメニュー → 「📱 スマホ接続」）を開く
3. 「🌐 外出先接続 (Tailscale)」のセクションに表示されたURLをコピー、またはQRコードを読み取り
4. スマホブラウザで開く → 通常のLAN接続と同じように使えます！

## 注意事項
- **Tailscale が OFF のときは LAN 接続に自動フォールバック**します（自宅では従来どおりWi-FiでOK）
- 外出先ではスマホの Tailscale を ON にするのを忘れずに
- スマホのモバイルデータ通信 + Tailscale でも動作可能（ただしデータ通信量が発生します）
- `tailscale serve` は起動のたびに実行する必要があります。必要に応じてスタートアップスクリプト化してください

## トラブルシューティング
| 症状 | 原因・対策 |
|---|---|
| スマホから接続できない | スマホのTailscaleがONか確認。PCの `tailscale serve` が実行中か確認 |
| 接続できたが画面が真っ白 | スマホPWAのService Workerキャッシュが古い。ブラウザの「サイト設定」→「キャッシュを削除」→再読込 |
| 承認ボタンが反応しない | スマホPWAを再読込。SWキャッシュ v3.2 以上が適用されているか確認 |