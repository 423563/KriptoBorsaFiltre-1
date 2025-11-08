# signal_engine.py
# Kuralları (rules.py) okuyup, veriyle karşılaştıran ve sinyal üreten temel motor

import importlib
from typing import List, Dict, Any

# Kural dosyasını dinamik olarak yükle
rules_module = importlib.import_module("rules")
RULES = rules_module.RULES

# Örnek veri formatı (gerçek veriyle değiştirilebilir)
example_data = {
    "BTCUSDT": {
        "5m": {"MA": 50000, "RSI": 65},
        "15m": {"MA": 50200, "RSI": 72},
    },
    "ETHUSDT": {
        "5m": {"MA": 3500, "RSI": 55},
        "15m": {"MA": 3550, "RSI": 68},
    },
    # ...
}

def evaluate_rule(_symbol: str, tf_data: Dict[str, Dict[str, Any]], rule: Dict[str, Any]) -> bool:
    """
    Bir sembol ve zaman dilimi verisi için verilen kuralı değerlendirir.
    """
    tfs = rule["timeframes"]
    indicator = rule["indicator"]
    condition = rule["condition"]
    # Basit örnek: MA up/down cross
    if indicator == "MA":
        if all(tf in tf_data for tf in tfs):
            ma1 = tf_data[tfs[0]]["MA"]
            ma2 = tf_data[tfs[1]]["MA"]
            if condition == "down_cross":
                return ma1 < ma2
            elif condition == "up_cross":
                return ma1 > ma2
    elif indicator == "RSI":
        tf = tfs[0]
        if tf in tf_data:
            rsi = tf_data[tf]["RSI"]
            if condition == "over":
                return rsi > rule.get("value", 70)
            elif condition == "under":
                return rsi < rule.get("value", 30)
    # Diğer indikatör ve koşullar için buraya ekleme yapılabilir
    return False

def scan_signals(data: Dict[str, Dict[str, Dict[str, Any]]], rules: List[Dict[str, Any]]):
    """
    Tüm semboller ve kurallar üzerinde sinyal taraması yapar.
    """
    results = []
    for symbol, tf_data in data.items():
        for rule in rules:
            if evaluate_rule(symbol, tf_data, rule):
                results.append({
                    "symbol": symbol,
                    "rule": rule["name"],
                    "description": rule.get("description", "")
                })
    return results

if __name__ == "__main__":
    signals = scan_signals(example_data, RULES)
    print("Sinyal Alanlar:")
    for s in signals:
        print(f"{s['symbol']}: {s['rule']} - {s['description']}")
