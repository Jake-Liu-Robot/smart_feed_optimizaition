"""
AxNano Smart-Feed Algorithm v9 — 配比枚举器
=============================================
生成所有合法的废料混合配比。

Bounds:
  1. sum(ratio_parts) ≤ ratio_sum_max (= 11)
  2. GCD = 1 (去除等比缩放重复，如 4:2 ≡ 2:1)
  3. 每个分量 ≥ 1 (组内所有流都参与)

注: (1,2) 和 (2,1) 视为不同配比（A多B少 vs A少B多）
"""

from math import gcd
from functools import reduce
from itertools import product


def generate_ratios(n_streams: int, max_sum: int) -> list:
    """
    生成 n_streams 个分量的所有合法配比。

    Args:
        n_streams: 参与混合的废料流数量 (1-5)
        max_sum: 配比总和上限，默认 11 (= F_total 取整)

    Returns:
        list of tuple[int, ...]: 所有合法配比

    Example:
        generate_ratios(2, 11) →
        [(1,1), (1,2), (2,1), (1,3), (3,1), (2,3), (3,2), ...]
    """
    if n_streams == 1:
        return [(1,)]  # 单流只有一种配比

    results = []
    upper = max_sum - n_streams + 1  # 单个分量的最大值

    for combo in product(range(1, upper + 1), repeat=n_streams):
        if sum(combo) > max_sum:
            continue
        if reduce(gcd, combo) != 1:
            continue
        results.append(combo)

    return results


# ─── 预计算统计 ───

def ratio_stats(max_streams: int = 5, max_sum: int = 11) -> dict:
    """
    计算各流数量下的配比数量，用于评估搜索空间。
    """
    stats = {}
    for n in range(1, max_streams + 1):
        ratios = generate_ratios(n, max_sum)
        stats[n] = len(ratios)
    return stats
