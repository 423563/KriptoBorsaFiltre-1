import threading
import time
from collections import defaultdict

# Her zaman dilimi için güncelleme aralığı (saniye)
TF_UPDATE_INTERVALS = {
    '1m': 2,
    '3m': 2,
    '5m': 10,
    '15m': 10,
    '1h': 10,
    '4h': 10,
    '6h': 10,
    '1d': 20,
    '1w': 20,
    '1M': 20,
}

class SignalBackgroundWorker:
    """
    Her coin ve zaman dilimi için arka planda veri çekip cache'e yazar.
    WebSocket ile anlık veri için ayrı bir yapı eklenebilir. Şimdilik REST ile BB sinyali.
    """
    def __init__(self, coin_symbols, timeframes, signal_func):
        self.coin_symbols = coin_symbols
        self.timeframes = timeframes  # örn. [('M1', '1m'), ...]
        self.signal_func = signal_func  # signal_calculator.fetch_bollinger_signal
        self.cache = defaultdict(lambda: defaultdict(lambda: 'neutral'))
        self._stop_event = threading.Event()
        self._threads = []

    def start(self):
        for tf_name, tf_binance in self.timeframes:
            t = threading.Thread(target=self._worker, args=(tf_name, tf_binance), daemon=True)
            t.start()
            self._threads.append(t)
            # Küçük bir gecikme ile başlat (yükü dağıtmak için)
            try:
                time.sleep(0.2)
            except Exception:
                pass

    def stop(self):
        self._stop_event.set()

    def _worker(self, tf_name, tf_binance):
        interval = TF_UPDATE_INTERVALS.get(tf_binance, 5)
        while not self._stop_event.is_set():
            for symbol in self.coin_symbols:
                sig = self.signal_func(symbol, tf_binance, tf_name)
                self.cache[symbol][tf_name] = sig
            time.sleep(interval)

    def get_signal(self, symbol, tf_name):
        return self.cache[symbol][tf_name]
