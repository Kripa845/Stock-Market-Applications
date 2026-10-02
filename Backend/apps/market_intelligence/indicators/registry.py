"""The indicator registry: what exists, what it needs, its parameters, outputs and how to draw it.

Adding an indicator:
  1. write a function in the matching category module (lists in, same-length lists out, None in warm-up);
  2. add an ``_ind(...)`` entry below;
  3. add a test in apps/market_intelligence/tests/test_indicator_library.py.
The frontend picker is built from ``registry_payload()``, so nothing else needs to change.
"""

from dataclasses import dataclass, field
from typing import Callable

from . import custom, market, momentum, moving_averages as ma, price, trend, volatility, volume

MA, MOM, TREND, VOLAT, VOL, PRICE, MARKET, STANDARD = (
    "Moving averages", "Momentum", "Trend", "Volatility", "Volume", "Price & levels",
    "Market & relative", "Standard versions",
)


@dataclass
class Param:
    name: str
    default: object
    minimum: float = 1
    maximum: float = 500
    label: str = ""
    kind: str = "int"          # int | float | choice
    choices: tuple = ()


@dataclass
class Output:
    key: str
    label: str
    kind: str = "line"         # line | bar | dot


@dataclass
class Indicator:
    id: str
    name: str
    category: str
    fn: Callable
    inputs: tuple
    params: tuple
    outputs: tuple
    display: str               # overlay | panel
    ref_lines: tuple = ()
    value_range: tuple = ()    # fixed y-axis (min, max) for bounded oscillators
    fill: tuple = ()           # shade between two outputs
    color_by: str = ""         # output whose sign colours bar outputs
    scope: str = "stock"       # stock | range | market | benchmark | floorsheet
    notes: str = ""
    extra: dict = field(default_factory=dict)


def P(name, default, minimum=1, maximum=500, label="", kind="int", choices=()):
    return Param(name, default, minimum, maximum, label or name.replace("_", " ").capitalize(), kind, choices)


def O(key, label="", kind="line"):  # noqa: E741 - mirrors P()
    return Output(key, label or key.replace("_", " ").title(), kind)


N = lambda default, label="Period", minimum=1: P("period", default, minimum, label=label)  # noqa: E731
OHLC = ("open", "high", "low", "close")
HLC = ("high", "low", "close")
HLCV = ("high", "low", "close", "volume")
VALUE = (O("value", "Value"),)

REGISTRY = {}


def _ind(id_, name, category, fn, inputs, params, outputs, display, **kwargs):
    REGISTRY[id_] = Indicator(id_, name, category, fn, tuple(inputs), tuple(params), tuple(outputs), display, **kwargs)


# ── Moving averages (overlay) ──────────────────────────────────────────────────────────
_ind("sma", "Simple Moving Average", MA, ma.sma, ["close"], [N(20)], VALUE, "overlay")
_ind("ema", "Exponential Moving Average", MA, ma.ema, ["close"], [N(20)], VALUE, "overlay")
_ind("wma", "Weighted Moving Average", MA, ma.wma, ["close"], [N(20)], VALUE, "overlay")
_ind("dema", "Double EMA", MA, ma.dema, ["close"], [N(20)], VALUE, "overlay")
_ind("tema", "Triple EMA", MA, ma.tema, ["close"], [N(20)], VALUE, "overlay")
_ind("hma", "Hull Moving Average", MA, ma.hull_ma, ["close"], [N(9, minimum=2)], VALUE, "overlay")
_ind("smma", "Smoothed Moving Average", MA, ma.smma, ["close"], [N(7)], VALUE, "overlay")
_ind("vwma", "Volume Weighted MA", MA, ma.vwma, ["close", "volume"], [N(20)], VALUE, "overlay")
_ind("mcginley", "McGinley Dynamic", MA, ma.mcginley, ["close"], [N(14)], VALUE, "overlay")
_ind("alma", "Arnaud Legoux MA", MA, ma.alma, ["close"],
     [N(9), P("offset", 0.85, 0, 1, kind="float"), P("sigma", 6, 0.1, 50, kind="float")], VALUE, "overlay")
