"""多智能体协作架构。

本模块实现了基于多 Agent 的协作架构，包括：
- IntentAgent: 意图识别 Agent
- PlannerAgent: 任务规划 Agent
- ExecutorAgent: 执行 Agent
- ReviewerAgent: 审核 Agent
- Coordinator: 多智能体协调器
"""

from app.agents.intent_agent import IntentAgent, intent_agent
from app.agents.planner_agent import PlannerAgent, planner_agent
from app.agents.executor_agent import ExecutorAgent, executor_agent
from app.agents.reviewer_agent import ReviewerAgent, reviewer_agent
from app.agents.coordinator import handle_message, confirm_action, verify_mfa, SESSIONS

__all__ = [
    "IntentAgent",
    "intent_agent",
    "PlannerAgent",
    "planner_agent",
    "ExecutorAgent",
    "executor_agent",
    "ReviewerAgent",
    "reviewer_agent",
    "handle_message",
    "confirm_action",
    "verify_mfa",
    "SESSIONS",
]
