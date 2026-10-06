import json

data = json.load(open('web_pet/pixel_perfect_data.json'))

html_template = open('web_pet/hd2d_showcase.html', encoding='utf-8').read()

# PIXEL_DATA を丸ごと置換
json_str = json.dumps(data, indent=2)
new_js_data = f"const PIXEL_DATA = {json_str};\n"

start_marker = "const PIXEL_DATA = {"
end_marker = "let currentChar = 'hisho';"

part1 = html_template.split(start_marker)[0]
part2 = html_template.split(end_marker)[1]

new_html = part1 + new_js_data + "\n    " + end_marker + part2

# drawExactProceduralPet の中で、外部画像ロード部分 (imgCache) を完全撤廃し、
# すべて PIXEL_DATA から100%ドット絵描画するように書き換える！
render_func_old = """    function drawExactProceduralPet(c, x, y, charId, pose) {
      c.save();

      // 1. 足元接地シャドウ (自然な影のみ、四角い光枠は完全排除)
      const isLay = (pose === 'lay');
      c.fillStyle = 'rgba(0, 0, 0, 0.65)';
      c.beginPath();
      c.ellipse(x, y + 26, isLay ? 50 : 36, isLay ? 10 : 8, 0, 0, Math.PI * 2);
      c.fill();

      // 呼吸による自然な微動
      const breatheY = isLay ? 0 : Math.sin(animTick * 0.05) * 2;

      // pose が reading, tea, pc の場合は公式スプライト画像を滑らかに描画
      if (pose === 'reading' || pose === 'tea' || pose === 'pc') {
        const suffix = frameToggle ? '_2.png' : '_1.png';
        let action = 'idle';
        if (pose === 'tea') action = 'tea';
        else if (pose === 'reading') action = 'reading';
        else if (pose === 'pc') action = (charId === 'kyle') ? 'focus' : 'reading';

        const imgSrc = `../assets/dot/${charId}/${action}${suffix}`;
        const img = getCachedImage(imgSrc);
        if (img && img.complete) {
          const drawW = 100, drawH = 100;
          c.drawImage(img, Math.round(x - drawW / 2), Math.round(y - drawH / 2 + breatheY - 6), drawW, drawH);
        }
        c.restore();
        return;
      }

      // pose が front, back, lay の場合はプロシージャルドット絵マトリクスから描画！
      let palette = (charId === 'hisho') ? PIXEL_DATA.hisho_palette : PIXEL_DATA.kyle_palette;
      let matrix = PIXEL_DATA.hisho_front;

      if (charId === 'hisho') {
        if (pose === 'front') matrix = PIXEL_DATA.hisho_front;
        else if (pose === 'back') matrix = PIXEL_DATA.hisho_back;
        else if (pose === 'lay') matrix = PIXEL_DATA.hisho_lay;
      } else {
        if (pose === 'front') matrix = PIXEL_DATA.kyle_front;
        else if (pose === 'back') matrix = PIXEL_DATA.kyle_back;
        else if (pose === 'lay') matrix = PIXEL_DATA.kyle_back; // カイルは貝殻を閉じる
      }

      // スケーリング: 32×32 のマトリクスを 1ドット = 3.2px で描画 (約102px 四方)
      const scale = 3.2;
      const startX = Math.round(x - (32 * scale) / 2);
      const startY = Math.round(y - (32 * scale) / 2 + breatheY);

      for (let row = 0; row < 32; row++) {
        const line = matrix[row] || "................................";
        for (let col = 0; col < 32; col++) {
          const ch = line[col] || '.';
          if (ch === '.') continue;

          const color = palette[ch];
          if (!color) continue;

          c.fillStyle = color;
          c.fillRect(
            Math.round(startX + col * scale),
            Math.round(startY + row * scale),
            Math.ceil(scale),
            Math.ceil(scale)
          );
        }
      }

      c.restore();
    }"""

render_func_new = """    function drawExactProceduralPet(c, x, y, charId, pose) {
      c.save();

      // 1. 足元接地シャドウ
      const isLay = (pose === 'lay');
      c.fillStyle = 'rgba(0, 0, 0, 0.65)';
      c.beginPath();
      c.ellipse(x, y + 26, isLay ? 52 : 36, isLay ? 10 : 8, 0, 0, Math.PI * 2);
      c.fill();

      // 呼吸による自然な微動
      const breatheY = isLay ? 0 : Math.sin(animTick * 0.05) * 2;

      // すべて 100% プロシージャル・ドット絵マトリクスから描画！
      let palette = (charId === 'hisho') ? PIXEL_DATA.hisho_palette : PIXEL_DATA.kyle_palette;
      let key = `${charId}_${pose}`;
      let matrix = PIXEL_DATA[key] || PIXEL_DATA[`${charId}_front`];

      // スケーリング: 32×32 のマトリクスを 1ドット = 3.2px でシャープに描画
      const scale = 3.2;
      const startX = Math.round(x - (32 * scale) / 2);
      const startY = Math.round(y - (32 * scale) / 2 + breatheY);

      for (let row = 0; row < 32; row++) {
        const line = matrix[row] || "................................";
        for (let col = 0; col < 32; col++) {
          const ch = line[col] || '.';
          if (ch === '.') continue;

          const color = palette[ch];
          if (!color) continue;

          c.fillStyle = color;
          c.fillRect(
            Math.round(startX + col * scale),
            Math.round(startY + row * scale),
            Math.ceil(scale),
            Math.ceil(scale)
          );
        }
      }

      c.restore();
    }"""

if render_func_old in new_html:
    new_html = new_html.replace(render_func_old, render_func_new)
    print("Replaced render function successfully")
else:
    print("WARNING: render_func_old not found, replacing manually")

open('web_pet/hd2d_showcase.html', 'w', encoding='utf-8').write(new_html)
print("Updated hd2d_showcase.html successfully")
