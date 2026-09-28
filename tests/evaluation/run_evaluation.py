"""自动化评测脚本"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.intent_agent import intent_agent
from tests.evaluation.metrics import (
    calculate_intent_accuracy,
    calculate_slot_f1,
    calculate_per_intent_metrics,
    generate_evaluation_report
)


def load_golden_dataset(dataset_path: str) -> List[Dict]:
    """加载黄金数据集"""
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['test_cases']


def run_intent_classification_test(test_cases: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """
    运行意图分类测试

    Args:
        test_cases: 测试用例列表

    Returns:
        (predictions, ground_truth) 元组
    """
    predictions = []
    ground_truth = []

    for case in test_cases:
        if case['category'] != 'intent_classification':
            continue

        input_text = case['input']
        expected = case['expected']

        # 调用意图识别 Agent
        result = intent_agent.process(input_text)

        # 记录预测结果
        predictions.append({
            'intent': result['intent'],
            'slots': result['slots']
        })

        # 记录真实标签
        ground_truth.append({
            'intent': expected['intent'],
            'slots': expected.get('slots', {})
        })

    return predictions, ground_truth


def run_slot_extraction_test(test_cases: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """
    运行槽位提取测试

    Args:
        test_cases: 测试用例列表

    Returns:
        (predictions, ground_truth) 元组
    """
    predictions = []
    ground_truth = []

    for case in test_cases:
        if case['category'] != 'slot_extraction':
            continue

        input_text = case['input']
        expected = case['expected']

        # 调用意图识别 Agent
        result = intent_agent.process(input_text)

        # 记录预测结果
        predictions.append({
            'intent': result['intent'],
            'slots': result['slots']
        })

        # 记录真实标签
        ground_truth.append({
            'intent': expected['intent'],
            'slots': expected.get('slots', {})
        })

    return predictions, ground_truth


def run_full_evaluation(dataset_path: str) -> str:
    """
    运行完整评测

    Args:
        dataset_path: 黄金数据集路径

    Returns:
        评测报告字符串
    """
    # 加载测试数据
    test_cases = load_golden_dataset(dataset_path)

    # 运行意图分类测试
    intent_predictions, intent_ground_truth = run_intent_classification_test(test_cases)

    # 运行槽位提取测试
    slot_predictions, slot_ground_truth = run_slot_extraction_test(test_cases)

    # 合并所有预测和真实标签
    all_predictions = intent_predictions + slot_predictions
    all_ground_truth = intent_ground_truth + slot_ground_truth

    # 计算指标
    intent_accuracy = calculate_intent_accuracy(all_predictions, all_ground_truth)
    slot_metrics = calculate_slot_f1(all_predictions, all_ground_truth)
    per_intent_metrics = calculate_per_intent_metrics(all_predictions, all_ground_truth)

    # 生成报告
    report = generate_evaluation_report(
        intent_accuracy=intent_accuracy,
        slot_metrics=slot_metrics,
        task_completion_rate=0.0,  # 暂时设为 0，后续可以添加任务完成率测试
        per_intent_metrics=per_intent_metrics
    )

    return report


def main():
    """主函数"""
    # 默认数据集路径
    dataset_path = Path(__file__).parent / 'golden_dataset.json'

    if not dataset_path.exists():
        print(f"错误: 找不到黄金数据集文件 {dataset_path}")
        sys.exit(1)

    print("开始运行评测...")
    print(f"数据集: {dataset_path}")
    print()

    # 运行评测
    report = run_full_evaluation(str(dataset_path))

    # 输出报告
    print(report)

    # 保存报告到文件
    report_path = Path(__file__).parent / 'evaluation_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n评测报告已保存到: {report_path}")


if __name__ == '__main__':
    main()
