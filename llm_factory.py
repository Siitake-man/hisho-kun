"""
ネオ秘書くん - Multi-LLM Factory (llm_factory.py)

OpenCode GO (DeepSeek), LM Studio (ローカルLLM), Google Gemini を
統一されたインターフェースで動的に切り替えて利用するためのファクトリモジュール。
APIから利用可能なモデル一覧を動的に探索・取得する機能をサポート。
"""

import os
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Dict, Any, List
from enum import Enum
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv, set_key

# 環境変数の読み込み
ENV_PATH = Path(__file__).parent / ".env"
DISCOVERED_MODELS_PATH = Path(__file__).parent / "discovered_models.json"
load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """サポートするLLMプロバイダ一覧"""
    OPENCODE = "opencode"       # OpenCode GO (DeepSeek-Flash / V3 / R1)
    LM_STUDIO = "lm_studio"     # LM Studio (ローカル・オフライン)
    GEMINI = "gemini"           # Google Gemini (クラウド標準)


# フォールバック用デフォルトモデル一覧
FALLBACK_MODELS = {
    LLMProvider.OPENCODE: [
        {"id": "deepseek-chat", "name": "deepseek-chat (DeepSeek-V3)"},
        {"id": "deepseek-reasoner", "name": "deepseek-reasoner (DeepSeek-R1)"},
        {"id": "deepseek-v4-flash", "name": "deepseek-v4-flash (高速)"},
    ],
    LLMProvider.GEMINI: [
        {"id": "gemini-2.5-flash", "name": "gemini-2.5-flash (推奨・最新爆速)"},
        {"id": "gemini-2.5-pro", "name": "gemini-2.5-pro (最高峰推論)"},
        {"id": "gemini-2.0-flash", "name": "gemini-2.0-flash (安定高速)"},
        {"id": "gemini-1.5-flash", "name": "gemini-1.5-flash (軽量大容量)"},
        {"id": "gemini-1.5-pro", "name": "gemini-1.5-pro (高精度)"},
    ],
    LLMProvider.LM_STUDIO: [
        {"id": "local-model", "name": "local-model (稼働中モデル)"},
    ]
}


