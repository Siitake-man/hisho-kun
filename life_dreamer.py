"""
ネオ秘書くん - 自律生活ドリーマーエンジン (life_dreamer.py)

ペットが時刻に応じて自律的に生活する（食事・入浴・睡眠・仕事・休息等）様を
生成し、天候変化もシミュレートするエンジン。

- LLM (Gemini等) を「ドリーマー」として定期呼び出しし、生活イベントと
  天候をJSON形式で生成する。
- LLM失敗時は時刻ベースのルールで必ず状態を更新する（フォールバック）。
- 生成した状態はスレッドセーフに保持され、/api/status 経由でスマホPWAへ、
  コールバック経由でPCデスクトップペットへ配信される。
"""

import json
import logging
import random
import threading
import time
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 生活イベントの種別 → PC/スマホペットのアニメ状態へのマッピング
ACTIVITY_PET_STATE_MAP = {
    "waking": "stretch",
    "breakfast": "happy",
    "lunch": "happy",
    "dinner": "cheer",
    "bathing": "care",
    "working": "focus",
    "resting": "tea",
    "reading": "reading",
    "sleeping": "sleepy",
    "playing": "celebrate",
}

WEATHER_LABELS = {
    "sunny": "☀️ 晴れ",
    "cloudy": "☁️ 曇り",
    "rainy": "🌧️ 雨",
    "snowy": "❄️ 雪",
    "thunder": "⚡ 嵐",
}


