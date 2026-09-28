"""评测指标计算模块"""

from typing import Dict, List, Any
from collections import defaultdict


def calculate_intent_accuracy(predictions: List[Dict], ground_truth: List[Dict]) -> float:
    """
    计算意图识别准确率

    Args:
        predictions: 预测结果列表 [{"intent": "xxx", "slots": {...}}, ...]
        ground_truth: 真实标签列表 [{"intent": "xxx", "slots": {...}}, ...]

    Returns:
        准确率 (0-1)
    """
    if len(predictions) != len(ground_truth):
        raise ValueError("预测结果和真实标签数量不一致")

    correct = sum(1 for pred, truth in zip(predictions, ground_truth)
                  if pred.get("intent") == truth.get("intent"))

    return correct / len(ground_truth) if ground_truth else 0.0


def calculate_slot_f1(predictions: List[Dict], ground_truth: List[Dict]) -> Dict[str, float]:
    """
    计算槽位填充的精确率、召回率和 F1 分数

    Args:
        predictions: 预测结果列表
        ground_truth: 真实标签列表

    Returns:
        {"precision": float, "recall": float, "f1": float}
    """
    if len(predictions) != len(ground_truth):
        raise ValueError("预测结果和真实标签数量不一致")

    total_tp = 0  # True Positives
    total_fp = 0  # False Positives
    total_fn = 0  # False Negatives

    for pred, truth in zip(predictions, ground_truth):
        pred_slots = pred.get("slots", {})
        truth_slots = truth.get("slots", {})

        # 计算当前样本的 TP, FP, FN
        for slot_name, slot_value in truth_slots.items():
            if slot_name in pred_slots and pred_slots[slot_name] == slot_value:
                total_tp += 1
            else:
                total_fn += 1

        # 检查预测中多出来的槽位
        for slot_name in pred_slots:
            if slot_name not in truth_slots:
                total_fp += 1

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn
    }


def calculate_task_completion_rate(results: List[Dict]) -> float:
    """
    计算任务完成率

    Args:
        results: 任务执行结果列表 [{"status": "success"|"failed"|"error"}, ...]

    Returns:
        完成率 (0-1)
    """
    if not results:
        return 0.0

    success_count = sum(1 for r in results if r.get("status") == "success")
    return success_count / len(results)


def calculate_per_intent_metrics(predictions: List[Dict], ground_truth: List[Dict]) -> Dict[str, Dict[str, float]]:
    """
    计算每个意图的详细指标

    Args:
        predictions: 预测结果列表
        ground_truth: 真实标签列表

    Returns:
        {intent_name: {"precision": float, "recall": float, "f1": float, "support": int}}
    """
    if len(predictions) != len(ground_truth):
        raise ValueError("预测结果和真实标签数量不一致")

    # 统计每个意图的 TP, FP, FN
    intent_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for pred, truth in zip(predictions, ground_truth):
        pred_intent = pred.get("intent")
        truth_intent = truth.get("intent")

        if pred_intent == truth_intent:
            intent_stats[truth_intent]["tp"] += 1
        else:
            if truth_intent:
                intent_stats[truth_intent]["fn"] += 1
            if pred_intent:
                intent_stats[pred_intent]["fp"] += 1

    # 计算每个意图的指标
    metrics = {}
    for intent, stats in intent_stats.items():
        tp = stats["tp"]
        fp = stats["fp"]
        fn = stats["fn"]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[intent] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn  # 真实标签中该意图的数量
        }

    return metrics


def generate_evaluation_report(
    intent_accuracy: float,
    slot_metrics: Dict[str, float],
    task_completion_rate: float,
    per_intent_metrics: Dict[str, Dict[str, float]]
) -> str:
    """
    生成评测报告

    Args:
        intent_accuracy: 意图识别准确率
        slot_metrics: 槽位填充指标
        task_completion_rate: 任务完成率
        per_intent_metrics: 每个意图的详细指标

    Returns:
        格式化的评测报告字符串
    """
    report = []
    report.append("=" * 60)
    report.append("银行 AI 智能体评测报告")
    report.append("=" * 60)
    report.append("")

    # 总体指标
    report.append("【总体指标】")
    report.append(f"  意图识别准确率: {intent_accuracy:.2%}")
    report.append(f"  槽位填充精确率: {slot_metrics['precision']:.2%}")
    report.append(f"  槽位填充召回率: {slot_metrics['recall']:.2%}")
    report.append(f"  槽位填充 F1:    {slot_metrics['f1']:.2%}")
    report.append(f"  任务完成率:     {task_completion_rate:.2%}")
    report.append("")

    # 每个意图的详细指标
    report.append("【各意图详细指标】")
    report.append(f"{'意图名称':<25} {'精确率':>8} {'召回率':>8} {'F1':>8} {'样本数':>6}")
    report.append("-" * 60)

    for intent, metrics in sorted(per_intent_metrics.items(), key=lambda x: x[1]['support'], reverse=True):
        report.append(
            f"{intent:<25} {metrics['precision']:>7.2%} {metrics['recall']:>7.2%} "
            f"{metrics['f1']:>7.2%} {metrics['support']:>6}"
        )

    report.append("")
    report.append("=" * 60)

    return "\n".join(report)
