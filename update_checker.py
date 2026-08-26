"""
ネオ秘書くん - 更新チェックエンジン (update_checker.py)

GitHub Releases API を参照し、新しいバージョンが公開されていないかを
バックグラウンドで定期チェックする「Level 1 (通知のみ)」の実装。
ダウンロード・インストール等の自己更新は一切行わない。

設計原則 (Why):
- 起動を絶対にブロックしない: デーモンスレッド + 初回チェックは起動15秒後。
- 失敗時はサイレント: オフライン環境は異常ではなく正常状態の一つ。
  ログ出力のみでユーザーへの警告は行わない。
- テレメトリゼロ: GitHub Releases への読み取り専用参照のみ。
- スマホ同期をブロックしない: /api/status から呼ばれる get_update_status() は
  キャッシュ読み取りのみで即座に返却し、必要時のみ別スレッドで再取得する。
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from version import RELEASES_API_URL, RELEASES_PAGE_URL, __version__

logger = logging.getLogger(__name__)

# キャッシュ有効期限 (秒)。期限切れ時は /api/status 等の呼び出し口から
# 非同期スレッドで再取得を促すだけで、呼び出し元をブロックしない。
_CACHE_TTL_SEC: float = 6.0 * 60.0 * 60.0  # 6時間
_FIRST_CHECK_DELAY_SEC: float = 15.0
_CHECK_INTERVAL_SEC: float = 6.0 * 60.0 * 60.0  # 6時間
_HTTP_TIMEOUT_SEC: float = 8.0

_lock = threading.Lock()
_cached_status: Dict[str, Any] = {}
_last_checked_at: float = 0.0
_announced_version: Optional[str] = None


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """バージョン文字列を比較可能な整数3つ組へ正規化する。

    'v1.2.3' / 'V1.2' / '1.2.3-beta' 等の表記ゆれに耐える。
    数値以外の接尾辞は無視し、欠損したパッチ/マイナー番号は 0 で補完する。

    Args:
        version_str: 正規化対象のバージョン文字列。

    Returns:
        Tuple[int, int, int]: (major, minor, patch) の整数3つ組。
    """
    cleaned = version_str.strip().lstrip("vV")
    nums = []
    for part in cleaned.split(".")[:3]:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        nums.append(int(digits) if digits else 0)
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def is_newer_version(latest: str, current: str) -> bool:
    """latest が current より新しいバージョンかどうかを判定する。

    Args:
        latest: 最新バージョン文字列 (例: 'v1.1.0')。
        current: 現在のバージョン文字列 (例: '1.0.0')。

    Returns:
        bool: latest > current の場合 True。
    """
    try:
        return parse_version(latest) > parse_version(current)
    except ValueError as e:
        logger.warning(f"バージョン比較に失敗: latest={latest!r}, current={current!r}, error={e}")
        return False


def fetch_latest_release(timeout_sec: float = _HTTP_TIMEOUT_SEC) -> Optional[Dict[str, Any]]:
    """GitHub Releases API から最新リリース情報を取得する。

    Args:
        timeout_sec: HTTP タイムアウト秒数。

    Returns:
        Optional[Dict[str, Any]]: 成功時は
            {"tag_name": str, "html_url": str, "display_name": str}。
            失敗時 (オフライン・404 等) は None。例外は握りつぶさずログへ出力する。
    """
    request = urllib.request.Request(
        RELEASES_API_URL,
        headers={
            "User-Agent": f"neo-secretary-updater/{__version__}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 404 = まだリリースを作成していない段階。異常ではないため INFO。
        logger.info(f"更新チェック: GitHub API 応答 {e.code} (リリース未作成の可能性)")
        return None
    except Exception as e:
        # オフライン等の一時的不達は DEBUG ログのみ (正常系の一部として扱う)
        logger.debug(f"更新チェック失敗 (オフライン?): {e}")
        return None

    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        logger.info("更新チェック: tag_name を持たないリリースのためスキップ")
        return None
    return {
        "tag_name": tag,
        "html_url": str(data.get("html_url") or RELEASES_PAGE_URL),
        "display_name": str(data.get("name") or tag),
    }


def _store_cache(release: Optional[Dict[str, Any]], update_available: bool) -> None:
    """チェック結果をモジュールキャッシュへ保存する (スレッド安全)。"""
    global _cached_status, _last_checked_at
    with _lock:
        _last_checked_at = time.time()
        _cached_status = {
            "update_available": update_available,
            "current_version": __version__,
            "latest_version": release["tag_name"] if release else None,
            "release_url": (release or {}).get("html_url", RELEASES_PAGE_URL),
            "checked_at": _last_checked_at,
        }


def refresh_cache() -> None:
    """最新リリースを同期的に取得してキャッシュを更新する。

    バックグラウンドスレッドからの呼び出しを想定。
    """
    release = fetch_latest_release()
    available = bool(release) and is_newer_version(release["tag_name"], __version__)
    _store_cache(release, available)


def get_update_status(force_refresh: bool = False) -> Dict[str, Any]:
    """現在把握している更新状態を即座に返す (ネットワーク呼び出しなし)。

    /api/status の高頻度ポーリングから安全に呼べるよう、本関数は決して
    ブロックしない。キャッシュが古い場合は裏側で再取得スレッドを起動し、
    今回は直近のキャッシュ値 (または初期値) を返す。

    Args:
        force_refresh: True の場合、キャッシュの鮮度に関係なく再取得を促す。

    Returns:
        Dict[str, Any]: update_available / current_version / latest_version /
            release_url / checked_at を含む辞書。
    """
    with _lock:
        cached = dict(_cached_status)
        last = _last_checked_at

    result: Dict[str, Any] = {
        "update_available": False,
        "current_version": __version__,
        "latest_version": None,
        "release_url": RELEASES_PAGE_URL,
        "checked_at": last if last > 0.0 else None,
    }
    result.update(cached)

    now = time.time()
    if force_refresh or last <= 0.0 or (now - last) > _CACHE_TTL_SEC:
        threading.Thread(
            target=refresh_cache, daemon=True, name="UpdateCacheRefresh"
        ).start()
    return result


def _checker_loop(gui: Any, interval_sec: float) -> None:
    """定期チェックループの本体 (デーモンスレッド上で実行される)。

    Args:
        gui: NeoSecretaryGUI インスタンス (None 可)。更新検知時は
            post_action 経由でメインスレッドへ通知をディスパッチする。
        interval_sec: チェック間隔秒数。
    """
    global _announced_version
    time.sleep(_FIRST_CHECK_DELAY_SEC)
    while True:
        release = fetch_latest_release()
        latest_tag = release["tag_name"] if release else None
        available = bool(release) and is_newer_version(latest_tag, __version__)
        _store_cache(release, available)

        if available and release is not None and latest_tag != _announced_version:
            _announced_version = latest_tag
            message = (
                f"🔔 【アップデートのお知らせ】\n"
                f"新しいバージョン {latest_tag} が公開されています！\n"
                f"現在のバージョン: v{__version__}\n"
                f"配布ページ: {release['html_url']}"
            )
            logger.info(f"新バージョン検知: {latest_tag} (現行 v{__version__})")
            if gui is not None:
                try:
                    # GUI操作は必ずメインスレッドへディスパッチ (Tkinterスレッド境界遵守)
                    gui.post_action(gui.update_message, message)
                except Exception as e:
                    logger.warning(f"GUI への更新通知ディスパッチに失敗: {e}")

        time.sleep(interval_sec)


def start_update_checker(gui: Any = None, interval_sec: float = _CHECK_INTERVAL_SEC) -> threading.Thread:
    """更新チェックのバックグラウンドループを開始する。

    Args:
        gui: NeoSecretaryGUI インスタンス (None 可)。
        interval_sec: チェック間隔秒数。デフォルト6時間。

    Returns:
        threading.Thread: 起動したデーモンスレッド。
    """
    thread = threading.Thread(
        target=_checker_loop, args=(gui, interval_sec), daemon=True, name="UpdateChecker"
    )
    thread.start()
    logger.info(f"🔄 更新チェッカーを開始しました (現行 v{__version__}, 間隔 {interval_sec / 3600.0:.0f}時間)")
    return thread
