"""LLM 调用层 — Provider / Model 管理 + 统一调用入口。

当前支持框架：openai（兼容所有 OpenAI 格式 API，如 laozhang、moonshot 等）
预留扩展：在 call_llm() 的 framework 分支中添加其他 SDK 即可。
"""
from __future__ import annotations

from datetime import datetime

from .config import load_config, save_config


# ─── 默认内置配置 ──────────────────────────────────────────────────────────────

_DEFAULT_PROVIDERS: list[dict] = []
_DEFAULT_MODELS:    list[dict] = []


# ─── Provider CRUD ───────────────────────────────────────────────────────────

def get_llm_providers() -> list[dict]:
    return load_config().get("llm_providers", _DEFAULT_PROVIDERS[:])


def add_llm_provider(name: str, base_url: str, api_key: str,
                     framework: str = "openai") -> str:
    """新增 Provider，返回生成的 provider_id。"""
    name = name.strip()
    base_url = base_url.strip().rstrip("/")
    api_key  = api_key.strip()
    if not (name and base_url and api_key):
        raise ValueError("name / base_url / api_key 均不能为空")
    provider_id = f"pvd_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    cfg = load_config()
    cfg.setdefault("llm_providers", []).append({
        "id":        provider_id,
        "name":      name,
        "base_url":  base_url,
        "api_key":   api_key,
        "framework": framework,
    })
    save_config(cfg)
    return provider_id


def remove_llm_provider(provider_id: str) -> None:
    """删除 Provider，同时删除其下所有 Model。"""
    cfg = load_config()
    cfg["llm_providers"] = [
        p for p in cfg.get("llm_providers", []) if p["id"] != provider_id
    ]
    cfg["llm_models"] = [
        m for m in cfg.get("llm_models", []) if m["provider_id"] != provider_id
    ]
    save_config(cfg)


def update_llm_provider(provider_id: str, **kwargs) -> None:
    """更新 Provider 字段（name / base_url / api_key）。"""
    cfg = load_config()
    for p in cfg.get("llm_providers", []):
        if p["id"] == provider_id:
            for k, v in kwargs.items():
                if k in ("name", "base_url", "api_key", "framework") and v is not None:
                    p[k] = str(v).strip()
            break
    save_config(cfg)


# ─── Model CRUD ──────────────────────────────────────────────────────────────

def get_llm_models() -> list[dict]:
    return load_config().get("llm_models", _DEFAULT_MODELS[:])


def add_llm_model(model_name: str, provider_id: str,
                  display_name: str = "") -> str:
    """新增 Model，返回 model_id。"""
    model_name = model_name.strip()
    if not model_name or not provider_id:
        raise ValueError("model_name / provider_id 均不能为空")
    providers = get_llm_providers()
    if not any(p["id"] == provider_id for p in providers):
        raise ValueError(f"Provider {provider_id} 不存在")
    model_id = f"mdl_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    cfg = load_config()
    cfg.setdefault("llm_models", []).append({
        "id":           model_id,
        "name":         model_name,
        "display_name": display_name.strip() or model_name,
        "provider_id":  provider_id,
    })
    save_config(cfg)
    return model_id


def remove_llm_model(model_id: str) -> None:
    cfg = load_config()
    cfg["llm_models"] = [
        m for m in cfg.get("llm_models", []) if m["id"] != model_id
    ]
    save_config(cfg)


def update_llm_model(model_id: str, **kwargs) -> None:
    """更新 Model 字段（name / display_name）。"""
    cfg = load_config()
    for m in cfg.get("llm_models", []):
        if m["id"] == model_id:
            for k, v in kwargs.items():
                if k in ("name", "display_name") and v is not None:
                    m[k] = str(v).strip() or m[k]
            break
    save_config(cfg)


# ─── 测试调用（不依赖已保存 config） ─────────────────────────────────────────

def call_llm_with_config(messages: list[dict], model: dict, provider: dict) -> str:
    """使用临时配置调用 LLM，用于新增配置前的连通性测试。

    model    须含 name 字段
    provider 须含 framework / base_url / api_key 字段
    """
    framework = provider.get("framework", "openai")

    if framework == "openai":
        from openai import OpenAI
        client = OpenAI(
            api_key=provider["api_key"],
            base_url=provider["base_url"],
        )
        completion = client.chat.completions.create(
            model=model["name"],
            stream=False,
            messages=messages,
        )
        return completion.choices[0].message.content or ""

    # 预留其他框架扩展点（后台按需添加分支）
    # elif framework == "anthropic": ...
    # elif framework == "zhipuai":   ...

    raise NotImplementedError(f"暂不支持框架：{framework}")


# ─── 调用入口 ─────────────────────────────────────────────────────────────────

def call_llm(messages: list[dict], model_id: str) -> str:
    """统一调用入口。

    messages 格式：[{"role": "system"|"user"|"assistant", "content": str}, ...]
    返回模型回复文本；失败时抛出异常。

    框架扩展：在下方 elif framework == "xxx" 分支添加其他 SDK。
    """
    models    = get_llm_models()
    providers = get_llm_providers()

    model = next((m for m in models if m["id"] == model_id), None)
    if not model:
        raise ValueError(f"未找到 Model（id={model_id}），请先在设置中添加。")

    provider = next((p for p in providers if p["id"] == model["provider_id"]), None)
    if not provider:
        raise ValueError(f"未找到 Provider（id={model['provider_id']}），请检查配置。")

    framework = provider.get("framework", "openai")

    if framework == "openai":
        from openai import OpenAI  # lazy import，避免未安装时启动报错
        client = OpenAI(
            api_key=provider["api_key"],
            base_url=provider["base_url"],
        )
        completion = client.chat.completions.create(
            model=model["name"],
            stream=False,
            messages=messages,
        )
        return completion.choices[0].message.content or ""

    # ── 预留其他框架 ────────────────────────────────────────────────────────
    # elif framework == "anthropic":
    #     from anthropic import Anthropic
    #     ...
    # elif framework == "zhipuai":
    #     ...

    raise NotImplementedError(f"暂不支持框架：{framework}")
