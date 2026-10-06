import json

data = json.load(open('web_pet/pixel_dump.json'))

# 秘書くん
colors_h = sorted(list(set(tuple(c[:3]) for row in data['hisho'] for c in row if c[3] > 0)))
p_map_h = {c: str(i+1) for i, c in enumerate(colors_h)}
rows_h = [''.join(p_map_h.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in data['hisho']]

# 正面 (ネクタイ改善)
front_h = list(rows_h)
# インデックス 18 (首元): 白襟 7 と ノット 4
r18 = list(front_h[18])
r18[14] = '7'; r18[15] = '4'; r18[16] = '4'; r18[17] = '7'
front_h[18] = ''.join(r18)

# インデックス 19: ネクタイ結び目下〜本体
r19 = list(front_h[19])
r19[14] = '7'; r19[15] = '4'; r19[16] = '4'; r19[17] = '8'
front_h[19] = ''.join(r19)

# インデックス 20: ネクタイ本体
r20 = list(front_h[20])
r20[15] = '4'; r20[16] = '4'; r20[17] = '8'
front_h[20] = ''.join(r20)

# インデックス 21: ネクタイ剣先 (尖り)
r21 = list(front_h[21])
r21[15] = '4'; r21[16] = '8'
front_h[21] = ''.join(r21)

# 後ろ姿 (hisho_back)
back_h = []
for y, row in enumerate(rows_h):
    if 11 <= y <= 23:
        new_row = list(row)
        for x in range(len(new_row)):
            if new_row[x] in ('6', '4', '5'):
                new_row[x] = '2'
            elif new_row[x] == '1' and 10 <= x <= 21 and 14 <= y <= 19:
                new_row[x] = '2'
        # 背中の中央ライン
        if 13 <= y <= 21:
            new_row[15] = '1'
        back_h.append(''.join(new_row))
    else:
        back_h.append(row)

# 寝転び (hisho_lay) - 90度回転＋目をつぶる
# 32x32 配列を右に90度回転
import numpy as np
arr_front = np.array([list(r) for r in rows_h])
# 秘書くんの実体領域 y: 4..25, x: 7..24 を切り出して回転
sub = arr_front[4:26, 7:25]
rot = np.rot90(sub, -1) # 右に90度

lay_h = [['.' for _ in range(32)] for _ in range(32)]
# 中央下部に配置
offset_y = 20 - rot.shape[0] // 2
offset_x = 16 - rot.shape[1] // 2
for y in range(rot.shape[0]):
    for x in range(rot.shape[1]):
        ch = rot[y, x]
        # 目を寝ている目(-)に
        lay_h[offset_y + y][offset_x + x] = ch
rows_lay_h = [''.join(r) for r in lay_h]

# カイル
colors_k = sorted(list(set(tuple(c[:3]) for row in data['kyle'] for c in row if c[3] > 0)))
p_map_k = {c: str(i+1) for i, c in enumerate(colors_k)}
rows_k = [''.join(p_map_k.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in data['kyle']]

# カイル後ろ姿
back_k = []
for y, row in enumerate(rows_k):
    new_row = list(row)
    for x in range(len(new_row)):
        if new_row[x] in ('6', '7'):
            new_row[x] = '3' if (x % 3 != 0) else '2'
    back_k.append(''.join(new_row))

with open('web_pet/pixel_hd2d_data.json', 'w') as f:
    json.dump({
        'hisho_palette': {
            "1": "#4A3B32", "2": "#A67B5B", "3": "#C49A76",
            "4": "#FFD700", "5": "#EF9A9A", "6": "#F5F5DC",
            "7": "#FFFFFF", "8": "#B8860B"
        },
        'hisho_front': front_h,
        'hisho_back': back_h,
        'hisho_lay': rows_lay_h,
        'kyle_palette': {str(i+1): f'#{r:02X}{g:02X}{b:02X}' for i, (r,g,b) in enumerate(colors_k)},
        'kyle_front': rows_k,
        'kyle_back': back_k
    }, f, indent=2)

print("Saved pixel_hd2d_data.json with tie improvement successfully")
