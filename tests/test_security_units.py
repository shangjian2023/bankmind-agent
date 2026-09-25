import pytest

from app.security.permissions import classify, GREEN, YELLOW, RED
from app.security.sandbox import safe_eval, SandboxViolation


def test_transfer_level_boundary():
    assert classify("transfer", {"amount": 1000.0}, "u001")[0] == YELLOW
    assert classify("transfer", {"amount": 1000.01}, "u001")[0] == RED
    assert classify("balance_query", {}, "u001")[0] == GREEN
    assert classify("report_loss", {}, "u001")[0] == RED


def test_sandbox_arithmetic():
    assert safe_eval("1 + 2 * 3", {}) == 7
    assert safe_eval("(cur - prev) / prev * 100", {"cur": 120, "prev": 100}) == pytest.approx(20.0)
    assert safe_eval("round(abs(-3.6))", {}) == 4


def test_sandbox_blocks_dangerous():
    for expr in [
        "__import__('os').system('dir')",
        "x.__class__",
        "open('/etc/passwd')",
        "[i for i in range(10)]",
        "'a' if True else 'b'",
    ]:
        with pytest.raises(SandboxViolation):
            safe_eval(expr, {"x": 1})
