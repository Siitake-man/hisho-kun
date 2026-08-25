"""
ネオ秘書くん - Multi-LLM Factory (llm_factory.py)

OpenCode GO (DeepSeek), LM Studio (ローカルLLM), Google Gemini を
統一されたインターフェースで動的に切り替えて利用するためのファクトリモジュール。
APIから利用可能なモデル一覧を動的に探索・取得する機能をサポート。
"""

import os
import json
import re
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Dict, Any, List, ClassVar
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
    GEMINI = "gemini"               # Google Gemini (推奨・最新爆速)
    CLAUDE = "claude"               # Anthropic Claude (Claude 5 Fable/Opus)
    OPENAI = "openai"               # OpenAI (GPT-5.6 Sol / Terra)
    OPENCODE = "opencode"           # OpenCode GO (DeepSeek-V4 / R1)
    GROQ = "groq"                   # Groq (超爆速推論)
    OPENROUTER = "openrouter"       # OpenRouter (万能モデルアグリゲーター)
    CUSTOM_OPENAI = "custom_openai" # 任意カスタムOpenAI互換エンドポイント
    LOCAL_GGUF = "local_gguf"       # 内包ローカルLLM (LFM 2.5 / models/*.gguf)
    OLLAMA = "ollama"               # Ollama (ローカル / リモート)
    LM_STUDIO = "lm_studio"         # LM Studio (ローカル)


