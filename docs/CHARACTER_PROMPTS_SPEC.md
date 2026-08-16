# 🎨 ネオ秘書くん キャラクタースプライト生成プロンプト仕様書
**最終更新日時**: 2026-08-16 19:25

本ドキュメントは、Midjourney、DALL-E 3、Bing Image Creator、Stable Diffusion 等の外部画像生成AIを用いて、ネオ秘書くんの高品質なキャラクタースプライトを自作・生成するためのプロンプト集と組み込み手順書です。

---

## 📌 共通の画像生成ルール（透過・切り抜きを容易にする設定）

1. **背景**: 必ず **純白背景（Pure White Background: `#FFFFFF`）** または **グリーンバック（Solid Bright Green Background: `#00FF00`）** を指定してください。
2. **構図**: **中央配置（Centered）**、**全身（Full Body）**、**孤立したマスコット（Isolated Mascot）** を指定。影（Cast Shadow）は薄めにするか無しに設定。
3. **スタイル**: `16-bit retro game pixel art aesthetic`, `cute chibi anime mascot`, `sharp clean contours` を共通呪文として付与。

---

## 🎭 4大キャラクターの原画プロンプト（英語 ＆ 日本語）

### 1. 🤖 秘書くん (Hisho-kun) - 知性派・3本毛の秘書
> **デザイン特徴**: 頭頂部に3本のピョコンとした毛、真面目な丸メガネ、茶色いレトロスーツ、ベージュシャツ、手帳を胸に抱える、知性的で可愛い笑顔。

```text
Pixel art sprite character of 'Hisho-kun', cute chibi anime secretary mascot boy, three distinct hair strands sticking up on top of head, round spectacles glasses, dark brown retro secretary suit jacket with skirt or trousers, light beige shirt, holding a small leather notebook, warm friendly smile, clean 16-bit retro game pixel art aesthetic, centered character on pure white background (#FFFFFF), sharp pixel contours, full body, isolated mascot illustration, masterpiece
```

---

### 2. 🍄 キノコ君 (Kinoko-kun) - 元気いっぱい・森の妖精
> **デザイン特徴**: 赤地に白水玉のキノコ傘帽子、元気な笑顔、緑のスカーフ、小さな手足、ピョンピョン跳ねるようなポーズ。

```text
Pixel art sprite character of 'Kinoko-kun', cute chibi mushroom boy mascot, big vibrant red mushroom cap hat with crisp white polka dots, playful smiling anime boy face, cute green scarf necktie, small chibi body, cheerful energetic pose, clean 16-bit retro game pixel art aesthetic, centered character on pure white background (#FFFFFF), sharp pixel contours, full body, isolated mascot illustration, masterpiece
```

---

### 3. 🦭 もちもち大福アザラシ (Seal) - 癒やし系・純白のアザラシ赤ちゃん
> **デザイン特徴**: まん丸もちもちの大福ボディ、真っ白な毛並み、つぶらな黒い瞳、ほんのりピンクのほっぺ、小さな前足（ヒレ）。

```text
Pixel art sprite character of a baby harp seal mascot, cute mochi-like ultra chubby round white seal, big glossy round black eyes, subtle soft pink blush on cheeks, tiny cute flippers, innocent comforting expression, clean 16-bit retro game pixel art aesthetic, centered character on pure white background (#FFFFFF), sharp pixel contours, full body, isolated mascot illustration, masterpiece
```

---

### 4. 🦫 ウォンバット (Wombat) - どっしり癒やし・四角いお尻
> **デザイン特徴**: コロンとした丸四角いフォルム、茶色いフサフサの毛並み、つぶらな瞳、黒い丸鼻、短い手足、穏やかでマイペースな表情。

```text
Pixel art sprite character of a cute chubby wombat mascot, sturdy rounded-square body silhouette, soft warm brown fur texture, small round black eyes, cute dark nose button, tiny short paws, calm gentle peaceful expression, clean 16-bit retro game pixel art aesthetic, centered character on pure white background (#FFFFFF), sharp pixel contours, full body, isolated mascot illustration, masterpiece
```

---

## 🎬 モーション・表情差分プロンプト（全29フレーム対応表）

生成したキャラクターの姿勢・表情を変更する際に追加するプロンプト修飾子です。

| フレーム名 | 動作・表情 | プロンプト追加キーワード |
|:---|:---|:---|
| `idle_1` | 待機（基本） | standing naturally, neutral cute smiling |
| `idle_2` | 待機（呼吸） | standing naturally, slightly bobbing down, breathing animation frame |
| `look_left` | 視線（左） | looking to the left side, eyes shifted left |
| `look_right` | 視線（右） | looking to the right side, eyes shifted right |
| `look_up` | 視線（上） | looking up towards the sky/user |
| `look_down` | 視線（下） | looking down towards floor |
| `thinking_1` | 考え中 1 | hand on chin, thoughtful looking up to the side, pondering expression |
| `thinking_2` | 考え中 2 | tilted head, cute curious questioning expression with small sweat drop |
| `happy` | 笑顔・喜び | joyful smiling with closed arched eyes, blushing cheeks, happy sparkles |
| `pet_love` | なでなで（愛） | blissful face, big pink heart floating above head, loving expression |
| `focus_1` | 集中作業 1 | wearing red headband or looking determined, studying/typing focused |
| `sleepy_1` | 居眠り 1 | droopy eyes, yawning with small open mouth |
| `sleepy_2` | 睡眠 | sleeping soundly, closed eyes, floating 'Zzz' pixel bubble |
| `alarm_ask` | 承認要請・質問 | surprised alert expression, holding a sign or waving hands, exclamation mark |
| `cheer` | 応援・ガッツ | punching both hands in the air, energetic cheering pose |
| `tea_1` | お茶休憩 | holding a steaming Japanese green tea teacup, relaxing pose |
| `reading_1` | 読書 | reading a small open retro book, intellectual cute pose |
| `stretch_1` | ストレッチ | stretching both arms high above head, refreshing yawny stretch |
| `celebrate_1` | タスク完了祝い | holding party popper or jumping with confetti/stars, triumphal pose |
| `care_1` | 寄り添い・気遣い | gentle warm smile, offering a warm drink or blanket, comforting pose |
| `night_1` | 夜間見守り | wearing nightcap or holding small brass candle/lantern, quiet nighttime mood |

---

## 🛠️ 画像の組み込み手順（3ステップ）

1. **背景の透過**:
   - 生成したJPEG/PNG画像を「背景透過ツール（remove.bg 等）」またはPhotoshop/GIMPで背景を完全透明（Alpha Channel）にしてPNG保存します。
2. **リサイズ**:
   - 推奨サイズ: **横140px × 縦140px**（または 128x128px / 256x256px）
3. **ファイル名の命名と配置**:
   - `assets/` フォルダ配下に以下のルールで配置します：
     - 秘書くん: `assets/hisho_[frame_name].png` （例: `assets/hisho_idle_1.png`）
     - キノコ君: `assets/kinoko_[frame_name].png`
     - アザラシ: `assets/seal_[frame_name].png`
     - ウォンバット: `assets/wombat_[frame_name].png`
   - ※ デフォルト共通スプライトとして利用する場合は `assets/[frame_name].png` に上書き配置するだけで即座に反映されます！
