import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'bb_settings.json')

# Varsayılan BB parametreleri
default_settings = {
    'M5': {'period': 20, 'stddev': 2.0},
    'M15': {'period': 20, 'stddev': 2.0},
    'H1': {'period': 20, 'stddev': 2.0},
    'H4': {'period': 20, 'stddev': 2.0},
    'H6': {'period': 20, 'stddev': 2.0},
    'D1': {'period': 20, 'stddev': 2.0},
    'W1': {'period': 20, 'stddev': 2.0},
    '1M': {'period': 20, 'stddev': 2.0},
}

def get_tf_bb_setting(tf):
    settings = load_settings()
    return settings.get(tf, default_settings.get(tf, {'period': 20, 'stddev': 2.0}))

def set_tf_bb_setting(tf, period, stddev):
    settings = load_settings()
    settings[tf] = {'period': period, 'stddev': stddev}
    save_settings(settings)

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return default_settings.copy()
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default_settings.copy()

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except (OSError, TypeError) as e:
        print(f"[BB Ayar kaydetme hatası]: {e}")