class LifeDreamerEngine:
    """ペットの自律生活状態を生成・保持するエンジン（スレッドセーフ）。

    ドリーマーLLMによる定期生成と、LLM失敗時の時刻ベースルール生成により、
    常に最新の生活状態（活動・天候・描写文）を提供する。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._on_state_change: Optional[Callable[[Dict[str, Any]], None]] = None
        # 初期状態は現在時刻ルールから導出
        self._state: Dict[str, Any] = {
            "current_activity": "resting",
            "weather": "sunny",
            "temperature": 20.0,
            "city": "",
            "message": "",
            "last_generated_at": 0.0,
            "history": [],
        }
        self._apply_rule_state(initial=True)

    # ---------------------------------------------------------------------
    # 公開API
    # ---------------------------------------------------------------------
    def set_on_state_change(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """状態変化時に呼ばれるコールバックを登録する（PCペットミラー用）。"""
        self._on_state_change = callback

    def get_life_state(self) -> Dict[str, Any]:
        """現在のライフステートのコピーを返す（スレッドセーフ）。"""
        with self._lock:
            snapshot = dict(self._state)
            snapshot["history"] = list(self._state["history"])
            return snapshot

    def start(self) -> None:
        """ドリーマー定期生成スレッドを起動する（多重起動防止付き）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._dreamer_loop,
            daemon=True,
            name="LifeDreamerThread",
        )
        self._thread.start()
        logger.info("🌈 [LifeDreamer] 自律生活ドリーマーエンジンを起動しました")

    # ---------------------------------------------------------------------
    # 内部実装: ステート更新
    # ---------------------------------------------------------------------
    def _update_state(self, activity: str, weather: str, message: str) -> None:
        """状態を更新し、必要ならコールバックを発火する。"""
        changed = False
        with self._lock:
            prev = (self._state["current_activity"], self._state["weather"])
            if (activity, weather) != prev or message != self._state["message"]:
                changed = True
                self._state["current_activity"] = activity
                self._state["weather"] = weather
                self._state["message"] = message
                self._state["last_generated_at"] = time.time()
                history: List[Dict[str, Any]] = self._state["history"]
                history.append({
                    "activity": activity,
                    "weather": weather,
                    "message": message,
                    "at": time.time(),
                })
                if len(history) > 20:
                    del history[:-20]
        if changed and self._on_state_change is not None:
            try:
                self._on_state_change(self.get_life_state())
            except Exception as e:  # コールバック側のエラーで本体を止めない
                logger.warning(f"🌈 [LifeDreamer] 状態変化コールバックエラー: {e}")

    # ---------------------------------------------------------------------
    # 内部実装: ルールベースフォールバック
    # ---------------------------------------------------------------------
    def _rule_activity(self, hour: int) -> tuple:
        """時刻から (活動種別, 描写文) のタプルを返す。"""
        if 5 <= hour < 7:
            return ("waking", "ふぁ〜…朝が来ましたね。そろそろ目を覚ます時間です。")
        if 7 <= hour < 9:
            return ("breakfast", "モグモグ…朝ごはんの時間です！今日も一日頑張ります💪")
        if 12 <= hour < 13:
            return ("lunch", "おなかすいたなぁ…ランチタイムです🍚")
        if 18 <= hour < 19:
            return ("dinner", "夕飯のにおい…！ボス、一緒に晩御飯にしましょう🍽️")
        if 19 <= hour < 21:
            return ("bathing", "ぽかぽか…お風呂に入ってさっぱりします🛁")
        if 21 <= hour < 23:
            return ("reading", "寝る前にちょっとだけ読書を…📖")
        if hour >= 23 or hour < 5:
            return ("sleeping", "すやすや…おやすみなさいませ…💤 zZZ")
        return ("working", "ボスのお仕事を見守っています！応援していますよ🔥")

    def _apply_rule_state(self, initial: bool = False) -> None:
        """現在時刻ベースのルールで状態を更新する（LLM失敗時のフォールバック）。"""
        now = datetime.now()
        activity, message = self._rule_activity(now.hour)
        weather = self._rule_weather(now.day)
        if initial:
            with self._lock:
                self._state.update({
                    "current_activity": activity,
                    "weather": weather,
                    "message": message,
                    "last_generated_at": time.time(),
                })
        else:
            self._update_state(activity, weather, message)

    @staticmethod
    def _rule_weather(day_of_month: int) -> str:
        """日付から決定的に天候を導出する（同じ日は同じ天気になる）。"""
        candidates = ["sunny", "cloudy", "rainy", "sunny", "sunny", "cloudy", "rainy"]
        base = candidates[day_of_month % len(candidates)]
        if day_of_month % 11 == 0:
            return "snowy"
        if day_of_month % 17 == 0:
            return "thunder"
        return base

    def _dreamer_loop(self) -> None:
        """5〜15分間隔でドリーマーLLMを呼び、生活イベントを生成し続ける。"""
        # 初回起動時にリアル天気を取得
        self._refresh_real_weather()
        while True:
            try:
                self._generate_once()
            except Exception as e:
                logger.warning(f"🌈 [LifeDreamer] 生成エラー（ルールで継続）: {e}")
                try:
                    self._apply_rule_state()
                except Exception:
                    pass
            wait_sec = random.randint(300, 900)
            time.sleep(wait_sec)

    def _refresh_real_weather(self) -> None:
        """リアルタイム天気を取得し、life_state の weather を上書きする。"""
        try:
            from weather_tools import get_weather as _get_weather
            w = _get_weather()
            if w.get("error"):
                logger.info(f"🌈 [LifeDreamer] リアル天気取得失敗（架空天気を維持）: {w['error']}")
                return
            real_weather = w["weather"]
            temp = w.get("temperature", 20.0)
            city = w.get("city", "不明")
            temp_str = f" {temp}°C" if temp else ""
            city_str = f" ({city})" if city else ""
            # 天気情報を life_state に反映（アクティビティは変えない）
            with self._lock:
                old_weather = self._state["weather"]
                self._state["weather"] = real_weather
                self._state["temperature"] = temp
                self._state["city"] = city
                # 天気が変わったら履歴にも記録
                if old_weather != real_weather:
                    self._state["message"] = f"外は{WEATHER_LABELS.get(real_weather, real_weather)}{temp_str}{city_str}です"
                    self._state["last_generated_at"] = time.time()
            logger.info(f"🌈 [LifeDreamer] リアル天気を反映: {WEATHER_LABELS.get(real_weather, real_weather)}{temp_str}{city_str}")
        except Exception as e:
            logger.debug(f"🌈 [LifeDreamer] リアル天気取得エラー（スキップ）: {e}")

    def _build_prompt(self, state: Dict[str, Any], now_str: str, real_weather_label: str = "") -> str:
        """ドリーマーLLM向けのプロンプトを構築する。"""
        history_lines = [
            f"- {h['message']}" for h in state.get("history", [])[-5:]
        ] or ["- （まだ何もありません）"]
        weather_names = " / ".join(f"{k}({v})" for k, v in WEATHER_LABELS.items())
        activity_names = " / ".join(ACTIVITY_PET_STATE_MAP.keys())
        real_weather_line = f"現在の実際の天気: {real_weather_label}\n" if real_weather_label else ""
        return (
            "あなたはデスクトップ秘書ペットの「生活の夢想家」です。\n"
            "ペットが今どんな生活をしているか、次の一つのイベントを創作してください。\n\n"
            f"現在時刻: {now_str}\n"
            f"{real_weather_line}"
            "直近の行動履歴:\n" + "\n".join(history_lines) + "\n\n"
            "以下のJSONのみを出力してください（説明文は禁止、コードブロックも禁止）:\n"
            '{"activity": "<活動種別>", "weather": "<天候キー>", '
            '"message": "<日本語の可愛い生活描写、40文字以内>"}\n\n'
            f"activity は次のいずれか: {activity_names}\n"
            f"weather は次のいずれか: {weather_names}\n"
            "時刻・天候・履歴に自然に合うものを選んでください。"
        )

    def _parse_llm_json(self, raw: str) -> Optional[Dict[str, str]]:
        """LLM出力からJSON部分を抽出してパースする（揺らぎに耐性を持たせる）。"""
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
        activity = str(data.get("activity", "")).strip()
        weather = str(data.get("weather", "")).strip()
        message = str(data.get("message", "")).strip()
        if activity not in ACTIVITY_PET_STATE_MAP:
            return None
        if weather not in WEATHER_LABELS:
            weather = self._rule_weather(datetime.now().day)
        if not message:
            message = "…"
        return {"activity": activity, "weather": weather, "message": message}

    def _generate_once(self) -> None:
        """ドリーマーLLMを一度呼び出して状態を更新する。"""
        from llm_factory import get_llm_factory

        # リアル天気を更新（前回取得から1時間以上経過していれば自動取得）
        self._refresh_real_weather()

        # 現在の state（リアル天気が反映済み）を取得
        state = self.get_life_state()
        real_weather = state.get("weather", "sunny")
        real_weather_label = WEATHER_LABELS.get(real_weather, real_weather)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        prompt = self._build_prompt(state, now_str, real_weather_label)

        try:
            model = get_llm_factory().create_model(temperature=0.9)
            response = model.invoke(prompt)
            raw = response.content if isinstance(response.content, str) else str(response.content)
        except Exception as e:
            logger.info(f"🌈 [LifeDreamer] LLM呼び出し失敗、ルールにフォールバック: {e}")
            self._apply_rule_state()
            return

        parsed = self._parse_llm_json(raw)
        if parsed is None:
            logger.info("🌈 [LifeDreamer] LLM出力の解析に失敗、ルールにフォールバック")
            self._apply_rule_state()
            return

        # LLMの天気は無視し、リアル天気を強制適用
        parsed["weather"] = real_weather

        logger.info(
            f"🌈 [LifeDreamer] 生活イベント生成: {parsed['activity']} / "
            f"{parsed['weather']} / {parsed['message']}"
        )
        self._update_state(parsed["activity"], parsed["weather"], parsed["message"])


# =============================================================================
# シングルトン提供
# =============================================================================
_global_engine: Optional[LifeDreamerEngine] = None
_global_engine_lock = threading.Lock()


def get_life_dreamer() -> LifeDreamerEngine:
    """LifeDreamerEngine のシングルトンを取得する。"""
    global _global_engine
    if _global_engine is None:
        with _global_engine_lock:
            if _global_engine is None:
                _global_engine = LifeDreamerEngine()
    return _global_engine
