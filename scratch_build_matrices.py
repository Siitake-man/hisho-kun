import json

data = json.load(open('web_pet/pixel_dump.json'))

# 秘書くん
colors_h = sorted(list(set(tuple(c[:3]) for row in data['hisho'] for c in row if c[3] > 0)))
p_map_h = {c: str(i+1) for i, c in enumerate(colors_h)}
rows_h = [''.join(p_map_h.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in data['hisho']]

# カイル
colors_k = sorted(list(set(tuple(c[:3]) for row in data['kyle'] for c in row if c[3] > 0)))
p_map_k = {c: str(i+1) for i, c in enumerate(colors_k)}
rows_k = [''.join(p_map_k.get(tuple(c[:3]), '.') if c[3]>0 else '.' for c in row) for row in data['kyle']]

with open('web_pet/pixel_matrices.json', 'w') as f:
    json.dump({
        'hisho_palette': {str(i+1): f'#{r:02X}{g:02X}{b:02X}' for i, (r,g,b) in enumerate(colors_h)},
        'hisho_front': rows_h,
        'kyle_palette': {str(i+1): f'#{r:02X}{g:02X}{b:02X}' for i, (r,g,b) in enumerate(colors_k)},
        'kyle_front': rows_k
    }, f, indent=2)

print("Saved pixel_matrices.json successfully")
