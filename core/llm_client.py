"""统一 LLM 调用层：JSON 校验、自动重试、调用日志。

对外接口：
  call_llm(system_prompt, user_prompt, *, model_id, expect_json, skill_name, session_id) -> str | dict
  call(messages, model_id, *, expect_json, skill_name, session_id) -> str | dict
  call_with_config(messages, model, provider) -> str   # 用于连通性测试
"""
from __future__ import annotations

import json
import time

from .db_manager import (
    get_llm_models, get_llm_providers,
    log_llm_call,
)


class LLMJsonParseError(ValueError):
    """LLM 返回内容无法解析为合法 JSON 时抛出。"""


def call(
    messages: list[dict],
    model_id: str,
    *,
    expect_json: bool = False,
    skill_name: str = "",
    session_id: str = "",
    max_retries: int = 2,
) -> str | dict:
    """统一调用入口。

    expect_json=True 时解析并校验 JSON 输出，失败自动追加重试提示（最多 max_retries 次）。
    自动写 llm_logs。
    """
    models    = get_llm_models()
    providers = get_llm_providers()

    model = next((m for m in models if m["id"] == model_id), None)
    if not model:
        raise ValueError(f"未找到 Model（id={model_id}），请先在搜索 Tab 添加。")

    provider = next((p for p in providers if p["id"] == model["provider_id"]), None)
    if not provider:
        raise ValueError(f"未找到 Provider（id={model['provider_id']}），请检查配置。")

    msgs    = list(messages)
    t_start = time.monotonic()
    last_error = ""

    for attempt in range(max_retries + 1):
        try:
            raw = _do_call(msgs, model, provider)
        except Exception as exc:
            last_error = str(exc)
            latency_ms = int((time.monotonic() - t_start) * 1000)
            log_llm_call(
                model_id=model_id,
                skill_name=skill_name,
                session_id=session_id,
                latency_ms=latency_ms,
                success=False,
                error_message=last_error,
            )
            raise

        if not expect_json:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            log_llm_call(
                model_id=model_id,
                skill_name=skill_name,
                session_id=session_id,
                latency_ms=latency_ms,
                success=True,
            )
            return raw

        # JSON 模式：尝试解析
        try:
            parsed = _parse_json(raw)
            latency_ms = int((time.monotonic() - t_start) * 1000)
            log_llm_call(
                model_id=model_id,
                skill_name=skill_name,
                session_id=session_id,
                latency_ms=latency_ms,
                success=True,
            )
            return parsed
        except ValueError:
            if attempt < max_retries:
                msgs = msgs + [
                    {"role": "assistant", "content": raw},
                    {"role": "user",      "content": "请只返回纯 JSON，不要有任何额外文字或 markdown 代码块。"},
                ]
            else:
                last_error = f"JSON 解析失败，原始输出：{raw[:200]}"
                latency_ms = int((time.monotonic() - t_start) * 1000)
                log_llm_call(
                    model_id=model_id,
                    skill_name=skill_name,
                    session_id=session_id,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=last_error,
                )
                raise ValueError(last_error)

    raise ValueError("LLM 调用超出重试次数")


def call_with_config(
    messages: list[dict], model: dict, provider: dict
) -> str:
    """使用临时配置调用 LLM，用于新增配置前的连通性测试。"""
    return _do_call(messages, model, provider)


def _do_call(messages: list[dict], model: dict, provider: dict) -> str:
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

    # 预留扩展点
    # elif framework == "anthropic":
    #     from anthropic import Anthropic
    #     ...

    raise NotImplementedError(f"暂不支持框架：{framework}")


def call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    model_id: str,
    expect_json: bool = True,
    skill_name: str = "",
    session_id: str = "",
) -> "str | dict":
    """简化调用接口：直接传入 system/user prompt 字符串。

    等价于 call([system, user], model_id, ...)，供 Skill 层优先使用。
    expect_json=True 时，JSON 解析失败抛出 LLMJsonParseError。
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    try:
        return call(
            messages,
            model_id=model_id,
            expect_json=expect_json,
            skill_name=skill_name,
            session_id=session_id,
        )
    except ValueError as exc:
        if expect_json and "JSON 解析失败" in str(exc):
            raise LLMJsonParseError(str(exc)) from exc
        raise


def _parse_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象，容忍 markdown 代码块包裹。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text  = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMJsonParseError(f"JSON 解析失败：{e}") from e
