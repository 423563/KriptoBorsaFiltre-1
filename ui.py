import pandas as pd
import tkinter as tk
import time
import concurrent.futures
APP_VERSION = "1.0.0"
import customtkinter as ctk
from settings import TIMEFRAMES, HEADERS, COLUMN_WIDTHS
import json
from collections import deque, defaultdict
import os
import logging
USER_STATE_PATH = os.path.join(os.path.dirname(__file__), "user_state.json")
logger = logging.getLogger(__name__)

def load_user_state():
    try:
        with open(USER_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"[HATA]: {e}")
        return {"balance": 1000.0, "selected_timeframes": [tf for tf in TIMEFRAMES]}

def save_user_state(balance, selected_timeframes, tf_states=None):
    try:
        payload = {"balance": balance, "selected_timeframes": selected_timeframes}
        if tf_states is not None:
            payload["tf_states"] = tf_states
        with open(USER_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except (OSError, TypeError) as e:
        print(f"[HATA]: {e}")

def run_app():
    app = CryptoDashboard()
    app.mainloop()

class CryptoDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.selected_coin = None
        self.chat_panel = None
        self.updates_active = True
        self.last_update_time = "Yükleniyor..."
        self.title("Crypto Dashboard")
        # Pencereyi tam ekran başlat
        self.after(100, self._cb_zoom_fullscreen)
        # --- Kullanıcı ayarlarını yükle ---
        # FIFO veri depolama: Her coin için fiyat/hacim geçmişi
        self.coin_history = None
        self.coin_history = {}  # {'BTCUSDT': deque([...]), ...}
        self.history_length = 100  # Son 100 veri saklanacak
        self.coin_indicators = None
        self.coin_indicators = {}  # {'BTCUSDT': {'rsi':..., 'macd':..., 'volume':...}, ...}
        # TF bazlı yüzde değişim için cache ve thread havuzu
        self._tf_change_cache = {}  # { (symbol, interval): (pct_float, ts_float) }
        try:
            import requests as _req
            self._http_session = _req.Session()
        except Exception:
            self._http_session = None
        self._pct_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        # Kombinasyon sıralama durumu: 0=normal, 1=yüzde azalan, 2=yüzde artan
        self._combo_sort_state = {'rise': 0, 'fall': 0}
        # VOLUME için sıralama durumu ve son 24h hacim cache'i
        self._combo_volume_sort_state = {'rise': 0, 'fall': 0}
        self._volume_map = {}
        # Yeni listelenenler için onboarding tarih sözlüğü (ms cinsinden epoch)
        self._onboard_date = {}
        # Trend katmanı devre dışı (eski sayaçlar kaldırıldı)
        # Satır seçim durumu (ana panel vurgusu için)
        self._selected_rows = set()
        # Kombinasyon hücre havuzu (flicker-free güncelleme için)
        self._combo_items = {'rise': {}, 'fall': {}}  # {side: {symbol: {'frame':..., 'parent':..., 'symbol_label':..., 'change_label':...}}}

        state = load_user_state()
        self.balance = state.get("balance", 1000.0)
        self._user_selected_timeframes = state.get("selected_timeframes", [tf for tf in TIMEFRAMES])
        # Güncelleme kontrolü
        try:
            with open("version.txt", "r") as f:
                latest_version = f.read().strip()
            if latest_version != APP_VERSION:
                self._show_update_popup(latest_version)
        except OSError as e:
            print(f"[Güncelleme kontrolü hatası]: {e}")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        ana_panel_width = int(screen_width * 0.5) + 112 - 54 - 27 - 54 + 13  # 4.5 cm (~122px) daha dar
        analiz_panel_width = 340 + 54  # 2 cm (~54px) daha geniş
        pencere_genislik = ana_panel_width + analiz_panel_width + 24  # 12px boşluk + kenar payı
        self.geometry(f"{pencere_genislik}x{screen_height}+0+0")
        self.configure(bg="#101A5A")

        # Frame'leri grid ile yan yana yerleştir
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Ana panel (sol)
        self.left_frame = ctk.CTkFrame(self, fg_color="#101A5A", width=ana_panel_width)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_propagate(False)

        # --- Kombinasyon Alarm Paneli (sağda sabit ve her zaman açık) ---
        analiz_panel_width = 757
        self.combination_panel = ctk.CTkFrame(self, fg_color="#18206A", width=analiz_panel_width, height=screen_height)
        self.combination_panel.grid(row=0, column=1, sticky="nsew", padx=2)
        self.combination_panel.grid_propagate(False)

        # Ana panel yapılandırması
        self.combination_panel.columnconfigure(0, weight=1)
        # Kombinasyon içerik alanı tüm yüksekliği kullanır
        self.combination_panel.rowconfigure(1, weight=1)
        
        # --- Zaman dilimi toggle butonları (3 durumlu) ---
        tf_frame = ctk.CTkFrame(self.combination_panel, fg_color="#1A237E", height=40)
        tf_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        tf_frame.grid_propagate(False)
        
        # Buton durumlarını takip etmek için sözlük (0: kapalı, 1: yeşil, 2: kırmızı)
        loaded_tf_states = state.get("tf_states", {tf: 0 for tf in TIMEFRAMES})
        # Beklenmeyen anahtar/değerleri filtrele ve int'e dök
        self.tf_states = {tf: int(loaded_tf_states.get(tf, 0)) % 3 for tf in TIMEFRAMES}
        
        # Güncelleme durumu ve zamanı
        self.updates_active = True
        self.last_update_time = "Yükleniyor..."
        
        # Butonları ortala
        tf_frame.columnconfigure(len(TIMEFRAMES), weight=1)
        
        # Sağ taraftaki kontroller için frame
        right_controls = ctk.CTkFrame(tf_frame, fg_color="transparent")
        right_controls.grid(row=0, column=len(TIMEFRAMES)+1, sticky="e", padx=5)
        
        # Son güncelleme zamanı
        self.lbl_last_update = ctk.CTkLabel(
            right_controls,
            text=self.last_update_time,
            font=ctk.CTkFont(family="Arial", size=10),
            text_color="#AAAAAA"
        )
        self.lbl_last_update.pack(side="right", padx=5)
        
        # Başlat/Durdur butonu
        self.btn_toggle_updates = ctk.CTkButton(
            right_controls,
            text="DURDUR",
            font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
            width=40,
            height=25,
            fg_color="#3949AB",
            hover_color="#303F9F",
            text_color="#FFFFFF",
            corner_radius=6,
            command=self._toggle_updates
        )
        self.btn_toggle_updates.pack(side="right")

        # YENİLE butonu (hemen soluna)
        self.btn_manual_refresh = ctk.CTkButton(
            right_controls,
            text="YENİLE",
            font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
            width=60,
            height=25,
            fg_color="#00796B",
            hover_color="#00695C",
            text_color="#FFFFFF",
            corner_radius=6,
            command=self._refresh_all_now
        )
        self.btn_manual_refresh.pack(side="right", padx=(0,5))
        
        # Her zaman dilimi için bir buton oluştur
        for idx, tf in enumerate(TIMEFRAMES):
            # Buton oluştur (daha kompakt)
            btn = ctk.CTkButton(
                master=tf_frame,
                text=tf,
                font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
                width=40,
                height=25,
                fg_color="#3949AB",
                hover_color="#303F9F",
                text_color="#FFFFFF",
                corner_radius=6
            )
            btn.grid(row=0, column=idx, padx=2, pady=0)
            
            # Buton tıklama işleyicisi
            def create_click_handler(tf_key, button):
                def on_click():
                    # Mevcut durumu al ve güncelle (0->1->2->0 döngüsü)
                    current_state = self.tf_states[tf_key]
                    new_state = (current_state + 1) % 3
                    self.tf_states[tf_key] = new_state
                    # Buton stilini güncelle
                    self._apply_tf_style(button, new_state)
                    
                    # Kombinasyon ayarlarını güncelle
                    self._update_combination_settings()
                return on_click
            
            # İşleyiciyi bağla
            btn.configure(command=create_click_handler(tf, btn))
            # Açılışta kayıtlı duruma göre stil uygula
            self._apply_tf_style(btn, self.tf_states.get(tf, 0))
            
        # Zaman güncelleme döngüsünü başlat
        self._update_timestamp()
            
        # --- İki sütunlu içerik alanı ---
        content_frame = ctk.CTkFrame(self.combination_panel, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        content_frame.columnconfigure(0, weight=1)  # Sol sütun
        content_frame.columnconfigure(1, weight=1)  # Sağ sütun
        content_frame.rowconfigure(0, weight=1)
        
        # Sol Panel (Yükselişler)
        left_panel = ctk.CTkFrame(content_frame, fg_color="#1A237E", corner_radius=8)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)  # İçerik için row=1
        
        # Sol Panel Başlık Çubuğu
        left_header = ctk.CTkFrame(left_panel, fg_color="#101A5A", height=30, corner_radius=6)
        left_header.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_header.columnconfigure(1, weight=1)
        
        # Yükseliş Başlığı
        self.rise_title = ctk.CTkLabel(
            left_header, 
            text="YÜKSELİŞ",
            font=ctk.CTkFont(family="Arial", size=12, weight="bold"),
            text_color="#4CAF50"
        )
        self.rise_title.grid(row=0, column=0, padx=5, sticky="w")
        
        # Sağdaki butonlar için frame
        right_buttons = ctk.CTkFrame(left_header, fg_color="transparent")
        right_buttons.grid(row=0, column=1, padx=5, sticky="e")
        
        # Volume Butonu
        volume_btn = ctk.CTkButton(
            right_buttons, 
            text="VOLUME",
            width=70,
            height=20,
            corner_radius=4,
            fg_color="#3949AB",
            hover_color="#303F9F",
            text_color="white",
            font=ctk.CTkFont(family="Arial", size=10, weight="bold")
        )
        volume_btn.pack(side="right", padx=2)
        self.volume_btn_rise = volume_btn
        
        # Sinyal Butonu
        signal_btn = ctk.CTkButton(
            right_buttons, 
            text="SİNYAL",
            width=60,
            height=20,
            corner_radius=4,
            fg_color="#3949AB",
            hover_color="#303F9F",
            text_color="white",
            font=ctk.CTkFont(family="Arial", size=10, weight="bold")
        )
        signal_btn.pack(side="right", padx=2)
        self.signal_btn_rise = signal_btn
        self.signal_btn_rise.configure(command=lambda: self._on_combo_signal_click('rise'))
        self.volume_btn_rise.configure(command=lambda: self._on_combo_volume_click('rise'))
        # Tooltip bağla (korumalı)
        try:
            self._attach_sort_tooltip(self.signal_btn_rise, lambda: self._get_signal_tooltip_text('rise'))
            self._attach_sort_tooltip(self.volume_btn_rise, lambda: self._get_volume_tooltip_text('rise'))
        except AttributeError:
            pass
        
        # İçerik alanı - 2 sütunlu yapı
        self.left_content = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.left_content.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.left_content.grid_rowconfigure(0, weight=1)
        self.left_content.grid_columnconfigure(0, weight=1)
        
        # Scrollable sol içerik
        self.left_scroll = ctk.CTkScrollableFrame(self.left_content, fg_color="transparent")
        self.left_scroll.grid(row=0, column=0, sticky="nsew")
        self.left_scroll.grid_columnconfigure(0, weight=1)
        self.left_scroll.grid_columnconfigure(1, weight=1)
        
        # Sol sütunlar (Yükseliş)
        self.left_col1 = ctk.CTkFrame(self.left_scroll, fg_color="transparent")
        self.left_col1.grid(row=0, column=0, sticky="nsew", padx=(0, 1))
        
        self.left_col2 = ctk.CTkFrame(self.left_scroll, fg_color="transparent")
        self.left_col2.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        
        # Sütun ayırıcı çizgi - Daha belirgin hale getirildi
        separator = ctk.CTkFrame(self.left_content, width=2, fg_color="#000000")
        separator.place(relx=0.5, rely=0, relwidth=0.004, relheight=1, anchor="n")
        
        # Sağ Panel (Düşüşler)
        right_panel = ctk.CTkFrame(content_frame, fg_color="#1A237E", corner_radius=8)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)  # İçerik için row=1
        
        # Sağ Panel Başlık Çubuğu
        right_header = ctk.CTkFrame(right_panel, fg_color="#101A5A", height=30, corner_radius=6)
        right_header.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        right_header.columnconfigure(1, weight=1)
        
        # Düşüş Başlığı
        self.fall_title = ctk.CTkLabel(
            right_header, 
            text="DÜŞÜŞ",
            font=ctk.CTkFont(family="Arial", size=12, weight="bold"),
            text_color="#F44336"
        )
        self.fall_title.grid(row=0, column=0, padx=5, sticky="w")
        
        # Sağdaki butonlar için frame
        right_buttons_drop = ctk.CTkFrame(right_header, fg_color="transparent")
        right_buttons_drop.grid(row=0, column=1, padx=5, sticky="e")
        
        # Volume Butonu
        volume_btn_drop = ctk.CTkButton(
            right_buttons_drop, 
            text="VOLUME",
            width=70,
            height=20,
            corner_radius=4,
            fg_color="#3949AB",
            hover_color="#303F9F",
            text_color="white",
            font=ctk.CTkFont(family="Arial", size=10, weight="bold")
        )
        volume_btn_drop.pack(side="right", padx=2)
        self.volume_btn_fall = volume_btn_drop
        
        # Sinyal Butonu
        signal_btn_drop = ctk.CTkButton(
            right_buttons_drop, 
            text="SİNYAL",
            width=60,
            height=20,
            corner_radius=4,
            fg_color="#3949AB",
            hover_color="#303F9F",
            text_color="white",
            font=ctk.CTkFont(family="Arial", size=10, weight="bold")
        )
        signal_btn_drop.pack(side="right", padx=2)
        self.signal_btn_fall = signal_btn_drop
        self.signal_btn_fall.configure(command=lambda: self._on_combo_signal_click('fall'))
        self.volume_btn_fall.configure(command=lambda: self._on_combo_volume_click('fall'))
        # Tooltip bağla (korumalı)
        try:
            self._attach_sort_tooltip(self.signal_btn_fall, lambda: self._get_signal_tooltip_text('fall'))
            self._attach_sort_tooltip(self.volume_btn_fall, lambda: self._get_volume_tooltip_text('fall'))
        except AttributeError:
            pass

        # Başlangıçta buton renklerini senkronize et (korumalı)
        try:
            self._update_combo_buttons_ui()
        except AttributeError:
            pass
        
        # İçerik alanı - 2 sütunlu yapı
        self.right_content = ctk.CTkFrame(right_panel, fg_color="transparent")
        self.right_content.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.right_content.grid_rowconfigure(0, weight=1)
        self.right_content.grid_columnconfigure(0, weight=1)
        
        # Scrollable sağ içerik
        self.right_scroll = ctk.CTkScrollableFrame(self.right_content, fg_color="transparent")
        self.right_scroll.grid(row=0, column=0, sticky="nsew")
        self.right_scroll.grid_columnconfigure(0, weight=1)
        self.right_scroll.grid_columnconfigure(1, weight=1)
        
        # Sağ sütunlar (Düşüş)
        self.right_col1 = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        self.right_col1.grid(row=0, column=0, sticky="nsew", padx=(0, 1))
        
        self.right_col2 = ctk.CTkFrame(self.right_scroll, fg_color="transparent")
        self.right_col2.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        
        # Sütun ayırıcı çizgi - Daha belirgin hale getirildi
        separator = ctk.CTkFrame(self.right_content, width=2, fg_color="#000000")
        separator.place(relx=0.5, rely=0, relwidth=0.004, relheight=1, anchor="n")
        
        # Alarm paneli kaldırıldı: boşluk kombinasyon alanına eklendi

        # --- Separator çizgi ---
        self.combination_panel.grid_columnconfigure(0, weight=1)

        # SCROLLABLE PANEL (Canvas + Frame + Scrollbar) - ANA PANELİN İÇİNE TAŞINDI

        # Alarm paneli kaldırıldı
        self.canvas = ctk.CTkCanvas(self.left_frame, bg="#101A5A", highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(self.left_frame, orientation="vertical", command=self.canvas.yview)
        self.scrollable_panel = ctk.CTkFrame(self.canvas, fg_color="#101A5A")



        def _on_scroll_config(_event=None):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.scrollable_panel.bind("<Configure>", _on_scroll_config)
        self.canvas.create_window((0, 0), window=self.scrollable_panel, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        # Mouse tekerleği ile scroll (Windows, Mac, Linux)
        # Aktif scroll hedefini takip et (ana panel veya scrollable frame'ler)
        self._active_scroll_target = {'type': None, 'widget': None}

        def _activate_scroll_target(widget, kind):
            try:
                self._active_scroll_target = {'type': kind, 'widget': widget}
            except Exception:
                pass

        def _deactivate_scroll_target(widget):
            try:
                cur = self._active_scroll_target
                if cur.get('widget') is widget:
                    self._active_scroll_target = {'type': None, 'widget': None}
            except Exception:
                pass

        def _scroll_widget(widget, steps):
            try:
                if widget is None:
                    return
                # Ana canvas
                if widget is self.canvas:
                    self.canvas.yview_scroll(steps, "units")
                    return
                # CTkScrollableFrame iç canvas'ını bul ve kaydır
                cv = getattr(widget, '_parent_canvas', None)
                if cv is None:
                    cv = getattr(widget, 'canvas', None)
                if cv is not None:
                    # Kombinasyon sütunlarında akıcı kaydırma için hızı artır
                    factor = 6 if (widget is self.left_scroll or widget is self.right_scroll) else 1
                    cv.yview_scroll(steps * factor, "units")
            except Exception:
                pass

        def _on_mousewheel_route(event):
            # Windows/Mac: event.delta; Linux: Button-4/5 ayrı
            steps = 0
            if hasattr(event, 'delta') and event.delta:
                steps = int(-1 * (event.delta/120))
            elif hasattr(event, 'num'):
                # Linux: Button-4 (up), Button-5 (down) -> adımı biraz büyüt
                base = 2
                steps = base if getattr(event, 'num', 0) == 5 else -base
            tgt = self._active_scroll_target.get('widget')
            _scroll_widget(tgt, steps)

        # Hover ile aktif hedefi belirle
        self.canvas.bind('<Enter>', lambda e: _activate_scroll_target(self.canvas, 'canvas'))
        self.canvas.bind('<Leave>', lambda e: _deactivate_scroll_target(self.canvas))
        self.left_scroll.bind('<Enter>', lambda e: _activate_scroll_target(self.left_scroll, 'scrollframe'))
        self.left_scroll.bind('<Leave>', lambda e: _deactivate_scroll_target(self.left_scroll))
        self.right_scroll.bind('<Enter>', lambda e: _activate_scroll_target(self.right_scroll, 'scrollframe'))
        self.right_scroll.bind('<Leave>', lambda e: _deactivate_scroll_target(self.right_scroll))

        # Global yönlendirme (uygulama içinde)
        self.bind_all('<MouseWheel>', _on_mousewheel_route)   # Windows, Mac
        self.bind_all('<Button-4>', _on_mousewheel_route)     # Linux up
        self.bind_all('<Button-5>', _on_mousewheel_route)     # Linux down
        self.panel = self.scrollable_panel
        self._create_panel()

    # Kombinasyon alarmı paneli fonksiyonları
    def _toggle_combination_alarm(self):
        # self.combination_alarm_active = not self.combination_alarm_active
        pass

    def _update_combination_settings(self, *_):
        # Aktif olan (yeşil veya kırmızı) zaman dilimlerini al
        active_timeframes = [tf for tf, state in self.tf_states.items() if state > 0]
        
        # Kombinasyon ayarlarını güncelle
        self.combination_settings = {
            'timeframes': active_timeframes,
            'states': {k: v for k, v in self.tf_states.items() if v > 0}
        }
        
        # Eğer güncellemeler aktifse, yeni eklenen zaman dilimleri için güncelleme başlat
        if hasattr(self, 'updates_active') and self.updates_active:
            for tf, state in self.tf_states.items():
                if state > 0:  # Eğer buton aktifse
                    self._start_updates_for_timeframe(tf)
        
        # Kullanıcı ayarlarını kaydet
        save_user_state(self.balance, active_timeframes, tf_states=self.tf_states)

    # --- Kombinasyon paneli buton click handler'ları ---
    def _on_combo_signal_click(self, side):
        try:
            print(f"[CLICK] Kombinasyon SİNYAL - side={side}")
            # 0 -> 1 -> 2 -> 0
            cur = self._combo_sort_state.get(side, 0)
            nxt = (cur + 1) % 3
            self._combo_sort_state[side] = nxt
            # Anında UI yenile
            self._schedule_combination_refresh()
            self._update_combo_buttons_ui()
            # Tooltip metnini anında güncelle
            try:
                widget = self.signal_btn_rise if side == 'rise' else self.signal_btn_fall
                self._refresh_tooltip_text(widget, lambda: self._get_signal_tooltip_text(side))
            except Exception:
                pass
        except Exception as e:
            print(f"[CLICK ERROR] signal: {e}")

    def _on_combo_volume_click(self, side):
        try:
            print(f"[CLICK] Kombinasyon VOLUME - side={side}")
            cur = self._combo_volume_sort_state.get(side, 0)
            nxt = (cur + 1) % 3
            self._combo_volume_sort_state[side] = nxt
            # Anında UI yenile
            self._schedule_combination_refresh()
            self._update_combo_buttons_ui()
            # Tooltip metnini anında güncelle
            try:
                widget = self.volume_btn_rise if side == 'rise' else self.volume_btn_fall
                self._refresh_tooltip_text(widget, lambda: self._get_volume_tooltip_text(side))
            except Exception:
                pass
        except Exception as e:
            print(f"[CLICK ERROR] volume: {e}")

    def _show_combination_panel(self):
        pass
        
    def _refresh_combination_alerts_panel(self):
        # Bu metod artık kullanılmıyor, çünkü eski sinyal kutularını kaldırdık
        # İleride gerekirse yeni panele özgü güncellemeler burada yapılabilir
        pass

    # Zaman dilimi butonları için stil uygulayıcı
    def _update_timestamp(self):
        """Son güncelleme zamanını günceller"""
        from datetime import datetime
        now = datetime.now()
        self.last_update_time = f"Son Güncelleme: {now.strftime('%H:%M:%S')}"
        self.lbl_last_update.configure(text=self.last_update_time)
        
        # Eğer güncellemeler aktifse 1 saniye sonra tekrar güncelle
        if self.updates_active:
            self.after(1000, self._update_timestamp)

    # --- Kombinasyon butonları: renk güncelleme ve tooltip yardımcıları ---
    def _update_combo_buttons_ui(self):
        def style(btn, active_fg, active_hover, is_active):
            try:
                if is_active:
                    btn.configure(fg_color=active_fg, hover_color=active_hover)
                else:
                    btn.configure(fg_color="#3949AB", hover_color="#303F9F")
            except Exception:
                pass
        # Signal states
        style(self.signal_btn_rise, "#00BFA5", "#00A089", self._combo_sort_state.get('rise',0) in (1,2))
        style(self.signal_btn_fall, "#00BFA5", "#00A089", self._combo_sort_state.get('fall',0) in (1,2))
        # Volume states
        style(self.volume_btn_rise, "#FFA726", "#FB8C00", self._combo_volume_sort_state.get('rise',0) in (1,2))
        style(self.volume_btn_fall, "#FFA726", "#FB8C00", self._combo_volume_sort_state.get('fall',0) in (1,2))

    def _get_signal_tooltip_text(self, side):
        st = self._combo_sort_state.get(side, 0)
        if st == 1:
            return "Yüzde: yüksekten düşüğe"
        if st == 2:
            return "Yüzde: düşükten yükseğe"
        return "Varsayılan"

    def _get_volume_tooltip_text(self, side):
        st = self._combo_volume_sort_state.get(side, 0)
        if st == 1:
            return "Hacim: yüksekten düşüğe"
        if st == 2:
            return "Hacim: düşükten yükseğe"
        return "Varsayılan"

    def _is_new_listing(self, symbol):
        try:
            ts = self._onboard_date.get(symbol)
            if not ts:
                return False
            now_ms = int(time.time() * 1000)
            return (now_ms - int(ts)) < (30 * 24 * 3600 * 1000)
        except Exception:
            return False

    def _attach_sort_tooltip(self, widget, text_provider):
        if not hasattr(self, '_tooltips'):
            self._tooltips = {}
        tip = {'win': None, 'lbl': None}
        self._tooltips[widget] = tip
        
        # Tooltip açıkken metni anında yenilemek için yardımcı
        def _update_text_now():
            try:
                if tip['win'] is not None and tip['lbl'] is not None:
                    txt = text_provider()
                    if txt:
                        tip['lbl'].configure(text=txt)
                        tip['win'].lift()
            except Exception:
                pass

        def show(event=None):
            # Metni hazırla
            try:
                txt = text_provider()
            except Exception:
                txt = ""
            if not txt:
                return
            # Pencere yoksa oluştur
            if tip['win'] is None:
                win = tk.Toplevel(self)
                try:
                    win.wm_overrideredirect(True)
                except Exception:
                    pass
                try:
                    win.attributes('-topmost', True)
                except Exception:
                    pass
                try:
                    win.configure(bg="#223066")  # Beyaz flash engelle
                except Exception:
                    pass
                lbl = ctk.CTkLabel(win, text=txt, fg_color="#223066", text_color="#FFFFFF", corner_radius=6)
                lbl.pack(ipadx=6, ipady=2)
                tip['win'] = win
                tip['lbl'] = lbl
            else:
                # Metni güncelle
                try:
                    if tip['lbl'] is not None:
                        tip['lbl'].configure(text=txt)
                except Exception:
                    pass
            move(event, update_text=False)

        def hide(_event=None):
            if tip['win'] is not None:
                try:
                    tip['win'].withdraw()
                except Exception:
                    pass

        def move(event=None, update_text=True):
            if tip['win'] is None:
                return
            try:
                # Metni her hareketle tazele (anında güncelleme)
                if update_text:
                    try:
                        txt = text_provider()
                        if tip['lbl'] is not None and txt:
                            tip['lbl'].configure(text=txt)
                    except Exception:
                        pass
                # Pozisyon: imlecin hafif sağı/altı
                if event is not None and hasattr(event, 'x_root') and hasattr(event, 'y_root'):
                    x = event.x_root + 12
                    y = event.y_root + 12
                else:
                    x = widget.winfo_rootx() + 12
                    y = widget.winfo_rooty() + widget.winfo_height() + 8
                tip['win'].deiconify()
                tip['win'].lift()
                tip['win'].wm_geometry(f"+{x}+{y}")
            except Exception:
                pass

        widget.bind('<Enter>', show)
        widget.bind('<Leave>', hide)
        widget.bind('<Motion>', move)
        # Dışarıdan da güncelleyebilmek için referans sakla
        widget._tooltip_update_fn = _update_text_now

    def _refresh_tooltip_text(self, widget, text_provider):
        try:
            if hasattr(widget, '_tooltip_update_fn') and callable(widget._tooltip_update_fn):
                # Sağlanan provider ile metni güncellemek için geçici olarak değiştir
                old = None
                if hasattr(self, '_tooltips') and widget in self._tooltips:
                    tip = self._tooltips.get(widget)
                    old = getattr(widget, '_tooltip_update_fn', None)
                    # Kısa süreli inline update
                    try:
                        if tip and tip.get('win') is not None and tip.get('lbl') is not None:
                            txt = text_provider()
                            if txt:
                                tip['lbl'].configure(text=txt)
                                tip['win'].lift()
                    except Exception:
                        pass
                # Geri yüklemeye gerek yok; update_fn idempotent
        except Exception:
            pass

    def _toggle_updates(self):
        """Tüm panel güncellemelerini başlatır veya durdurur"""
        self.updates_active = not self.updates_active
        
        if self.updates_active:
            self.btn_toggle_updates.configure(text="DURDUR", fg_color="#3949AB")
            self._update_timestamp()
            # Tüm zaman aralığı butonlarını aktif et
            for tf, state in self.tf_states.items():
                if state > 0:  # Eğer buton aktifse (yeşil veya kırmızı)
                    # İlgili zaman aralığının güncellemelerini başlat
                    self._start_updates_for_timeframe(tf)
        else:
            self.btn_toggle_updates.configure(text="BAŞLAT", fg_color="#666666")
            # Tüm zaman aralığı güncellemelerini durdur
            for tf in self.tf_states.keys():
                self._stop_updates_for_timeframe(tf)
                
    def _start_updates_for_timeframe(self, timeframe):
        """Belirtilen zaman aralığı için güncellemeleri başlat"""
        # Burada ilgili zaman aralığı için güncelleme işlemlerini başlat
        # Örnek: self.after(interval, self._update_timeframe_data, timeframe)
        pass
        
    def _stop_updates_for_timeframe(self, timeframe):
        """Belirtilen zaman aralığı için güncellemeleri durdur"""
        # Burada ilgili zaman aralığı için güncelleme işlemlerini durdur
        # Örnek: self.after_cancel(update_id) gibi
        pass
    
    def _apply_tf_style(self, button, state):
        try:
            if state == 0:  # Kapalı
                button.configure(fg_color="#3D4A99", hover_color="#36428C", text_color="#FFFFFF")
            elif state == 1:  # Yeşil
                button.configure(fg_color="#2E7D32", hover_color="#276B2B", text_color="#FFFFFF")
            else:  # Kırmızı
                button.configure(fg_color="#C62828", hover_color="#AB2222", text_color="#FFFFFF")
        except Exception as e:
            logger.debug("_apply_tf_style error: %s", e)

    # _combo_update_signals_loop kaldırıldı (kullanılmıyordu)

    @staticmethod
    def signal_cell_click(_event, symbol, tf_val):
        print(f"Signal cell clicked: {symbol} - {tf_val}")

    @staticmethod
    def _show_update_popup(latest_version):
        print(f"Yeni sürüm mevcut: {latest_version}")

    @staticmethod
    def _open_bb_popup(tf_name):
        print(f"Bollinger ayarları açıldı: {tf_name}")

    def _create_panel(self):
        # Panel ana çerçevesi artık scrollable_panel olacak!
        panel = self.scrollable_panel  # Kısaltma için
        # Üst butonlar
        
        button_height = 18
        button_corner = 6
        # --- Sütun başlık genişlikleri ---
        header_widths = {
            'Sembol': 100,
            '$ Fiyat': 70,
            '24H %': 70
        }
        # Üstteki butonlar için de aynı genişlikleri kullan
        self.start_stop_btn = ctk.CTkButton(panel, text="BORSA SEÇİMİ", fg_color="#FF5252", hover_color="#FF5252", text_color="#FFF", height=button_height, width=header_widths.get('Sembol', 90), corner_radius=button_corner)
        self.start_stop_btn.grid(row=0, column=0, padx=3, pady=6)
        self.start_stop_btn.configure(command=self._show_combination_panel)

        self.buy_btn = ctk.CTkButton(panel, text="Al", fg_color="#4CAF50", hover_color="#43A047", text_color="#FFF", height=button_height, width=header_widths.get('$ Fiyat', 90), corner_radius=button_corner)
        self.buy_btn.grid(row=0, column=1, padx=3, pady=6)
        self.sell_btn = ctk.CTkButton(panel, text="Sat", fg_color="#888888", hover_color="#888888", text_color="#FFF", height=button_height, width=header_widths.get('24H %', 90), corner_radius=button_corner)
        self.sell_btn.grid(row=0, column=2, padx=3, pady=6)
        # Başlıklar
        col = 0
        for title in HEADERS:
    
            if title in ["No", "★", "!"]:
                continue  # Bu başlıkları atla
            w = header_widths.get(title, 90)
            header_button = ctk.CTkButton(
                panel,
                text=title,
                font=("Arial", 13, "bold"),
                fg_color="#888888",
                text_color="#FFF",
                hover_color="#666666",
                width=w,
                height=button_height,
                corner_radius=button_corner
            )
            header_button.grid(row=1, column=col, padx=(4,4), pady=4, sticky="nsew")
            # Soft çizgi (en sağ hariç)
            if col < len(HEADERS) - 1:
                border = ctk.CTkLabel(panel, text="", fg_color="#223066", width=1, height=18)
                border.grid(row=1, column=col+1, sticky="ns")
            col += 1
        # Zaman dilimi sütunları (üstte dişli, altta zaman dilimi)
        tf_width = COLUMN_WIDTHS.get("TIMEFRAME", 54)
        # --- Zaman dilimi toggle state ---
        self.active_timeframes = {tf: True for tf in TIMEFRAMES}
        self.tf_labels = {}
        for idx, tf_val in enumerate(TIMEFRAMES):
            btn = ctk.CTkButton(
                self.panel,
                text="\u2699",
                width=tf_width,
                height=18,
                fg_color="#FFD700",
                text_color="#101A5A",
                hover_color="#FFE066",
                font=("Arial", 12, "bold"),
                corner_radius=6,
                command=lambda tf_name=tf_val: self._open_bb_popup(tf_name)
            )
            btn.grid(row=0, column=col+idx, padx=(2,2), pady=1)
            # Zaman etiketi toggle
            def make_toggle(tf_name):
                def toggle(_event=None):
                    tf_label = self.tf_labels[tf_name]
                    self.active_timeframes[tf_name] = not self.active_timeframes[tf_name]
                    if self.active_timeframes[tf_name]:
                        tf_label.configure(fg_color="#4CAF50", text_color="#FFF")
                    else:
                        tf_label.configure(fg_color="#888888", text_color="#444444")
                    self._refresh_signals_table(force=True)
                return toggle
            tf_label_local = ctk.CTkLabel(
                self.panel,
                text=tf_val,
                font=("Arial", 11, "bold"),
                text_color="#FFF",
                fg_color="#4CAF50",
                width=tf_width,
                height=18,
                corner_radius=8
            )
            tf_label_local.grid(row=1, column=col+idx, padx=(2,2), pady=1, sticky="nsew")
            tf_label_local.bind("<Button-1>", make_toggle(tf_val))
            self.tf_labels[tf_val] = tf_label_local
            if idx < len(TIMEFRAMES) - 1:
                border = ctk.CTkLabel(self.panel, text="", fg_color="#223066", width=1, height=18)
                border.grid(row=1, column=col+idx+1, sticky="ns")

        # --- COIN TABLOSU ---
        # Ana panel arka plan ve vurgulama renkleri
        self._table_bg = "#151E4A"
        self._row_highlight_bg = "#223066"
        self.signal_labels = []
        self.coin_rows = []
        table_bg = self._table_bg
        table_fg = "#FFD700"
        cell_fg = "#FFF"
        from ws_utils import SignalBackgroundWorker
        from signal_calculator import fetch_supertrend_signal
        # Binance API'den en yüksek hacimli 37 coin'i çek
        import requests
        try:
            # --- Binance USDT Futures: Sadece aktif ve fiyatı olan coinler ---
            exch_info = requests.get('https://fapi.binance.com/fapi/v1/exchangeInfo').json()
            active_symbols = set(
                s['symbol'] for s in exch_info['symbols']
                if s['contractType'] == 'PERPETUAL' and s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING'
            )
            # onboardDate topla (varsa)
            try:
                self._onboard_date = {
                    s['symbol']: int(s.get('onboardDate'))
                    for s in exch_info.get('symbols', [])
                    if s.get('onboardDate') is not None
                }
            except Exception:
                self._onboard_date = {}
            ticker_data = requests.get('https://fapi.binance.com/fapi/v1/ticker/24hr').json()
            filtered_pairs = [
                item for item in ticker_data
                if item['symbol'] in active_symbols and float(item.get('lastPrice', 0)) > 0
            ]
            sorted_pairs = sorted(filtered_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
            self.coin_symbols = [item['symbol'] for item in sorted_pairs[:150]]
            if 'BTCUSDT' in self.coin_symbols:
                self.coin_symbols.remove('BTCUSDT')
            self.coin_symbols = ['BTCUSDT'] + self.coin_symbols
        except requests.RequestException as e:
            # Hata olursa eski statik listeyi kullan
            print(f"[HATA] Binance API'den coin listesi çekilemedi: {e}")
            self.coin_symbols = [
                "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "SUIUSDT", "FARTCOINUSDT", "UNIUSDT", "FUNUSDT", "HYPEUSDT", "BCHUSDT", "AAVEUSDT", "ADAUSDT", "TUSDT", "WIFUSDT"
            ]

        # Önce eski widget'ları temizle (tabloyu yeniden oluştururken)
        for row in getattr(self, 'coin_rows', []):
            for widget in row:
                widget.destroy()
        for row in getattr(self, 'signal_labels', []):
            for widget in row:
                widget.destroy()
        self.signal_labels = []
        self.coin_rows = []
        for row_idx, symbol in enumerate(self.coin_symbols, start=0):
            row_widgets = []
            row_signal_labels = []
            # Sembol, Fiyat, Değişim hücreleri
            values = [symbol, "-", "-"]
            for col_idx, value in enumerate(values):
                fg = table_fg if col_idx == 0 else cell_fg
                # Yeni listelenen coinler: isim mor (#ff00fe) – 30 gün boyunca
                if col_idx == 0 and self._is_new_listing(symbol):
                    fg = '#ff00fe'
                cell = ctk.CTkLabel(
                    master=self.panel,
                    text=value,
                    font=("Arial", 11),
                    text_color=fg,
                    fg_color=table_bg,
                    height=18
                )
                cell.grid(row=row_idx+2, column=col_idx, padx=1, pady=1, sticky="nsew")
                row_widgets.append(cell)
                # Sembol sütunu (coin adı) için tıklanabilirlik ekle (sadece ilk sütun)
                if col_idx == 0:
                    row_index = row_idx
                    def on_coin_click(_event=None, sym=symbol, r=row_index):
                        # Alarm popup'ını aç
                        try:
                            self._open_alarm_popup({'symbol': sym, 'type': '-'})
                        except Exception as err:
                            print(f"[ALARM POPUP OPEN ERROR]: {err}")
                        # İsteğe bağlı: sohbet paneline otomatik mesaj bırak (mevcut davranışı koru)
                        try:
                            widgets_local = self.coin_rows[r] if r < len(self.coin_rows) else row_widgets
                            fiyat = widgets_local[1].cget('text') if len(widgets_local) > 1 else '-'
                            degisim = widgets_local[2].cget('text') if len(widgets_local) > 2 else '-'
                            if hasattr(self, 'chat_panel') and self.chat_panel is not None:
                                msg = f"{sym} için teknik analiz yapar mısın? Son fiyat: {fiyat}, Değişim: {degisim}"
                                self.chat_panel.entry.delete(0, 'end')
                                self.chat_panel.entry.insert(0, msg)
                                self.chat_panel.on_enter()
                        except Exception as err:
                            print(f"[COIN CLICK ERROR]: {err}")
                    cell.bind("<Button-1>", on_coin_click)
            # Sinyal noktaları (●) - her zaman tam TIMEFRAMES kadar ve eksiksiz
            for tf_idx, tf_val in enumerate(TIMEFRAMES):
                sig_toggle_label = ctk.CTkLabel(
                    master=self.panel,
                    text="●",
                    font=("Arial", 13),
                    text_color="#FFD700",
                    fg_color=table_bg,
                    width=54,
                    height=18
                )
                sig_toggle_label.grid(row=row_idx+2, column=3+tf_idx, padx=1, pady=1, sticky="nsew")
                sig_toggle_label.bind("<Button-1>", lambda _event, symbol_cl=symbol, tf_val_cl=tf_val: self.signal_cell_click(_event, symbol_cl, tf_val_cl))
                def on_enter(_event=None, r=row_idx):
                    for c in self.coin_rows[r]:
                        c.configure(fg_color="#223066")
                    for s in self.signal_labels[r]:
                        s.configure(fg_color="#223066")
                def on_leave(_event=None, r=row_idx, tf=tf_val):
                    # Hover bittiğinde seçili satırsa highlight rengini koru
                    try:
                        row_symbol = self.coin_rows[r][0].cget('text')
                    except Exception:
                        row_symbol = None
                    target_bg = self._row_highlight_bg if (row_symbol in self._selected_rows) else table_bg
                    for c in self.coin_rows[r]:
                        c.configure(fg_color=target_bg)
                    for s in self.signal_labels[r]:
                        s.configure(fg_color=target_bg)
                    self.tf_labels[tf].configure(fg_color="#4CAF50")
                sig_toggle_label.bind("<Enter>", on_enter)
                sig_toggle_label.bind("<Leave>", on_leave)
                row_signal_labels.append(sig_toggle_label)
            self.signal_labels.append(row_signal_labels)
            self.coin_rows.append(row_widgets)
        # Grid ayarlarını panelde uygula
        total_columns = len(HEADERS) + len(TIMEFRAMES)
        for col_idx in range(total_columns):
            self.panel.grid_columnconfigure(col_idx, weight=1)
        # Sinyal sistemi başlat
        tf_pairs = [(tf, {'M5':'5m','M15':'15m','H1':'1h','H4':'4h','H6':'6h','D1':'1d','W1':'1w','1M':'1M'}[tf]) for tf in TIMEFRAMES]
        self.signal_worker = SignalBackgroundWorker(self.coin_symbols, tf_pairs, fetch_supertrend_signal)
        self.signal_worker.start()
        self._refresh_signals_table()
        self._update_prices()
        # Veri birikimi kontrolü başlat
        self._start_history_collection()
        self._schedule_combination_refresh()

    def _refresh_signals_table(self, force=None):
        if force is None:
            force = False
        self._refresh_signals_table_once()
        if not force:
            self.after(10000, self._refresh_signals_table)

    def _toggle_row_selection(self, symbol):
        # Tekil seçim:
        # - Aynı sembole tekrar tıklanırsa seçim kaldır
        # - Başka bir sembole tıklanırsa önceki seçimi temizle, yeni sembolü seç
        try:
            idx = self.coin_symbols.index(symbol)
        except ValueError:
            return
        if symbol in self._selected_rows:
            # Seçimi kaldır
            try:
                self._selected_rows.remove(symbol)
            except KeyError:
                pass
            try:
                for c in self.coin_rows[idx]:
                    c.configure(fg_color=self._table_bg)
                for s in self.signal_labels[idx]:
                    s.configure(fg_color=self._table_bg)
            except Exception:
                pass
            return
        # Farklı bir sembol seçiliyor: önce tüm mevcut seçimleri temizle
        prev_selected = list(self._selected_rows)
        for prev in prev_selected:
            try:
                pidx = self.coin_symbols.index(prev)
            except ValueError:
                continue
            try:
                for c in self.coin_rows[pidx]:
                    c.configure(fg_color=self._table_bg)
                for s in self.signal_labels[pidx]:
                    s.configure(fg_color=self._table_bg)
            except Exception:
                pass
            try:
                self._selected_rows.remove(prev)
            except KeyError:
                pass
        # Yeni sembolü seç ve vurgula
        self._selected_rows.add(symbol)
        try:
            for c in self.coin_rows[idx]:
                c.configure(fg_color=self._row_highlight_bg)
            for s in self.signal_labels[idx]:
                s.configure(fg_color=self._row_highlight_bg)
        except Exception:
            pass

    def _update_prices(self):
        self._update_prices_once()
        self.after(10000, self._update_prices)

    def _refresh_signals_table_once(self):
        import time
        if not hasattr(self, '_signal_flash_states'):
            self._signal_flash_states = {}
        now = time.time()
        for row_idx, symbol in enumerate(self.coin_symbols):
            for tf_idx, tf_val in enumerate(TIMEFRAMES):
                label = self.signal_labels[row_idx][tf_idx]
                key = (symbol, tf_val)
                if not self.active_timeframes[tf_val]:
                    label.configure(text="", text_color="#223066")
                    continue
                raw_sig = self.signal_worker.get_signal(symbol, tf_val)
                flash = self._signal_flash_states.get(key)
                # Neutral yok: önceki geçerli duruma map et, yoksa varsayılan 'down'
                if raw_sig in ("up", "down"):
                    display_sig = raw_sig
                else:
                    prev = flash['sig'] if isinstance(flash, dict) else None
                    display_sig = prev if prev in ("up", "down") else "down"
                try:
                    self._check_trigger_for(symbol, tf_val, display_sig)
                except (KeyError, AttributeError, ValueError):
                    pass
                if flash is None or flash.get('sig') != display_sig:
                    # up<->down geçişlerinde flash başlat
                    if flash is not None and ((flash.get('sig') == 'up' and display_sig == 'down') or (flash.get('sig') == 'down' and display_sig == 'up')):
                        self._signal_flash_states[key] = {'sig': display_sig, 'ts': now}
                    else:
                        self._signal_flash_states[key] = {'sig': display_sig, 'ts': 0}
                    flash = self._signal_flash_states[key]
                elapsed = now - flash['ts']
                if display_sig == "up":
                    color = "#7FFF00" if 0 < flash['ts'] and elapsed < 15 else "#00611C"
                else:  # display_sig == 'down'
                    color = "#FF0000" if 0 < flash['ts'] and elapsed < 15 else "#800000"
                if 0 < flash['ts'] and elapsed < 15:
                    label.configure(text="●", text_color=color, font=("Arial", 18, "bold"))
                else:
                    label.configure(text="●", text_color=color, font=("Arial", 15, "bold"))

    def _update_prices_once(self):
        import requests
        prices = {}
        changes = {}
        try:
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            for coin in data:
                symbol = coin['symbol']
                if symbol in self.coin_symbols:
                    price = float(coin['lastPrice'])
                    prices[symbol] = price
                    changes[symbol] = float(coin['priceChangePercent'])
                    try:
                        self._volume_map[symbol] = float(coin.get('quoteVolume', 0.0))
                    except Exception:
                        pass
                    if symbol not in self.coin_history:
                        self.coin_history[symbol] = deque(maxlen=self.history_length)
                    self.coin_history[symbol].append({
                        'price': price,
                        'change': changes[symbol],
                        'timestamp': coin.get('closeTime', None)
                    })
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"[Fiyat güncelleme hatası]: {e}")
        for row_idx, symbol in enumerate(self.coin_symbols):
            price = prices.get(symbol)
            price_str = f"{price:.2f}" if price is not None else self.coin_rows[row_idx][1].cget("text")
            self.coin_rows[row_idx][1].configure(text=price_str)
            change = changes.get(symbol)
            change_str = f"{change:+.2f}%" if change is not None else self.coin_rows[row_idx][2].cget("text")
            if change is not None:
                color = "#00FF00" if change > 0 else ("#FF4C4C" if change < 0 else "#FFD700")
            else:
                color = "#FFD700"
            self.coin_rows[row_idx][2].configure(text=change_str, text_color=color)

    def _refresh_all_now(self):
        try:
            # Zaman etiketi
            self._update_timestamp()
            # Fiyatlar ve sinyaller (tek seferlik)
            self._update_prices_once()
            self._refresh_signals_table_once()
            # Kombine paneli bir kez hesapla ve çiz
            rise, fall = self._evaluate_combinations()
            try:
                self.rise_title.configure(text=f"YÜKSELİŞ ({len(rise)})")
                self.fall_title.configure(text=f"DÜŞÜŞ ({len(fall)})")
            except Exception:
                pass
            self._update_combination_ui(rise, fall)
        except Exception as e:
            print(f"[MANUAL REFRESH ERROR]: {e}")

    def _schedule_combination_refresh(self):
        try:
            rise, fall = self._evaluate_combinations()
            try:
                self.rise_title.configure(text=f"YÜKSELİŞ ({len(rise)})")
                self.fall_title.configure(text=f"DÜŞÜŞ ({len(fall)})")
            except Exception:
                pass
            self._update_combination_ui(rise, fall)
        except Exception as e:
            print(f"[Kombinasyon Hatası]: {e}")
        self.after(5000, self._schedule_combination_refresh)

    def _highest_active_interval(self):
        # Seçili (state>0) TF'ler arasında en yüksek TF'yi bul ve Binance interval döndür
        ranks = {"M5":1, "M15":2, "H1":3, "H4":4, "H6":5, "D1":6, "W1":7, "1M":8}
        tf_to_interval = {"M5":"5m","M15":"15m","H1":"1h","H4":"4h","H6":"6h","D1":"1d","W1":"1w","1M":"1M"}
        actives = [tf for tf, st in self.tf_states.items() if st > 0 and tf in ranks]
        if not actives:
            return None
        highest = max(actives, key=lambda t: ranks[t])
        return tf_to_interval.get(highest)

    def _fetch_tf_change(self, symbol, interval):
        # Cache kontrolü
        key = (symbol, interval)
        ttl = self._get_ttl_for_interval(interval)
        now_ts = time.time()
        entry = self._tf_change_cache.get(key)
        if entry and (now_ts - entry[1] < ttl):
            return entry[0]
        # İstek yap
        try:
            session = self._http_session
            if session is None:
                import requests
                session = requests
            url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=2"
            resp = session.get(url, timeout=8)
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                return None
            prev_close = float(data[-2][4])
            last_close = float(data[-1][4])
            if prev_close == 0:
                return None
            pct = (last_close - prev_close) / prev_close * 100.0
            self._tf_change_cache[key] = (pct, now_ts)
            return pct
        except Exception as e:
            print(f"[TF % HATA] {symbol} {interval}: {e}")
            return None

    def _get_ttl_for_interval(self, interval):
        return {
            '5m': 60,      # 1 dk
            '15m': 120,    # 2 dk
            '1h': 300,     # 5 dk
            '4h': 600,     # 10 dk
            '6h': 900,     # 15 dk
            '1d': 1800,    # 30 dk
            '1w': 3600,    # 60 dk
            '1M': 3600,    # 60 dk
        }.get(interval, 300)

    def _prefetch_tf_change_async(self, symbols, interval):
        if not symbols or interval is None:
            return
        missing = []
        now_ts = time.time()
        ttl = self._get_ttl_for_interval(interval)
        for sym in symbols:
            key = (sym, interval)
            ent = self._tf_change_cache.get(key)
            if not ent or (now_ts - ent[1] >= ttl):
                missing.append(sym)
        if not missing:
            return
        def _task(sym):
            try:
                self._fetch_tf_change(sym, interval)
            except Exception:
                pass
        for sym in missing:
            self._pct_executor.submit(_task, sym)
        # Yakında taze değerler gelecek, nazikçe yeniden çiz
        self.after(1200, lambda: self._schedule_combination_refresh())

    def _evaluate_combinations(self):
        green_tfs = [tf for tf, st in self.tf_states.items() if st == 1]
        red_tfs = [tf for tf, st in self.tf_states.items() if st == 2]
        if not green_tfs and not red_tfs:
            return [], []
        symbols = getattr(self, 'coin_symbols', [])
        rise_matches = []
        fall_matches = []
        # Yeşil kombinasyon: tüm seçili yeşil TF'lerde "up" olmalı
        if green_tfs:
            for symbol in symbols:
                ok = True
                for tf in green_tfs:
                    try:
                        s = self.signal_worker.get_signal(symbol, tf)
                    except Exception:
                        s = None
                    if s != "up":
                        ok = False
                        break
                if ok:
                    rise_matches.append(symbol)
        # Kırmızı kombinasyon: tüm seçili kırmızı TF'lerde "down" olmalı
        if red_tfs:
            for symbol in symbols:
                ok = True
                for tf in red_tfs:
                    try:
                        s = self.signal_worker.get_signal(symbol, tf)
                    except Exception:
                        s = None
                    if s != "down":
                        ok = False
                        break
                if ok:
                    fall_matches.append(symbol)
        print(f"[KOMBİNE] rise={len(rise_matches)} fall={len(fall_matches)} | green_tfs={green_tfs} red_tfs={red_tfs}")
        return rise_matches, fall_matches

    def _evaluate_trend_reversals(self):
        """Hafif Trend (seçim tabanlı, nötr yok):
        - Kullanıcı büyük TF'yi yeşil (zirve) veya kırmızı (dip) olarak işaretler.
        - En büyük TF tarafı 'majör' kabul edilir.
          * Majör=YEŞİL ve (any(G up) & any(R down)) => zirve adayı (top)
          * Majör=KIRMIZI ve (any(R down) & any(G up)) => dip adayı (dip)
        Not: Sayaç/cooldown yok; ek yük yaratmaz."""
        symbols = getattr(self, 'coin_symbols', [])
        dip_set, top_set = set(), set()
        green_tfs = [tf for tf, st in self.tf_states.items() if st == 1]
        red_tfs = [tf for tf, st in self.tf_states.items() if st == 2]
        if not green_tfs or not red_tfs:
            return dip_set, top_set

        def _tf_rank(tf):
            ranks = {'M1':1,'M3':2,'M5':3,'M15':4,'H1':5,'H4':6,'H6':7,'D1':8,'W1':9,'1M':10}
            return ranks.get(tf, 0)

        max_g = max((_tf_rank(tf) for tf in green_tfs), default=0)
        max_r = max((_tf_rank(tf) for tf in red_tfs), default=0)
        if max_g == 0 and max_r == 0:
            return dip_set, top_set

        major = 'green' if max_g > max_r else ('red' if max_r > max_g else 'tie')

        for symbol in symbols:
            # any up/down check; nötr yok sayılır
            g_up = False
            for tf in green_tfs:
                try:
                    s = self.signal_worker.get_signal(symbol, tf)
                except Exception:
                    s = None
                if s == 'up':
                    g_up = True
                    break
            r_down = False
            for tf in red_tfs:
                try:
                    s = self.signal_worker.get_signal(symbol, tf)
                except Exception:
                    s = None
                if s == 'down':
                    r_down = True
                    break
            # H1 filtresi: major=green için H1=down, major=red için H1=up
            try:
                h1_sig = self.signal_worker.get_signal(symbol, 'H1')
            except Exception:
                h1_sig = None
            if major == 'green':
                if g_up and r_down and h1_sig == 'down':
                    top_set.add(symbol)
            elif major == 'red':
                if r_down and g_up and h1_sig == 'up':
                    dip_set.add(symbol)
            else:  # tie: hiçbir taraf belirgin büyük değil; tutucu davran
                pass
        return dip_set, top_set

    def _update_combination_ui(self, rise_matches, fall_matches):
        # Trend etiketleri (dip/zirve) hesapla (koru)
        dip_set, top_set = self._evaluate_trend_reversals()

        def add_cell(parent, symbol, price, change, timestamp, dirc):
            # Koyu lacivert kapsül, yön rengine göre koyu ve hafif kalın outline
            bg = '#1c2340'
            if dirc == 'rise':
                border = '#0F4728'
            else:
                border = '#571616'
            # Değişim rengi: metin işaretine göre (+ yeşil, - kırmızı)
            def _parse_change_to_float(txt):
                try:
                    return float(str(txt).replace('%','').replace('+','').strip())
                except Exception:
                    return None
            _val = _parse_change_to_float(change)
            if _val is None:
                change_color = '#C9CFDD'
            else:
                change_color = '#36D06B' if _val >= 0 else '#FF6B6B'

            display_symbol = symbol if len(symbol) <= 10 else f"{symbol[:9]}…"
            # Sembol rengi: daha yumuşak sıcak ton (daha az parlak)
            text_color = '#D7C070'
            # Yeni listelenen coinler: isim mor (#ff00fe) – 30 gün boyunca
            try:
                if self._is_new_listing(symbol):
                    text_color = '#ff00fe'
            except Exception:
                pass

            frame = ctk.CTkFrame(
                parent,
                fg_color=bg,
                corner_radius=8,
                border_width=2,
                border_color=border,
                width=180,
                height=24
            )
            frame.pack(fill='x', padx=3, pady=1)
            frame.pack_propagate(False)

            row_frame = ctk.CTkFrame(frame, fg_color='transparent')
            row_frame.pack(fill='both', expand=True, padx=6, pady=2)
            row_frame.pack_propagate(False)

            # Trend ikonu: kurala göre panel tarafına yerleştir
            # - Zirveden düşüş (top_set): YÜKSELİŞ panelinde kırmızı ↘
            # - Dipten dönüş (dip_set): DÜŞÜŞ panelinde yeşil ↗
            show_top_on_rise = (dirc == 'rise' and symbol in top_set)
            show_dip_on_fall = (dirc == 'fall' and symbol in dip_set)
            if show_top_on_rise or show_dip_on_fall:
                icon = '↘' if show_top_on_rise else '↗'
                icon_color = '#D77A7A' if show_top_on_rise else '#7FC59B'
                icon_label = ctk.CTkLabel(row_frame, text=icon, text_color=icon_color, font=("Arial", 12, "bold"))
                icon_label.pack(side='left', padx=(0,4))
                # Çerçeveyi de belirginleştir (normalden daha kalın)
                try:
                    if show_top_on_rise:
                        # Zirveden düşüş için kırmızı (bir tık daha yumuşak)
                        frame.configure(border_color='#b30000', border_width=2)
                    else:
                        # Dipten dönüş için yeşil (kullanıcının rengi)
                        frame.configure(border_color='#009000', border_width=2)
                except Exception:
                    pass

            symbol_label = ctk.CTkLabel(
                row_frame,
                text=display_symbol,
                text_color=text_color,
                font=("Arial", 11, "bold"),
                anchor='w'
            )
            symbol_label.pack(side='left')
            try:
                # Kombinasyonda isim tıklanınca ana panel satırını seç/aç
                symbol_label.bind('<Button-1>', lambda _e, sym=symbol: self._toggle_row_selection(sym))
            except Exception:
                pass

            change_label = ctk.CTkLabel(
                row_frame,
                text=change,
                text_color=change_color,
                font=("Arial", 11, "bold"),
                anchor='center'
            )
            change_label.pack(side='left', padx=8)
            # Zaman etiketi kaldırıldı (son güncelleme üst barda gösteriliyor)
            return {
                'frame': frame,
                'parent': parent,
                'symbol_label': symbol_label,
                'change_label': change_label
            }
        from datetime import datetime
        now = datetime.now().strftime('%H:%M')
        price_map = {}
        for idx, sym in enumerate(self.coin_symbols):
            try:
                price_map[sym] = self.coin_rows[idx][1].cget('text')
            except Exception:
                price_map[sym] = '-'

        # Yüzde için: SADECE 24H % (Binance 24hr endpoint'inden gelen)
        tf_symbols = list(dict.fromkeys(list(rise_matches) + list(fall_matches)))
        pct_map = {}
        for sym in tf_symbols:
            try:
                idx = self.coin_symbols.index(sym)
                pct_map[sym] = self.coin_rows[idx][2].cget('text')
            except Exception:
                pct_map[sym] = '-'
        # Sıralama: 0=normal, 1=azalan (yüksek->düşük), 2=artan (düşük->yüksek)
        def _pct_to_float(s):
            try:
                return float(str(s).replace('%','').replace('+','').strip())
            except Exception:
                return float('nan')
        rise_state = self._combo_sort_state.get('rise', 0)
        fall_state = self._combo_sort_state.get('fall', 0)
        if rise_state == 1:
            rise_matches = sorted(rise_matches, key=lambda sym: _pct_to_float(pct_map.get(sym, 'nan')), reverse=True)
        elif rise_state == 2:
            rise_matches = sorted(rise_matches, key=lambda sym: _pct_to_float(pct_map.get(sym, 'nan')))
        if fall_state == 1:
            fall_matches = sorted(fall_matches, key=lambda sym: _pct_to_float(pct_map.get(sym, 'nan')), reverse=True)
        elif fall_state == 2:
            fall_matches = sorted(fall_matches, key=lambda sym: _pct_to_float(pct_map.get(sym, 'nan')))

        # Volume sıralaması aktifse, yüzde sıralamasını override et
        rise_vstate = self._combo_volume_sort_state.get('rise', 0)
        fall_vstate = self._combo_volume_sort_state.get('fall', 0)
        def _vol(sym):
            v = self._volume_map.get(sym)
            try:
                return float(v) if v is not None else float('nan')
            except Exception:
                return float('nan')
        if rise_vstate == 1:
            rise_matches = sorted(rise_matches, key=lambda sym: _vol(sym), reverse=True)
        elif rise_vstate == 2:
            rise_matches = sorted(rise_matches, key=lambda sym: _vol(sym))
        if fall_vstate == 1:
            fall_matches = sorted(fall_matches, key=lambda sym: _vol(sym), reverse=True)
        elif fall_vstate == 2:
            fall_matches = sorted(fall_matches, key=lambda sym: _vol(sym))

        # Artımsal güncelleme (flicker-free)
        desired = {
            'rise': list(rise_matches),
            'fall': list(fall_matches),
        }

        # Hedef kolon dağıtımı (dengeli): sadece hedef parent değişirse yeniden oluştur
        def _target_parent(side, idx_l, idx_r):
            if side == 'rise':
                return (self.left_col1, idx_l) if idx_l <= idx_r else (self.left_col2, idx_r)
            else:
                return (self.right_col1, idx_l) if idx_l <= idx_r else (self.right_col2, idx_r)

        # Güncelle/ekle
        for side in ('rise', 'fall'):
            items = self._combo_items.get(side, {})
            idx1 = idx2 = 0
            for i, sym in enumerate(desired[side]):
                # Hedef parent hesapla
                parent, idx_use = _target_parent(side, idx1, idx2)
                if parent in (self.left_col1, self.right_col1):
                    idx1 += 1
                else:
                    idx2 += 1
                entry = items.get(sym)
                price_txt = price_map.get(sym, '-')
                pct_txt = pct_map.get(sym, '-')
                dirc = 'rise' if side == 'rise' else 'fall'
                # Sınır rengi: trend setlerine göre
                border_color = '#571616'
                if dirc == 'rise':
                    border_color = '#b30000' if sym in top_set else '#0F4728'
                else:
                    border_color = '#009000' if sym in dip_set else '#571616'
                if entry is None or entry.get('parent') is not parent:
                    # Yoksa veya parent değişmişse: varsa eskiyi kaldır, yeni oluştur
                    if entry is not None:
                        try:
                            entry['frame'].destroy()
                        except Exception:
                            pass
                        items.pop(sym, None)
                    new_ent = add_cell(parent, sym, price_txt, pct_txt, now, dirc)
                    try:
                        new_ent['frame'].configure(border_color=border_color)
                    except Exception:
                        pass
                    items[sym] = new_ent
                else:
                    # Mevcut: in-place güncelle
                    try:
                        entry['change_label'].configure(text=pct_txt, text_color=('#36D06B' if _pct_to_float(pct_txt) >= 0 else '#FF6B6B'))
                        entry['symbol_label'].configure(text=(sym if len(sym) <= 10 else f"{sym[:9]}…"))
                        entry['frame'].configure(border_color=border_color)
                        # Sıra: yeniden pack ederek yeri güncelle (destroy etmeden)
                        entry['frame'].pack_forget()
                        entry['frame'].pack(fill='x', padx=3, pady=1)
                    except Exception:
                        pass
            # Silinecekler (artık listede olmayanlar)
            for sym_old in list(items.keys()):
                if sym_old not in desired[side]:
                    try:
                        items[sym_old]['frame'].destroy()
                    except Exception:
                        pass
                    items.pop(sym_old, None)
            self._combo_items[side] = items

    def _start_history_collection(self):
        self.after(5000, self._check_history_ready)

    def _check_history_ready(self):
        ready = all(len(q) >= self.history_length for q in self.coin_history.values() if q)
        if ready and len(self.coin_history) == len(self.coin_symbols):
            self._calculate_indicators()
            self._send_chat_message("RSI/MACD/hacim hesaplaması başladı!")
        else:
            self.after(5000, self._check_history_ready)
    def _cb_zoom_fullscreen(self):
        try:
            self.state('zoomed')
        except tk.TclError as e:
            logger.debug("Fullscreen zoom failed: %s", e)

    # Alarm yardımcıları kaldırıldı

    def _send_chat_message(self, msg):
        try:
            if hasattr(self.chat_panel, 'add_message'):
                self.chat_panel.add_message("AI", msg)
        except Exception as e:
            print(f"[SOHBET PANELİ]: Mesaj gönderilemedi. Hata: {e}")

    def _calculate_indicators(self):
        for symbol, history in self.coin_history.items():
            if len(history) < 20:
                continue
            df = pd.DataFrame(list(history))
            self.coin_indicators[symbol] = self._compute_indicators(df)

    @staticmethod
    def _compute_indicators(df):
        delta = df['price'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        ema12 = df['price'].ewm(span=12, adjust=False).mean()
        ema26 = df['price'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = macd.iloc[-1] if not macd.empty else None
        signal_value = signal.iloc[-1] if signal is not None and not signal.empty else None
        volume = df['price'].rolling(window=14).std().iloc[-1] if len(df) >= 14 else None
        return {
            'rsi': float(rsi.iloc[-1]) if not rsi.empty else None,
            'macd': float(macd_value) if macd_value is not None else None,
            'macd_signal': float(signal_value) if signal_value is not None else None,
            'volume': float(volume) if volume is not None else None
        }


