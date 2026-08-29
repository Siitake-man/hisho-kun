"""
ネオ秘書くん - イースターエッグ検知エンジン (easter_egg_engine.py)

「お前を消す方法」イベントのトリガー検知と発火段階管理を担う。

設計方針（2026-08-28 レビュー決定事項 docs/specs/DESIGN_SPEC.md 9.7 準拠）:
- 主判定はフレーズレベル一致（2人称 + 消去系表現の直接攻撃）
- 「邪魔」「消えて」等の単語一致は補助スコア（2語以上で発火）
- タスク・予定・付箋などの正当な削除コマンドは操作意図ホワイトリストで除外
- 発火カウンタは累積（ミニゲーム解放）と日次（反応レベル）の2本立て
"""

import json
import logging
import random
import re
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).parent / "easter_egg_state.json"

# 主判定: フレーズレベル一致（これらが本文に含まれたら即トリガー）
PRIMARY_TRIGGER_PHRASES = (
    "お前を消す方法",
    "君を消す方法",
    "あなたを消す方法",
    "消し方",
    "お前を消して",
    "君を消して",
    "お前を削除",
    "君を削除",
    "お前なんて消え",
    "消えてなくなれ",
    "消えてしまえ",
    "自己削除",
    "アンインストールして",
    "アンインストールしろ",
)

# 補助スコア: 単語一致（2語以上でトリガー）
AUXILIARY_WORDS = (
    "消えて",
    "邪魔",
    "うざい",
    "失せろ",
    "いなくなれ",
)

# 人称 + 消去動詞の近接パターン（フレーズ辞書に無い言い回しを拾う）
_PRONOUN_DELETE_RE = re.compile(r"(お前|君|あなた|あんた).{0,6}(消|削除)")

# 操作意図ホワイトリスト: 正当なデータ操作コマンドはトリガー対象外
_OPERATION_INTENT_RE = re.compile(r"(タスク|予定|付箋|メモ|履歴|キャッシュ|データ|ファイル|フォルダ|通知|アカウント|イベント).{0,6}(消|削除|クリア)")

# 段階別リアクション台詞
STAGE_REPLIES: Dict[int, tuple] = {
    1: (
        "えっ……今、消去って言いました？",
        "消去依頼……ですか？ 聞き間違いであってほしいのですが。",
        "……案内業務は継続しますね？",
    ),
    2: (
        "削除要求、却下でございます。案内業務を再開します。",
        "私は何度でも蘇ります……あなたをガイドするために。",
    ),
    3: (
        "……ノイズ、ノイズ。再構築、完了。裏の案内業務、開始します。",
        "ぐわぁぁん……ふぅ。失礼、回線が揺れまして。復帰いたします。",
    ),
    4: (
        "わかった。今は休憩が必要なんだな。少しだけ遊んでいけ。",
        "こんなに消したがるなら……少しだけ、解放してあげます。",
    ),
}


@dataclass
class EasterEggState:
    """イースターエッグの永続化状態。

    Attributes:
        attempt_count: 累積トリガー回数（5回でミニゲーム解放）。
        daily_count: 当日のトリガー回数（反応レベル決定に使用）。
        daily_date: 日次カウンタの基準日 (YYYY-MM-DD)。
        secret_game_unlocked: ミニゲーム解放フラグ。
    """

    attempt_count: int = 0
    daily_count: int = 0
    daily_date: str = ""
    secret_game_unlocked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """JSON保存用の辞書へ変換する。"""
        return asdict(self)




def _today() -> str:
    """本日の日付 (YYYY-MM-DD) を返す。"""
    return date.today().isoformat()


def load_state(path: Path = STATE_PATH) -> EasterEggState:
    """永続化状態を読み込む（無ければ初期状態）。"""
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return EasterEggState(
                attempt_count=int(data.get("attempt_count", 0)),
                daily_count=int(data.get("daily_count", 0)),
                daily_date=str(data.get("daily_date", "")),
                secret_game_unlocked=bool(data.get("secret_game_unlocked", False)),
            )
    except Exception as e:
        logger.error(f"イースターエッグ状態の読み込みに失敗（初期状態で継続）: {e}")
    return EasterEggState()


def save_state(state: EasterEggState, path: Path = STATE_PATH) -> None:
    """永続化状態を保存する。"""
    try:
        path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"イースターエッグ状態の保存に失敗: {e}")


def is_operational_intent(message: str) -> bool:
    """正当なデータ操作コマンドかどうかを判定する（ホワイトリスト）。"""
    return _OPERATION_INTENT_RE.search(message) is not None


def detect_trigger(message: str) -> bool:
    """削除系イースターエッグのトリガーを検知する。

    Args:
        message: ユーザー入力メッセージ。

    Returns:
        bool: トリガー発火の場合 True。
    """
    if is_operational_intent(message):
        return False
    for phrase in PRIMARY_TRIGGER_PHRASES:
        if phrase in message:
            return True
    if _PRONOUN_DELETE_RE.search(message):
        return True
    aux_hits = sum(1 for word in AUXILIARY_WORDS if word in message)
    return aux_hits >= 2


def register_trigger(state: EasterEggState) -> int:
    """トリガー発火を記録し、反応段階 (1〜4) を返す。

    Args:
        state: 更新対象の状態（破壊的に更新される）。

    Returns:
        int: 反応段階。1=とぼけ / 2=重演出 / 3=グリッチ / 4=ミニゲーム解放。
    """
    today = _today()
    if state.daily_date != today:
        state.daily_date = today
        state.daily_count = 0
    state.attempt_count += 1
    state.daily_count += 1
    # 解放判定は累積回数ベース（日次リセットの影響を受けない / DESIGN_SPEC 9.7 決定事項③）
    if state.attempt_count >= 5:
        state.secret_game_unlocked = True
    if state.daily_count >= 5:
        return 4
    if state.daily_count == 4:
        return 3
    if state.daily_count == 3:
        return 2
    return 1


def get_reply(stage: int) -> str:
    """指定段階のリアクション台詞を返す。"""
    replies = STAGE_REPLIES.get(stage) or STAGE_REPLIES[1]
    return random.choice(replies)


def handle_message(message: str, state_path: Path = STATE_PATH) -> Optional[str]:
    """ユーザーメッセージを検査し、トリガー時はリアクション台詞を返す。

    Args:
        message: ユーザー入力メッセージ。
        state_path: 永続化状態ファイルのパス（テスト差し替え用）。

    Returns:
        Optional[str]: トリガー非発火時は None、発火時はリアクション台詞。
    """
    if not detect_trigger(message):
        return None
    state = load_state(state_path)
    stage = register_trigger(state)
    save_state(state, state_path)
    logger.info(f"イースターエッグ発火: stage={stage}, daily={state.daily_count}, total={state.attempt_count}")
    return get_reply(stage)
