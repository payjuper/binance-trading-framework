import os
import time
import math
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import *

# ========= USER CONFIG =========
SYMBOL        = "BTCUSDT"            # USDT market is the most stable. Use "BTCUSDC" if supported.
INTERVAL      = Client.KLINE_INTERVAL_1MINUTE
LOOKBACK      = 140                  # lookback window (minutes)
THRESHOLD     = 0.04                 # enter long if current price dropped >= 4% from recent high
TP_RATIO      = 0.008                # +0.8% take profit
SL_RATIO      = 0.003                # -0.3% stop loss
LEVERAGE      = 50
MARGIN_TYPE   = "ISOLATED"           # "CROSSED" or "ISOLATED"
RISK_PCT      = 0.95                 # use 95% of available balance
POLL_SEC      = 10                   # loop polling interval (seconds)

# ✅ logging interval (print balance & drop ratio)
LOG_INTERVAL  = 60 * 60              # print once per hour (set to 300 for 5 min, 60 for 1 min, etc.)

TESTNET       = False                # True if using Binance Futures testnet
# =================================

load_dotenv()
API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")
if not API_KEY or not API_SECRET:
    raise RuntimeError("Missing API keys in .env file (BINANCE_API_KEY / BINANCE_SECRET_KEY)")

client = Client(API_KEY, API_SECRET, testnet=TESTNET)
if TESTNET:
    client.FUTURES_URL = "https://testnet.binancefuture.com/fapi/v1"

def now_str():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

def ensure_symbol_exists(symbol):
    info = client.futures_exchange_info()
    syms = {s["symbol"] for s in info["symbols"]}
    if symbol not in syms:
        raise RuntimeError(
            f"[CONFIG] Futures symbol '{symbol}' not found. "
            f"Use 'BTCUSDT' or check if your account/endpoint supports {symbol}."
        )

def get_symbol_filters(symbol):
    info = client.futures_exchange_info()
    for s in info["symbols"]:
        if s["symbol"] == symbol:
            lot = next(f for f in s["filters"] if f["filterType"] == "LOT_SIZE")
            price = next(f for f in s["filters"] if f["filterType"] == "PRICE_FILTER")
            return float(lot["stepSize"]), float(lot["minQty"]), float(price["tickSize"])
    raise RuntimeError(f"[CONFIG] No filters for {symbol}. (Unsupported symbol)")

def round_step(qty, step):
    return math.floor(qty / step) * step

def get_quote_asset(symbol):
    # BTCUSDT -> USDT / BTCUSDC -> USDC
    if symbol.endswith("USDT"): return "USDT"
    if symbol.endswith("USDC"): return "USDC"
    return "USDT"

def get_available_quote_balance(asset):
    bals = client.futures_account_balance()
    for b in bals:
        if b["asset"] == asset:
            return float(b["availableBalance"])
    return 0.0

def ensure_leverage_and_margin(symbol):
    try:
        client.futures_change_margin_type(symbol=symbol, marginType=MARGIN_TYPE)
    except Exception:
        pass  # already set
    client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)

def current_position_size(symbol):
    pos = client.futures_position_information(symbol=symbol)
    if not pos:
        return 0.0, 0.0
    amt = float(pos[0].get("positionAmt", 0) or 0)
    entry = float(pos[0].get("entryPrice", 0) or 0)
    return amt, entry  # >0: long, 0: flat

def cancel_all_open_orders(symbol):
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
    except Exception as e:
        print("[WARN] Failed to cancel open orders:", e)

def get_klines(symbol, interval, limit):
    kl = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    cols = ["open_time","open","high","low","close","volume","close_time",
            "quote_asset_volume","trades","taker_buy_base","taker_buy_quote","ignore"]
    df = pd.DataFrame(kl, columns=cols)
    df["high"] = df["high"].astype(float)
    df["close"] = df["close"].astype(float)
    return df

def place_long_market_with_brackets(symbol, qty, entry_price):
    # enter long
    client.futures_create_order(
        symbol=symbol,
        side=SIDE_BUY,
        type=ORDER_TYPE_MARKET,
        quantity=qty
    )
    # TP/SL orders (close entire position when triggered)
    tp_price = round(entry_price * (1 + TP_RATIO), 2)
    sl_price = round(entry_price * (1 - SL_RATIO), 2)

    client.futures_create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
        stopPrice=tp_price,
        closePosition=True,
        reduceOnly=True,
        timeInForce=TIME_IN_FORCE_GTC
    )
    client.futures_create_order(
        symbol=symbol,
        side=SIDE_SELL,
        type=FUTURE_ORDER_TYPE_STOP_MARKET,
        stopPrice=sl_price,
        closePosition=True,
        reduceOnly=True,
        timeInForce=TIME_IN_FORCE_GTC
    )
    return tp_price, sl_price

def main():
    quote_asset = get_quote_asset(SYMBOL)
    print(f"[START] {SYMBOL} trading bot (LONG) | leverage={LEVERAGE}x | margin={MARGIN_TYPE} | testnet={TESTNET}")

    # sanity checks
    ensure_symbol_exists(SYMBOL)
    step, min_qty, tick = get_symbol_filters(SYMBOL)
    ensure_leverage_and_margin(SYMBOL)

    last_log_ts = 0.0
    in_position_prev = False

    while True:
        try:
            df = get_klines(SYMBOL, INTERVAL, LOOKBACK)
            last = df["close"].iloc[-1]
            recent_high = df["high"].max()
            drop = (recent_high - last) / recent_high if recent_high > 0 else 0.0

            # position and balance
            pos_size, entry_price = current_position_size(SYMBOL)
            in_position = abs(pos_size) > 0
            avail_quote = get_available_quote_balance(quote_asset)

            # periodic log
            now_ts = time.time()
            if now_ts - last_log_ts >= LOG_INTERVAL:
                print(f"[{now_str()}] ✅ Bot running | drop: {drop*100:.2f}% | balance({quote_asset}): {avail_quote:.2f}")
                last_log_ts = now_ts

            # entry condition
            if not in_position and drop >= THRESHOLD:
                if avail_quote <= 0:
                    print(f"[{now_str()}] [SKIP] No {quote_asset} balance available.")
                else:
                    notional = avail_quote * RISK_PCT * LEVERAGE
                    raw_qty = notional / last
                    qty = round_step(raw_qty, step)
                    if qty < min_qty:
                        print(f"[{now_str()}] [SKIP] qty<{min_qty}. qty={qty}")
                    else:
                        print(f"[{now_str()}] [ENTRY] LONG {SYMBOL} qty={qty}, price~{last:.2f}, drop={drop*100:.2f}%")
                        tp, sl = place_long_market_with_brackets(SYMBOL, qty, last)
                        print(f"[{now_str()}] [BRACKETS] TP={tp}, SL={sl}")

            # detect flat (position closed) -> cancel leftover orders
            if in_position_prev and not in_position:
                print(f"[{now_str()}] [FLAT] Position closed → cancel leftover orders.")
                cancel_all_open_orders(SYMBOL)

            in_position_prev = in_position

        except Exception as e:
            print(f"[{now_str()}] [ERROR] {e}")

        time.sleep(POLL_SEC)

if __name__ == "__main__":
    main()
