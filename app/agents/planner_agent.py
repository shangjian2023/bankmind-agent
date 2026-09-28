"""任务规划 Agent：负责 DAG 规划和执行顺序生成。"""

from app.agent import planner


class PlannerAgent:
    """任务规划 Agent"""

    def plan(self, intent: str) -> dict | None:
        """
        根据意图生成 DAG 计划。

        Args:
            intent: 意图名称

        Returns:
            DAG 模板字典，包含 required_slots, optional_slots, nodes
        """
        return planner.build(intent)

    def get_execution_order(self, nodes: list) -> list:
        """
        计算 DAG 节点的执行顺序。

        Args:
            nodes: DAG 节点列表

        Returns:
            按拓扑排序的执行顺序
        """
        return planner.topo_sort(nodes)


# 单例
planner_agent = PlannerAgent()
