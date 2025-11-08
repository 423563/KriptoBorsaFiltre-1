import requests
from bb_config import get_tf_bb_setting

def fetch_bollinger_signal(symbol, interval, tf):
    """
    Binance'den son kapanış fiyatlarını çekip BB sinyali döndürür. Ayarları bb_config'tan okur.
    """
    try:
        bb_settings = get_tf_bb_setting(tf)
        period = bb_settings.get('period', 20)
        stddev = bb_settings.get('stddev', 2.0)
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={period+1}"
        resp = requests.get(url, timeout=8)
        data = resp.json()
        closes = []
        for c in data:
            try:
                if len(c) >= 5:
                    closes.append(float(c[4]))
            except (IndexError, ValueError, TypeError):
                continue
        if len(closes) < period:
            return 'neutral'
        ma = sum(closes[-period:]) / period
        std = (sum((x - ma)**2 for x in closes[-period:]) / period) ** 0.5
        upper = ma + stddev * std
        lower = ma - stddev * std
        last = closes[-1]
        if last > upper:
            return 'up'
        elif last < lower:
            return 'down'
        elif last > ma:
            return 'up'
        elif last < ma:
            return 'down'
        else:
            return 'neutral'
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
        print(f"[ERROR] fetch_bollinger_signal: {e}")
        return 'neutral'

def fetch_supertrend_signal(symbol, interval, tf, atr_period=10, multiplier=3.0, source='hl2'):
    """
    Supertrend yönü: 'up' veya 'down'
    - ATR: RMA tabanlı
    - Kaynak: 'hl2' ( (high+low)/2 ) veya 'close'
    """
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={max(atr_period*3, 60)}"
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if not isinstance(data, list) or len(data) < atr_period + 2:
            return 'neutral'
        highs, lows, closes = [], [], []
        for c in data:
            try:
                highs.append(float(c[2]))
                lows.append(float(c[3]))
                closes.append(float(c[4]))
            except (IndexError, ValueError, TypeError):
                return 'neutral'
        # Kaynak seri
        if source == 'close':
            src = closes
        else:
            src = [(h + l) / 2.0 for h, l in zip(highs, lows)]
        # True Range ve ATR (RMA)
        tr = []
        for i in range(len(closes)):
            if i == 0:
                tr.append(highs[i] - lows[i])
            else:
                tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
        atr = [0.0] * len(tr)
        # RMA başlangıç: ilk atr_period değerinin SMA'sı
        seed = sum(tr[:atr_period]) / atr_period
        atr[atr_period-1] = seed
        alpha = 1.0 / atr_period
        for i in range(atr_period, len(tr)):
            atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
        # Üst/alt bandlar ve trend
        up = [None] * len(src)
        dn = [None] * len(src)
        trend = [0] * len(src)
        for i in range(len(src)):
            if i < atr_period-1:
                continue
            up[i] = src[i] + multiplier * atr[i]
            dn[i] = src[i] - multiplier * atr[i]
            if i == atr_period-1:
                trend[i] = 1 if closes[i] > dn[i] else -1
                continue
            # Bandların devamlılığı (Pine mantığına yakınlaştırma)
            up[i] = min(up[i], up[i-1] if up[i-1] is not None else up[i])
            dn[i] = max(dn[i], dn[i-1] if dn[i-1] is not None else dn[i])
            if trend[i-1] == -1 and closes[i] > up[i]:
                trend[i] = 1
            elif trend[i-1] == 1 and closes[i] < dn[i]:
                trend[i] = -1
            else:
                trend[i] = trend[i-1]
        last_trend = trend[-1] if trend[-1] != 0 else trend[-2]
        return 'up' if last_trend == 1 else 'down'
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
        print(f"[ERROR] fetch_supertrend_signal: {e}")
        return 'neutral'

# --- TEST KODU ---
if __name__ == "__main__":
    test_symbol = "BTCUSDT"
    test_interval = "1h"
    test_tf = "H1"
    print("BB:", fetch_bollinger_signal(test_symbol, test_interval, test_tf))
    print("ST:", fetch_supertrend_signal(test_symbol, test_interval, test_tf))