# フォールバック用デフォルトモデル一覧（2026年8月最新ラインナップ）
FALLBACK_MODELS = {
    LLMProvider.GEMINI: [
        {"id": "gemini-3.7-flash", "name": "gemini-3.7-flash (2026最新・高効率爆速)"},
        {"id": "gemini-3.1-pro", "name": "gemini-3.1-pro (最高峰ディープリサーチ)"},
        {"id": "gemini-spark", "name": "gemini-spark (24/7 常時稼働エージェント専用)"},
        {"id": "gemini-2.5-flash", "name": "gemini-2.5-flash (安定高速)"},
        {"id": "gemini-2.5-pro", "name": "gemini-2.5-pro (高精度論理推論)"},
    ],
    LLMProvider.CLAUDE: [
        {"id": "claude-fable-5", "name": "claude-fable-5 (最新最高峰知能・エージェント最前線)"},
        {"id": "claude-opus-5", "name": "claude-opus-5 (最高峰コーディング・長文執筆)"},
        {"id": "claude-3-7-sonnet-20250219", "name": "claude-3-7-sonnet (思考ハイブリッド)"},
        {"id": "claude-3-5-sonnet-20241022", "name": "claude-3-5-sonnet (高精度安定)"},
        {"id": "claude-3-5-haiku-20241022", "name": "claude-3-5-haiku (超高速軽量)"},
    ],
    LLMProvider.OPENAI: [
        {"id": "gpt-5.6-sol", "name": "gpt-5.6-sol (最新最高峰STEM・論理推論フラグシップ)"},
        {"id": "gpt-5.6-terra", "name": "gpt-5.6-terra (汎用フラグシップ)"},
        {"id": "gpt-5.6-luna", "name": "gpt-5.6-luna (高速軽量最新世代)"},
        {"id": "gpt-4.5-preview", "name": "gpt-4.5-preview (知識モデル)"},
        {"id": "o3-mini", "name": "o3-mini (推論特化・爆速)"},
    ],
    LLMProvider.OPENCODE: [
        {"id": "deepseek-v4-pro", "name": "deepseek-v4-pro (2026最新・最高峰オープン推論)"},
        {"id": "deepseek-v4-flash", "name": "deepseek-v4-flash (超高速推論)"},
        {"id": "deepseek-reasoner", "name": "deepseek-reasoner (DeepSeek-R1)"},
        {"id": "deepseek-chat", "name": "deepseek-chat (DeepSeek-V3)"},
    ],
    LLMProvider.GROQ: [
        {"id": "deepseek-v4-flash", "name": "deepseek-v4-flash (Groq 超爆速)"},
        {"id": "qwen3.8-max", "name": "qwen3.8-max (Alibaba 最新最高峰オープン)"},
        {"id": "deepseek-r1-distill-llama-70b", "name": "deepseek-r1-distill-llama-70b (超爆速推論)"},
        {"id": "llama-3.3-70b-versatile", "name": "llama-3.3-70b-versatile (フラグシップ)"},
        {"id": "qwen-2.5-coder-32b", "name": "qwen-2.5-coder-32b (爆速コーディング)"},
    ],
    LLMProvider.OPENROUTER: [
        {"id": "anthropic/claude-fable-5", "name": "Claude Fable 5 (OpenRouter)"},
        {"id": "anthropic/claude-opus-5", "name": "Claude Opus 5 (OpenRouter)"},
        {"id": "openai/gpt-5.6-sol", "name": "GPT-5.6 Sol (OpenRouter)"},
        {"id": "google/gemini-3.7-flash", "name": "Gemini 3.7 Flash (OpenRouter)"},
        {"id": "google/gemini-3.1-pro", "name": "Gemini 3.1 Pro (OpenRouter)"},
        {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro (OpenRouter)"},
        {"id": "qwen/qwen3.8-max", "name": "Qwen 3.8 Max (OpenRouter)"},
    ],
    LLMProvider.CUSTOM_OPENAI: [
        {"id": "custom-model", "name": "custom-model (カスタム指定モデル)"},
    ],
    LLMProvider.LOCAL_GGUF: [
        {"id": "lfm2.5-2.6b", "name": "LFM 2.5 (2.6B) - Liquid Foundation超軽量ハイブリッド"},
        {"id": "minicpm5-1b-claude-opus-fable5-v2-thinking", "name": "MiniCPM-5 (1B) - オンデバイス思考モデル"},
        {"id": "google/gemma-4-e4b", "name": "Gemma 4 (E4B) - Google最新エッジ"},
        {"id": "Bonsai-1.5B-Japanese", "name": "Bonsai (1.5B) - 日本語特化超低レイテンシ"},
        {"id": "Qwen2.5-Coder-1.5B-Instruct", "name": "Qwen2.5-Coder (1.5B) - コーディング特化"},
        {"id": "SmolLM2-1.7B-Instruct", "name": "SmolLM2 (1.7B) - 高効率オンデバイス"},
    ],
    LLMProvider.OLLAMA: [
        {"id": "deepseek-v4:latest", "name": "deepseek-v4 (Ollama)"},
        {"id": "qwen3.8:latest", "name": "qwen3.8 (Ollama)"},
        {"id": "gemma4:latest", "name": "gemma4 (Ollama)"},
        {"id": "phi4:latest", "name": "phi4 (Ollama)"},
    ],
    LLMProvider.LM_STUDIO: [
        {"id": "lfm2.5-2.6b", "name": "lfm2.5-2.6b (Liquid Foundation)"},
        {"id": "minicpm5-1b-claude-opus-fable5-v2-thinking@f16", "name": "MiniCPM-5 1B Thinking (F16)"},
        {"id": "local-model", "name": "local-model (LM Studio稼働中モデル)"},
    ]
}


class LLMFactory:
    """
    LLMインスタンスの生成と切り替えを統括するファクトリクラス。
    クラウド（Gemini 3, Claude 5, GPT-5.6, DeepSeek V4, Qwen 3.8）から
    任意のカスタムOpenAI互換エンドポイント、内包ローカルモデルまでをシームレスに一元管理します。
    """
    
    MODELS_DIR = Path(__file__).parent / "models"
    
    DEFAULT_CONFIGS = {
        LLMProvider.GEMINI: {
            "name": "Google Gemini",
            "default_model": os.getenv("GEMINI_MODEL", "gemini-3.7-flash"),
            "base_url": None,
            "api_key_env": "GOOGLE_API_KEY",
        },
        LLMProvider.CLAUDE: {
            "name": "Anthropic Claude",
            "default_model": os.getenv("CLAUDE_MODEL", "claude-fable-5"),
            "base_url": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
            "api_key_env": "ANTHROPIC_API_KEY",
        },
        LLMProvider.OPENAI: {
            "name": "OpenAI",
            "default_model": os.getenv("OPENAI_MODEL", "gpt-5.6-sol"),
            "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "api_key_env": "OPENAI_API_KEY",
        },
        LLMProvider.OPENCODE: {
            "name": "OpenCode GO (DeepSeek)",
            "default_model": os.getenv("OPENCODE_MODEL", "deepseek-v4-pro"),
            "base_url": os.getenv("OPENCODE_BASE_URL", "https://api.opencode.go.jp/v1"),
            "api_key_env": "OPENCODE_API_KEY",
        },
        LLMProvider.GROQ: {
            "name": "Groq (超爆速推論)",
            "default_model": os.getenv("GROQ_MODEL", "deepseek-v4-flash"),
            "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            "api_key_env": "GROQ_API_KEY",
        },
        LLMProvider.OPENROUTER: {
            "name": "OpenRouter (万能ハブ)",
            "default_model": os.getenv("OPENROUTER_MODEL", "anthropic/claude-fable-5"),
            "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            "api_key_env": "OPENROUTER_API_KEY",
        },
        LLMProvider.CUSTOM_OPENAI: {
            "name": "任意カスタムOpenAI互換 (Custom API)",
            "default_model": os.getenv("CUSTOM_OPENAI_MODEL", "custom-model"),
            "base_url": os.getenv("CUSTOM_OPENAI_BASE_URL", "http://localhost:8000/v1"),
            "api_key_env": "CUSTOM_OPENAI_API_KEY",
        },
        LLMProvider.LOCAL_GGUF: {
            "name": "内包ローカルLLM (GGUF / Sidecar)",
            "default_model": os.getenv("LOCAL_GGUF_MODEL", "lfm2.5-2.6b"),
            "base_url": os.getenv("LOCAL_GGUF_BASE_URL", "http://localhost:8080/v1"),
            "api_key_env": None,
        },
        LLMProvider.OLLAMA: {
            "name": "Ollama (Local/Remote)",
            "default_model": os.getenv("OLLAMA_MODEL", "deepseek-v4:latest"),
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "api_key_env": None,
        },
        LLMProvider.LM_STUDIO: {
            "name": "LM Studio (Local)",
            "default_model": os.getenv("LM_STUDIO_MODEL", "lfm2.5-2.6b"),
            "base_url": os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
            "api_key_env": None,
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
                            
            elif provider == LLMProvider.LOCAL_GGUF:
                # models/ ディレクトリ内の .gguf ファイルのみを表示（フォールバックプリセットは混ぜない）
                self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
                for f in self.MODELS_DIR.glob("*.gguf"):
                    models_list.append({
                        "id": f.name,
                        "name": f"📦 {f.stem} (Local GGUF)"
                    })
                # models/ にファイルが無い場合のみフォールバックプリセットを表示
                if not models_list:
                    models_list = list(FALLBACK_MODELS[LLMProvider.LOCAL_GGUF])

            elif provider in (
                LLMProvider.OPENCODE, LLMProvider.LM_STUDIO, LLMProvider.OPENAI,
                LLMProvider.GROQ, LLMProvider.OPENROUTER, LLMProvider.OLLAMA,
                LLMProvider.CUSTOM_OPENAI
            ):
                if provider in (LLMProvider.OPENCODE, LLMProvider.OPENAI, LLMProvider.GROQ, LLMProvider.OPENROUTER) and not target_api_key:
                    raise ValueError(f"{config.get('api_key_env', 'API Key')} が設定されていません。")
                
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

            elif provider == LLMProvider.CLAUDE:
                # Claude はフォールバックリストを使用
                models_list = list(FALLBACK_MODELS[LLMProvider.CLAUDE])
                            
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

    def sync_all_discovered_models(self, background: bool = True) -> Dict[str, Any]:
        """
        全プロバイダのAPIエンドポイントやmodels/ディレクトリを巡回し、
        最新の利用可能モデル一覧を動的取得してキャッシュを更新・永続化します。
        """
        import threading

        def _sync_worker():
            logger.info("🌐 全プロバイダの最新モデル一覧を巡回・同期中...")
            results = {}
            for prov in LLMProvider:
                try:
                    models = self.fetch_available_models(prov.value)
                    results[prov.value] = len(models)
                except Exception as ex:
                    results[prov.value] = f"Error: {ex}"
            logger.info(f"✓ 全プロバイダのモデル同期が完了しました: {results}")
            return results

        if background:
            t = threading.Thread(target=_sync_worker, daemon=True, name="LLMModelSyncThread")
            t.start()
            return {"status": "started_in_background"}
        else:
            return _sync_worker()

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

        # 1. Google Gemini
        if provider == LLMProvider.GEMINI:
            api_key = os.getenv("GOOGLE_API_KEY", "")
            if not api_key:
                logger.warning("GOOGLE_API_KEY が設定されていません。")
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                google_api_key=api_key
            )

        # 2. Anthropic Claude
        elif provider == LLMProvider.CLAUDE:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY が設定されていません。")
            try:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model_name=model_name,
                    temperature=temperature,
                    anthropic_api_key=api_key,
                    streaming=True
                )
            except ImportError:
                # langchain-anthropic 未導入時は OpenAI 互換またはフォールバック
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                    base_url="https://api.anthropic.com/v1",
                    api_key=api_key,
                    streaming=True
                )

        # 3. 内包ローカルLLM (llama-cpp-python でプロセス内直接推論)
        elif provider == LLMProvider.LOCAL_GGUF:
            # models/ ディレクトリからGGUFファイルを検索
            self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
            gguf_path = self.MODELS_DIR / model_name
            if not gguf_path.exists():
                # 拡張子なしの場合は .gguf を補完
                if not model_name.endswith(".gguf"):
                    gguf_path = self.MODELS_DIR / f"{model_name}.gguf"
                if not gguf_path.exists():
                    raise FileNotFoundError(
                        f"GGUFモデルが見つかりません: {model_name}\n"
                        f"models/ フォルダに .gguf ファイルを配置してください。"
                    )

            logger.info(f"📦 ローカルGGUFモデルをロード中: {gguf_path.name}")
            try:
                from llama_cpp import Llama
                from langchain_core.language_models.chat_models import BaseChatModel
                from langchain_core.messages import AIMessage, BaseMessage
                from langchain_core.outputs import ChatGeneration, ChatResult

                class LlamaCppChatModel(BaseChatModel):
                    """llama-cpp-python を LangChain BaseChatModel に適合させるアダプター。

                    ローカルGGUFモデルは関数呼び出し（tool calling）をサポートしないため、
                    bind_tools が呼ばれた場合は空のツールバインディングを返し、
                    エージェントのルーティングでツールを使わず直接応答する。
                    """

                    def __init__(self, model_path: str, temperature: float = 0.7, n_ctx: int = 4096, n_threads: int = 4):
                        super().__init__()
                        self._llm = Llama(
                            model_path=model_path,
                            n_ctx=n_ctx,
                            n_threads=n_threads,
                            verbose=False,
                        )
                        self._temperature = temperature
                        # ネイティブテンプレート用のJinja2フォーマッタ（遅延初期化）
                        self._formatter = None

                    @property
                    def _llm_type(self) -> str:
                        return "llama-cpp-python"

                    def bind_tools(self, tools, **kwargs):
                        """ローカルGGUFモデルはtool calling非対応のため、ツール無しの自身を返す。"""
                        logger.info("📦 ローカルGGUFモデルはtool calling非対応です。直接応答モードで動作します。")
                        return self

                    # 思考ブロックの開始/終了タグ。XMLパーサーに解釈されないよう連結で生成する。
                    # ※ "/" の入れ忘りに注意（"<think>" だと開始タグになり誤動作する）
                    # ClassVar 注釈必須: Pydantic がモデルフィールドと誤認するため
                    THINK_OPEN: ClassVar[str] = "<" + "think" + ">"
                    THINK_CLOSE: ClassVar[str] = "<" + "/think" + ">"

                    def _to_chat_dicts(self, messages: list) -> list:
                        """LangChainメッセージリストをOpenAI形式のdictリストに変換する。"""
                        chat_dicts = []
                        for msg in messages:
                            role = msg.type if hasattr(msg, "type") else "user"
                            content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            llama_role = {"human": "user", "ai": "assistant", "system": "system"}.get(role, "user")
                            chat_dicts.append({"role": llama_role, "content": content})
                        return chat_dicts

                    def _get_formatter(self):
                        """GGUF埋め込みのチャットテンプレートからJinja2フォーマッタを構築する。

                        Llamaオブジェクトには apply_chat_template が無いため、
                        llama-cpp-python 公式の Jinja2ChatFormatter を利用する。
                        なおテンプレート内の {%- generation -%} はHuggingFace拡張タグで
                        標準Jinja2が解釈できないため、事前に除去する。
                        """
                        if self._formatter is None:
                            from llama_cpp.llama_chat_format import Jinja2ChatFormatter

                            raw_template = self._llm.metadata.get("tokenizer.chat_template", "")
                            # HF拡張の generation ブロックタグを除去（中身は保持される）
                            clean_template = re.sub(
                                r"\{%-?\s*(?:end)?generation\s*-?%\}", "", raw_template
                            )
                            eos_token = self._llm.detokenize([self._llm.token_eos()]).decode("utf-8", errors="ignore")
                            bos_token = self._llm.detokenize([self._llm.token_bos()]).decode("utf-8", errors="ignore")
                            self._formatter = Jinja2ChatFormatter(
                                template=clean_template,
                                eos_token=eos_token,
                                bos_token=bos_token,
                            )
                        return self._formatter

                    def _build_native_prompt(self, messages: list) -> str:
                        """ネイティブチャットテンプレートでプロンプトを構築し、思考ブロックを閉じた状態にする。

                        LFM2.5のテンプレートは生成プロンプト末尾を "<think>" にするため、
                        これを "</think>" に差し替えて思考フェーズを丸ごとスキップし、
                        本応答のみを高速に生成させる。
                        """
                        formatter = self._get_formatter()
                        # Jinja2ChatFormatter は既定で add_generation_prompt=True を
                        # 内部で渡すため、ここでは messages のみを指定する。
                        rendered = formatter(
                            messages=self._to_chat_dicts(messages),
                        ).prompt
                        if isinstance(rendered, bytes):
                            rendered = rendered.decode("utf-8")
                        if rendered.endswith(self.THINK_OPEN):
                            rendered = rendered[: -len(self.THINK_OPEN)] + self.THINK_CLOSE
                        return rendered

                    def _generate(self, messages: list, stop=None, run_manager=None, **kwargs):
                        """同期推論でメッセージリストから応答を生成する。

                        ネイティブテンプレートで構築したプロンプト（思考ブロック閉じ済み）を
                        create_completion に渡し、アシスタント終端トークンまで補完する。
                        """
                        response = self._llm.create_completion(
                            prompt=self._build_native_prompt(messages),
                            max_tokens=kwargs.get("max_tokens", 512),
                            temperature=self._temperature,
                            stop=stop or ["<|im_end|>"],
                        )
                        text = response["choices"][0]["text"].strip()
                        ai_msg = AIMessage(content=text)
                        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

                    def _stream(self, messages: list, stop=None, run_manager=None, **kwargs):
                        """ストリーミング推論（astream 対応）。

                        llama-cpp-python の stream=True を使い、トークンごとに
                        LangChain の ChatGenerationChunk を yield する。
                        """
                        from langchain_core.messages import AIMessageChunk
                        from langchain_core.outputs import ChatGenerationChunk

                        response = self._llm.create_completion(
                            prompt=self._build_native_prompt(messages),
                            max_tokens=kwargs.get("max_tokens", 512),
                            temperature=self._temperature,
                            stop=stop or ["<|im_end|>"],
                            stream=True,
                        )
                        # プロンプト構築時に思考ブロックを閉じ済みのため、
                        # 差分テキストをそのままクリーンな本文としてストリーミングする。
                        for chunk in response:
                            choices = chunk.get("choices", [])
                            delta_text = choices[0].get("text", "") if choices else ""
                            if delta_text:
                                yield ChatGenerationChunk(
                                    message=AIMessageChunk(content=delta_text)
                                )

                return LlamaCppChatModel(
                    model_path=str(gguf_path),
                    temperature=temperature,
                    n_ctx=4096,
                    n_threads=4,
                )
            except ImportError:
                logger.error("llama-cpp-python がインストールされていません。pip install llama-cpp-python を実行してください。")
                raise ImportError("内包ローカルLLMを利用するには 'llama-cpp-python' が必要です。")

        # 4. OpenAI 互換プロバイダ群 (OpenAI, OpenCode, Groq, OpenRouter, Ollama, LM Studio)
        else:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                logger.error("langchain-openai がインストールされていません。")
                raise ImportError("OpenAI互換モデルを利用するには 'langchain-openai' が必要です。")

            api_key_env = config.get("api_key_env")
            api_key = os.getenv(api_key_env, "dummy-key") if api_key_env else "local-key"
            base_url = os.getenv(f"{provider.value.upper()}_BASE_URL", config.get("base_url"))

            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                base_url=base_url,
                api_key=api_key,
                streaming=True
            )

    def is_provider_configured(self, provider: LLMProvider) -> bool:
        """指定されたプロバイダが現在実際に利用可能（有効なAPIキー設定済み、または実機モデル稼働中）かを判定"""
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        config = self.DEFAULT_CONFIGS.get(provider, {})
        api_key_env = config.get("api_key_env")

        # 1. APIキーが必要なクラウドプロバイダ (ダミー値や未設定を除外)
        if api_key_env:
            key_val = os.getenv(api_key_env, "").strip()
            if not key_val or key_val.startswith("your_") or key_val.startswith("dummy_") or key_val == "your-api-key-here":
                return False
            return True

        # 2. 内包ローカルLLM (models/ ディレクトリ内に実際に .gguf ファイルが存在するか)
        if provider == LLMProvider.LOCAL_GGUF:
            models_dir = Path(__file__).parent / "models"
            if models_dir.exists():
                ggufs = list(models_dir.glob("*.gguf"))
                return len(ggufs) > 0
            return False

        # 3. 任意カスタムOpenAI互換 (Base URLまたはAPIキーが明示設定されているか)
        if provider == LLMProvider.CUSTOM_OPENAI:
            custom_key = os.getenv("CUSTOM_OPENAI_API_KEY", "").strip()
            custom_url = os.getenv("CUSTOM_OPENAI_BASE_URL", "").strip()
            return bool(custom_key or (custom_url and custom_url != "http://localhost:8000/v1"))

        # 4. Ollama / LM Studio (実機サーバーからモデル取得に成功しているか)
        if provider in (LLMProvider.OLLAMA, LLMProvider.LM_STUDIO):
            cached = self._discovered_models.get(provider, [])
            fallback = FALLBACK_MODELS.get(provider, [])
            # キャッシュが存在し、かつ未接続フォールバックと異なる＝実機接続成功
            if cached and cached != fallback:
                return True
            return False

        return False

    def list_presets(self, only_configured: bool = False) -> Dict[str, Any]:
        """UIメニュー等で表示するための全プロバイダ・モデル一覧を取得"""
        result = {}
        for p in LLMProvider:
            is_configured = self.is_provider_configured(p)
            is_current = (p == self._current_provider)
            
            # 利用可能プロバイダのみに絞り込む場合（現在のプロバイダは必ず含める）
            if only_configured and not (is_configured or is_current):
                continue

            cfg = self.DEFAULT_CONFIGS[p]
            models = self.get_models_for_provider(p)
            result[p.value] = {
                "name": cfg["name"],
                "is_current_provider": is_current,
                "is_configured": is_configured,
                "models": models,
                "current_model": self.current_model_name if is_current else cfg["default_model"]
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
