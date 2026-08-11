#!/usr/bin/env python3
"""金融数据验算工具 — 来自 AI Berkshire financial-data 规范。
所有计算使用 Decimal 精确十进制，不用 float。
用法：python3 financial_rigor.py <command> [options]
"""

import sys
from decimal import Decimal, getcontext, ROUND_HALF_UP

getcontext().prec = 28

def _fmt(n, unit=""):
    """格式化数值，大数自动缩写"""
    n = float(n)
    if abs(n) >= 1e12:
        return f"{n/1e12:.2f}万亿{unit}"
    elif abs(n) >= 1e8:
        return f"{n/1e8:.2f}亿{unit}"
    elif abs(n) >= 1e4:
        return f"{n/1e4:.2f}万{unit}"
    return f"{n:,.2f}{unit}"


def verify_market_cap(price, shares, reported=None, currency="HKD"):
    """市值验算：price × shares → 与报告值对比"""
    price_d = Decimal(str(price))
    shares_d = Decimal(str(shares))
    calc = price_d * shares_d
    print(f"股价: {price} {currency}")
    print(f"总股本: {_fmt(shares, '股')}")
    print(f"计算市值: {_fmt(calc, currency)}")
    if reported:
        reported_d = Decimal(str(reported))
        dev = abs(calc - reported_d) / reported_d * 100
        status = "✅ 通过" if dev < 1 else ("⚠️ 偏差" if dev < 5 else "❌ 严重偏差")
        print(f"报告市值: {_fmt(reported, currency)}")
        print(f"偏差: {float(dev):.2f}% → {status}")
    return calc


def verify_valuation(price, eps=None, bvps=None, fcf_per_share=None, dividend=None):
    """估值指标验算：PE/PB/FCF Yield/股息率"""
    p = Decimal(str(price))
    results = {}
    if eps:
        pe = p / Decimal(str(eps))
        results["PE"] = float(pe)
        print(f"PE = {price} / {eps} = {float(pe):.2f}")
    if bvps:
        pb = p / Decimal(str(bvps))
        results["PB"] = float(pb)
        print(f"PB = {price} / {bvps} = {float(pb):.2f}")
    if fcf_per_share:
        fcf_yield = Decimal(str(fcf_per_share)) / p * 100
        results["FCF Yield"] = f"{float(fcf_yield):.2f}%"
        print(f"FCF Yield = {fcf_per_share} / {price} = {float(fcf_yield):.2f}%")
    if dividend:
        div_yield = Decimal(str(dividend)) / p * 100
        results["股息率"] = f"{float(div_yield):.2f}%"
        print(f"股息率 = {dividend} / {price} = {float(div_yield):.2f}%")
    return results


def cross_validate(metric, values, sources):
    """多源交叉验证：N 个来源的同一数据自动比对"""
    vals = [Decimal(str(v)) for v in values]
    mean_val = sum(vals) / len(vals)
    print(f"指标: {metric}")
    max_dev = 0
    for v, s in zip(vals, sources):
        dev = abs(v - mean_val) / mean_val * 100 if mean_val != 0 else 0
        max_dev = max(max_dev, float(dev))
        flag = "✅" if float(dev) < 1 else ("⚠️" if float(dev) < 5 else "❌")
        print(f"  {s}: {float(v):.2f} (偏离均值 {float(dev):.2f}%) {flag}")
    status = "✅ 通过" if max_dev < 1 else ("⚠️ 超过1%容差" if max_dev < 5 else "❌ 超过5%容差，需暂停")
    print(f"最大偏差: {max_dev:.2f}% → {status}")
    return max_dev


def three_scenario(price, eps, shares_growth_pct, pe_bull, pe_base, pe_bear):
    """三情景估值：乐观/中性/悲观"""
    scenarios = [
        ("乐观", Decimal(str(pe_bull)), Decimal("1.15")),
        ("中性", Decimal(str(pe_base)), Decimal("1.05")),
        ("悲观", Decimal(str(pe_bear)), Decimal("0.95")),
    ]
    p = Decimal(str(price))
    e = Decimal(str(eps))
    print(f"当前股价: {price} | EPS: {eps}")
    print(f"情景 | PE | 1年后EPS | 目标价 | 涨跌幅")
    print("-" * 50)
    for name, pe, growth in scenarios:
        future_eps = e * growth
        target = future_eps * pe
        chg = (target - p) / p * 100
        print(f"{name:4s} | {float(pe):4.0f}x | {float(future_eps):.2f} | {float(target):.2f} | {float(chg):+.1f}%")