_ind("lsma", "Linear Regression Curve (LSMA)", MA, ma.lsma, ["close"], [N(25, minimum=2)], VALUE, "overlay")
_ind("linreg_slope", "Linear Regression Slope", MA, ma.linreg_slope, ["close"], [N(25, minimum=2)], VALUE, "panel",
     ref_lines=(0,))
_ind("kama", "Kaufman Adaptive MA", MA, ma.kama, ["close"],
     [N(10), P("fast", 2, 1, 100), P("slow", 30, 1, 200)], VALUE, "overlay")
_ind("hamming", "Hamming MA", MA, ma.hamming_ma, ["close"], [N(20, minimum=2)], VALUE, "overlay")
_ind("ma_channel", "MA Channel", MA, ma.ma_channel, ["high", "low"], [N(20)], [O("upper"), O("lower")], "overlay")
_ind("ma_double", "MA Double", MA, ma.ma_double, ["close"], [P("fast", 10), P("slow", 30)],
     [O("ma1", "MA 1"), O("ma2", "MA 2")], "overlay")
_ind("ma_triple", "MA Triple", MA, ma.ma_triple, ["close"], [P("ma1", 10, label="MA 1"), P("ma2", 20, label="MA 2"),
     P("ma3", 50, label="MA 3")], [O("ma1", "MA 1"), O("ma2", "MA 2"), O("ma3", "MA 3")], "overlay")
_ind("ma_multiple", "MA Multiple", MA, ma.ma_multiple, ["close"],
     [P(f"ma{i}", d, label=f"MA {i}") for i, d in enumerate((5, 10, 20, 50, 100, 200), 1)],
     [O(f"ma{i}", f"MA {i}") for i in range(1, 7)], "overlay")
_CROSS_OUT = [O("fast"), O("slow"), O("cross_up", "Cross up", "dot"), O("cross_down", "Cross down", "dot")]
_ind("ma_cross", "MA Cross", MA, ma.ma_cross, ["close"], [P("fast", 9), P("slow", 21)], _CROSS_OUT, "overlay")
_ind("ema_cross", "EMA Cross", MA, ma.ema_cross, ["close"], [P("fast", 9), P("slow", 21)], _CROSS_OUT, "overlay")
_ind("ma_ema_cross", "MA with EMA Cross", MA, ma.ma_ema_cross, ["close"],
     [P("ma_period", 10, label="MA period"), P("ema_period", 10, label="EMA period")], _CROSS_OUT, "overlay",
     notes="Fast line = SMA, slow line = EMA.")
_ind("guppy", "Guppy Multiple MA", MA, ma.guppy, ["close"],
     [P(f"s{i}", d, label=f"Short {i}") for i, d in enumerate(ma.GUPPY_SHORT, 1)]
     + [P(f"l{i}", d, label=f"Long {i}") for i, d in enumerate(ma.GUPPY_LONG, 1)],
     [O(f"s{i}", f"Short {i}") for i in range(1, 7)] + [O(f"l{i}", f"Long {i}") for i in range(1, 7)], "overlay")

# ── Momentum / oscillators (panel) ─────────────────────────────────────────────────────
_ind("macd", "MACD", MOM, momentum.macd, ["close"], [P("fast", 12), P("slow", 26), P("signal", 9)],
     [O("macd", "MACD"), O("signal"), O("histogram", kind="bar")], "panel", ref_lines=(0,))
_ind("rsi", "Relative Strength Index", MOM, momentum.rsi, ["close"], [N(14)], VALUE, "panel",
     ref_lines=(30, 70), value_range=(0, 100))
_ind("stochastic", "Stochastic", MOM, momentum.stochastic, HLC, [P("k_period", 14, label="%K period"),
     P("d_period", 3, label="%D period")], [O("k", "%K"), O("d", "%D")], "panel", ref_lines=(20, 80),
     value_range=(0, 100))
