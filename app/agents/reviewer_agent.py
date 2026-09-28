"""审核 Agent：负责输出审核和幻觉检测。"""

import re
from typing import Any


class ReviewerAgent:
    """审核 Agent"""

    def review_output(self, intent: str, result: dict, slots: dict) -> dict:
        """
        审核工具执行结果，检测幻觉和异常。

        Args:
            intent: 意图名称
            result: 工具执行结果
            slots: 用户输入的槽位

        Returns:
            {
                "approved": bool,  # 是否通过审核
                "reason": str | None,  # 拒绝原因
                "sanitized_result": dict,  # 清理后的结果
            }
        """
        review_result = {
            "approved": True,
            "reason": None,
            "sanitized_result": result,
        }

        # 1. 检查转账金额是否异常（超过槽位中指定金额的 2 倍）
        if intent == "transfer" and "amount" in slots:
            expected_amount = slots["amount"]
            actual_amount = result.get("amount", 0)
            if actual_amount > expected_amount * 2:
                review_result["approved"] = False
                review_result["reason"] = f"转账金额异常：期望 {expected_amount}，实际 {actual_amount}"
                return review_result

        # 2. 检查余额是否为负数
        if "balance" in result and result["balance"] < 0:
            review_result["approved"] = False
            review_result["reason"] = "余额为负数，可能存在计算错误"
            return review_result

        # 3. 检查是否包含敏感信息泄露
        result_str = str(result)
        if self._contains_sensitive_info(result_str):
            review_result["approved"] = False
            review_result["reason"] = "结果包含敏感信息"
            return review_result

        return review_result

    def _contains_sensitive_info(self, text: str) -> bool:
        """检查文本是否包含敏感信息。"""
        # 检查是否包含完整的银行卡号（16-19位数字）
        if re.search(r'\b\d{16,19}\b', text):
            return True

        # 检查是否包含完整的身份证号
        if re.search(r'\b\d{17}[\dXx]\b', text):
            return True

        # 检查是否包含 API Key 模式
        if re.search(r'(api[_-]?key|secret|password)\s*[:=]\s*\S+', text, re.IGNORECASE):
            return True

        return False

    def validate_response(self, intent: str, response_text: str) -> dict:
        """
        验证最终回复文本。

        Args:
            intent: 意图名称
            response_text: 生成的回复文本

        Returns:
            {
                "valid": bool,
                "issues": list[str],
            }
        """
        issues = []

        # 1. 检查回复长度
        if len(response_text) > 2000:
            issues.append("回复过长")

        # 2. 检查是否包含不适当的内容
        if self._contains_inappropriate_content(response_text):
            issues.append("包含不适当内容")

        # 3. 检查转账回复是否包含关键信息
        if intent == "transfer":
            if not any(keyword in response_text for keyword in ["转账", "成功", "失败"]):
                issues.append("转账回复缺少关键信息")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }

    def _contains_inappropriate_content(self, text: str) -> bool:
        """检查是否包含不适当内容。"""
        # 简单检查：是否包含明显的错误信息模式
        error_patterns = [
            r"系统错误",
            r"未知错误",
            r"请联系管理员",
        ]
        for pattern in error_patterns:
            if re.search(pattern, text):
                return True
        return False


# 单例
reviewer_agent = ReviewerAgent()
