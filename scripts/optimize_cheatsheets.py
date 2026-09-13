"""
ネオ秘書くん チートシートHTML最適化スクリプト
1. Base64画像埋め込みを assets/*.jpg への相対パス参照に変換してファイルサイズを劇的軽量化 (11.5MB -> 約50KB)
2. 全体俯瞰図 (Showcase) へのリンク切れを修正
3. 社内Slack周知文を削除し、一般公開向けの「概要 ＆ 推しポイント」に刷新
"""

import os
import re
import shutil

GUIDES_DIR = os.path.join("docs", "guides")
HTML_PATH = os.path.join(GUIDES_DIR, "NEO_HISHO_CHEAT_SHEETS.html")
BACKUP_PATH = os.path.join(GUIDES_DIR, "NEO_HISHO_CHEAT_SHEETS.html.bak")

def optimize_html():
    if not os.path.exists(HTML_PATH):
        print(f"[ERROR] {HTML_PATH} が見つかりません。")
        return

    # 1. バックアップ作成
    shutil.copy2(HTML_PATH, BACKUP_PATH)
    print(f"[OK] バックアップを作成しました: {BACKUP_PATH}")

    with open(HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    orig_len = len(content)
    print(f"[INFO] 元のファイルサイズ: {orig_len:,} bytes ({orig_len / (1024*1024):.2f} MB)")

    # 2. リンク切れの修正
    content = content.replace('href="🌟_システム俯瞰図_Showcase.html"', 'href="../neo-secretary-showcase.html"')
    content = content.replace("🌟_システム俯瞰図_Showcase.html", "../neo-secretary-showcase.html")

    # 3. ナビゲーションタブの文言修正
    content = content.replace("📢 周知文 ＆ 概要", "📢 概要 ＆ 特長")

    # 4. Base64画像の置換 (assets/*.jpg への軽量化)
    # openLightbox('data:image/jpeg;base64,...') と <img src="data:image/jpeg;base64,...">
    # 6つの画像に対応:
    # 0: banner_main.jpg
    # 1: cs01_setup.jpg
    # 2: cs02_mobile.jpg
    # 3: cs03_calendar.jpg
    # 4: cs04_agent.jpg
    # 5: cs05_localllm.jpg
    asset_names = [
        "banner_main.jpg",
        "cs01_setup.jpg",
        "cs02_mobile.jpg",
        "cs03_calendar.jpg",
        "cs04_agent.jpg",
        "cs05_localllm.jpg"
    ]

    # 正規表現で Base64 jpeg を検索して順番に置換
    # パターン: data:image/jpeg;base64,[A-Za-z0-9+/=]+
    def replace_base64_occurrences(text):
        # 該当するBase64文字列のリスト（ユニーク）を抽出
        matches = re.findall(r'data:image/jpeg;base64,[A-Za-z0-9+/=]{100,}', text)
        unique_matches = []
        for m in matches:
            if m not in unique_matches:
                unique_matches.append(m)
        
        print(f"[INFO] 検出されたBase64画像数: {len(unique_matches)} 個")
        for i, b64_str in enumerate(unique_matches):
            if i < len(asset_names):
                asset_rel_path = f"assets/{asset_names[i]}"
                text = text.replace(b64_str, asset_rel_path)
                print(f"  - 画像 #{i+1} を {asset_rel_path} に置換しました")
        return text

    content = replace_base64_occurrences(content)

    # 5. 社内Slackアナウンス文（コピペ用）セクションの削除・一般公開用への刷新
    # <div class="card-body">\s*<span class="section-tag">📢 社内Slack周知用テンプレート</span> ... </div>\s*</div>\s*</section>
    old_slack_section_pattern = re.compile(
        r'<div class="card-body">\s*<span class="section-tag">📢 社内Slack周知用テンプレート</span>.*?</div>\s*</div>\s*</section>',
        re.DOTALL
    )

    new_public_section = """<div class="card-body">
          <span class="section-tag">✨ プロダクト概要</span>
          <h2 class="section-title">ネオ秘書くん - あなたの専属卓上AI秘書</h2>
          <p class="lead-text">「席を外してもAI開発が止まらない」。眠っていたスマホを卓上遠隔承認リモコン＆相棒ペットに転生させ、開発者の生命時間を最大化します。</p>

          <div class="scene-card" style="margin-top: 24px; border-left: 4px solid var(--primary);">
            <h3 class="scene-title">🔥 ここがすごい！『ネオ秘書くん』の6大推しポイント</h3>
            <div class="scene-flow">
              <div class="scene-flow-step">
                <span>📱</span>
                <span><strong>① 余っているスマホが「卓上スマート秘書」に化ける</strong>: デスク横に置くだけで、可愛いピクセルペットがトコトコ動きながら開発を見守ります。</span>
              </div>
              <div class="scene-flow-step">
                <span>🚀</span>
                <span><strong>② アプリインストール一切不要（PWA完結）</strong>: スマホのブラウザでQRコードを読むだけ。ストレージを圧迫せず即座に繋がります。</span>
              </div>
              <div class="scene-flow-step">
                <span>🤖</span>
                <span><strong>③ コーディングエージェント連携 ＆ スマホ遠隔承認</strong>: Claude Code、Cline、Antigravity等のコマンド実行をスマホからワンタップで即承認！</span>
              </div>
              <div class="scene-flow-step">
                <span>📅</span>
                <span><strong>④ Googleカレンダー自動同期 ＆ 先回りサジェスト</strong>: スケジュールを先読みし、次の予定や空き時間のタスクを気の利いた提案でお知らせします。</span>
              </div>
              <div class="scene-flow-step">
                <span>🔒</span>
                <span><strong>⑤ 完全ローカルLLM内蔵 ＆ セキュア通信</strong>: 機密情報やプライベートな予定も安心。完全オフライン＆暗号化メッシュ（Tailscale）で外部漏洩ゼロ。</span>
              </div>
              <div class="scene-flow-step">
                <span>💬</span>
                <span><strong>⑥ 使い方に迷ったら「秘書くん」自身に聞けばOK</strong>: 「何ができるの？」「カレンダー連携はどうやる？」と話しかければ、丁寧にガイドしてくれます。</span>
              </div>
            </div>
          </div>

          <div style="margin-top: 24px; display: flex; gap: 12px; flex-wrap: wrap;">
            <button class="tab-btn" style="background: var(--primary); color: #fff; padding: 10px 20px;" onclick="switchTab('cs01')">🚀 ① 初期導入ガイドを見る ➔</button>
            <button class="tab-btn" style="background: var(--bg-tertiary); color: var(--primary); padding: 10px 20px;" onclick="switchTab('scenes')">🎯 活用シーン集を見る ➔</button>
          </div>
        </div>
      </div>
    </section>"""

    if old_slack_section_pattern.search(content):
        content = old_slack_section_pattern.sub(new_public_section, content)
        print("[OK] 社内Slackアナウンス文を削除し、一般公開用の特長セクションに刷新しました。")
    else:
        print("[WARN] 社内Slackセクションの正規表現マッチが見つかりませんでした。手動確認を推奨します。")

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    new_len = len(content)
    print(f"[SUCCESS] 最適化完了！ 新しいファイルサイズ: {new_len:,} bytes ({new_len / 1024:.2f} KB)")
    print(f"[REDUCTION] サイズ削減率: {(1 - new_len/orig_len)*100:.2f}% 削減！")

if __name__ == "__main__":
    optimize_html()
