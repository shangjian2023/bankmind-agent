"""受限求值沙箱：Agent 生成的计算表达式只允许算术与白名单函数，禁止属性访问、下标、导入等。"""

import ast
import operator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}

_FUNCS = {"abs": abs, "min": min, "max": max, "round": round, "sum": sum}
_CONSTS = {"pi": 3.141592653589793}


class SandboxViolation(Exception):
    pass


def _eval(node, variables):
    if isinstance(node, ast.Expression):
        return _eval(node.body, variables)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise SandboxViolation(f"未授权变量: {node.id}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval(node.left, variables), _eval(node.right, variables))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand, variables))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval(a, variables) for a in node.args])
    raise SandboxViolation(f"禁止的语法节点: {type(node).__name__}")


def safe_eval(expr, variables):
    tree = ast.parse(expr, mode="eval")
    return _eval(tree, variables)