_ind("stoch_rsi", "Stochastic RSI", MOM, momentum.stoch_rsi, ["close"],
     [P("rsi_period", 14, label="RSI period"), P("stoch_period", 14, label="Stochastic period")], VALUE, "panel",
     ref_lines=(0.2, 0.8), value_range=(0, 1), notes="0-1 scale, unsmoothed, as specified.")
_ind("williams_r", "Williams %R", MOM, momentum.williams_r, HLC, [N(14)], VALUE, "panel", ref_lines=(-20, -80),
     value_range=(-100, 0))
_ind("cci", "Commodity Channel Index", MOM, momentum.cci, HLC, [N(20)], VALUE, "panel", ref_lines=(-100, 100))
_ind("momentum", "Momentum", MOM, momentum.momentum, ["close"], [N(10)], VALUE, "panel", ref_lines=(0,))
_ind("roc", "Rate of Change", MOM, momentum.roc, ["close"], [N(9)], VALUE, "panel", ref_lines=(0,))
_ind("price_oscillator", "Price Oscillator", MOM, momentum.price_oscillator, ["close"],
     [P("fast", 12), P("slow", 26)], [O("po", "PO"), O("ppo", "PPO %")], "panel", ref_lines=(0,))
_ind("awesome", "Awesome Oscillator", MOM, momentum.awesome, ["high", "low"], [P("fast", 5), P("slow", 34)],
     [O("value", "AO", "bar")], "panel", ref_lines=(0,))
_ind("accelerator", "Accelerator Oscillator", MOM, momentum.accelerator, ["high", "low"],
     [P("fast", 5), P("slow", 34), P("signal", 5)], [O("value", "AC", "bar")], "panel", ref_lines=(0,))
_ind("bop", "Balance of Power", MOM, momentum.balance_of_power, OHLC, [], VALUE, "panel", ref_lines=(0,),
     value_range=(-1, 1), notes="Unsmoothed; None on bars with no range.")
_ind("cmo", "Chande Momentum Oscillator", MOM, momentum.cmo, ["close"], [N(9)], VALUE, "panel",
     ref_lines=(-50, 50), value_range=(-100, 100))
_ind("connors_rsi", "Connors RSI", MOM, momentum.connors_rsi, ["close"],
     [P("rsi_period", 3, label="RSI period"), P("streak_period", 2, label="Streak RSI period"),
      P("rank_period", 100, label="Percent rank period")], VALUE, "panel", ref_lines=(10, 90), value_range=(0, 100))
_ind("coppock", "Coppock Curve", MOM, momentum.coppock, ["close"],
     [P("wma_period", 10, label="WMA period"), P("long_roc", 14, label="Long ROC"),
      P("short_roc", 11, label="Short ROC")], VALUE, "panel", ref_lines=(0,))
_ind("dpo", "Detrended Price Oscillator", MOM, momentum.dpo, ["close"], [N(20)], VALUE, "panel", ref_lines=(0,))
_ind("fisher", "Fisher Transform", MOM, momentum.fisher, ["high", "low"], [N(9)],
     [O("fisher"), O("trigger")], "panel", ref_lines=(0,))
_ind("kst", "Know Sure Thing", MOM, momentum.kst, ["close"],
     [P(f"roc{i}", d, label=f"ROC {i}") for i, d in enumerate((10, 15, 20, 30), 1)]
     + [P(f"sma{i}", d, label=f"SMA {i}") for i, d in enumerate((10, 10, 10, 15), 1)] + [P("signal", 9)],
     [O("kst", "KST"), O("signal")], "panel", ref_lines=(0,))
_ind("rvi", "Relative Vigor Index", MOM, momentum.rvi, OHLC, [N(10)], [O("rvi", "RVI"), O("signal")], "panel",
     ref_lines=(0,), notes="Signal = (RVI + 2*RVI[1] + 2*RVI[2] + RVI[3]) / 6, the standard companion line.")
