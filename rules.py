# rules.py
# Kullanıcı tarafından kolayca değiştirilebilen, kural tabanlı sinyal sistemi için şablon

# Kural örnekleri:
# Her kural bir sözlük (dict) olarak tanımlanır.
# "timeframes": Hangi zaman dilimleri birlikte kontrol edilecek
# "indicator": Kullanılacak indikatör (örn. MA, EMA, RSI)
# "condition": Koşul (örn. 'down_cross', 'up_cross', 'over', 'under')
# "value": (opsiyonel) Eşik değer (örn. RSI için 70 veya 30)

RULES = [
    {
        "name": "MA 5-15 Down Cross",
        "timeframes": ["5m", "15m"],
        "indicator": "MA",
        "condition": "down_cross",
        "description": "5 ve 15 dakikalık MA'da aşağı kesişme olursa sinyal üret."
    },
    {
        "name": "MA 5-15 Up Cross",
        "timeframes": ["5m", "15m"],
        "indicator": "MA",
        "condition": "up_cross",
        "description": "5 ve 15 dakikalık MA'da yukarı kesişme olursa sinyal üret."
    },
    {
        "name": "RSI Overbought",
        "timeframes": ["15m"],
        "indicator": "RSI",
        "condition": "over",
        "value": 70,
        "description": "15 dakikalıkta RSI 70'in üstüne çıkarsa uyar."
    },
    # Buraya istediğin kadar yeni kural ekleyebilirsin.
]

# Not: Bu dosya sadece kural tanımı içerir. Sinyal motoru ana kodda bu kuralları okuyacak.
