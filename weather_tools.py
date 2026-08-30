"""
ネオ秘書くん - リアルタイム天気取得ツール (weather_tools.py)

Open-Meteo（無料・APIキー不要）と ip-api.com で現在地の天気を取得する。
life_dreamer がこのデータを利用して、現実の天気に合った生活描写を生成する。
"""
import json
import logging
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# キャッシュ（1時間）
_weather_cache: Dict[str, Any] = {}
_weather_cache_time: float = 0.0
_weather_cache_lock = threading.Lock()
CACHE_TTL_SEC = 3600  # 1時間

import os
from pathlib import Path

# 手動設定の場所（設定画面から書き換え）
_manual_location: Optional[str] = None  # "lat,lon" または都市名
_manual_location_lock = threading.Lock()

WEATHER_LOCATION_ENV_KEY = "WEATHER_LOCATION"


def load_location_from_env() -> Optional[str]:
    """設定された地域文字列を .env / 環境変数から取得してセットする。"""
    loc = os.getenv(WEATHER_LOCATION_ENV_KEY, "").strip()
    if loc:
        set_location(loc)
        return loc
    return None


def get_current_location_setting() -> str:
    """現在設定されている地域文字列を返す（未設定なら空文字）。"""
    with _manual_location_lock:
        return _manual_location or ""


def save_location(location_str: str) -> None:
    """現在地を手動設定し、.env へ永続保存する。"""
    loc_clean = location_str.strip()
    set_location(loc_clean)
    try:
        from dotenv import set_key
        import app_paths
        env_path = app_paths.get_app_root() / ".env"
        set_key(str(env_path), WEATHER_LOCATION_ENV_KEY, loc_clean)
        os.environ[WEATHER_LOCATION_ENV_KEY] = loc_clean
        logger.info(f"地域設定を .env に保存しました: {loc_clean}")
    except Exception as e:
        logger.warning(f"地域設定の .env 保存に失敗 (メモリ上のみ適用): {e}")


def set_location(location_str: str) -> None:
    """現在地を手動設定する（空文字で解除＝IP自動検出に戻る）。"""
    with _manual_location_lock:
        global _manual_location
        _manual_location = location_str.strip() or None
    # キャッシュをクリアして次回取得時に再取得させる
    with _weather_cache_lock:
        global _weather_cache_time
        _weather_cache_time = 0.0


def get_weather() -> Dict[str, Any]:
    """現在地の天気情報を取得する（キャッシュ付き・スレッドセーフ）。

    Returns:
        {"weather": "sunny/cloudy/rainy/snowy/thunder",
         "temperature": 22.5, "city": "Tokyo", "error": None}
        失敗時は error に文字列が入る
    """
    global _weather_cache_time, _weather_cache
    now = time.time()
    with _weather_cache_lock:
        if now - _weather_cache_time < CACHE_TTL_SEC and _weather_cache:
            return dict(_weather_cache)

    # 1. 位置情報を取得
    lat, lon, city = _get_location()
    if lat is None:
        result = {"weather": "sunny", "temperature": 20.0, "city": "不明", "error": "位置情報の取得に失敗しました"}
        with _weather_cache_lock:
            _weather_cache = result
            _weather_cache_time = now
        return dict(result)

    # 2. 天気情報を取得
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current_weather=true&timezone=auto"
            f"&forecast_days=1"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "NeoSecretary/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cw = data.get("current_weather", {})
        wmo_code = cw.get("weathercode", 0)
        temperature = cw.get("temperature", 20.0)
        weather = _wmo_to_condition(wmo_code)
        result = {
            "weather": weather,
            "temperature": temperature,
            "city": city,
            "error": None,
        }
    except Exception as e:
        logger.warning(f"天気取得エラー: {e}")
        result = {"weather": "sunny", "temperature": 20.0, "city": city, "error": str(e)}

    with _weather_cache_lock:
        _weather_cache = result
        _weather_cache_time = now
    return dict(result)


def _get_location() -> Tuple[Optional[float], Optional[float], str]:
    """現在地の緯度経度と都市名を取得する。

    手動設定があればそれを優先、なければ IP 自動検出。
    """
    with _manual_location_lock:
        if _manual_location:
            parts = _manual_location.split(",")
            if len(parts) == 2:
                try:
                    return float(parts[0]), float(parts[1]), "手動設定"
                except ValueError:
                    pass
            # 都市名指定 → ジオコーディング（Open-MeteoのジオコーディングAPI）
            try:
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(_manual_location)}&count=1&language=ja&format=json"
                req = urllib.request.Request(geo_url, headers={"User-Agent": "NeoSecretary/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    geo = json.loads(resp.read().decode("utf-8"))
                if geo.get("results"):
                    r = geo["results"][0]
                    lat, lon = r["latitude"], r["longitude"]
                    city = r.get("name", _manual_location)
                    country = r.get("country", "")
                    return lat, lon, f"{city}, {country}" if country else city
            except Exception as e:
                logger.warning(f"ジオコーディングエラー: {e}")
            return None, None, _manual_location

    # IP 自動検出
    try:
        req = urllib.request.Request("http://ip-api.com/json/", headers={"User-Agent": "NeoSecretary/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            ip_data = json.loads(resp.read().decode("utf-8"))
        if ip_data.get("status") == "success":
            lat = ip_data["lat"]
            lon = ip_data["lon"]
            city = ip_data.get("city", "不明")
            return lat, lon, city
    except Exception as e:
        logger.warning(f"IP位置情報取得エラー: {e}")
    return None, None, "不明"


def _wmo_to_condition(wmo_code: int) -> str:
    """WMO 天気コードを簡易表記に変換する。"""
    if wmo_code == 0:
        return "sunny"
    if 1 <= wmo_code <= 3:
        return "cloudy"
    if 51 <= wmo_code <= 67 or 80 <= wmo_code <= 82:
        return "rainy"
    if 71 <= wmo_code <= 77 or 85 <= wmo_code <= 86:
        return "snowy"
    if 95 <= wmo_code <= 99:
        return "thunder"
    if 45 <= wmo_code <= 48:
        return "cloudy"
    return "cloudy"