"""执行 Agent：负责工具调用和执行。"""

from typing import Any

from app.tools.registry import REGISTRY, ToolError


class ExecutorAgent:
    """执行 Agent"""

    def execute_tool(self, tool_name: str, ctx: dict) -> Any:
        """
        执行单个工具。

        Args:
            tool_name: 工具名称
            ctx: 执行上下文，包含 user_id, slots, results 等

        Returns:
            工具执行结果

        Raises:
            ToolError: 工具执行失败
        """
        if tool_name not in REGISTRY:
            raise ToolError(f"工具 {tool_name} 不存在")

        tool_func = REGISTRY[tool_name]
        return tool_func(ctx)

    def execute_dag(self, nodes: list, execution_order: list, ctx: dict) -> dict:
        """
        执行整个 DAG。

        Args:
            nodes: DAG 节点列表
            execution_order: 执行顺序
            ctx: 执行上下文

        Returns:
            执行结果字典 {node_id: result}
        """
        results = {}
        nodes_dict = {n["id"]: n for n in nodes}

        for node_id in execution_order:
            node = nodes_dict[node_id]
            tool_name = node["tool"]
            result = self.execute_tool(tool_name, ctx)
            results[node_id] = result
            ctx["results"][node_id] = result

        return results


# 单例
executor_agent = ExecutorAgent()
