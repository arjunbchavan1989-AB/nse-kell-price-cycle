"""Daily-bar, deterministic approximation of the supplied Kell cycle diagrams.

Thresholds below are engineering choices, not Oliver Kell's published formulas.
All rolling pivots are shifted: today's bar never creates its own breakout pivot.
"""
import numpy as np
import pandas as pd

PHASES = [
    ("RE", "Reversal Extension", "#dba64c", "bottoming"),
    ("WP", "Wedge Pop", "#52b5d3", "bullish"),
    ("CB", "EMA Crossback", "#48bd91", "bullish"),
    ("BB", "Base 'n Break", "#93c668", "bullish"),
    ("EE", "Exhaustion Extension", "#bb8ae8", "risk"),
    ("WD", "Wedge Drop", "#ed827d", "bearish"),
    ("BC", "Bearish Crossback", "#df9b70", "bearish"),
    ("BD", "Bearish Base Break", "#c880ad", "bearish"),
    ("TR", "Trend / Holding", "#7c99b8", "mixed"),
    ("NC", "No Clear Setup", "#85929d", "neutral"),
]
CONFIG = {
    "ema_fast": 10, "ema_slow": 20, "atr_period": 14,
    "extension_atr": 3.0, "climax_high_atr": 4.0,
    "breakout_volume_ratio": 1.2, "climax_volume_ratio": 1.5,
    "pop_pivot_sessions": 5, "base_sessions": 10,
    "base_width_atr_max": 4.0, "contraction_ratio_max": .85,
    "ema_touch_atr": .5, "crossback_window_sessions": 30,
    "event_visibility_sessions": 5, "minimum_history": 100,
}


def indicators(frame):
    d = frame.copy().sort_index()
    previous = d.close.shift(1)
    tr = pd.concat([d.high-d.low, (d.high-previous).abs(), (d.low-previous).abs()], axis=1).max(axis=1)
    # Explicit Wilder seed (initial mean followed by recursive smoothing).
    atr = pd.Series(np.nan, index=d.index)
    n = CONFIG["atr_period"]
    if len(d) >= n:
        atr.iloc[n-1] = tr.iloc[:n].mean()
        for i in range(n, len(d)):
            atr.iloc[i] = (atr.iloc[i-1]*(n-1)+tr.iloc[i])/n
    d["atr"] = atr
    d["ema10"] = d.close.ewm(span=10, adjust=False, min_periods=10).mean()
    d["ema20"] = d.close.ewm(span=20, adjust=False, min_periods=20).mean()
    d["ema20_slope"] = d.ema20-d.ema20.shift(3)
    d["volume_ratio"] = d.volume/d.volume.rolling(20).mean().shift(1)
    d["extension10"] = (d.close-d.ema10)/d.atr
    d["extension20"] = (d.close-d.ema20)/d.atr
    d["range_atr"] = tr/d.atr
    d["position"] = (d.close-d.low)/(d.high-d.low).replace(0, np.nan)
    d["pivot5_hi"] = d.high.rolling(5).max().shift(1)
    d["pivot5_lo"] = d.low.rolling(5).min().shift(1)
    d["pivot10_hi"] = d.high.rolling(10).max().shift(1)
    d["pivot10_lo"] = d.low.rolling(10).min().shift(1)
    d["high20"] = d.high.rolling(20).max()
    d["low20"] = d.low.rolling(20).min()
    d["base_width_atr"] = (d.pivot10_hi-d.pivot10_lo)/d.atr.shift(1)
    d["contraction"] = tr.rolling(5).mean().shift(1)/tr.rolling(20).mean().shift(1)
    d["prior_below"] = (d.close < d.ema20).rolling(15).sum().shift(1)
    d["prior_above"] = (d.close > d.ema20).rolling(15).sum().shift(1)
    return d