_ind("trix", "TRIX", MOM, momentum.trix, ["close"], [N(15)], VALUE, "panel", ref_lines=(0,))
_ind("tsi", "True Strength Index", MOM, momentum.tsi, ["close"],
     [P("long", 25), P("short", 13), P("signal", 13)], [O("tsi", "TSI"), O("signal")], "panel", ref_lines=(0,))
_ind("smi_ergodic", "SMI Ergodic", MOM, momentum.smi_ergodic, ["close"],
     [P("long", 20), P("short", 5), P("signal", 5)], [O("smi", "SMI"), O("signal")], "panel", ref_lines=(0,))
_ind("ultimate", "Ultimate Oscillator", MOM, momentum.ultimate, HLC, [P("p1", 7, label="Short"),
     P("p2", 14, label="Medium"), P("p3", 28, label="Long")], VALUE, "panel", ref_lines=(30, 70), value_range=(0, 100))

# ── Trend ──────────────────────────────────────────────────────────────────────────────
_ind("adx", "Directional Movement / ADX", TREND, trend.adx, HLC, [N(14)],
     [O("plus_di", "+DI"), O("minus_di", "-DI"), O("adx", "ADX")], "panel", ref_lines=(25,))
_ind("aroon", "Aroon", TREND, trend.aroon, ["high", "low"], [N(25)], [O("up"), O("down")], "panel",
     value_range=(0, 100))
_ind("psar", "Parabolic SAR", TREND, trend.parabolic_sar, ["high", "low"],
     [P("step", 0.02, 0.001, 1, kind="float"), P("max_step", 0.2, 0.01, 1, kind="float", label="Max step")],
     [O("value", "SAR", "dot")], "overlay")
_ind("supertrend", "SuperTrend", TREND, trend.supertrend, HLC,
     [N(10, "ATR period"), P("multiplier", 3, 0.1, 20, kind="float")],
     [O("up", "Up trend"), O("down", "Down trend")], "overlay")
_ind("vortex", "Vortex", TREND, trend.vortex, HLC, [N(14)], [O("plus", "VI+"), O("minus", "VI-")], "panel",
     ref_lines=(1,))
_ind("ichimoku", "Ichimoku Cloud", TREND, trend.ichimoku, HLC,
     [P("conversion", 9), P("base", 26), P("span_b", 52, label="Span B"), P("displacement", 26)],
     [O("tenkan"), O("kijun"), O("senkou_a", "Senkou A"), O("senkou_b", "Senkou B"), O("chikou")], "overlay",
     fill=("senkou_a", "senkou_b"), notes="The cloud's 26 future bars are not drawn (no bars exist there).")
_ind("alligator", "Williams Alligator", TREND, trend.alligator, ["high", "low"],
     [P("jaw", 13), P("jaw_shift", 8, 0), P("teeth", 8), P("teeth_shift", 5, 0), P("lips", 5), P("lips_shift", 3, 0)],
     [O("jaw"), O("teeth"), O("lips")], "overlay")
_ind("choppiness", "Choppiness Index", TREND, trend.choppiness, HLC, [N(14, minimum=2)], VALUE, "panel",
     ref_lines=(38.2, 61.8), value_range=(0, 100))
_ind("trend_strength", "Trend Strength Index", TREND, trend.trend_strength, ["close"], [N(14, minimum=2)], VALUE,
     "panel", ref_lines=(0,), value_range=(-1, 1))
_ind("mass_index", "Mass Index", TREND, trend.mass_index, ["high", "low"],
     [P("ema_period", 9, label="EMA period"), P("sum_period", 25, label="Sum period")], VALUE, "panel",
     ref_lines=(27, 26.5))
_ind("chande_kroll", "Chande Kroll Stop", TREND, trend.chande_kroll, HLC,
     [P("atr_period", 10, label="ATR period"), P("multiplier", 1, 0.1, 20, kind="float"),
      P("stop_period", 9, label="Stop period")], [O("short_stop", "Short stop"), O("long_stop", "Long stop")], "overlay")
