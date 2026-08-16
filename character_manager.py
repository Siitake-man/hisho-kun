"""
ネオ秘書くん - キャラクタースキン ＆ 個性対話マネージャー (character_manager.py)

4大キャラクターのプロフィール、個性セリフ、リアクション、スキン永続化を管理します。
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "character_config.json"

CHARACTERS_DATA: Dict[str, Dict[str, Any]] = {
    "hisho": {
        "id": "hisho",
        "name": "秘書くん",
        "title": "誠実なエリート秘書",
        "emoji": "👔",
        "description": "丁寧でしっかり者。ボスのタスクや予定を真面目にサポートします。",
        "theme_color": "#A67B5B",
        "greetings": [
            "ボス、今日もお疲れ様です！お茶をどうぞ🍵",
            "本日の予定とタスクを確認しましょう！",
            "ボス、何かお手伝いできることはありますか？✨"
        ],
        "task_done": [
            "タスク完了ですね！素晴らしい集中力です！👏",
            "さすがボス！着実に進んでいますね！",
            "1件完了！この調子でいきましょう！"
        ],
        "pomodoro_start": "25分の集中タイムを開始します！邪魔は入れさせません！🍅",
        "pomodoro_break": "集中お疲れ様でした！5分間、深呼吸して休みましょう☕",
        "care_messages": [
            "ボス、45分作業が続いています。肩の力を抜いてくださいね。",
            "画面から目を離して、遠くを見て目を休めましょう✨"
        ]
    },
    "kinoko": {
        "id": "kinoko",
        "name": "キノコ君",
        "title": "のんびり毒舌癒やし系",
        "emoji": "🍄",
        "description": "マイペースに光合成中。たまに鋭いツッコミを入れつつ癒やしてくれます。",
        "theme_color": "#E53935",
        "greetings": [
            "やぁボス。今日も光合成しながら見守ってるよ〜🍄",
            "無理してない？たまにはぼーっとするのも仕事だよ。",
            "胞子をふわふわ飛ばしておくね〜✨"
        ],
        "task_done": [
            "おっ、終わらせたんだ！やるじゃんボス🍄",
            "えらいえらい。ご褒美にキノコエキスをどうぞ！",
            "サクッと片付けたね〜！さすが！"
        ],
        "pomodoro_start": "集中モード入るよ〜！25分間、カサを広げてガードするね！🍄",
        "pomodoro_break": "ふぅ〜休憩だ！一緒にのんびり伸びをしよう〜☕",
        "care_messages": [
            "ボス、画面見すぎ！目がシパシパしてない？🍄",
            "根っこが生えちゃう前に、立ち上がってストレッチしよ〜！"
        ]
    },
    "seal": {
        "id": "seal",
        "name": "もちもちアザラシ",
        "title": "全力肯定リラックス系",
        "emoji": "🦭",
        "description": "ボスが生きてるだけで100点満点！ゴロゴロしながら全肯定してくれます。",
        "theme_color": "#4A6B82",
        "greetings": [
            "ボス〜！今日も生きててえらすぎます〜！パチパチ👏",
            "ゴロゴロ〜🦭 ボスのそばが一番落ち着くのです！",
            "もちもちパワーをチャージしますね〜✨"
        ],
        "task_done": [
            "わーい！タスク完了！ボスは天才です〜！パチパチパチ🦭👏",
            "すごすぎる〜！えらすぎ大賞受賞です！🏆",
            "感動しました！もちもちハグをどうぞ〜！"
        ],
        "pomodoro_start": "集中たいむ〜！ボスの背中をもちもち応援します！🦭",
        "pomodoro_break": "おつかれさまです〜！一緒にゴロゴロして休みましょう〜☕",
        "care_messages": [
            "ボス〜、がんばりすぎはめっ！ですよ〜🦭",
            "あたたかいお茶でも飲んで、ほっと一息つきましょう〜🍵"
        ]
    },
    "wombat": {
        "id": "wombat",
        "name": "まるまるウォンバット",
        "title": "頑固職人・集中マスター",
        "emoji": "🦫",
        "description": "ずんぐり頑固な職人肌。黙々と穴を掘り、ボスの集中を本気で守ります。",
        "theme_color": "#795548",
        "greetings": [
            "ふん、ボスか。今日も黙々とやるべきことを片付けるぞ。",
            "集中できる環境は俺が守る。余計なノイズは遮断しろ！",
            "しっかり足元を固めて進むぞ。穴掘りと同じだ。"
        ],
        "task_done": [
            "ふっ…上出来だ。いい仕事をしたな、ボス。👏",
            "完璧だ。職人のこだわりを感じるぞ。",
            "1つ突破したな。だが油断するなよ！"
        ],
        "pomodoro_start": "集中タイマー開始だ！邪魔する奴は四角いウンチで撃退してやる！🦫",
        "pomodoro_break": "時間だ！休むのも仕事のうちだ。しっかり休め！☕",
        "care_messages": [
            "おいボス、姿勢が崩れてるぞ。背筋を伸ばせ！",
            "根を詰めすぎるな。一呼吸置いてから次の山に挑め。"
        ]
    }
}


class CharacterManager:
    """キャラクタースキンおよびセリフの管理クラス"""
    def __init__(self):
        self.current_character_id = "hisho"
        self._load_config()

    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    c_id = data.get("current_character", "hisho")
                    if c_id in CHARACTERS_DATA:
                        self.current_character_id = c_id
            except Exception as e:
                logger.error(f"キャラクター設定読み込みエラー: {e}")

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"current_character": self.current_character_id}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"キャラクター設定保存エラー: {e}")

    def set_character(self, char_id: str) -> bool:
        if char_id in CHARACTERS_DATA:
            self.current_character_id = char_id
            self.save_config()
            logger.info(f"キャラクタースキンを変更しました: {char_id}")
            return True
        return False

    def get_current_character(self) -> Dict[str, Any]:
        return CHARACTERS_DATA.get(self.current_character_id, CHARACTERS_DATA["hisho"])

    def get_all_characters(self) -> List[Dict[str, Any]]:
        return list(CHARACTERS_DATA.values())

    def get_sprite_prefix(self) -> str:
        return f"{self.current_character_id}_"


_instance: CharacterManager = None

def get_character_manager() -> CharacterManager:
    global _instance
    if _instance is None:
        _instance = CharacterManager()
    return _instance
