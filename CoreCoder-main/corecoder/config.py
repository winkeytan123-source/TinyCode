"""Configuration - env vars and defaults."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _load_dotenv():
    """Load .env from cwd, walking up to home dir. No-op if python-dotenv missing."""
    try:
        from dotenv import load_dotenv
        # search cwd first, then parent dirs up to ~
        env_path = Path(".env")
        if not env_path.exists():
            cur = Path.cwd()
            home = Path.home()
            while cur != home and cur != cur.parent:
                candidate = cur / ".env"
                if candidate.exists():
                    env_path = candidate
                    break
                cur = cur.parent
        load_dotenv(env_path, override=True)
    except ImportError:
        pass  # python-dotenv not installed, silently skip


@dataclass
class ModelProfile:
    """一个模型的完整配置信息"""
    name: str          # 模型名，如 deepseek-v4-pro
    api_key: str       # 对应的 API Key
    base_url: str      # 对应的 Base URL


@dataclass
class Config:
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    max_context_tokens: int = 128_000
    provider: str = "openai"
    # 所有可用模型的配置列表
    model_profiles: dict[str, ModelProfile] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Config":
        """从 .env 文件读取配置，支持多模型"""
        _load_dotenv()

        # 解析所有 MODEL_<别名>_NAME / MODEL_<别名>_API_KEY / MODEL_<别名>_BASE_URL
        model_profiles = _parse_model_profiles()

        # 确定默认模型
        default_model = os.getenv("CORECODER_DEFAULT_MODEL") or os.getenv("CORECODER_MODEL", "gpt-4o")

        # 找到默认模型对应的 api_key 和 base_url
        api_key = ""
        base_url = None

        if default_model in model_profiles:
            profile = model_profiles[default_model]
            api_key = profile.api_key
            base_url = profile.base_url
        else:
            # 回退: 兼容旧的单模型环境变量方式
            api_key = (
                os.getenv("CORECODER_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("DEEPSEEK_API_KEY")
                or ""
            )
            base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("CORECODER_BASE_URL")

        return cls(
            model=default_model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=int(os.getenv("CORECODER_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("CORECODER_TEMPERATURE", "0")),
            max_context_tokens=int(os.getenv("CORECODER_MAX_CONTEXT", "128000")),
            provider=os.getenv("CORECODER_PROVIDER", "openai"),
            model_profiles=model_profiles,
        )

    def get_profile(self, model_name: str) -> Optional[ModelProfile]:
        """根据模型名获取完整配置，找不到返回 None"""
        return self.model_profiles.get(model_name)

    def list_models(self) -> list[str]:
        """列出所有已配置的模型名"""
        return list(self.model_profiles.keys())


def _parse_model_profiles() -> dict[str, ModelProfile]:
    """
    从环境变量中解析所有 MODEL_<ALIAS>_NAME/API_KEY/BASE_URL 组合。
    返回 {模型名: ModelProfile} 字典。
    """
    # 收集所有别名
    aliases: set[str] = set()
    for key in os.environ:
        if key.startswith("MODEL_") and key.endswith("_NAME"):
            # MODEL_DEEPSEEK_NAME -> alias = DEEPSEEK
            alias = key[6:-5]  # 去掉 "MODEL_" 和 "_NAME"
            if alias:
                aliases.add(alias)

    profiles: dict[str, ModelProfile] = {}
    for alias in aliases:
        name = os.getenv(f"MODEL_{alias}_NAME", "")
        api_key = os.getenv(f"MODEL_{alias}_API_KEY", "")
        base_url = os.getenv(f"MODEL_{alias}_BASE_URL", "")
        if name and api_key and base_url:
            profiles[name] = ModelProfile(name=name, api_key=api_key, base_url=base_url)

    return profiles