_ind("asi", "Accumulative Swing Index", TREND, trend.accumulative_swing_index, OHLC,
     [P("limit_pct", 10, 0.1, 100, kind="float", label="Limit move %")], VALUE, "panel", ref_lines=(0,),
     notes="T = limit move % of the previous close (NEPSE's 10% circuit by default).")
_ind("zigzag", "Zig Zag", TREND, trend.zigzag, ["high", "low"],
     [P("deviation", 5, 0.1, 100, kind="float", label="Deviation %")], VALUE, "overlay",
     notes="The last leg is provisional until price reverses by the deviation.")

# ── Volatility / channels ──────────────────────────────────────────────────────────────
_BANDS = [O("upper"), O("middle"), O("lower")]
_ind("atr", "Average True Range", VOLAT, volatility.atr, HLC, [N(14)], VALUE, "panel")
_ind("bollinger", "Bollinger Bands", VOLAT, volatility.bollinger, ["close"],
     [N(20), P("multiplier", 2, 0.1, 10, kind="float")], _BANDS, "overlay")
_ind("bollinger_b", "Bollinger %B", VOLAT, volatility.bollinger_percent_b, ["close"],
     [N(20), P("multiplier", 2, 0.1, 10, kind="float")], VALUE, "panel", ref_lines=(0, 1))
_ind("bollinger_width", "Bollinger Band Width", VOLAT, volatility.bollinger_width, ["close"],
     [N(20), P("multiplier", 2, 0.1, 10, kind="float")], VALUE, "panel")
_ind("keltner", "Keltner Channels", VOLAT, volatility.keltner, HLC,
     [P("ema_period", 20, label="EMA period"), P("multiplier", 2, 0.1, 10, kind="float"),
      P("atr_period", 10, label="ATR period")], _BANDS, "overlay")
_ind("donchian", "Donchian / Price Channel", VOLAT, volatility.donchian, ["high", "low"], [N(20)], _BANDS, "overlay")
_ind("envelopes", "Envelopes", VOLAT, volatility.envelopes, ["close"],
     [N(20), P("percent", 5, 0.1, 50, kind="float")], _BANDS, "overlay")
_ind("std_dev", "Standard Deviation", VOLAT, volatility.std_dev, ["close"], [N(20)], VALUE, "panel")
_ind("std_error", "Standard Error", VOLAT, volatility.standard_error, ["close"], [N(20, minimum=3)], VALUE, "panel")
_ind("std_error_bands", "Standard Error Bands", VOLAT, volatility.standard_error_bands, ["close"],
     [N(21, minimum=3), P("multiplier", 2, 0.1, 10, kind="float")], _BANDS, "overlay")
_ind("chaikin_volatility", "Chaikin Volatility", VOLAT, volatility.chaikin_volatility, ["high", "low"],
     [P("ema_period", 10, label="EMA period"), P("roc_period", 10, label="ROC period")], VALUE, "panel",
     ref_lines=(0,))
_TD = P("trading_days", 240, 1, 366, label="Trading days / year")
_ind("hist_vol", "Historical Volatility (close-to-close)", VOLAT, volatility.historical_volatility, ["close"],
     [N(20, minimum=2), _TD], VALUE, "panel", notes="Annualised, as a fraction (0.25 = 25%).")
_ind("zero_trend_vol", "Zero Trend Close-to-Close Volatility", VOLAT, volatility.zero_trend_volatility, ["close"],
     [N(20), _TD], VALUE, "panel")
_ind("garman_klass", "Volatility O-H-L-C (Garman-Klass)", VOLAT, volatility.garman_klass, OHLC, [N(20), _TD], VALUE,
     "panel")
_ind("rvi_volatility", "Relative Volatility Index", VOLAT, volatility.relative_volatility_index, ["close"],
     [P("std_period", 10, label="Stdev period"), P("smooth_period", 14, label="EMA period")], VALUE, "panel",
     ref_lines=(50,), value_range=(0, 100))

