import re
import unicodedata

def clean_text(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.strip()
    return text

def contains_crypto_keyword(text):
    crypto_keywords = ["btc", "eth", "usdt", "coin", "kripto", "borsa"]
    text = clean_text(text)
    for keyword in crypto_keywords:
        if re.search(rf'(?<!\\w){keyword}(?!\\w)', text):
            return True
    return False

# Test senaryoları
if __name__ == "__main__":
    test_cases = [
        "btc bugün ne olur?",
        "btc’nin fiyatı nedir?",
        "Btc. yükselir mi?",
        "merhaba",
        "eth analiz yapar mısın?",
        "borsa hakkında bilgi ver.",
        "kripto para nedir?",
        "Bugün hava nasıl?"
    ]
    for msg in test_cases:
        print(f"'{msg}': {contains_crypto_keyword(msg)}")
