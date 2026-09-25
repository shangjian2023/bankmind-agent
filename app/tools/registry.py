class ToolError(Exception):
    """业务级失败：参数缺失、余额不足、对象不存在等，向用户友好展示。"""


REGISTRY = {}


def tool(name):
    def deco(fn):
        REGISTRY[name] = fn
        return fn

    return deco