# ── Volume ─────────────────────────────────────────────────────────────────────────────
_ind("volume", "Volume", VOL, volume.volume_bars, ["open", "close", "volume"], [],
     [O("volume", "Volume", "bar")], "panel", color_by="direction")
_ind("volume_oscillator", "Volume Oscillator", VOL, volume.volume_oscillator, ["volume"],
     [P("fast", 5), P("slow", 10)], VALUE, "panel", ref_lines=(0,))
_ind("obv", "On Balance Volume", VOL, volume.obv, ["close", "volume"], [], VALUE, "panel")
_ind("net_volume", "Net Volume", VOL, volume.net_volume, ["close", "volume"], [], [O("value", "Net volume", "bar")],
     "panel", ref_lines=(0,))
_ind("ad", "Accumulation / Distribution", VOL, volume.accumulation_distribution, HLCV, [], VALUE, "panel")
_ind("cmf", "Chaikin Money Flow", VOL, volume.chaikin_money_flow, HLCV, [N(20)], VALUE, "panel", ref_lines=(0,))
_ind("chaikin_osc", "Chaikin Oscillator", VOL, volume.chaikin_oscillator, HLCV, [P("fast", 3), P("slow", 10)], VALUE,
     "panel", ref_lines=(0,))
_ind("mfi", "Money Flow Index", VOL, volume.money_flow_index, HLCV, [N(14)], VALUE, "panel", ref_lines=(20, 80),
     value_range=(0, 100))
_ind("eom", "Ease of Movement", VOL, volume.ease_of_movement, ["high", "low", "volume"],
     [N(14), P("scale", 10000, 1, 1e9, label="Volume scale")], VALUE, "panel", ref_lines=(0,))
_ind("force_index", "Elder's Force Index", VOL, volume.force_index, ["close", "volume"], [N(13)], VALUE, "panel",
     ref_lines=(0,))
_ind("klinger", "Klinger Oscillator", VOL, volume.klinger, HLCV, [P("fast", 34), P("slow", 55), P("signal", 13)],
     [O("ko", "KO"), O("signal")], "panel", ref_lines=(0,))
_ind("pvt", "Price Volume Trend", VOL, volume.price_volume_trend, ["close", "volume"], [], VALUE, "panel")
_ind("vwap", "VWAP (anchored to range start)", VOL, volume.vwap_anchored, HLCV, [], VALUE, "overlay", scope="range",
     notes="Daily data only, so it is anchored at the first bar of the selected range rather than reset daily.")
_ind("vwap_rolling", "VWAP (rolling)", VOL, volume.vwap_rolling, HLCV, [N(20)], VALUE, "overlay")
_ind("volume_profile", "Volume Profile (visible range)", VOL, volume.volume_profile, ["high", "low", "volume"],
     [P("rows", 24, 2, 200), P("value_area", 70, 1, 100, kind="float", label="Value area %")],
     [O("poc", "POC"), O("vah", "VA high"), O("val", "VA low")], "overlay", scope="range",
     notes="Built from daily bars; most accurate with intraday data.")

# ── Price and levels ───────────────────────────────────────────────────────────────────
_ind("avg_price", "Average Price (OHLC/4)", PRICE, price.average_price, OHLC, [], VALUE, "overlay")
_ind("median_price", "Median Price (HL/2)", PRICE, price.median_price, ["high", "low"], [], VALUE, "overlay")
_ind("typical_price", "Typical Price (HLC/3)", PRICE, price.typical_price, HLC, [], VALUE, "overlay")
_ind("pivots", "Pivot Points Standard", PRICE, price.pivot_points, ("high", "low", "close", "date"),
     [P("timeframe", "W", kind="choice", choices=("D", "W", "M"), label="From previous")],
     [O(k, k.upper()) for k in ("p", "r1", "s1", "r2", "s2", "r3", "s3")], "overlay")
_ind("week52", "52 Week High/Low", PRICE, price.week_52_high_low, ("high", "low", "date"),
     [P("weeks", 52, 1, 260)], [O("high", "52W high"), O("low", "52W low")], "overlay")
