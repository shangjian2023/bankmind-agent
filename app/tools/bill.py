from collections import defaultdict
from datetime import date, timedelta

from app import config
from app.data import repositories as repo
from app.security.sandbox import safe_eval
from app.tools.registry import tool


def _stats(amounts):
    n = len(amounts)
    mean = sum(amounts) / n if n else 0
    var = sum((a - mean) ** 2 for a in amounts) / n if n else 0
    return mean, var ** 0.5


@tool("analyze_bills")
def analyze_bills(ctx):
    yearly = ctx["slots"].get("period") == "year"
    window = 365 if yearly else 90
    since = (date.today() - timedelta(days=window)).isoformat()
    rows = repo.transactions_since(ctx["user_id"], since)
    debits = [r for r in rows if r["amount"] < 0]
    incomes = [r["amount"] for r in rows if r["amount"] > 0]

    cat_totals = defaultdict(float)
    for d in debits:
        cat_totals[d["category"]] += abs(d["amount"])
    cat_sorted = sorted(cat_totals.items(), key=lambda kv: -kv[1])

    amounts = [abs(d["amount"]) for d in debits]
    mean, std = _stats(amounts)
    big = [d for d in debits if abs(d["amount"]) > mean + config.ANOMALY_AMOUNT_SIGMA * std]

    dup_map = defaultdict(list)
    for d in debits:
        dup_map[(d["counterparty"], abs(d["amount"]))].append(d["ts"])
    duplicates = [
        {"counterparty": k[0], "amount": k[1], "count": len(v)}
        for k, v in dup_map.items()
        if len(v) >= config.ANOMALY_DUPLICATE_MIN
    ]

    this_month = date.today().replace(day=1).isoformat()[:7]
    last_month = (date.today().replace(day=1) - timedelta(days=1)).isoformat()[:7]
    m_cur = sum(abs(d["amount"]) for d in debits if d["ts"][:7] == this_month)
    m_prev = sum(abs(d["amount"]) for d in debits if d["ts"][:7] == last_month)
    change_pct = safe_eval("(cur - prev) / prev * 100", {"cur": m_cur, "prev": m_prev}) if m_prev > 0 else None

    monthly_series = defaultdict(float)
    for d in debits:
        monthly_series[d["ts"][:7]] += abs(d["amount"])
    monthly_sorted = [{"month": ym, "amount": round(v, 2)} for ym, v in sorted(monthly_series.items())]

    total = sum(amounts)
    if yearly:
        monthly = defaultdict(float)
        for d in debits:
            monthly[d["ts"][:7]] += abs(d["amount"])
        biggest = max(debits, key=lambda d: abs(d["amount"])) if debits else None
        lines = [f"近一年支出 {total:.2f} 元，收入 {sum(incomes):.2f} 元。", "逐月支出："]
        for ym in sorted(monthly):
            lines.append(f"- {ym}: {monthly[ym]:.2f} 元")
        for cat, t in cat_sorted[:3]:
            lines.append(f"Top 分类 - {cat}: {t:.2f} 元")
        if biggest:
            lines.append(f"最大单笔支出：{biggest['counterparty']} {abs(biggest['amount']):.2f} 元（{biggest['ts'][:10]}）。")
    else:
        lines = [f"近90天支出 {total:.2f} 元，收入 {sum(incomes):.2f} 元。"]
        for cat, t in cat_sorted[:5]:
            share = safe_eval("x / total * 100", {"x": t, "total": total}) if total else 0
            lines.append(f"- {cat}: {t:.2f} 元（占 {share:.1f}%）")
        if change_pct is not None:
            trend = "上升" if change_pct > 0 else "下降"
            lines.append(f"本月支出 {m_cur:.2f} 元，较上月{trend} {abs(change_pct):.1f}%。")
    if big:
        names = "、".join(f"{b['counterparty']} {abs(b['amount']):.0f}元" for b in big)
        lines.append(f"⚠ 异常大额交易：{names}，建议核实。")
    for dp in duplicates:
        lines.append(
            f"⚠ 疑似自动扣费：{dp['counterparty']} 每 {abs(dp['amount']):.0f} 元 ×{dp['count']} 次，可用「查订阅」管理。"
        )
    if not big and not duplicates:
        lines.append("未发现明显异常交易。")

    return {
        "total_out": round(total, 2),
        "total_in": round(sum(incomes), 2),
        "category_totals": {k: round(v, 2) for k, v in cat_sorted},
        "monthly_series": monthly_sorted,
        "month_current": round(m_cur, 2),
        "month_prev": round(m_prev, 2),
        "change_pct": round(change_pct, 1) if change_pct is not None else None,
        "anomalies_big": [{"counterparty": b["counterparty"], "amount": b["amount"], "ts": b["ts"]} for b in big],
        "anomalies_duplicate": duplicates,
        "report_text": "\n".join(lines),
    }
