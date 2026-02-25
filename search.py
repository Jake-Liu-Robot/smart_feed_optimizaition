"""
AxNano Smart-Feed Algorithm v9 — 递归搜索引擎
===============================================
Step 4: 枚举所有可行的多相喂料计划
       使用 3 bounds + 3 pruning 策略控制搜索空间

搜索策略:
  Bound 1: ratio sum ≤ ratio_sum_max
  Bound 2: GCD = 1 (去重)
  Bound 3: depth ≤ N (最多 N 个 phase)
  Prune 1: W < W_min → 跳过不可行分支
  Prune 2: cost_so_far ≥ best_cost → 剪枝
  Prune 3: Memoization (缓存子问题最优解)
"""

from itertools import combinations
from .models import WasteStream, SystemConfig, PhaseResult, Schedule
from .ratios import generate_ratios
from .gatekeeper import evaluate_phase


def search(
    streams: list,
    cfg: SystemConfig,
) -> tuple:
    """
    搜索最优喂料计划。

    Args:
        streams: 所有废料流
        cfg: 系统配置

    Returns:
        (best_cost, best_phases): 最低成本及对应的 phase 列表
    """
    streams_map = {s.stream_id: s for s in streams}
    inventory = {s.stream_id: s.quantity_L for s in streams}
    N = len(streams)

    # 预生成各子集大小的配比
    ratio_cache = {}
    for n in range(1, N + 1):
        ratio_cache[n] = generate_ratios(n, cfg.ratio_sum_max)

    # Memoization 缓存
    memo = {}

    # 搜索统计
    stats = {"evaluated": 0, "pruned_infeasible": 0,
             "pruned_bound": 0, "memo_hits": 0}

    def _search(inv: dict, cost_so_far: float,
                best_cost: float, depth: int) -> tuple:
        """
        递归核心。

        Args:
            inv: 当前库存 {stream_id: remaining_L}
            cost_so_far: 已累计成本
            best_cost: 目前已知最优总成本
            depth: 当前递归深度

        Returns:
            (best_total_cost, phases_list)
        """
        # 获取仍有库存的流
        active = {sid: qty for sid, qty in inv.items() if qty > 0}

        # 终止: 所有库存耗尽
        if not active:
            return cost_so_far, []

        # BOUND 3: 最大 phase 数 = 废料总数
        if depth > N:
            return float("inf"), []

        # PRUNE 3: Memoization
        memo_key = frozenset(
            (sid, round(qty, 2)) for sid, qty in sorted(active.items())
        )
        if memo_key in memo:
            stats["memo_hits"] += 1
            cached_cost, cached_phases = memo[memo_key]
            total = cost_so_far + cached_cost
            return total, list(cached_phases)

        active_ids = sorted(active.keys())
        best_sub_cost = float("inf")
        best_phases = None

        # 枚举所有非空子集
        for subset_size in range(1, len(active_ids) + 1):
            for subset in combinations(active_ids, subset_size):

                # 获取该子集大小的所有合法配比 (Bound 1 + 2)
                ratios_list = ratio_cache.get(len(subset), [(1,)])

                subset_streams = [streams_map[sid] for sid in subset]

                for ratios in ratios_list:
                    stats["evaluated"] += 1

                    # 评估该 phase (含 Gatekeeper + 可行性检查)
                    phase = evaluate_phase(
                        subset_streams, ratios, active, cfg
                    )

                    # PRUNE 1: 不可行 (W < W_min)
                    if phase is None:
                        stats["pruned_infeasible"] += 1
                        continue

                    # PRUNE 2: Branch & Bound
                    if cost_so_far + phase.cost_total >= best_cost:
                        stats["pruned_bound"] += 1
                        continue

                    # 更新库存
                    new_inv = dict(inv)
                    num_batches = min(
                        active[sid] / ratio
                        for sid, ratio in zip(subset, ratios)
                    )
                    for sid, ratio in zip(subset, ratios):
                        new_inv[sid] = active[sid] - ratio * num_batches

                    # 递归
                    sub_total, sub_phases = _search(
                        new_inv,
                        cost_so_far + phase.cost_total,
                        best_cost,
                        depth + 1,
                    )

                    if sub_total < best_cost:
                        best_cost = sub_total
                        best_sub_cost = sub_total - cost_so_far
                        best_phases = [phase] + sub_phases

        # 缓存子问题最优解
        if best_phases is not None:
            memo[memo_key] = (best_sub_cost, list(best_phases))
            return cost_so_far + best_sub_cost, best_phases
        else:
            # 没有可行解
            memo[memo_key] = (float("inf"), [])
            return float("inf"), []

    best_cost, best_phases = _search(inventory, 0.0, float("inf"), 0)

    return best_cost, best_phases, stats


def build_optimized_schedule(
    streams: list,
    cfg: SystemConfig,
) -> tuple:
    """
    构建最优计划。

    Returns:
        (Schedule, search_stats)
    """
    best_cost, best_phases, stats = search(streams, cfg)

    if best_phases is None or best_cost == float("inf"):
        return None, stats

    schedule = Schedule(
        phases=best_phases,
        total_cost=best_cost,
        total_runtime_min=sum(p.runtime_min for p in best_phases),
    )
    return schedule, stats