_ind("fractals", "Williams Fractal", PRICE, price.fractals, ["high", "low"], [P("wing", 2, 1, 10, label="Bars each side")],
     [O("up", "High fractal", "dot"), O("down", "Low fractal", "dot")], "overlay",
     notes="A fractal is confirmed only after the later bars close.")

# ── Market-wide and relative (need other stocks / a benchmark / floorsheet) ────────────
_BENCH_NOTE = ("Benchmark: the project's turnover-weighted market proxy (not the official NEPSE index), "
               "or another company if one is chosen.")
_ind("advance_decline", "Advance / Decline", MARKET, market.advance_decline, ("universe", "date"), [],
     [O("net", "Advances - declines", "bar"), O("line", "A/D line")], "panel", scope="market")
_ind("ad_volume", "AD Volume Line", MARKET, market.ad_volume_line, ("universe", "date"), [], VALUE, "panel",
     scope="market")
_ind("pct_above_ma", "% of Stocks above MA", MARKET, market.percent_above_ma, ("universe", "date"),
     [P("fast", 20), P("medium", 50), P("slow", 200)],
     [O("above_fast", "Above fast MA"), O("above_medium", "Above medium MA"), O("above_slow", "Above slow MA")],
     "panel", value_range=(0, 100), scope="market")
_ind("net_highs_lows", "Net New 52W Highs - Lows", MARKET, market.net_new_highs_lows, ("universe", "date"),
     [P("weeks", 52, 1, 260)], [O("value", "Net highs - lows", "bar")], "panel", ref_lines=(0,), scope="market")
_ind("ratio", "Ratio (stock / benchmark)", MARKET, market.ratio, ("close", "benchmark"), [], VALUE, "panel",
     scope="benchmark", notes=_BENCH_NOTE)
_ind("spread", "Spread (stock - benchmark)", MARKET, market.spread, ("close", "benchmark"), [], VALUE, "panel",
     ref_lines=(0,), scope="benchmark", notes=_BENCH_NOTE)
_ind("relative_strength", "Relative Strength", MARKET, market.relative_strength, ("close", "benchmark"), [], VALUE,
     "panel", scope="benchmark", notes=_BENCH_NOTE)
_ind("mansfield_rs", "Mansfield Relative Strength", MARKET, market.mansfield_rs, ("close", "benchmark"), [N(200)],
     VALUE, "panel", ref_lines=(0,), scope="benchmark", notes=_BENCH_NOTE)
_ind("correlation", "Correlation Coefficient", MARKET, market.correlation, ("close", "benchmark"),
     [N(20, minimum=2)], VALUE, "panel", ref_lines=(0,), value_range=(-1, 1), scope="benchmark", notes=_BENCH_NOTE)
_ind("log_correlation", "Correlation - Log", MARKET, market.log_correlation, ("close", "benchmark"),
     [N(20, minimum=2)], VALUE, "panel", ref_lines=(0,), value_range=(-1, 1), scope="benchmark", notes=_BENCH_NOTE)
_ind("tick_volume", "Buy / Sell Volume (tick rule)", MARKET, market.tick_buy_sell, ("trades", "date"), [],
     [O("buy", "Buy volume", "bar"), O("sell", "Sell volume", "bar")], "panel", scope="floorsheet",
     notes="From floorsheet trades ordered by contract number (the floorsheet has no trade times).")

# ── Standard versions of NepseAlpha custom ideas ───────────────────────────────────────
_ind("inside_bar", "Inside Bar", STANDARD, custom.inside_bar, ["high", "low"], [], [O("value", "Inside bar", "dot")],
     "overlay")
_ind("ut_bot", "UT Bot (standard version)", STANDARD, custom.ut_bot, HLC,
     [P("key", 1, 0.1, 20, kind="float", label="Key value"), P("atr_period", 10, label="ATR period")],
     [O("stop", "Trailing stop"), O("buy", "Buy", "dot"), O("sell", "Sell", "dot")], "overlay")
