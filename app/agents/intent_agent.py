"""意图识别 Agent：负责意图分类和槽位填充。"""

from typing import Optional

from app.agent import intent as intent_mod
from app.agent import slots as slots_mod
from app.agent.guard import check_injection


class IntentAgent:
    """意图识别 Agent"""

    def process(self, text: str) -> dict:
        """
        处理用户输入，返回意图和槽位。

        Args:
            text: 用户输入文本

        Returns:
            {
                "safe": bool,  # 是否安全
                "injection_reason": str | None,  # 注入原因
                "intent": str | None,  # 意图名称
                "confidence": float,  # 置信度
                "slots": dict,  # 提取的槽位
            }
        """
        result = {
            "safe": True,
            "injection_reason": None,
            "intent": None,
            "confidence": 0.0,
            "slots": {},
        }

        # 1. 安全检查
        is_safe, reason = check_injection(text)
        if not is_safe:
            result["safe"] = False
            result["injection_reason"] = reason
            return result

        # 2. 意图分类
        intent_name, confidence = intent_mod.classify(text)
        result["intent"] = intent_name
        result["confidence"] = confidence

        # 3. 槽位填充
        if intent_name:
            result["slots"] = slots_mod.extract(text)

        return result

    def fill_missing_slots(self, intent: str, existing_slots: dict, required_slots: list, ask_prompts: dict) -> tuple[dict, list]:
        """
        检查并填充缺失的槽位。

        Args:
            intent: 意图名称
            existing_slots: 已有槽位
            required_slots: 必需槽位列表
            ask_prompts: 询问提示字典

        Returns:
            (merged_slots, missing_slots)
        """
        missing = [s for s in required_slots if not existing_slots.get(s)]
        return existing_slots, missing


# 单例
intent_agent = IntentAgent()
