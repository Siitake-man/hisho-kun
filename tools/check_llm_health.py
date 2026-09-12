#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネオ秘書くん - LLM プロバイダ健康診断ツール (tools/check_llm_health.py)

各設定済み LLM プロバイダに軽量 ping (1トークン chat) を送り、
API 提供側の仕様変更 (必須ヘッダー追加・モデル削除・認証方式変更等) を
「アプリが沈黙してから」ではなく「健康診断で」早期検知する (2026-09-09 創設)。

使い方 (PowerShell):
    & .\\venv\\Scripts\\python.exe tools\\check_llm_health.py
    & .\\venv\\Scripts\\python.exe tools\\check_llm_health.py --timeout 30

終了コード: 0 = 全設定済みプロバイダ正常 (または未設定スキップ) / 1 = 異常あり

Notes:
- 通信は httpx を使用する。urllib の既定 UA (Python-urllib) は Cloudflare 保護下の
  プロバイダ (例: opencode.ai) で 403 error code 1010 にブロックされるため。
- キー値は一切表示しない (ステータスとエラー本文の先頭断片のみ)。
"""

import argparse
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

# .env をプロジェクトルートから読み込む (tools/ からの相対)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# プロバイダ既定 Base URL (.env 未設定時のフォールバック)
_DEFAULT_BASE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "opencode": "https://opencode.ai/zen/go/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "custom_openai": "http://localhost:8000/v1",
    "lm_studio": "http://localhost:1234/v1",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}

# プロバイダごとの API キー環境変数 (未設定のプロバイダはスキップ対象)
_API_KEY_ENVS: Dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "opencode": "OPENCODE_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "custom_openai": "CUSTOM_OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}

# プロバイダごとのモデル名環境変数 ＆ 既定値
_MODEL_ENVS: Dict[str, str] = {
    "openai": "OPENAI_MODEL",
    "opencode": "OPENCODE_MODEL",
    "groq": "GROQ_MODEL",
    "openrouter": "OPENROUTER_MODEL",
    "custom_openai": "CUSTOM_OPENAI_MODEL",
    "anthropic": "CLAUDE_MODEL",
    "gemini": "GEMINI_MODEL",
}
_DEFAULT_MODELS: Dict[str, str] = {
    "openai": "gpt-4o-mini",
    "opencode": "deepseek-v4.1-flash",
    "groq": "llama-3.1-8b-instant",
    "openrouter": "openai/gpt-4o-mini",
    "custom_openai": "custom-model",
    "lm_studio": "local-model",
    "anthropic": "claude-sonnet-4-5",
    "gemini": "gemini-2.0-flash",
}


@dataclass
class ProbeRequest:
    """健康診断リクエストの構成 (純粋データ・ネットワーク非接触で検証可能)。"""

    url: str
    headers: Dict[str, str]
    payload: Dict[str, Any] = field(default_factory=dict)


def build_chat_probe(provider: str, base_url: str, api_key: str, model: str) -> ProbeRequest:
    """プロバイダ別の 1 トークン chat プローブを構築する (純粋関数)。

    Args:
        provider: プロバイダ識別子 (openai / opencode / groq / openrouter /
            custom_openai / lm_studio / anthropic / gemini)。
        base_url: プロバイダの Base URL。
        api_key: API キー (平文。ログには出力しない)。
        model: プローブに使用するモデル名。

    Returns:
        ProbeRequest: 構築されたリクエスト。

    Raises:
        ValueError: 未知のプロバイダ識別子の場合 (Fail-Fast)。
    """
    p = provider.lower()
    base = base_url.rstrip("/")

    if p == "opencode":
        # 2026-09 仕様変更: x-opencode-session ヘッダー必須 (欠落時は 400 MissingSessionID)
        return ProbeRequest(
            url=f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "x-opencode-session": os.getenv("OPENCODE_SESSION_ID", uuid.uuid4().hex),
            },
            payload={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        )

    if p == "anthropic":
        return ProbeRequest(
            url=f"{base}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-23",
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )

    if p == "gemini":
        return ProbeRequest(
            url=f"{base}/models/{model}:generateContent",
            headers={"Content-Type": "application/json"},
            payload={
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 1},
            },
        )

    if p in ("openai", "groq", "openrouter", "custom_openai", "lm_studio"):
        return ProbeRequest(
            url=f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        )

    raise ValueError(f"unknown provider: {provider}")


def _run_probe(probe: ProbeRequest, timeout: float) -> Optional[str]:
    """プローブを実行し、成功時は None / 失敗時はエラー要因 (1行) を返す。

    Args:
        probe: 実行するリクエスト。
        timeout: タイムアウト秒。

    Returns:
        Optional[str]: 正常時 None。失敗時はステータスまたは例外の要因文字列。
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(probe.url, json=probe.payload, headers=probe.headers)
        if resp.status_code == 200:
            return None
        body_head = resp.text[:160].replace("\n", " ")
        return f"HTTP {resp.status_code}: {body_head}"
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:160]}"


def main() -> int:
    """健康診断のエントリポイント。

    Returns:
        int: 0 = 全設定済みプロバイダ正常 / 1 = 異常あり。
    """
    parser = argparse.ArgumentParser(description="LLM プロバイダ健康診断 (ネオ秘書くん)")
    parser.add_argument("--timeout", type=float, default=20.0, help="1プローブのタイムアウト秒")
    args = parser.parse_args()

    load_dotenv(_PROJECT_ROOT / ".env")

    print("🩺 LLM プロバイダ健康診断を開始します (キー値は表示しません)")
    failures = 0

    for provider, key_env in _API_KEY_ENVS.items():
        api_key = (os.getenv(key_env, "") or "").strip()
        if not api_key:
            print(f"⏭ {provider}: 未設定のためスキップ ({key_env} なし)")
            continue

        base_url = (
            (os.getenv(f"{provider.upper()}_BASE_URL", "") or "").strip()
            or _DEFAULT_BASE_URLS[provider]
        )
        model_env = _MODEL_ENVS.get(provider, "")
        model = (os.getenv(model_env, "") or "").strip() if model_env else ""
        model = model or _DEFAULT_MODELS.get(provider, "default")

        try:
            probe = build_chat_probe(provider, base_url, api_key, model)
        except ValueError as e:
            print(f"❌ {provider}: {e}")
            failures += 1
            continue

        error = _run_probe(probe, args.timeout)
        if error is None:
            print(f"✅ {provider}: OK (model={model})")
        else:
            print(f"❌ {provider}: {error}")
            failures += 1

    # LM Studio はキー不要のローカルサーバー (起動中なら到達可能・未起動は問題なし)
    lm_url = (os.getenv("LM_STUDIO_BASE_URL", "") or "").strip() or _DEFAULT_BASE_URLS["lm_studio"]
    lm_model = (os.getenv("LM_STUDIO_MODEL", "") or "").strip() or _DEFAULT_MODELS["lm_studio"]
    probe = build_chat_probe("lm_studio", lm_url, "local-key", lm_model)
    error = _run_probe(probe, min(args.timeout, 5.0))
    if error is None:
        print(f"✅ lm_studio: OK (model={lm_model})")
    else:
        print(f"⏭ lm_studio: 未起動/到達不可 (起動中でなければ問題なし): {error}")

    if failures:
        print(f"\n→ 結果: {failures} 件のプロバイダで異常を検知しました。")
        return 1
    print("\n→ 結果: 設定済みプロバイダはすべて正常です。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

