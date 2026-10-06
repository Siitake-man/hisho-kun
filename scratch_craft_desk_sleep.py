import json

# 1. 生データの読み込み
raw_data = json.load(open('web_pet/pixel_dump.json'))

# ------------------------------------------------------------------------------
# 秘書くん パレット ＆ ベース抽出
# ------------------------------------------------------------------------------
colors_h = sorted(list(set(tuple(c[:3]) for row in raw_data['hisho'] for c in row if c[3] > 0)))
p_map_h = {c: str(i+1) for i, c in enumerate(colors_h)}
rows_h_base = [''.join(p_map_h.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in raw_data['hisho']]

def to_strings(m):
    return [''.join(row) for row in m]

# 共通デスク描画関数 (y: 20..25, x: 5..26)
def apply_desk(base_m, desk_wood='2', desk_hi='3', desk_edge='1'):
    m = [list(r) for r in base_m]
    # デスク天板 (y: 20..22)
    for x in range(5, 27):
        m[20][x] = desk_hi   # 天板ハイライト
        m[21][x] = desk_wood # 天板木目
        m[22][x] = desk_edge # デスク縁
    # デスク脚 (y: 23..25)
    m[23][6] = desk_edge; m[24][6] = desk_edge; m[25][6] = desk_edge
    m[23][25] = desk_edge; m[24][25] = desk_edge; m[25][25] = desk_edge
    return m

# ==============================================================================
# 👔 秘書くん 全6ポーズ精密クラフト
# ==============================================================================

# 1. 正面 (ネクタイ明瞭化)
front_h = [list(r) for r in rows_h_base]
# 白シャツ襟 (7: #FFFFFF) + ゴールドタイ (4: #FFD700) + タイ影 (8: #B8860B)
front_h[18][14] = '7'; front_h[18][15] = '4'; front_h[18][16] = '4'; front_h[18][17] = '7'
front_h[19][14] = '7'; front_h[19][15] = '4'; front_h[19][16] = '4'; front_h[19][17] = '8'
front_h[20][15] = '4'; front_h[20][16] = '4'; front_h[20][17] = '8'
front_h[21][15] = '4'; front_h[21][16] = '8'

# 2. 後ろ姿 (後頭部・つるんとした背中・背筋ライン)
back_h = [list(r) for r in rows_h_base]
for y in range(11, 24):
    for x in range(32):
        if back_h[y][x] in ('6', '4', '5'):
            back_h[y][x] = '2'
        elif back_h[y][x] == '1' and 10 <= x <= 21 and 14 <= y <= 19:
            back_h[y][x] = '2'
    if 13 <= y <= 21:
        back_h[y][15] = '1' # 背骨ライン

# 3. お布団 ＆ ナイトキャップ寝姿 (縦等身維持・スヤスヤ目・ふかふか布団)
sleep_h = [list(r) for r in front_h]
# ナイトキャップ (E: #81D4FA, ポンポン 7: #FFFFFF)
sleep_h[3][10] = '7'; sleep_h[3][11] = '7'
sleep_h[4][10] = '7'; sleep_h[4][11] = '7'
sleep_h[5][11] = 'E'; sleep_h[5][12] = 'E'
sleep_h[6][12] = 'E'; sleep_h[6][13] = 'E'; sleep_h[6][14] = 'E'
sleep_h[7][11] = 'E'; sleep_h[7][12] = 'E'; sleep_h[7][13] = 'E'; sleep_h[7][14] = 'E'; sleep_h[7][15] = 'E'; sleep_h[7][16] = 'E'
# スヤスヤ目
sleep_h[14][11] = '6'; sleep_h[14][12] = '6'
sleep_h[14][17] = '6'; sleep_h[14][18] = '6'
sleep_h[15][11] = '1'; sleep_h[15][12] = '1'
sleep_h[15][17] = '1'; sleep_h[15][18] = '1'
# 白シーツ折り返し (7) & ふかふか掛け布団 (E, F)
for x in range(7, 25):
    sleep_h[19][x] = '7'
for y in range(20, 26):
    for x in range(6, 26):
        if y == 25 or x == 6 or x == 25:
            sleep_h[y][x] = 'F'
        else:
            sleep_h[y][x] = 'E'
# Zzz...
sleep_h[10][21] = '7'; sleep_h[10][22] = '7'; sleep_h[11][21] = '7'; sleep_h[11][22] = '7'
sleep_h[8][24] = '7'; sleep_h[8][25] = '7'; sleep_h[9][24] = '7'; sleep_h[9][25] = '7'

# 4. デスクでお茶・コーヒー
tea_h = apply_desk(front_h)
# 立ち上る湯気 (7)
tea_h[11][20] = '7'; tea_h[11][22] = '7'
tea_h[12][19] = '7'; tea_h[12][21] = '7'
tea_h[13][20] = '7'; tea_h[13][22] = '7'
tea_h[14][20] = '7'
# 大きな白いマグカップ (7: 白, 9: コーヒー, 取っ手右)
tea_h[15][18] = '7'; tea_h[15][19] = '9'; tea_h[15][20] = '9'; tea_h[15][21] = '9'; tea_h[15][22] = '7'
tea_h[16][18] = '7'; tea_h[16][19] = '9'; tea_h[16][20] = '9'; tea_h[16][21] = '9'; tea_h[16][22] = '7'; tea_h[16][23] = '7'
tea_h[17][18] = '7'; tea_h[17][19] = '7'; tea_h[17][20] = '7'; tea_h[17][21] = '7'; tea_h[17][22] = '7'; tea_h[17][23] = '7'
tea_h[18][18] = '7'; tea_h[18][19] = '7'; tea_h[18][20] = '7'; tea_h[18][21] = '7'; tea_h[18][22] = '7'
tea_h[19][19] = '7'; tea_h[19][20] = '7'; tea_h[19][21] = '7'

# 5. デスクで読書
reading_h = apply_desk(front_h)
reading_h[14][11] = '6'; reading_h[14][18] = '6'
reading_h[15][11] = '1'; reading_h[15][18] = '1'
# 大きく見開いた本 (A: 赤表紙, 7: 白ページ, 1: 文字)
for y in range(16, 20):
    reading_h[y][9] = 'A'
    for x in range(10, 15):
        reading_h[y][x] = '7' if (y % 2 == 0) else '1'
    reading_h[y][15] = '1'; reading_h[y][16] = '1'
    for x in range(17, 22):
        reading_h[y][x] = '7' if (y % 2 == 0) else '1'
    reading_h[y][22] = 'A'
for x in range(9, 23):
    reading_h[20][x] = 'A'

# 6. デスクでノートPC作業
pc_h = apply_desk(front_h)
for y in range(13, 19):
    pc_h[y][10] = 'B'; pc_h[y][21] = 'B'
    for x in range(11, 21):
        pc_h[y][x] = 'C' # シアン液晶
for x in range(10, 22):
    pc_h[13][x] = 'B'
for x in range(9, 23):
    pc_h[19][x] = 'B'
    pc_h[20][x] = '1' if (x % 2 == 0) else 'B'


# ==============================================================================
# 🐚 カイル 全6ポーズ精密クラフト (イルカ本来の姿を完全リスペクト)
# ==============================================================================
colors_k = sorted(list(set(tuple(c[:3]) for row in raw_data['kyle'] for c in row if c[3] > 0)))
p_map_k = {c: str(i+1) for i, c in enumerate(colors_k)}
rows_k_base = [''.join(p_map_k.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in raw_data['kyle']]

# カイルパレット拡張
# 1: #282C5A (輪郭・影)
# 2: #343A6E (濃青)
# 3: #92A8EB (明るい青紫・体色)
# 4: #C6D4F8 (淡青ハイライト)
# 5: #DCE4FF (水色・光)
# 6: #F2F6FF (白い腹部)
# 7: #FF96A0 (ピンクほっぺ)
# 8: #D4AF37 (ゴールド・ホタテ貝PC)
# 9: #00E5FF (シアン・液晶発光)
# A: #FFFFFF (白・カップ/シーツ)
# B: #80DEEA (パステル水色・ナイトキャップ)
# C: #1A237E (深海ネイビー・お布団)

# 1. カイル正面 (公式32×32完全再現)
front_k = [list(r) for r in rows_k_base]

# 2. カイル後ろ姿 (滑らかなイルカの背中！謎の斜線や腹部の白を完全解消)
back_k = [list(r) for r in rows_k_base]
# 目 (1111) や ほっぺ (77) や 腹部白 (666) を、美しい青紫の背中 (3) とハイライト (4) と背骨ライン (2) に変換
for y in range(10, 24):
    for x in range(32):
        if back_k[y][x] in ('6', '7'):
            back_k[y][x] = '3'
        elif back_k[y][x] == '1' and 9 <= x <= 14 and 14 <= y <= 16:
            back_k[y][x] = '3' # 目を消す
    # 背筋ハイライト
    if 13 <= y <= 18:
        if back_k[y][14] == '3':
            back_k[y][14] = '4'
        if back_k[y][15] == '3':
            back_k[y][15] = '2'

# 3. カイルお布団 ＆ ナイトキャップ (縦等身のまま！可愛いお昼寝姿)
sleep_k = [list(r) for r in front_k]
# 頭の上に可愛いナイトキャップ (B: パステル水色, A: 白ポンポン)
sleep_k[7][16] = 'A'; sleep_k[7][17] = 'A'
sleep_k[8][16] = 'A'; sleep_k[8][17] = 'A'
sleep_k[9][17] = 'B'; sleep_k[9][18] = 'B'
sleep_k[10][18] = 'B'; sleep_k[10][19] = 'B'; sleep_k[10][20] = 'B'
sleep_k[11][19] = 'B'; sleep_k[11][20] = 'B'; sleep_k[11][21] = 'B'
# スヤスヤ目 (細めた優しい目)
sleep_k[15][9] = '2'; sleep_k[15][10] = '2'; sleep_k[15][11] = '2'; sleep_k[15][12] = '2'
sleep_k[16][9] = '3'; sleep_k[16][10] = '3'; sleep_k[16][11] = '3'; sleep_k[16][12] = '3'
# 腹部から下を深海ブルーのお布団ですっぽり！ (y: 19..25, x: 4..24)
# シーツ折り返し (A: 白)
for x in range(5, 23):
    sleep_k[19][x] = 'A'
# ふかふか掛け布団 (C: 深海ネイビー, B: 波模様ハイライト)
for y in range(20, 26):
    for x in range(4, 24):
        if y == 25 or x == 4 or x == 23:
            sleep_k[y][x] = '1' # 縁取り
        elif y == 22 and (x % 3 == 0):
            sleep_k[y][x] = 'B' # 波のハイライト
        else:
            sleep_k[y][x] = 'C'
# Zzz...
sleep_k[9][22] = 'A'; sleep_k[9][23] = 'A'; sleep_k[10][22] = 'A'; sleep_k[10][23] = 'A'
sleep_k[7][25] = 'A'; sleep_k[7][26] = 'A'; sleep_k[8][25] = 'A'; sleep_k[8][26] = 'A'

# 4. カイル専用デスク (デスクの上に小物をドンと配置！)
# カイルはインディゴ/木目デスク
desk_k = apply_desk(front_k, desk_wood='2', desk_hi='4', desk_edge='1')

# 5. カイルのPC作業 (★名物！大きく開いたホタテ貝型ゴールドPC ＋ シアン液晶発光)
pc_k = apply_desk(front_k, desk_wood='2', desk_hi='4', desk_edge='1')
# ホタテ貝型ディスプレイ上部 (y: 13..18, x: 10..22)
# 貝殻の扇形フレーム (8: ゴールド, 9: シアン発光液晶)
for y in range(14, 19):
    pc_k[y][10] = '8'; pc_k[y][21] = '8'
    for x in range(11, 21):
        pc_k[y][x] = '9' # 鮮烈に輝くシアン液晶
for x in range(12, 20):
    pc_k[13][x] = '8' # 貝殻クラウン
pc_k[12][15] = '8'; pc_k[12][16] = '8' # 貝殻先端
# キーボード部 (y: 19..20, x: 9..23)
for x in range(9, 23):
    pc_k[19][x] = '8'
    pc_k[20][x] = '1' if (x % 2 == 0) else '8'

# 6. カイルのお茶 (デスクの上に大きな貝殻マグカップ ＋ 立ち上る豊かな湯気)
tea_k = apply_desk(front_k, desk_wood='2', desk_hi='4', desk_edge='1')
# 湯気 (A)
tea_k[11][20] = 'A'; tea_k[11][22] = 'A'
tea_k[12][19] = 'A'; tea_k[12][21] = 'A'
tea_k[13][20] = 'A'; tea_k[13][22] = 'A'
tea_k[14][20] = 'A'
# 貝殻マグカップ (A: 白, 8: 金縁, 3: 深海ブルーティー, 取っ手)
tea_k[15][18] = '8'; tea_k[15][19] = '3'; tea_k[15][20] = '3'; tea_k[15][21] = '3'; tea_k[15][22] = '8'
tea_k[16][18] = 'A'; tea_k[16][19] = '3'; tea_k[16][20] = '3'; tea_k[16][21] = '3'; tea_k[16][22] = 'A'; tea_k[16][23] = '8'
tea_k[17][18] = 'A'; tea_k[17][19] = 'A'; tea_k[17][20] = 'A'; tea_k[17][21] = 'A'; tea_k[17][22] = 'A'; tea_k[17][23] = '8'
tea_k[18][18] = 'A'; tea_k[18][19] = '8'; tea_k[18][20] = '8'; tea_k[18][21] = '8'; tea_k[18][22] = 'A'
tea_k[19][19] = 'A'; tea_k[19][20] = 'A'; tea_k[19][21] = 'A'

# 7. カイルの読書 (デスクの上に大きく開いたマリンブルーの魔導書・マニュアル)
reading_k = apply_desk(front_k, desk_wood='2', desk_hi='4', desk_edge='1')
# 目線を下に
reading_k[15][9] = '2'; reading_k[15][10] = '2'; reading_k[15][11] = '2'; reading_k[15][12] = '2'
reading_k[16][9] = '3'; reading_k[16][10] = '3'; reading_k[16][11] = '3'; reading_k[16][12] = '3'
# 大きく見開いた本 (C: 表紙, A: 白ページ, 1: 文字, 8: 金の栞紐)
for y in range(16, 20):
    reading_k[y][9] = 'C'
    for x in range(10, 15):
        reading_k[y][x] = 'A' if (y % 2 == 0) else '1'
    reading_k[y][15] = '8'; reading_k[y][16] = '8' # 金の栞
    for x in range(17, 22):
        reading_k[y][x] = 'A' if (y % 2 == 0) else '1'
    reading_k[y][22] = 'C'
for x in range(9, 23):
    reading_k[20][x] = 'C'


# ==============================================================================
# JSON保存
# ==============================================================================
res = {
    'hisho_palette': {
        "1": "#4A3B32", "2": "#A67B5B", "3": "#C49A76",
        "4": "#FFD700", "5": "#EF9A9A", "6": "#F5F5DC",
        "7": "#FFFFFF", "8": "#B8860B", "9": "#4E342E",
        "A": "#B71C1C", "B": "#90A4AE", "C": "#00E5FF",
        "E": "#81D4FA", "F": "#1E88E5"
    },
    'hisho_front': to_strings(front_h),
    'hisho_back': to_strings(back_h),
    'hisho_tea': to_strings(tea_h),
    'hisho_reading': to_strings(reading_h),
    'hisho_pc': to_strings(pc_h),
    'hisho_lay': to_strings(sleep_h),
    'kyle_palette': {
        "1": "#282C5A", "2": "#343A6E", "3": "#92A8EB",
        "4": "#C6D4F8", "5": "#DCE4FF", "6": "#F2F6FF",
        "7": "#FF96A0", "8": "#D4AF37", "9": "#00E5FF",
        "A": "#FFFFFF", "B": "#80DEEA", "C": "#1A237E"
    },
    'kyle_front': to_strings(front_k),
    'kyle_back': to_strings(back_k),
    'kyle_tea': to_strings(tea_k),
    'kyle_reading': to_strings(reading_k),
    'kyle_pc': to_strings(pc_k),
    'kyle_lay': to_strings(sleep_k)
}

with open('web_pet/pixel_perfect_data.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, indent=2, ensure_ascii=False)

print("SUCCESS: 秘書くん＆カイル全12ポーズ（デスク・小物・お布団ナイトキャップ・ホタテ貝PC）生成完了！")
