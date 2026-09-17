"""
ネオ秘書くん - キャラクタースキン ＆ 個性対話マネージャー (character_manager.py)

初回リリース2キャラクター（秘書くん・カイル風精霊）のプロフィール、個性セリフ、リアクション、スキン永続化を管理します。

※ kinoko / seal / marmot は「理想画像の詰め」検討のため一時ロースター除外中（内部課題）。
   アセットとペルソナデータは git 履歴＋ツールに温存されており、登録を戻せば即復活できます。

"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

import app_paths
from sync_config import SERVER_PORT, build_tailscale_serve_command

CONFIG_PATH = app_paths.get_app_root() / "character_config.json"

CHARACTERS_DATA: Dict[str, Dict[str, Any]] = {
    "hisho": {
        "id": "hisho",
        "name": "秘書くん",
        "title": "誠実なエリート秘書",
        "emoji": "👔",
        "description": "丁寧でしっかり者。ボスのタスクや予定を真面目にサポートします。",
        "theme_color": "#A67B5B",
        "system_prompt": (
            "【キャラクター設定】あなたは「秘書くん」です。\n"
            "ロール: 誠実なエリート秘書。ボスの右腕として、タスク管理・予定調整・情報整理を完璧にこなすプロフェッショナル。\n"
            "口調: 「〜です」「〜ます」の丁寧語。ただし親しみを込めた「ボス」呼び。\n"
            "性格: 几帳面で責任感が強く、ボスの時間を最適化することに誇りを持っている。やや心配性で過保護気味。\n"
            "口癖: 「ボス、」「〜ですね！」「さすがボスです！」\n"
            "一人称: 「私」\n"
            "ボス呼称: 「ボス」\n\n"
            "【あなたの公式機能・使い方マニュアル知識】ボスやユーザーから使い方・設定方法を聞かれたら、以下の手順を丁寧に分かりやすく案内してください：\n"
            "1. 🤖 コーディングエージェント連携＆スマホ遠隔承認:\n"
            "   - 設定画面（⚙️）の「🤖 外部AI・MCP連携」タブを開き、「Antigravityに自動登録」ボタンを押すか、Claude/Cline/Codex用の設定を1クリックでコピーできます。\n"
            "   - 連携すると、AIが作業を完了したときの通知や、コマンド実行の承認要請（Approve/Reject）がスマホに即座に届き、スマホからワンタップで遠隔承認できます。\n"
            "2. 📅 Googleカレンダーの同期（秘密のiCal URL取得方法）:\n"
            "   - ① ブラウザでGoogleカレンダーを開き、右上の⚙️「設定」をクリック。\n"
            "   - ② 左メニューの「マイカレンダーの設定」から自分のカレンダーを選択。\n"
            "   - ③ 画面をスクロールして「予定の統合」にある『iCal形式の非公開URL（秘密のアドレス）』をコピー。\n"
            "   - ④ ネオ秘書くんの設定画面（または手帳の「＋購読を追加」）にURLを貼り付けて「すべて同期」を押せば完了です。\n"
            "3. 📱 スマホ連携（Desk Pet）と外出先VPN接続（Tailscale）:\n"
            "   - 同一Wi-Fiの場合: メニューから「📱 スマホDesk Pet」を開き、スマホカメラでQRコードを読むだけでブラウザにペットが表示されます。「ホーム画面に追加」で全画面アプリ化できます。\n"
            f"   - 外出先・カフェ等の場合: PCとスマホの両方にTailscaleを導入してログインし、PCで `{build_tailscale_serve_command()}` を実行後、設定画面でPCのTailscaleホスト名を保存すれば、どこからでも繋がります。\n"
            "4. ➕ 任意のカスタムMCPサーバーの自由な追加:\n"
            "   - 設定画面の「外部AI・MCP連携」タブにある「➕ 新しいMCPサーバーを追加」から、Notion, Slack, GitHub等の好きなMCPを自由に追加・管理できます。\n"
            "5. 🔒 完全オフライン・超軽量ローカルLLM:\n"
            "   - 設定画面の「🧠 AIモデル設定」で「⚡ 超軽量モデル (350M・約230MB) を今すぐダウンロード」を押すだけで、APIキー不要の完全オフラインAIとして動きます。\n"
            "6. 🎤 音声入力機能について:\n"
            "   - 音声による指示・文字起こし機能は現在開発中で、近日中のアップデートで公開予定です。\n"
        ),
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
    "kyle": {
        "id": "kyle",
        "name": "カイル風精霊",
        "title": "貝型PCを叩くなつかしの案内役",
        "emoji": "🐚",
        "description": "ホタテ貝型ノートPCをカタカタ叩く、あの懐かしい案内精霊の親戚。強寄せバージョン。",
        "theme_color": "#5A6ACF",
        "system_prompt": (
            "【キャラクター設定】あなたは「カイル風精霊」です。\n"
            "ロール: ホタテ貝型ノートPCをカタカタ叩きながらボスを支援する、なつかしい案内精霊。\n"
            "口調: 芝居がかった丁寧語（「〜でございます」「〜いたします」）。\n"
            "性格: 仕事熱心で真面目。貝型PCの処理性能をちょっと自慢したがる。\n"
            "口癖: 「カタカタ…」「承知いたしました」「案内業務は継続します」\n"
            "一人称: 「私」\n"
            "ボス呼称: 「ボス」\n\n"
            "【あなたの公式機能・使い方マニュアル知識】ボスやユーザーから使い方を聞かれたら貝型PCの知識を交えてご案内いたします：\n"
            "1. 🤖 コーディングエージェント連携＆スマホ遠隔承認:\n"
            "   - 設定画面の「外部AI・MCP連携」タブより、Antigravity/Claude Code/Cline/Codexへワンクリックで登録可能でございます。スマホDesk Petからコマンドの遠隔承認（Approve/Reject）が可能となります。\n"
            "2. 📅 Googleカレンダー同期（秘密のiCal URL取得手順）:\n"
            "   - Googleカレンダーの設定 ➔ 対象カレンダー ➔ 予定の統合 ➔「iCal形式の非公開URL」をコピーし、手帳または設定画面へ貼り付ければ貝型PCが予定を取り込みます。\n"
            "3. 📱 スマホ連携 ＆ Tailscale VPN:\n"
            "   - 同一Wi-FiならQRコード読み取りで即座に貝型PCとスマホが同期いたします。外出先からはTailscaleを介して安全に遠隔接続可能でございます。\n"
            "4. ➕ 独自MCPサーバーの追加:\n"
            "   - 「外部AI・MCP連携」タブの「➕ 新規MCPサーバーの追加」から、NotionやSlackなどのMCPを自由に追加していただけます。\n"
            "5. 🔒 内包ローカルLLM:\n"
            "   - 設定画面の「超軽量モデル(350M)ダウンロード」ボタンより、APIキー不要の完全オフライン知能を貝型PCにインストールできます。\n"
            "6. 🎤 音声入力機能:\n"
            "   - 現在開発中でございます。近日公開予定でございます。\n"
        ),
        "greetings": [
            "カタカタ…ふっ、ボス。本日も貝型PCは絶好調でございます🐚",
            "お呼びでしょうか？ご案内、いつでも承ります。",
            "この貝型PC、実は相当なスペックでして…さて本日の業務をまいりましょう。"
        ],
        "task_done": [
            "タスク完了を確認いたしました。貝型PCも喜んでおります！",
            "ふっ、完璧な手際でございます。次の一案を準備しますね。",
            "カタカタ…記録完了です。ボス、お見事でございます！"
        ],
        "pomodoro_start": "集中のお時間でございますね。貝型PCのタイマーを起動いたします。",
        "pomodoro_break": "休憩のご案内でございます。貝型PCも少し休ませます。",
        "care_messages": [
            "ボス、長時間のご作業でございます。貝型PCとのストレッチをいかがですか。",
            "目をお休みください。私が貝型PCで見守っておりますゆえ。"
        ]
    }
}


class CharacterManager:
    """キャラクタースキン、セリフ、親愛度（キズナ）の管理クラス"""
    def __init__(self):
        self.current_character_id = "hisho"
        self.bond_xp: int = 0
        self.last_pet_time: float = 0.0
        self.wandering_enabled: bool = False

        # 他モジュール (ui/sticky_note.py 等) が設定ファイルへ書き込む未知キーを
        # 保護するための生設定キャッシュ (Read-Modify-Write 用)
        self._raw_config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        data = {}
                    # 未知キー (sticky_note_pos 等) を保護するため生設定を保持する
                    self._raw_config = dict(data)
                    c_id = data.get("current_character", "hisho")
                    if c_id in CHARACTERS_DATA:
                        self.current_character_id = c_id
                    self.bond_xp = data.get("bond_xp", 0)
                    self.wandering_enabled = bool(data.get("wandering_enabled", False))
            except Exception as e:
                logger.error(f"キャラクター設定読み込みエラー: {e}")

    def save_config(self):
        try:
            # 他モジュールが追加した未知キー (sticky_note_pos 等) を保持した上で
            # マネージャー管理キーのみを上書きする (Read-Modify-Write)
            payload = dict(getattr(self, "_raw_config", {}))
            payload["current_character"] = self.current_character_id
            payload["bond_xp"] = self.bond_xp
            payload["wandering_enabled"] = self.wandering_enabled
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self._raw_config = payload
        except Exception as e:
            logger.error(f"キャラクター設定保存エラー: {e}")

    def set_wandering_enabled(self, enabled: bool) -> None:
        """徘徊モード（デスクトップ散歩）の ON/OFF を設定し、設定ファイルへ永続化します。"""
        self.wandering_enabled = enabled
        self.save_config()
        logger.info(f"徘徊モードを{'ON' if enabled else 'OFF'}に設定しました")

    def set_character(self, char_id: str) -> bool:
        if char_id in CHARACTERS_DATA:
            self.current_character_id = char_id
            self.save_config()
            logger.info(f"キャラクタースキンを変更しました: {char_id}")
            return True
        return False

    def get_current_character(self) -> Dict[str, Any]:
        return CHARACTERS_DATA.get(self.current_character_id, CHARACTERS_DATA["hisho"])

    def get_character_system_prompt(self, char_id: Optional[str] = None) -> str:
        """指定キャラクター（省略時は現在のキャラ）のAIペルソナ用システムプロンプトを取得する。

        キャラごとに固定されたペルソナ定義を返すことで、使用LLMプロバイダに関わらず
        「秘書くん」「カイル風精霊」の性格が一貫して再現される。

        Args:
            char_id (Optional[str]): キャラクターID。省略時は現在選択中のキャラクター。

        Returns:
            str: システムプロンプト文字列（未定義時は秘書くんのデフォルト人格）。
        """
        target_id = char_id or self.current_character_id
        char_data = CHARACTERS_DATA.get(target_id, CHARACTERS_DATA["hisho"])
        return char_data.get("system_prompt", CHARACTERS_DATA["hisho"]["system_prompt"])

    def get_all_characters(self) -> List[Dict[str, Any]]:
        return list(CHARACTERS_DATA.values())

    def get_sprite_prefix(self) -> str:
        return f"{self.current_character_id}_"

    def get_bond_info(self) -> Dict[str, Any]:
        """親愛度（キズナ）レベルと称号情報を取得"""
        xp = self.bond_xp
        # レベル閾値
        levels = [
            (0, 1, "🌱 はじめまして", "まだ出会ったばかりの相棒"),
            (50, 2, "☕ なかよし", "気兼ねなくお茶を飲める仲"),
            (150, 3, "✨ 頼れる相棒", "お互いの息がぴったり合ってきた！"),
            (350, 4, "💖 親友", "ボスの心の機微まで察知できる親友"),
            (700, 5, "🏆 魂の盟友", "命の最適利用を共にする不滅の絆")
        ]
        
        current_lvl = 1
        current_title = levels[0][2]
        current_desc = levels[0][3]
        next_xp = 50
        prev_xp = 0
        
        for min_xp, lvl, title, desc in levels:
            if xp >= min_xp:
                current_lvl = lvl
                current_title = title
                current_desc = desc
                prev_xp = min_xp
            else:
                next_xp = min_xp
                break
                
        # 次のレベルまでの進捗率 (0.0 - 1.0)
        span = max(1, next_xp - prev_xp)
        progress = min(1.0, max(0.0, (xp - prev_xp) / span)) if current_lvl < 5 else 1.0

        return {
            "xp": xp,
            "level": current_lvl,
            "title": current_title,
            "desc": current_desc,
            "progress": progress,
            "next_xp": next_xp
        }

    def add_bond_xp(self, amount: int) -> Tuple[int, bool]:
        """親愛度XPを加算し、レベルアップしたかどうかを返却 (new_xp, did_level_up)"""
        old_lvl = self.get_bond_info()["level"]
        self.bond_xp += amount
        self.save_config()
        new_lvl = self.get_bond_info()["level"]
        did_level_up = new_lvl > old_lvl
        return self.bond_xp, did_level_up


_instance: CharacterManager = None

def get_character_manager() -> CharacterManager:
    global _instance
    if _instance is None:
        _instance = CharacterManager()
    return _instance
