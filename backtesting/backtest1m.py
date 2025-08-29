import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

# Load data (1-minute OHLCV; change filename accordingly)
df = pd.read_csv("btc_1m_merged.csv")
df['datetime'] = pd.to_datetime(df['datetime'])
for col in ['quote_asset_volume', 'taker_buy_quote_vol', 'high', 'low', 'open', 'close']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df.dropna(inplace=True)

highs = df['high'].values
lows = df['low'].values
closes = df['close'].values
opens = df['open'].values
quotes = df['quote_asset_volume'].values
datetimes = df['datetime'].values
ratios = df['quote_asset_volume'].rolling(window=20).mean().values / quotes

# Parameters
initial_balance = 100.0
leverage = 35
fee_rate = 0.0004

results = []
balance = initial_balance
daily_trade_counts = {}
last_exit_index = -10
n = len(df)

for i in range(26, n - 28):
    if balance < 1:
        break
    if ratios[i] < 1.0 or i - last_exit_index <= 3:
        continue

    trend = closes[i-3:i]
    if not ((trend[2] > trend[1] > trend[0]) or (trend[2] < trend[1] < trend[0])):
        continue

    box_high = max(highs[i - 5:i])
    box_low = min(lows[i - 5:i])
    box_width = box_high - box_low
    avg_range = sum(highs[i - 20:i] - lows[i - 20:i]) / 20
    if box_width >= avg_range * 0.8:
        continue

    body = closes[i] - opens[i]
    full_range = highs[i] - lows[i]
    if full_range == 0 or abs(body / full_range) < 0.5:
        continue
    if abs(closes[i] - opens[i]) < full_range * 0.1:
        continue

    vol = quotes[i]
    prev_vol = quotes[i - 1]
    if prev_vol == 0 or vol / prev_vol < 1.5:
        continue

    center_price = (highs[i] + lows[i]) / 2
    if abs(closes[i] - center_price) / closes[i] > 0.025:
        continue

    entry_type = None
    entry_price = closes[i]
    entry_time = datetimes[i]
    entry_day = pd.to_datetime(entry_time).date()

    if closes[i] > box_high and body > 0:
        if max(highs[i+1:i+4]) < entry_price * 1.001:
            continue
        entry_type = 'LONG'
        tp = entry_price * 1.005  # 0.5% target
        sl = entry_price * 0.997  # -0.3% stop
    elif closes[i] < box_low and body < 0:
        if min(lows[i+1:i+4]) > entry_price * 0.999:
            continue
        entry_type = 'SHORT'
        tp = entry_price * 0.995
        sl = entry_price * 1.003

    if entry_type:
        for j in range(1, 30):  # monitor up to 30 minutes
            if i + j >= len(df):
                break
            high = highs[i + j]
            low = lows[i + j]
            exit_time = datetimes[i + j]

            if entry_type == 'LONG':
                if low <= sl:
                    exit_price = sl
                    result = 'STOPLOSS'
                    break
                elif high >= tp:
                    exit_price = tp
                    result = 'TAKEPROFIT'
                    break
            elif entry_type == 'SHORT':
                if high >= sl:
                    exit_price = sl
                    result = 'STOPLOSS'
                    break
                elif low <= tp:
                    exit_price = tp
                    result = 'TAKEPROFIT'
                    break
        else:
            continue

        last_exit_index = i + j
        trade_num = daily_trade_counts.get(entry_day, 0) + 1
        daily_trade_counts[entry_day] = trade_num
        trade_label = f'{entry_day} Trade{trade_num}'

        pnl = (exit_price - entry_price) / entry_price if entry_type == 'LONG' else (entry_price - exit_price) / entry_price
        trade_size = balance * leverage
        fee = trade_size * fee_rate * 2
        profit = trade_size * pnl
        net = profit - fee
        balance += net

        results.append({
            'TradeID': trade_label,
            'EntryTime': entry_time,
            'ExitTime': exit_time,
            'Side': entry_type,
            'EntryPrice': round(entry_price, 2),
            'ExitPrice': round(exit_price, 2),
            'Result': result,
            'PnL(%)': round(pnl * 100, 2),
            'PnL($)': round(net, 2),
            'Balance': round(balance, 2)
        })

# Results DataFrame
result_df = pd.DataFrame(results)

# 📊 Equity curve (with improved hover info)
pio.renderers.default = 'browser'
fig = go.Figure()

# Balance line
fig.add_trace(go.Scatter(
    x=result_df['EntryTime'],
    y=result_df['Balance'],
    mode='lines',
    name='Balance',
    line=dict(width=2, color='blue')
))

# Entry/exit markers with hover only
for idx, row in result_df.iterrows():
    color = 'green' if row['Result'] == 'TAKEPROFIT' else 'red'
    fig.add_trace(go.Scatter(
        x=[row['EntryTime']],
        y=[row['Balance']],
        mode='markers',
        marker=dict(color=color, size=8),
        hovertext=(
            f"{row['TradeID']} | {row['Side']} {row['Result']}<br>"
            f"Entry: {row['EntryPrice']} / Exit: {row['ExitPrice']}<br>"
            f"P/L: {row['PnL(%)']}% ({row['PnL($)']} $)<br>"
            f"Balance: {row['Balance']} $"
        ),
        hoverinfo="text",
        name=row['Result'],
        showlegend=(idx == 0 or (idx == 1 and row['Result'] == 'STOPLOSS'))
    ))

fig.update_layout(
    title='💰 Strategy Equity Curve (1m)',
    xaxis_title='Time',
    yaxis_title='Balance ($)',
    height=600,
    template='plotly_white'
)

fig.show()

# 📋 Performance summary
print(result_df)
print(f"\n📈 Total trades: {len(result_df)}")
print(f"✅ Win rate: {(result_df['Result'] == 'TAKEPROFIT').mean() * 100:.2f}%")
print(f"💰 Final balance: ${balance:.2f}")