class LLMFactory:
    """
    LLMインスタンスの生成と切り替えを統括するファクトリクラス。
    APIから利用可能なモデル一覧を動的に取得・JSONキャッシュ・永続化する機能を持ちます。
    """
    
    DEFAULT_CONFIGS = {
        LLMProvider.OPENCODE: {
            "name": "OpenCode GO (DeepSeek)",
            "default_model": os.getenv("OPENCODE_MODEL", "deepseek-chat"),
            "base_url": os.getenv("OPENCODE_BASE_URL", "https://api.opencode.go.jp/v1"),
            "api_key_env": "OPENCODE_API_KEY",
        },
        LLMProvider.LM_STUDIO: {
            "name": "LM Studio (Local)",
            "default_model": os.getenv("LM_STUDIO_MODEL", "local-model"),
            "base_url": os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
            "api_key_env": None,
        },
        LLMProvider.GEMINI: {
            "name": "Google Gemini",
            "default_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "base_url": None,
            "api_key_env": "GOOGLE_API_KEY",
        }
    }

    def __init__(self, default_provider: Optional[str] = None):
        """ファクトリの初期化"""
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        env_provider = os.getenv("DEFAULT_LLM_PROVIDER", LLMProvider.OPENCODE.value).lower()
        target_provider = default_provider or env_provider
        
        try:
            self._current_provider = LLMProvider(target_provider)
        except ValueError:
            logger.warning(f"未知のプロバイダ '{target_provider}' が指定されたため、OpenCode GO を使用します。")
            self._current_provider = LLMProvider.OPENCODE
            
        self._current_model: Optional[str] = None
        # 動的にAPIから取得したモデルキャッシュ (provider -> List[Dict[str, str]])
        self._discovered_models: Dict[LLMProvider, List[Dict[str, str]]] = {}
        self._load_cached_discovered_models()
        
        logger.info(f"LLMFactory が初期化されました。現在のプロバイダ: {self._current_provider.value} (モデル: {self.current_model_name})")

    def _load_cached_discovered_models(self):
        """ディスク上の discovered_models.json からキャッシュを復元"""
        if DISCOVERED_MODELS_PATH.exists():
            try:
                with open(DISCOVERED_MODELS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for prov_key, models in data.items():
                        try:
                            prov = LLMProvider(prov_key)
                            self._discovered_models[prov] = models
                        except ValueError:
                            pass
                logger.info(f"モデルキャッシュをロードしました: {list(self._discovered_models.keys())}")
            except Exception as e:
                logger.warning(f"モデルキャッシュ読み込みエラー: {e}")

    def _save_cached_discovered_models(self):
        """モデルキャッシュを discovered_models.json へ永続化"""
        try:
            data = {prov.value: models for prov, models in self._discovered_models.items()}
            with open(DISCOVERED_MODELS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("モデルキャッシュを discovered_models.json に保存しました")
        except Exception as e:
            logger.error(f"モデルキャッシュ保存エラー: {e}")

    @property
    def current_provider(self) -> LLMProvider:
        """現在選択されているプロバイダを取得"""
        return self._current_provider

    @property
    def current_model_name(self) -> str:
        """現在選択されているモデル名を取得"""
        if self._current_model:
            return self._current_model
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        env_key = f"{self._current_provider.value.upper()}_MODEL"
        return os.getenv(env_key, self.DEFAULT_CONFIGS[self._current_provider]["default_model"])

    def switch_provider(self, provider: str, model_name: Optional[str] = None) -> bool:
        """利用するLLMプロバイダとモデルを動的に切り替え、.env に永続化"""
        try:
            new_provider = LLMProvider(provider.lower())
            self._current_provider = new_provider
            
            if model_name:
                self._current_model = model_name
            else:
                env_key = f"{new_provider.value.upper()}_MODEL"
                self._current_model = os.getenv(env_key, self.DEFAULT_CONFIGS[new_provider]["default_model"])
                
            # .env に次回起動用のデフォルトプロバイダとモデル名を永続化
            try:
                set_key(str(ENV_PATH), "DEFAULT_LLM_PROVIDER", new_provider.value)
                model_env_key = f"{new_provider.value.upper()}_MODEL"
                set_key(str(ENV_PATH), model_env_key, self.current_model_name)
                load_dotenv(dotenv_path=ENV_PATH, override=True)
            except Exception as env_err:
                logger.warning(f".env 永続化エラー: {env_err}")
                
            logger.info(f"LLMプロバイダを '{new_provider.value}' (モデル: {self.current_model_name}) に切り替え・保存しました。")
            return True
        except ValueError:
            logger.error(f"無効なLLMプロバイダが指定されました: {provider}")
            return False

    def fetch_available_models(
        self, 
        provider_name: str, 
        api_key: Optional[str] = None, 
        base_url: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        指定されたプロバイダのAPIエンドポイントから、利用可能なモデル一覧を動的に取得します。
        
        Args:
            provider_name: 'opencode', 'lm_studio', 'gemini'
            api_key: テスト用/直接指定のAPIキー（省略時は .env から読込）
            base_url: テスト用/直接指定のBase URL（省略時は .env から読込）
            
        Returns:
            List[Dict[str, str]]: [{"id": "model_id", "name": "表示名"}, ...]
        """
        # 最新の .env を反映
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        
        provider = LLMProvider(provider_name.lower())
        config = self.DEFAULT_CONFIGS[provider]
        
        target_api_key = api_key or os.getenv(config["api_key_env"] or "", "")
        target_base_url = (base_url or os.getenv("OPENCODE_BASE_URL" if provider == LLMProvider.OPENCODE else "LM_STUDIO_BASE_URL", config["base_url"] or "")).rstrip("/")
        
        models_list: List[Dict[str, str]] = []
        
        try:
            if provider == LLMProvider.GEMINI:
                # APIキーのサニタイズ（クォーテーションや余計な空白を除去）
                target_api_key = target_api_key.strip().strip('"\'')
                if not target_api_key:
                    raise ValueError("GOOGLE_API_KEY が設定されていません。")
                
                # アプローチ1: 公式SDK (google.generativeai) の試行
                sdk_success = False
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=target_api_key)
                    for m in genai.list_models():
                        if "generateContent" in getattr(m, "supported_generation_methods", []):
                            m_id = m.name.replace("models/", "")
                            disp_name = getattr(m, "display_name", m_id)
                            models_list.append({
                                "id": m_id,
                                "name": f"{disp_name} ({m_id})" if disp_name != m_id else m_id
                            })
                    if models_list:
                        sdk_success = True
                except Exception as sdk_err:
                    logger.warning(f"SDK経由でのGeminiモデル取得をスキップし、REST APIで再試行します: {sdk_err}")

                # アプローチ2: REST API (x-goog-api-key ヘッダー)
                if not sdk_success:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(target_api_key)}"
                    headers = {
                        "x-goog-api-key": target_api_key,
                        "User-Agent": "NeoSecretary/1.0",
                        "Accept": "application/json"
                    }
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        data = json.loads(response.read().decode())
                        for m in data.get("models", []):
                            methods = m.get("supportedGenerationMethods", [])
                            if "generateContent" in methods:
                                m_id = m.get("name", "").replace("models/", "")
                                disp_name = m.get("displayName", m_id)
                                models_list.append({
                                    "id": m_id,
                                    "name": f"{disp_name} ({m_id})" if disp_name != m_id else m_id
                                })
                            
            elif provider in (LLMProvider.OPENCODE, LLMProvider.LM_STUDIO):
                if provider == LLMProvider.OPENCODE and not target_api_key:
                    raise ValueError("OPENCODE_API_KEY が設定されていません。")
                
                # OpenAI 互換の GET /models エンドポイントを叩く
                url = f"{target_base_url}/models"
                headers = {
                    "User-Agent": "NeoSecretary/1.0",
                    "Accept": "application/json"
                }
                if target_api_key:
                    headers["Authorization"] = f"Bearer {target_api_key}"
                    
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    for m in data.get("data", []):
                        m_id = m.get("id", "")
                        if m_id:
                            models_list.append({
                                "id": m_id,
                                "name": m_id
                            })
                            
            if models_list:
                # 成功した場合はキャッシュを更新してJSONへ永続化
                self._discovered_models[provider] = models_list
                self._save_cached_discovered_models()
                logger.info(f"{provider.value} から {len(models_list)} 件のモデルを取得・キャッシュしました。")
                return models_list
            else:
                logger.warning(f"{provider.value} のモデル一覧が空でした。フォールバックを使用します。")
                return FALLBACK_MODELS.get(provider, [])
                
        except Exception as e:
            logger.error(f"{provider.value} のモデル一覧取得に失敗しました: {e}")
            fallback = FALLBACK_MODELS.get(provider, [])
            if fallback:
                self._discovered_models[provider] = fallback
                logger.info(f"{provider.value} のフォールバックモデル一覧 ({len(fallback)} 件) をロードしました。")
                return fallback
            raise e

    def get_models_for_provider(self, provider: LLMProvider) -> List[Dict[str, str]]:
        """キャッシュされたモデル一覧、またはフォールバック一覧を取得"""
        if provider in self._discovered_models and self._discovered_models[provider]:
            return self._discovered_models[provider]
        return FALLBACK_MODELS.get(provider, [])

    def create_model(self, temperature: float = 0.7) -> BaseChatModel:
        """現在選択されているプロバイダ・モデルに基づいて BaseChatModel インスタンスを生成"""
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        
        provider = self._current_provider
        config = self.DEFAULT_CONFIGS[provider]
        model_name = self.current_model_name

        logger.info(f"LLMモデルを生成中: Provider={provider.value}, Model={model_name}")

        if provider == LLMProvider.GEMINI:
            api_key = os.getenv("GOOGLE_API_KEY", "")
            if not api_key:
                logger.warning("GOOGLE_API_KEY が設定されていません。")
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                google_api_key=api_key
            )

        elif provider in (LLMProvider.OPENCODE, LLMProvider.LM_STUDIO):
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                logger.error("langchain-openai がインストールされていません。")
                raise ImportError("OpenAI互換モデルを利用するには 'langchain-openai' が必要です。")

            if provider == LLMProvider.OPENCODE:
                base_url = os.getenv("OPENCODE_BASE_URL", config["base_url"])
                api_key = os.getenv("OPENCODE_API_KEY", "")
                if not api_key:
                    logger.warning("OPENCODE_API_KEY が設定されていません。")
            else:
                base_url = os.getenv("LM_STUDIO_BASE_URL", config["base_url"])
                api_key = "lm-studio"

            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                base_url=base_url,
                api_key=api_key,
                streaming=True
            )

        else:
            raise ValueError(f"未対応のプロバイダです: {provider}")

    def list_presets(self) -> Dict[str, Any]:
        """UIメニュー等で表示するための全プロバイダ・モデル一覧を取得"""
        result = {}
        for p in LLMProvider:
            cfg = self.DEFAULT_CONFIGS[p]
            models = self.get_models_for_provider(p)
            result[p.value] = {
                "name": cfg["name"],
                "is_current_provider": (p == self._current_provider),
                "models": models,
                "current_model": self.current_model_name if (p == self._current_provider) else cfg["default_model"]
            }
        return result

    def save_settings(self, settings: Dict[str, str]) -> bool:
        """
        GUI等から入力されたAPIキーやBase URL、デフォルトモデルを .env に永続化保存します。
        """
        try:
            if not ENV_PATH.exists():
                ENV_PATH.touch()
            for key, val in settings.items():
                if val is not None:
                    set_key(str(ENV_PATH), key, val)
                    os.environ[key] = val
            logger.info("設定を .env ファイルに保存・同期しました。")
            return True
        except Exception as e:
            logger.error(f"設定保存エラー: {e}")
            return False


# シングルトンインスタンスの提供
_global_factory: Optional[LLMFactory] = None

def get_llm_factory() -> LLMFactory:
    """グローバルなLLMFactoryインスタンスを取得"""
    global _global_factory
    if _global_factory is None:
        _global_factory = LLMFactory()
    return _global_factory
