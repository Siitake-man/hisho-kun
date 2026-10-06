import json
import re

# 1. 最新のピクセルデータを読み込み
with open('web_pet/pixel_perfect_data.json', 'r', encoding='utf-8') as f:
    pixel_data = json.load(f)

# JSON文字列化
pixel_json_str = json.dumps(pixel_data, indent=2, ensure_ascii=False)

# 2. hd2d_showcase.html を読み込み
with open('web_pet/hd2d_showcase.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 3. PIXEL_DATA の置換
# const PIXEL_DATA = { ... }; の部分を正規表現で置換
pattern = r'const PIXEL_DATA = \{[\s\S]*?\n\s*\};'
replacement = f'const PIXEL_DATA = {pixel_json_str};'

if not re.search(pattern, html):
    raise ValueError("PIXEL_DATA pattern not matched!")

html = re.sub(pattern, replacement, html)

# 4. ボタンUIとラベルの更新
# ポーズボタンの更新
old_buttons = '''        <button class="opt-btn active" id="btn-pose-front" onclick="selectPose('front')">
          <span>👀 正面 (Front)</span>
          <span style="font-size:9px;opacity:0.8;">ネクタイ明瞭化</span>
        </button>
        <button class="opt-btn" id="btn-pose-back" onclick="selectPose('back')">
          <span>🔙 後ろ姿 (Back)</span>
          <span style="font-size:9px;opacity:0.8;">後頭部・背中</span>
        </button>
        <button class="opt-btn" id="btn-pose-lay" onclick="selectPose('lay')">
          <span>💤 コロンと寝転ぶ</span>
          <span style="font-size:9px;opacity:0.8;">スヤスヤ休む姿</span>
        </button>
        <button class="opt-btn" id="btn-pose-reading" onclick="selectPose('reading')">
          <span>📖 本を読む</span>
          <span style="font-size:9px;opacity:0.8;">公式アニメーション</span>
        </button>
        <button class="opt-btn" id="btn-pose-tea" onclick="selectPose('tea')">
          <span>🍵 お茶を飲む</span>
          <span style="font-size:9px;opacity:0.8;">公式アニメーション</span>
        </button>
        <button class="opt-btn" id="btn-pose-pc" onclick="selectPose('pc')">
          <span>💻 PC作業</span>
          <span style="font-size:9px;opacity:0.8;">公式アニメーション</span>
        </button>'''

new_buttons = '''        <button class="opt-btn active" id="btn-pose-front" onclick="selectPose('front')">
          <span>👀 正面 (Front)</span>
          <span style="font-size:9px;opacity:0.8;">ネクタイ立体化/イルカ</span>
        </button>
        <button class="opt-btn" id="btn-pose-back" onclick="selectPose('back')">
          <span>🔙 後ろ姿 (Back)</span>
          <span style="font-size:9px;opacity:0.8;">後頭部/イルカ背中</span>
        </button>
        <button class="opt-btn" id="btn-pose-lay" onclick="selectPose('lay')">
          <span>💤 お布団＆パジャマ帽</span>
          <span style="font-size:9px;opacity:0.8;">縦等身スヤスヤ寝姿</span>
        </button>
        <button class="opt-btn" id="btn-pose-reading" onclick="selectPose('reading')">
          <span>📖 デスクで読書</span>
          <span style="font-size:9px;opacity:0.8;">木製机に見開き本</span>
        </button>
        <button class="opt-btn" id="btn-pose-tea" onclick="selectPose('tea')">
          <span>☕ デスクでお茶・珈琲</span>
          <span style="font-size:9px;opacity:0.8;">木製机に大マグ湯気</span>
        </button>
        <button class="opt-btn" id="btn-pose-pc" onclick="selectPose('pc')">
          <span>💻 デスクでPC作業</span>
          <span style="font-size:9px;opacity:0.8;">シアン発光/ホタテ貝PC</span>
        </button>'''

if old_buttons in html:
    html = html.replace(old_buttons, new_buttons)

# 5. セリフ更新ロジックの刷新
old_bubble = '''    function updateSpeechBubble() {
      const bubble = document.getElementById('speech-bubble');
      if (currentChar === 'hisho') {
        if (currentPose === 'front') {
          bubble.innerText = 'ボス！白シャツに黄色のネクタイを締めました！ネクタイだと分かりますか？👔✨';
        } else if (currentPose === 'back') {
          bubble.innerText = '本棚の資料を確認中です…（ボスの大好きな後ろ姿です✨）';
        } else if (currentPose === 'lay') {
          bubble.innerText = 'ふぅ…コロンと横になって一休みです💤 ボスも無理しないでくださいね。';
        } else if (currentPose === 'reading') {
          bubble.innerText = '本棚の資料を精読中…ボスの業務に役立つ知見を見つけました！📖';
        } else if (currentPose === 'tea') {
          bubble.innerText = '淹れたての温かいほうじ茶です。ボス、一息ついてくださいね🍵';
        } else {
          bubble.innerText = '書類の整理とスケジュール調整に集中しています！📋';
        }
      } else {
        if (currentPose === 'front') {
          bubble.innerText = 'カタカタ…！カイル風精霊、元の端正な貝殻姿で待機中でございます🐚✨';
        } else if (currentPose === 'back') {
          bubble.innerText = 'ホタテ貝殻の美しい筋模様…後ろ姿も完璧でございます🐚✨';
        } else if (currentPose === 'lay') {
          bubble.innerText = '貝殻を閉じて少し休止モード…スヤスヤ…💤';
        } else if (currentPose === 'reading') {
          bubble.innerText = '貝型PCのマニュアルを読み込んでおります…📖';
        } else if (currentPose === 'tea') {
          bubble.innerText = '貝型PCの冷却も兼ねて、お茶を一服いたします🍵';
        } else {
          bubble.innerText = 'カタカタカタッ…！貝型PC、爆速で業務ログを記録中！⚡';
        }
      }
    }'''

new_bubble = '''    function updateSpeechBubble() {
      const bubble = document.getElementById('speech-bubble');
      if (currentChar === 'hisho') {
        if (currentPose === 'front') {
          bubble.innerText = 'ボス！白シャツに黄色のネクタイを締めました！立体的な結び目です👔✨';
        } else if (currentPose === 'back') {
          bubble.innerText = '本棚の前で資料を確認中…（ボスの大好きな後ろ姿です✨）';
        } else if (currentPose === 'lay') {
          bubble.innerText = 'ナイトキャップとお布団ですっぽりスヤスヤ…💤 ボスも温かくしてくださいね。';
        } else if (currentPose === 'reading') {
          bubble.innerText = '木製デスクで見開きの分厚い本を精読中です！📖✨';
        } else if (currentPose === 'tea') {
          bubble.innerText = '木製デスクに淹れたて珈琲をご用意しました！湯気も立っていますよ☕';
        } else {
          bubble.innerText = '木製デスクのノートPCでカタカタ集中作業中です！シアン画面で作業効率UP💻✨';
        }
      } else {
        if (currentPose === 'front') {
          bubble.innerText = 'カタカタ…！案内精霊カイル、本来の端正なイルカ姿で待機中でございます🐚✨';
        } else if (currentPose === 'back') {
          bubble.innerText = '滑らかなイルカの背中でございます…謎の斜線は綺麗に消えました🐚✨';
        } else if (currentPose === 'lay') {
          bubble.innerText = 'ナイトキャップを被り、深海ブルーのお布団で休止モード…スヤスヤ…💤';
        } else if (currentPose === 'reading') {
          bubble.innerText = 'デスクの上で分厚いマニュアル本を精読中でございます…📖';
        } else if (currentPose === 'tea') {
          bubble.innerText = 'デスクの貝殻マグカップから淹れたてのお茶をいただきます☕';
        } else {
          bubble.innerText = 'カタカタカタッ…！名物・ホタテ貝型ゴールドPC、爆速で叩いております！⚡🐚';
        }
      }
    }'''

if old_bubble in html:
    html = html.replace(old_bubble, new_bubble)

# 保存
with open('web_pet/hd2d_showcase.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: hd2d_showcase.html updated perfectly!")
