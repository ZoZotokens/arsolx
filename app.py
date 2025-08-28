import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import ccxt
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator

app = Flask(__name__)
CORS(app)

def analyze(symbol, timeframe, limit):
    exchange = ccxt.kucoin()  # تغییر به KuCoin
    if "/" not in symbol and symbol.endswith("USDT"):
        symbol = symbol[:-4] + "/USDT"
    elif "/" not in symbol and len(symbol) > 3:
        symbol = symbol[:3] + "/" + symbol[3:]
    
    ohlcv = exchange.fetch_ohlcv(symbol.upper(), timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    close = df['close']
    ema20 = EMAIndicator(close, window=20).ema_indicator()
    ema50 = EMAIndicator(close, window=50).ema_indicator()
    rsi = RSIIndicator(close, window=14).rsi()
    macd = MACD(close)
    macd_line = macd.macd()
    macd_signal = macd.macd_signal()

    first_price = close.iloc[0]
    last_price = close.iloc[-1]
    pct_change = (last_price - first_price) / first_price if first_price != 0 else 0
    linear_vote = 0
    linear_threshold = 0.002
    if pct_change > linear_threshold:
        linear_vote = 1
    elif pct_change < -linear_threshold:
        linear_vote = -1

    ma_vote = 0
    if ema20.iloc[-1] > ema50.iloc[-1]:
        ma_vote = 1
    elif ema20.iloc[-1] < ema50.iloc[-1]:
        ma_vote = -1

    lookback_for_slope = min(5, len(ema20)-1)
    slope_vote = 0
    if lookback_for_slope >= 1:
        slope = ema20.iloc[-1] - ema20.iloc[-1 - lookback_for_slope]
        if slope > 0:
            slope_vote = 1
        elif slope < 0:
            slope_vote = -1

    score = (linear_vote * 0.3) + (ma_vote * 0.4) + (slope_vote * 0.3)

    final_trend = "نامشخص"
    if score > 0.1:
        final_trend = "صعودی"
    elif score < -0.1:
        final_trend = "نزولی"
    else:
        final_trend = "خنثی"

    rsi_val = rsi.iloc[-1]
    macd_diff = macd_line.iloc[-1] - macd_signal.iloc[-1]

    strength = ""
    if final_trend == "صعودی":
        if rsi_val > 60 and macd_diff > 0:
            strength = " قوی"
        elif 50 < rsi_val <= 60:
            strength = " ضعیف"
    elif final_trend == "نزولی":
        if rsi_val < 40 and macd_diff < 0:
            strength = " قوی"
        elif 40 <= rsi_val < 50:
            strength = " ضعیف"

    tail_n = min(30, len(df))
    resistance = round(df['high'].tail(tail_n).max(), 8)
    support = round(df['low'].tail(tail_n).min(), 8)
    timestamp = df['timestamp'].iloc[-1]
    last_price_rounded = round(last_price, 8)

    return {
        "final_trend": final_trend + strength,
        "resistance": resistance,
        "support": support,
        "rsi": round(rsi_val, 2),
        "macd": round(macd_line.iloc[-1], 6),
        "macd_signal": round(macd_signal.iloc[-1], 6),
        "last_price": last_price_rounded,
        "timestamp": timestamp.strftime('%Y-%m-%d %H:%M'),
        "votes": {
            "linear_vote": linear_vote,
            "ma_vote": ma_vote,
            "slope_vote": slope_vote,
            "score": round(score, 3)
        }
    }

@app.route('/analyze', methods=['POST'])
def analyze_route():
    data = request.get_json()
    symbol = data.get('symbol')
    timeframe = data.get('timeframe')
    limit = int(data.get('limit', 100))
    result = analyze(symbol, timeframe, limit)
    return jsonify({'result': result})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

