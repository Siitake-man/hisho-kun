"""
QR接続ダイアログのユーティリティ関数テスト (tests/test_qr_dialog.py)

UI (CustomTkinter) を起動せず、URL生成・IP判定・ipconfig解析のロジックのみを検証する。

実行方法:
    python tests/test_qr_dialog.py
    python -m pytest tests/test_qr_dialog.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.qr_dialog import (  # noqa: E402
    TAILSCALE_HTTP_PORT,
    TAILSCALE_SERVE_COMMAND,
    build_lan_url,
    build_tailscale_http_url,
    build_tailscale_https_url,
    extract_ipv4_addresses,
    get_tailscale_ips,
    is_tailscale_ip,
)


def test_is_tailscale_ip():
    """100.64.0.0/10 帯のみ True を返すこと。"""
    assert is_tailscale_ip("100.101.102.103") is True
    assert is_tailscale_ip("100.64.0.1") is True
    assert is_tailscale_ip("100.127.255.254") is True
    assert is_tailscale_ip("100.63.0.1") is False      # 帯の直前
    assert is_tailscale_ip("100.128.0.1") is False     # 帯の直後
    assert is_tailscale_ip("192.168.1.5") is False
    assert is_tailscale_ip("127.0.0.1") is False
    assert is_tailscale_ip("not-an-ip") is False


def test_extract_ipv4_addresses():
    """ipconfig 風テキストから有効な IPv4 のみ抽出すること。"""
    sample = (
        "イーサネット アダプター Tailscale:\n"
        "   IPv4 アドレス . . . . . . . . . . . .: 100.101.1.5\n"
        "ワイヤレス LAN アダプター Wi-Fi:\n"
        "   IPv4 アドレス . . . . . . . . . . . .: 192.168.10.23\n"
        "   デフォルト ゲートウェイ . . . . . .: 192.168.10.1\n"
        "   自動構成 IPv4 アドレス. . . . . . .: 169.254.13.37\n"
        "   サブネット マスク . . . . . . . . .: 255.255.255.0\n"
    )
    ips = extract_ipv4_addresses(sample)
    assert "100.101.1.5" in ips
    assert "192.168.10.23" in ips
    assert "192.168.10.1" in ips
    assert "169.254.13.37" not in ips   # リンクローカル除外
    assert "127.0.0.1" not in ips


def test_build_urls():
    """各 URL ビルダーが仕様どおりの文字列を返すこと。"""
    assert build_lan_url("192.168.1.5") == f"http://192.168.1.5:{TAILSCALE_HTTP_PORT}"
    assert build_tailscale_https_url("myhost.ts.net") == "https://myhost.ts.net/"
    assert build_tailscale_https_url("  ") == ""
    assert build_tailscale_http_url("100.101.1.5") == f"http://100.101.1.5:{TAILSCALE_HTTP_PORT}"
    assert build_tailscale_http_url("") == ""


def test_serve_command_constant():
    """コピー用コマンド定数が仕様どおりであること。"""
    assert TAILSCALE_SERVE_COMMAND == f"tailscale serve --bg {TAILSCALE_HTTP_PORT}"


def test_get_tailscale_ips_returns_list():
    """実環境での検出がリストを返すこと（Tailscale 未導入なら空リスト）。"""
    ips = get_tailscale_ips()
    assert isinstance(ips, list)
    for ip in ips:
        assert is_tailscale_ip(ip)


def main() -> None:
    """pytest 未導入環境向けの単体実行ランナー。"""
    tests = [
        test_is_tailscale_ip,
        test_extract_ipv4_addresses,
        test_build_urls,
        test_serve_command_constant,
        test_get_tailscale_ips_returns_list,
    ]
    failed = 0
    for func in tests:
        try:
            func()
            print(f"PASS: {func.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {func.__name__} ({e})")
    if failed:
        raise SystemExit(f"{failed} tests failed")
    print("ALL-QR-DIALOG-TESTS-PASS")


if __name__ == "__main__":
    main()
