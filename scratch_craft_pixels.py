import json

# ==============================================================================
# 🎨 秘書くん (32x32) マトリクス設計
# パレット:
# 1: #4A3B32 (焦げ茶輪郭・目・鼻)
# 2: #A67B5B (毛並み茶色)
# 3: #C49A76 (毛並みハイライト)
# 4: #FFD700 (ネクタイ黄色)
# 5: #EF9A9A (チーク・耳ピンク)
# 6: #F5F5DC (顔・お腹クリーム色)
# 7: #FFFFFF (白シャツ襟・マグカップ・本のページ・湯気)
# 8: #B8860B (ネクタイ陰影)
# 9: #4E342E (コーヒー)
# A: #B71C1C (本の赤ハードカバー)
# B: #90A4AE (ノートPCシルバー)
# C: #00E5FF (PC液晶シアン発光)
# D: #81D4FA (枕の淡い水色)
# ==============================================================================

def empty_32():
    return [['.' for _ in range(32)] for _ in range(32)]

def to_strings(m):
    return [''.join(row) for row in m]

# ------------------------------------------------------------------------------
# 1. 秘書くん: 正面 (ネクタイ改良版)
# ------------------------------------------------------------------------------
raw_data = json.load(open('web_pet/pixel_dump.json'))
colors_h = sorted(list(set(tuple(c[:3]) for row in raw_data['hisho'] for c in row if c[3] > 0)))
p_map_h = {c: str(i+1) for i, c in enumerate(colors_h)}
rows_base = [''.join(p_map_h.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in raw_data['hisho']]

front_h = [list(r) for r in rows_base]
# ネクタイ明瞭化 (白シャツ襟 + 黄色ネクタイ + 陰影 + 剣先)
front_h[18][14] = '7'; front_h[18][15] = '4'; front_h[18][16] = '4'; front_h[18][17] = '7'
front_h[19][14] = '7'; front_h[19][15] = '4'; front_h[19][16] = '4'; front_h[19][17] = '8'
front_h[20][15] = '4'; front_h[20][16] = '4'; front_h[20][17] = '8'
front_h[21][15] = '4'; front_h[21][16] = '8'

# ------------------------------------------------------------------------------
# 2. 秘書くん: 後ろ姿 (Back)
# 正面と完全一致する頭部・輪郭で、後頭部と背中を描画
# ------------------------------------------------------------------------------
back_h = [list(r) for r in rows_base]
for y in range(11, 24):
    for x in range(32):
        if back_h[y][x] in ('6', '4', '5'):
            back_h[y][x] = '2'
        elif back_h[y][x] == '1' and 10 <= x <= 21 and 14 <= y <= 19:
            back_h[y][x] = '2' # 目の位置を毛並みに
    if 13 <= y <= 21:
        back_h[y][15] = '1' # 背骨・スーツの縫い目

# ------------------------------------------------------------------------------
# 3. 秘書くん: お茶/コーヒーを飲む (Tea / Coffee)
# 両手で白い陶器のマグカップを持ち、ふわふわと白い湯気が立ち上る！
# ------------------------------------------------------------------------------
tea_h = [list(r) for r in front_h]
# 湯気 (y: 13..15, x: 15..17)
tea_h[13][16] = '7'; tea_h[13][18] = '7'
tea_h[14][15] = '7'; tea_h[14][17] = '7'
tea_h[15][16] = '7'
# マグカップ (y: 18..22, x: 13..19)
# カップ本体 (白7, コーヒー9, 取っ手7)
tea_h[18][14] = '7'; tea_h[18][15] = '9'; tea_h[18][16] = '9'; tea_h[18][17] = '7' # カップ口
tea_h[19][14] = '7'; tea_h[19][15] = '9'; tea_h[19][16] = '9'; tea_h[19][17] = '7'; tea_h[19][18] = '7' # 取っ手上
tea_h[20][14] = '7'; tea_h[20][15] = '7'; tea_h[20][16] = '7'; tea_h[20][17] = '7'; tea_h[20][18] = '7' # 取っ手下
tea_h[21][14] = '7'; tea_h[21][15] = '7'; tea_h[21][16] = '7'; tea_h[21][17] = '7' # カップ底
# 両手 (茶色2) がカップを包み込む
tea_h[19][13] = '2'; tea_h[20][13] = '2'
tea_h[19][19] = '2'; tea_h[20][19] = '2'

# ------------------------------------------------------------------------------
# 4. 秘書くん: 本を読む (Reading)
# 両手で開いた赤いハードカバーの本を持っている！見開きページが白く文字が見える！
# ------------------------------------------------------------------------------
reading_h = [list(r) for r in front_h]
# 視線を少し下に落とす (目 y:14 を 1ドット下げて y:15 に)
reading_h[14][11] = '6'; reading_h[14][18] = '6'
reading_h[15][11] = '1'; reading_h[15][18] = '1'
# 開いた本 (y: 18..22, x: 11..21)
# 赤いハードカバー外枠 A, 見開きページ白 7, ページ文字の線 1, 本の背表紙 1
# 上辺
reading_h[18][11] = 'A'; reading_h[18][12] = '7'; reading_h[18][13] = '7'; reading_h[18][14] = '7'; reading_h[18][15] = '1'; reading_h[18][16] = '7'; reading_h[18][17] = '7'; reading_h[18][18] = '7'; reading_h[18][19] = 'A'
# 本の中身
reading_h[19][11] = 'A'; reading_h[19][12] = '7'; reading_h[19][13] = '1'; reading_h[19][14] = '7'; reading_h[19][15] = '1'; reading_h[19][16] = '7'; reading_h[19][17] = '1'; reading_h[19][18] = '7'; reading_h[19][19] = 'A'
reading_h[20][11] = 'A'; reading_h[20][12] = '7'; reading_h[20][13] = '7'; reading_h[20][14] = '7'; reading_h[20][15] = '1'; reading_h[20][16] = '7'; reading_h[20][17] = '7'; reading_h[20][18] = '7'; reading_h[20][19] = 'A'
reading_h[21][11] = 'A'; reading_h[21][12] = '7'; reading_h[21][13] = '1'; reading_h[21][14] = '7'; reading_h[21][15] = '1'; reading_h[21][16] = '7'; reading_h[21][17] = '1'; reading_h[21][18] = '7'; reading_h[21][19] = 'A'
# 下辺
reading_h[22][11] = 'A'; reading_h[22][12] = 'A'; reading_h[22][13] = 'A'; reading_h[22][14] = 'A'; reading_h[22][15] = '1'; reading_h[22][16] = 'A'; reading_h[22][17] = 'A'; reading_h[22][18] = 'A'; reading_h[22][19] = 'A'
# 両手 (茶色2)
reading_h[20][10] = '2'; reading_h[20][20] = '2'

# ------------------------------------------------------------------------------
# 5. 秘書くん: ノートPC作業 (PC / Focus)
# 秘書くんの前に、開いたシルバーのノートPC！青い液晶画面が発光！
# ------------------------------------------------------------------------------
pc_h = [list(r) for r in front_h]
# 液晶画面 (y: 17..21, x: 12..20)
for y in range(17, 21):
    pc_h[y][12] = 'B'; pc_h[y][20] = 'B'
    for x in range(13, 20):
        pc_h[y][x] = 'C' # シアン液晶
pc_h[17][12] = 'B'; pc_h[17][20] = 'B' # 画面枠
# キーボード部 (手前水平 y: 21..23, x: 11..21)
for x in range(11, 21):
    pc_h[21][x] = 'B'
    pc_h[22][x] = '1' if (x % 2 == 0) else 'B' # 黒いキートップ
# パチパチ叩く両手
pc_h[21][10] = '2'; pc_h[21][21] = '2'

# ------------------------------------------------------------------------------
# 6. 秘書くん: スヤスヤ寝転ぶ (Lay Down / Sleep)
# ふかふかの水色枕に頭を乗せ、横たわって目を閉じてスヤスヤ寝る！
# ------------------------------------------------------------------------------
lay_h = empty_32()
# ふかふかの枕 (y: 19..24, x: 5..10)
for y in range(19, 25):
    for x in range(5, 11):
        lay_h[y][x] = 'D'
lay_h[19][5] = '.'; lay_h[19][10] = '.'; lay_h[24][5] = '.'; lay_h[24][10] = '.' # 丸み

# 寝ている秘書くんの体 (横向きの丸いフォルム y: 17..25, x: 9..26)
# 耳 (y: 15..17, x: 8..11)
lay_h[15][9] = '1'; lay_h[16][8] = '1'; lay_h[16][9] = '5'; lay_h[16][10] = '1'; lay_h[17][9] = '5'
# 頭部・体輪郭 (焦げ茶1)
for x in range(9, 25):
    lay_h[18][x] = '1'
    lay_h[24][x] = '1'
for y in range(19, 24):
    lay_h[y][8] = '1'
    lay_h[y][25] = '1'

# 中身: 毛並み2、お腹クリーム6
for y in range(19, 24):
    for x in range(9, 25):
        lay_h[y][x] = '6' if (x <= 17) else '2'

# スヤスヤ閉じた目 (--), ピンクのほっぺ 5, 鼻 1
lay_h[20][12] = '1'; lay_h[20][13] = '1' # つむった目
lay_h[21][10] = '5'; lay_h[21][11] = '5' # ほっぺチーク
lay_h[21][14] = '1'                       # 鼻
# 小さな足
lay_h[25][22] = '1'; lay_h[25][23] = '3'
# Zzz... (空中に浮かぶ眠りの文字 y: 12..15, x: 19..25)
lay_h[14][19] = '7'; lay_h[14][20] = '7'; lay_h[15][19] = '7'; lay_h[15][20] = '7' # z
lay_h[12][23] = '7'; lay_h[12][24] = '7'; lay_h[13][23] = '7'; lay_h[13][24] = '7' # Z

# ==============================================================================
# 🐚 カイル風精霊 (32x32) マトリクス設計
# パレット:
# 1: #282C5A (濃紺輪郭・目)
# 2: #343A6E (貝殻リブ・濃青)
# 3: #92A8EB (貝殻ベース水色)
# 4: #C6D4F8 (ハイライト)
# 5: #DCE4FF (シェル発光)
# 6: #F2F6FF (顔の白)
# 7: #FF96A0 (ピンクチーク)
# 8: #D4AF37 (貝PCシェル・ゴールド)
# 9: #00E5FF (貝PCシアン液晶)
# A: #FFFFFF (カップ・本のページ)
# B: #4E342E (コーヒー)
# ==============================================================================
colors_k = sorted(list(set(tuple(c[:3]) for row in raw_data['kyle'] for c in row if c[3] > 0)))
p_map_k = {c: str(i+1) for i, c in enumerate(colors_k)}
rows_k_raw = [''.join(p_map_k.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in raw_data['kyle']]
front_k = [list(r) for r in rows_k_raw]

# カイル: 後ろ姿 (ホタテ貝殻の美しい縦筋扇形)
back_k = [list(r) for r in rows_k_raw]
for y in range(12, 23):
    for x in range(32):
        if back_k[y][x] in ('6', '7'):
            # 放射状リブ
            back_k[y][x] = '2' if (x % 3 == 0) else '3'

# カイル: 貝PC作業 (ホタテ貝殻ノートPCを開いてカタカタ！)
pc_k = [list(r) for r in front_k]
# 貝PC (y: 19..24, x: 10..22)
# 上の貝殻 (液晶 9, 枠 8)
pc_k[19][14] = '8'; pc_k[19][15] = '9'; pc_k[19][16] = '9'; pc_k[19][17] = '8'
pc_k[20][13] = '8'; pc_k[20][14] = '9'; pc_k[20][15] = '9'; pc_k[20][16] = '9'; pc_k[20][17] = '9'; pc_k[20][18] = '8'
# 下の貝殻 (キーボード部 8, キートップ 2)
pc_k[21][12] = '8'; pc_k[21][13] = '2'; pc_k[21][14] = '2'; pc_k[21][15] = '2'; pc_k[21][16] = '2'; pc_k[21][17] = '2'; pc_k[21][18] = '2'; pc_k[21][19] = '8'
pc_k[22][13] = '8'; pc_k[22][14] = '8'; pc_k[22][15] = '8'; pc_k[22][16] = '8'; pc_k[22][17] = '8'; pc_k[22][18] = '8'

# カイル: コーヒーカップ (Tea)
tea_k = [list(r) for r in front_k]
tea_k[18][15] = 'A'; tea_k[18][16] = 'B'; tea_k[18][17] = 'A'
tea_k[19][15] = 'A'; tea_k[19][16] = 'A'; tea_k[19][17] = 'A'; tea_k[19][18] = 'A'
tea_k[20][15] = 'A'; tea_k[20][16] = 'A'; tea_k[20][17] = 'A'

# カイル: 本を読む (Reading)
reading_k = [list(r) for r in front_k]
reading_k[19][14] = '2'; reading_k[19][15] = 'A'; reading_k[19][16] = '1'; reading_k[19][17] = 'A'; reading_k[19][18] = '2'
reading_k[20][14] = '2'; reading_k[20][15] = 'A'; reading_k[20][16] = '1'; reading_k[20][17] = 'A'; reading_k[20][18] = '2'

# カイル: 貝殻を閉じて寝転ぶ (Lay)
lay_k = empty_32()
for y in range(18, 25):
    for x in range(10, 24):
        lay_k[y][x] = '3' if (x % 3 != 0) else '2'
for x in range(12, 22):
    lay_k[17][x] = '2'; lay_k[25][x] = '2'
lay_k[20][18] = '1'; lay_k[20][19] = '1' # つむった目
# Zzz
lay_k[14][22] = '6'; lay_k[14][23] = '6'; lay_k[15][22] = '6'

# 保存
res = {
    'hisho_palette': {
        "1": "#4A3B32", "2": "#A67B5B", "3": "#C49A76",
        "4": "#FFD700", "5": "#EF9A9A", "6": "#F5F5DC",
        "7": "#FFFFFF", "8": "#B8860B", "9": "#4E342E",
        "A": "#B71C1C", "B": "#90A4AE", "C": "#00E5FF",
        "D": "#81D4FA"
    },
    'hisho_front': to_strings(front_h),
    'hisho_back': to_strings(back_h),
    'hisho_tea': to_strings(tea_h),
    'hisho_reading': to_strings(reading_h),
    'hisho_pc': to_strings(pc_h),
    'hisho_lay': to_strings(lay_h),
    'kyle_palette': {
        "1": "#282C5A", "2": "#343A6E", "3": "#92A8EB",
        "4": "#C6D4F8", "5": "#DCE4FF", "6": "#F2F6FF",
        "7": "#FF96A0", "8": "#D4AF37", "9": "#00E5FF",
        "A": "#FFFFFF", "B": "#4E342E"
    },
    'kyle_front': to_strings(front_k),
    'kyle_back': to_strings(back_k),
    'kyle_pc': to_strings(pc_k),
    'kyle_tea': to_strings(tea_k),
    'kyle_reading': to_strings(reading_k),
    'kyle_lay': to_strings(lay_k)
}

with open('web_pet/pixel_perfect_data.json', 'w') as f:
    json.dump(res, f, indent=2)

print("Saved pixel_perfect_data.json successfully!")
