"""
基础性能压测脚本
使用 httpx 进行并发请求测试，验证系统在负载下的表现
"""

import asyncio
import time
from dataclasses import dataclass
from typing import List

import httpx


@dataclass
class RequestResult:
    """单次请求结果"""
    status_code: int
    elapsed_ms: float
    success: bool


@dataclass
class BenchmarkResult:
    """压测结果汇总"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time_seconds: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    requests_per_second: float


async def make_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    json_data: dict = None
) -> RequestResult:
    """发送单次请求并记录结果"""
    start = time.perf_counter()
    try:
        response = await client.request(method, url, json=json_data)
        elapsed = (time.perf_counter() - start) * 1000
        return RequestResult(
            status_code=response.status_code,
            elapsed_ms=elapsed,
            success=response.status_code < 400
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return RequestResult(
            status_code=0,
            elapsed_ms=elapsed,
            success=False
        )


async def run_benchmark(
    base_url: str,
    concurrency: int,
    total_requests: int,
    endpoint: str = "/api/chat",
    payload: dict = None
) -> BenchmarkResult:
    """
    运行压测

    Args:
        base_url: 服务基础 URL
        concurrency: 并发数
        total_requests: 总请求数
        endpoint: 测试端点
        payload: 请求体
    """
    if payload is None:
        payload = {"user_id": "u001", "message": "查余额"}

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # 创建任务队列
        tasks = []
        for _ in range(total_requests):
            task = make_request(client, "POST", endpoint, payload)
            tasks.append(task)

        # 并发执行
        start_time = time.perf_counter()
        results: List[RequestResult] = []

        # 分批执行以控制并发
        batch_size = concurrency
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch)
            results.extend(batch_results)

        total_time = time.perf_counter() - start_time

    # 统计结果
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    latencies = [r.elapsed_ms for r in successful]

    if not latencies:
        return BenchmarkResult(
            total_requests=total_requests,
            successful_requests=0,
            failed_requests=total_requests,
            total_time_seconds=total_time,
            avg_latency_ms=0,
            min_latency_ms=0,
            max_latency_ms=0,
            p50_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            requests_per_second=0
        )

    latencies.sort()
    avg_latency = sum(latencies) / len(latencies)
    min_latency = latencies[0]
    max_latency = latencies[-1]
    p50_latency = latencies[int(len(latencies) * 0.50)]
    p95_latency = latencies[int(len(latencies) * 0.95)]
    p99_latency = latencies[int(len(latencies) * 0.99)]
    rps = len(successful) / total_time

    return BenchmarkResult(
        total_requests=total_requests,
        successful_requests=len(successful),
        failed_requests=len(failed),
        total_time_seconds=total_time,
        avg_latency_ms=avg_latency,
        min_latency_ms=min_latency,
        max_latency_ms=max_latency,
        p50_latency_ms=p50_latency,
        p95_latency_ms=p95_latency,
        p99_latency_ms=p99_latency,
        requests_per_second=rps
    )


def print_result(result: BenchmarkResult):
    """打印压测结果"""
    print("\n" + "=" * 60)
    print("性能压测结果")
    print("=" * 60)
    print(f"总请求数: {result.total_requests}")
    print(f"成功请求: {result.successful_requests}")
    print(f"失败请求: {result.failed_requests}")
    print(f"总耗时: {result.total_time_seconds:.2f}s")
    print(f"QPS: {result.requests_per_second:.2f}")
    print("-" * 60)
    print("延迟统计 (ms):")
    print(f"  平均: {result.avg_latency_ms:.2f}")
    print(f"  最小: {result.min_latency_ms:.2f}")
    print(f"  最大: {result.max_latency_ms:.2f}")
    print(f"  P50:  {result.p50_latency_ms:.2f}")
    print(f"  P95:  {result.p95_latency_ms:.2f}")
    print(f"  P99:  {result.p99_latency_ms:.2f}")
    print("=" * 60 + "\n")


async def main():
    """主函数"""
    base_url = "http://localhost:8000"

    print("开始性能压测...")
    print(f"目标服务: {base_url}")

    # 测试 1: 低并发基准测试
    print("\n[测试 1] 低并发基准测试 (5 并发, 50 请求)")
    result1 = await run_benchmark(base_url, concurrency=5, total_requests=50)
    print_result(result1)

    # 测试 2: 中等并发测试
    print("\n[测试 2] 中等并发测试 (20 并发, 200 请求)")
    result2 = await run_benchmark(base_url, concurrency=20, total_requests=200)
    print_result(result2)

    # 测试 3: 高并发压力测试
    print("\n[测试 3] 高并发压力测试 (50 并发, 500 请求)")
    result3 = await run_benchmark(base_url, concurrency=50, total_requests=500)
    print_result(result3)

    # 测试 4: 不同端点测试
    print("\n[测试 4] 健康检查端点测试 (10 并发, 100 请求)")
    result4 = await run_benchmark(
        base_url,
        concurrency=10,
        total_requests=100,
        endpoint="/api/health",
        payload=None
    )
    print_result(result4)


if __name__ == "__main__":
    asyncio.run(main())
