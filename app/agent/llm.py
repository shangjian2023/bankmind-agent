"""LLM 抽象层：默认 MockLLM（规则引擎），预留 OpenAI 兼容接口。"""

from app import config


class MockLLM:
    """无 Key 时的可运行兜底：意图识别和回复生成均由规则引擎完成。"""

    name = "mock"

    def chat(self, messages, tools=None):
        return {"role": "assistant", "content": "[MockLLM] 规则引擎已接管本回合。"}


class OpenAICompatLLM:
    def __init__(self):
        if not (config.OPENAI_API_KEY and config.OPENAI_BASE_URL):
            raise RuntimeError("LLM_MODE=openai 需要配置 OPENAI_API_KEY / OPENAI_BASE_URL")

    name = "openai-compatible"

    def chat(self, messages, tools=None):
        import httpx

        body = {"model": config.OPENAI_MODEL, "messages": messages}
        if tools:
            body["tools"] = tools
        resp = httpx.post(
            f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]


def get_llm():
    if config.LLM_MODE == "openai":
        return OpenAICompatLLM()
    return MockLLM()