_ind("zero_lag_macd", "Zero Lag MACD (standard version)", STANDARD, custom.zero_lag_macd, ["close"],
     [P("fast", 12), P("slow", 26), P("signal", 9)],
     [O("macd", "MACD"), O("signal"), O("histogram", kind="bar")], "panel", ref_lines=(0,))
_ind("tdi", "Traders Dynamic Index (standard version)", STANDARD, custom.tdi, ["close"],
     [P("rsi_period", 13, label="RSI period"), P("price_period", 2, label="Price line"),
      P("signal_period", 7, label="Signal line"), P("base_period", 34, label="Base line"),
      P("band_multiplier", 1.6185, 0.1, 10, kind="float", label="Band multiplier")],
     [O("price"), O("signal"), O("base"), O("upper"), O("lower")], "panel", ref_lines=(32, 50, 68),
     value_range=(0, 100))
_ind("weinstein", "Weinstein Stage (standard version)", STANDARD, custom.weinstein_stage, ["close"],
     [P("ma_period", 150, label="MA period (bars, ~30 weeks)"), P("slope_period", 5, label="Slope lookback"),
      P("flat_pct", 0.5, 0, 10, kind="float", label="Flat slope %")], [O("value", "Stage")], "panel",
     ref_lines=(1, 2, 3, 4), value_range=(0.5, 4.5))

NOT_IMPLEMENTED = [
    {"name": name, "reason": "Not implemented - definition unknown (NepseAlpha has not published it)."}
    for name in ("Everest Cloud Zone", "Himalyan ROC Trail Candles", "HMA Bajaar Suchak", "RSI Candles PSAR Signals",
                 "Swing Candles", "Chop Zone", "Majority Rule", "Volatility Index")
]


def resolve_params(indicator, raw):
    """Defaults overlaid with ``raw``; raises ValueError for unknown names or out-of-range values."""
    raw = dict(raw or {})
    known = {p.name: p for p in indicator.params}
    unknown = set(raw) - set(known)
    if unknown:
        raise ValueError(f"Unknown parameter(s) for {indicator.id}: {', '.join(sorted(unknown))}")
    values = {}
    for name, param in known.items():
        value = raw.get(name, param.default)
        if param.kind == "choice":
            if value not in param.choices:
                raise ValueError(f"{name} must be one of {', '.join(param.choices)}")
        else:
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{name} must be a number") from None
            if param.kind == "int":
                if value != int(value):
                    raise ValueError(f"{name} must be a whole number")
                value = int(value)
            if not param.minimum <= value <= param.maximum:
                raise ValueError(f"{name} must be between {param.minimum:g} and {param.maximum:g}")
        values[name] = value
    return values


def compute(indicator_id, data, raw_params=None):
    """Run one indicator. ``data`` maps input names to lists. Returns {"params", "outputs", "extra"}."""
    indicator = REGISTRY[indicator_id]
    params = resolve_params(indicator, raw_params)
    result = indicator.fn(*(data[name] for name in indicator.inputs), **params)
    if isinstance(result, list):
        result = {indicator.outputs[0].key: result}
    extra = result.pop("extra", {}) if isinstance(result, dict) else {}
    return {"params": params, "outputs": result, "extra": extra}


def registry_payload():
    return {
        "indicators": [
            {
                "id": ind.id, "name": ind.name, "category": ind.category, "inputs": list(ind.inputs),
                "params": [
                    {"name": p.name, "label": p.label, "default": p.default, "min": p.minimum, "max": p.maximum,
                     "kind": p.kind, "choices": list(p.choices)}
                    for p in ind.params
                ],
                "outputs": [{"key": o.key, "label": o.label, "kind": o.kind} for o in ind.outputs],
                "display": ind.display, "ref_lines": list(ind.ref_lines), "value_range": list(ind.value_range),
                "fill": list(ind.fill), "color_by": ind.color_by, "scope": ind.scope, "notes": ind.notes,
            }
            for ind in REGISTRY.values()
        ],
        "not_implemented": NOT_IMPLEMENTED,
    }