def classify(frame):
    d = indicators(frame)
    history = []
    pop_at = drop_at = None
    crossback_done = bear_crossback_done = False
    last_event = None
    last_exhaustion_high = None
    exhaustion_at = None
    previous_phase = "NC"
    records = []
    for i in range(len(d)):
        r = d.iloc[i]
        regime = "neutral"
        if r.close > r.ema20 and r.ema10 > r.ema20 and r.ema20_slope > 0:
            regime = "bullish"
        elif r.close < r.ema20 and r.ema10 < r.ema20 and r.ema20_slope < 0:
            regime = "bearish"
        if i < CONFIG["minimum_history"]-1 or not np.isfinite(r.atr) or r.atr <= 0:
            records.append({"phase":"NC", "regime":regime, "signal":None, "signal_age":None, "reasons":["Insufficient warm-up history"], "retest_highs":False})
            continue
        prev = d.iloc[i-1]
        up = regime == "bullish"
        down = regime == "bearish"
        reversal = r.extension20 <= -CONFIG["extension_atr"] and r.low <= r.low20
        exhaustion = r.close > r.ema20 and (
            r.extension10 >= CONFIG["extension_atr"] or (
                (r.high-r.ema10)/r.atr >= CONFIG["climax_high_atr"]
                and r.volume_ratio >= CONFIG["climax_volume_ratio"]
                and r.position <= .4))
        pop = (r.close > max(r.ema10,r.ema20) and r.close > r.pivot5_hi
               and r.prior_below >= 5 and prev.close <= max(prev.ema10,prev.ema20)
               and r.volume_ratio >= CONFIG["breakout_volume_ratio"])
        drop = (r.close < min(r.ema10,r.ema20) and r.close < r.pivot5_lo
                and r.prior_above >= 5 and prev.close >= min(prev.ema10,prev.ema20)
                and r.volume_ratio >= CONFIG["breakout_volume_ratio"])
        touch = min(abs(r.low-r.ema10),abs(r.low-r.ema20)) <= CONFIG["ema_touch_atr"]*r.atr
        resistance_touch = min(abs(r.high-r.ema10),abs(r.high-r.ema20)) <= CONFIG["ema_touch_atr"]*r.atr
        cb = (pop_at is not None and 1 <= i-pop_at <= CONFIG["crossback_window_sessions"]
              and not crossback_done and r.ema20_slope >= 0 and touch
              and r.close >= r.ema20 and r.close > prev.close and r.position >= .6)
        bc = (drop_at is not None and 1 <= i-drop_at <= CONFIG["crossback_window_sessions"]
              and not bear_crossback_done and r.ema20_slope <= 0 and resistance_touch
              and r.close <= r.ema20 and r.close < prev.close and r.position <= .4)
        tight = r.base_width_atr <= CONFIG["base_width_atr_max"] and r.contraction <= CONFIG["contraction_ratio_max"]
        bb = up and tight and r.close > r.pivot10_hi and r.volume_ratio >= CONFIG["breakout_volume_ratio"]
        bd = down and tight and r.close < r.pivot10_lo and r.volume_ratio >= CONFIG["breakout_volume_ratio"]
        event = None
        reasons = []
        # Precedence is explicit and prevents directional events sharing a label.
        for code, condition, explanation in [
            ("EE", exhaustion, "Stretched above EMA10; extension risk, not a confirmed top"),
            ("RE", reversal, "At a 20-session low and stretched below EMA20; bottom not confirmed"),
            ("WD", drop, "Loss of both EMAs and prior 5-session support after an advance, with volume"),
            ("WP", pop, "Reclaim of both EMAs and prior 5-session resistance after weakness, with volume"),
            ("CB", cb, "First confirmed EMA support retest within 30 sessions of Wedge Pop"),
            ("BC", bc, "First confirmed EMA resistance retest within 30 sessions of Wedge Drop"),
            ("BB", bb, "Break above a contracted 10-session base in a bullish EMA stack"),
            ("BD", bd, "Break below a contracted 10-session base in a bearish EMA stack"),
        ]:
            if condition:
                event = code
                reasons = [explanation]
                break
        if event == "WP":
            pop_at = i; crossback_done = False; drop_at = None
        elif event == "WD":
            drop_at = i; bear_crossback_done = False; pop_at = None
        elif event == "CB":
            crossback_done = True
        elif event == "BC":
            bear_crossback_done = True
        elif event == "EE":
            last_exhaustion_high = r.high; exhaustion_at = i
        if event:
            last_event = {"code":event, "index":i, "date":str(d.index[i].date()), "reason":reasons[0]}
            history.append({"date":last_event["date"], "code":event, "close":round(float(r.close),2)})
        phase = event
        age = 0 if event else None
        if phase is None and last_event:
            code = last_event["code"]
            elapsed = i-last_event["index"]
            compatible = (
                (code in ("WP","CB","BB") and r.close >= r.ema20)
                or (code in ("WD","BC","BD") and r.close <= r.ema20)
                or (code == "EE" and r.extension10 >= 1.5)
                or (code == "RE" and r.extension20 <= -1.5))
            if compatible and elapsed <= CONFIG["event_visibility_sessions"]:
                phase = code; age = elapsed; reasons = ["Recent signal retained within its 5-session visibility window", last_event["reason"]]
        if phase is None:
            phase = "TR" if regime != "neutral" else "NC"
            reasons = [("Bullish" if up else "Bearish")+" EMA alignment; no fresh named setup"] if regime != "neutral" else ["Mixed EMA structure; no named setup qualifies"]
        retest = bool(exhaustion_at is not None and 2 <= i-exhaustion_at <= 15
                      and r.high >= last_exhaustion_high*.98 and r.close < r.high)
        records.append({"phase":phase, "regime":regime, "signal":event, "signal_age":age,
                        "reasons":reasons, "retest_highs":retest})
        previous_phase = phase
    result = records[-1]
    result["previous_phase"] = records[-2]["phase"] if len(records)>1 else "NC"
    result["changed"] = result["phase"] != result["previous_phase"]
    result["last_event"] = {k:v for k,v in last_event.items() if k!="index"} if last_event else None
    result["events"] = history[-30:]
    return result, d