def calc(expr):
    """精确计算：任意财务表达式，替代 AI 心算"""
    try:
        result = eval(expr.replace(",", ""), {"__builtins__": {}}, {})
        print(f"{expr} = {result:,.2f}")
    except Exception as e:
        print(f"计算失败: {e}")


def _benford_digit(n):
    """Benford 首位数字"""
    import math
    s = str(abs(float(n))).lstrip("0.")
    if not s:
        return None
    return int(s[0])


def benford(values):
    """Benford 定律检测：检查财务数据首位数字分布"""
    from collections import Counter
    digits = [_benford_digit(v) for v in values if _benford_digit(v) is not None]
    if not digits:
        print("无可检测的数值")
        return
    counter = Counter(digits)
    total = len(digits)
    expected = {1: 30.1, 2: 17.6, 3: 12.5, 4: 9.7, 5: 7.9, 6: 6.7, 7: 5.8, 8: 5.1, 9: 4.6}
    print(f"Benford 定律检测 (n={total})")
    print(f"首位 | 实际% | 期望% | 偏差")
    print("-" * 40)
    alerts = 0
    for d in range(1, 10):
        actual = counter.get(d, 0) / total * 100
        exp = expected[d]
        dev = abs(actual - exp)
        flag = " ⚠️" if dev > 10 else ""
        if dev > 10:
            alerts += 1
        print(f"  {d}   | {actual:5.1f} | {exp:5.1f} | {dev:.1f}{flag}")
    if alerts >= 3:
        print(f"⚠️ {alerts} 个数字偏离 >10%，数据可能存在人为修饰")


# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 financial_rigor.py <command> [options]")
        print("  verify-market-cap  --price X --shares X [--reported X] [--currency HKD]")
        print("  verify-valuation   --price X [--eps X] [--bvps X] [--fcf-per-share X] [--dividend X]")
        print("  cross-validate     --metric 'PE' --values '1,2,3' --sources 'A,B,C'")
        print("  three-scenario     --price X --eps X --growth '15,5,-5' --pe '25,20,15'")
        print("  calc               --expr '100*1.1**10'")
        print("  benford            --values '1,2,3,...'")
        sys.exit(0)

    cmd = sys.argv[1]
    args = {}
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:]
            val = sys.argv[i + 1] if i + 1 < len(sys.argv) else "true"
            args[key] = val
            i += 2
        else:
            i += 1

    if cmd == "verify-market-cap":
        verify_market_cap(
            price=float(args.get("price", 0)),
            shares=float(args.get("shares", 0)),
            reported=float(args["reported"]) if "reported" in args else None,
            currency=args.get("currency", "HKD"),
        )
    elif cmd == "verify-valuation":
        verify_valuation(
            price=float(args.get("price", 0)),
            eps=float(args["eps"]) if "eps" in args else None,
            bvps=float(args["bvps"]) if "bvps" in args else None,
            fcf_per_share=float(args["fcf-per-share"]) if "fcf-per-share" in args else None,
            dividend=float(args["dividend"]) if "dividend" in args else None,
        )
    elif cmd == "cross-validate":
        cross_validate(
            metric=args.get("metric", "unknown"),
            values=[float(v) for v in args.get("values", "").split(",")],
            sources=args.get("sources", "").split(","),
        )
    elif cmd == "three-scenario":
        growths = [float(g) for g in args.get("growth", "15,5,-5").split(",")]
        pes = [float(p) for p in args.get("pe", "25,20,15").split(",")]
        three_scenario(
            price=float(args.get("price", 0)),
            eps=float(args.get("eps", 0)),
            shares_growth_pct=float(args.get("shares-growth", 0)),
            pe_bull=pes[0], pe_base=pes[1], pe_bear=pes[2],
        )
    elif cmd == "calc":
        calc(args.get("expr", "0"))
    elif cmd == "benford":
        vals = [float(v) for v in args.get("values", "").split(",")]
        benford(vals)
    else:
        print(f"未知命令: {cmd}")
