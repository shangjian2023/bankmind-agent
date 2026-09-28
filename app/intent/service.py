"""意图识别服务 - 集成开源方案"""

import json
from typing import Optional, Dict, List, Tuple
from app.data import database
from app.agent.llm import get_llm
from app import config


class IntentRecognitionService:
    """意图识别服务"""

    def __init__(self):
        self.llm = get_llm()
        self.intent_config = self._load_intent_config()

    def _load_intent_config(self) -> Dict:
        """从数据库加载意图配置"""
        with database.connection() as conn:
            config_row = conn.execute(
                "SELECT config_value FROM system_config WHERE config_key = 'intent_config'"
            ).fetchone()

            if config_row:
                return json.loads(config_row["config_value"])

            # 默认配置
            return {
                "provider": "regex",  # regex, llm, hybrid
                "confidence_threshold": 0.7,
                "fallback_enabled": True,
                "max_retries": 3
            }

    async def recognize(self, text: str, context: Optional[Dict] = None) -> Tuple[str, float]:
        """
        识别用户意图

        Args:
            text: 用户输入文本
            context: 上下文信息（用户信息、会话历史等）

        Returns:
            (intent_name, confidence): 意图名称和置信度
        """
        provider = self.intent_config.get("provider", "regex")

        if provider == "regex":
            return self._recognize_with_regex(text)
        elif provider == "llm":
            return await self._recognize_with_llm(text, context)
        elif provider == "hybrid":
            # 先用正则，失败再用 LLM
            intent, conf = self._recognize_with_regex(text)
            if conf < self.intent_config.get("confidence_threshold", 0.7):
                if self.intent_config.get("fallback_enabled", True):
                    return await self._recognize_with_llm(text, context)
            return intent, conf
        else:
            return "unknown", 0.0

    def _recognize_with_regex(self, text: str) -> Tuple[str, float]:
        """使用正则表达式识别意图"""
        from app.agent.intent import classify
        return classify(text)

    async def _recognize_with_llm(self, text: str, context: Optional[Dict] = None) -> Tuple[str, float]:
        """使用 LLM 识别意图"""
        try:
            # 构建提示词
            prompt = self._build_intent_prompt(text, context)

            # 调用 LLM
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个银行智能助手，负责识别用户意图。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )

            # 解析响应
            intent_data = json.loads(response)
            intent = intent_data.get("intent", "unknown")
            confidence = intent_data.get("confidence", 0.5)

            return intent, confidence

        except Exception as e:
            print(f"LLM intent recognition failed: {e}")
            # 降级到正则
            return self._recognize_with_regex(text)

    def _build_intent_prompt(self, text: str, context: Optional[Dict] = None) -> str:
        """构建意图识别提示词"""
        # 加载可用意图列表
        intents = self._get_available_intents()

        prompt = f"""请分析以下用户输入，识别其意图。

用户输入：{text}

可用意图列表：
{json.dumps(intents, ensure_ascii=False, indent=2)}

请以 JSON 格式返回识别结果：
{{
  "intent": "意图名称",
  "confidence": 0.0-1.0,
  "slots": {{
    "参数名": "参数值"
  }}
}}

只返回 JSON，不要其他内容。"""

        return prompt

    def _get_available_intents(self) -> List[Dict]:
        """获取可用意图列表"""
        with database.connection() as conn:
            rows = conn.execute(
                "SELECT intent_name, description, examples FROM intent_definitions WHERE enabled = 1"
            ).fetchall()

            return [
                {
                    "name": row["intent_name"],
                    "description": row["description"],
                    "examples": json.loads(row["examples"]) if row["examples"] else []
                }
                for row in rows
            ]

    async def update_config(self, config: Dict):
        """更新意图识别配置"""
        self.intent_config.update(config)

        with database.connection() as conn:
            conn.execute(
                "UPDATE system_config SET config_value = ? WHERE config_key = 'intent_config'",
                (json.dumps(self.intent_config),)
            )


# 全局实例
intent_service = IntentRecognitionService()
