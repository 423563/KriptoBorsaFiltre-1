"""
Alarm popup ve alarm listesi mantığının anlık yedeği.
Bu dosya, mevcut ui.py içindeki alarm ile ilgili metotları bir mixin sınıfında saklar.
İleride yeni panele tekrar entegre ederken bu sınıfı miras alıp metotları kullanabiliriz.

Notlar:
- Kod, doğrudan çalıştırılabilir olmak için gerekli importları içerir; ancak UI ile bağlanmadığı sürece çalıştırılmaz.
- self üzerinde beklenen alanlar: `_alarm_popup`, `_alarm_info_label`, `_alarm_list_frame`, `_alarm_panel_main`, `balance`, `_user_selected_timeframes`.
- `USER_STATE_PATH` bu dosyada da tanımlıdır; UI tarafında aynısını kullanıyorsan aynı değere işaret eder.
"""
from __future__ import annotations
import os
import json
import uuid
import time as _time
import tkinter as tk
import customtkinter as ctk

USER_STATE_PATH = os.path.join(os.path.dirname(__file__), "user_state.json")


class AlarmMixinSnapshot:
    def _on_combo_signal_click(self, event, signal):
        try:
            self._open_alarm_popup(signal)
        except Exception as err:
            print(f"[ALARM POPUP ERROR]: {err}")
        return "break"

    def _open_alarm_popup(self, signal):
        """Seçilen kombinasyon sinyali için alarm kurma popup'ı tekil olarak aç veya öne getir."""
        # VAR OLAN POPUP'I KAPAT VE YENİSİNİ OLUŞTUR (buton komutları güncel kalsın)
        try:
            if getattr(self, "_alarm_popup", None) is not None and self._alarm_popup.winfo_exists():
                self._alarm_popup.destroy()
        except tk.TclError:
            pass
        # Yeni popup oluştur
        popup = tk.Toplevel(self)
        self._alarm_popup = popup
        popup.title("Alarm Kur")
        popup.configure(bg="#18206A")
        # Ekranın sağ alt köşesine konumlandır (sağdan ve alttan 40px boşluk)
        popup.update_idletasks()
        popup_width = popup.winfo_width() or 714
        popup_height = popup.winfo_height() or 260

        # Ekran çözünürlüğünü al
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()

        # Sağ alt köşe + 200px boşluk
        x_position = screen_width - popup_width - 200
        y_position = screen_height - popup_height - 40

        popup.geometry(f"714x260+{x_position}+{y_position}")
        # Odak ve modal davranış
        try:
            popup.transient(self)
            popup.attributes("-topmost", True)
            popup.after(200, lambda: popup.attributes("-topmost", False))
            popup.grab_set()
            popup.focus_force()
        except tk.TclError:
            pass

        def _on_close():
            try:
                popup.destroy()
            finally:
                self._alarm_popup = None
                self._alarm_info_label = None

        popup.protocol("WM_DELETE_WINDOW", _on_close)
        try:
            popup.bind("<Escape>", lambda *_: (_on_close(), "break"))
        except tk.TclError:
            pass
        # Başlık
        title = tk.Label(popup, text="Alarm Kur", bg="#18206A", fg="#FFD700", font=("Arial", 16, "bold"))
        title.pack(pady=(12, 8))
        # Bilgi
        info = tk.Label(
            popup,
            text=f"Sembol: {signal.get('symbol','-')}    Tür: {signal.get('type','-')}",
            bg="#18206A", fg="#FFFFFF", font=("Arial", 12)
        )
        info.pack(pady=(0, 10))
        self._alarm_info_label = info
        # Buton grupları
        up_frame = tk.LabelFrame(popup, text="YÜKSELİŞ", bg="#18206A", fg="#FFD700", font=("Arial", 11, "bold"))
        up_frame.pack(fill="x", padx=12, pady=(4, 6))
        down_frame = tk.LabelFrame(popup, text="DÜŞÜŞ", bg="#18206A", fg="#FFD700", font=("Arial", 11, "bold"))
        down_frame.pack(fill="x", padx=12, pady=(0, 10))
        tf_map = [
            ("5 DK", "M5"),
            ("15 DK", "M15"),
            ("1 ST", "H1"),
            ("4 ST", "H4"),
            ("6 ST", "H6"),
            ("1 G", "D1"),
        ]

        def add_btn(parent, text, tfc, direction):
            btn = tk.Button(
                parent, text=f"{text} {direction}",
                bg="#3355FF" if direction == "YÜKSELİŞ" else "#FF5252",
                fg="#FFFFFF", activebackground="#223066", relief="flat", padx=8, pady=4,
                command=lambda: self._save_alarm(signal.get('symbol'), "UP" if direction == "YÜKSELİŞ" else "DOWN", tfc, popup)
            )
            btn.pack(side="left", padx=6, pady=6)

        for label_txt, tf_code in tf_map:
            add_btn(up_frame, label_txt, tf_code, "YÜKSELİŞ")
        for label_txt, tf_code in tf_map:
            add_btn(down_frame, label_txt, tf_code, "DÜŞÜŞ")

        close_btn = tk.Button(popup, text="Kapat", command=lambda: popup.event_generate("<<CloseAlarm>>") or popup.destroy(), bg="#444", fg="#FFF")
        close_btn.pack(pady=(0, 10))

    def _save_alarm(self, symbol, direction, tf_code, popup=None):
        """Alarmı user_state.json içine kaydet."""
        # Mevcut durumu oku
        try:
            with open(USER_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
        alarms = state.get("alarms", [])
        created_at = _time.strftime("%Y-%m-%d %H:%M")
        alarms.append({
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "direction": direction,
            "tf": tf_code,
            "created_at": created_at,
            "enabled": True
        })
        state["alarms"] = alarms
        # Var olan anahtarları koru
        state.setdefault("balance", getattr(self, "balance", 1000.0))
        state.setdefault("selected_timeframes", list(getattr(self, "_user_selected_timeframes", [])))
        try:
            with open(USER_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ALARM SAVE ERROR]: {e}")
        # Küçük bir bildirim
        try:
            toast = tk.Toplevel(self)
            toast.overrideredirect(True)
            toast.configure(bg="#223066")
            toast.geometry("260x36+40+40")
            msg = tk.Label(toast, text=f"Alarm kaydedildi: {symbol} {direction} {tf_code}", bg="#223066", fg="#FFF", font=("Arial", 10))
            msg.pack(fill="both", expand=True, padx=8, pady=6)
            toast.after(1500, toast.destroy)
        except Exception:
            pass
        # Listeyi yenile (varsa)
        try:
            self._render_alarm_list_panel()
        except Exception:
            pass
        # Kayıt sırasında ses çalma yok; ses yalnızca koşul gerçekleştiğinde çalınacak
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    def _load_alarms(self):
        try:
            with open(USER_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
        return state.get("alarms", [])

    def _check_trigger_for(self, symbol, tf_code, sig):
        """Mevcut sinyale göre kayıtlı alarmı tetikle. sig: 'up' | 'down' | 'neutral'"""
        try:
            if not hasattr(self, "_alarm_triggered"):
                self._alarm_triggered = set()  # {(symbol, direction, tf)}
            if sig not in ("up", "down"):
                # Nötr durumda tetik kilidini kaldır (gelecek geçişlerde tekrar çalabilsin)
                to_remove = {(s, d, t) for (s, d, t) in self._alarm_triggered if s == symbol and t == tf_code}
                if to_remove:
                    self._alarm_triggered -= to_remove
                # Varsa ilgili satır vurgularını da kaldır
                try:
                    for a in self._load_alarms():
                        if a.get("symbol") == symbol and a.get("tf") == tf_code:
                            self._highlight_alarm_row(a.get("id"), False)
                except Exception:
                    pass
                return
            direction = "UP" if sig == "up" else "DOWN"
            key = (symbol, direction, tf_code)
            if key in self._alarm_triggered:
                return  # Aynı koşul için tekrar çalma
            alarms = self._load_alarms()
            matches = [
                a for a in alarms if (
                    a.get("symbol") == symbol and a.get("direction") == direction and a.get("tf") == tf_code and a.get("enabled", True)
                )
            ]
            has_match = any(
                a.get("symbol") == symbol and a.get("direction") == direction and a.get("tf") == tf_code and a.get("enabled", True)
                for a in matches
            )
            if has_match:
                # Ses çal ve küçük toast göster
                try:
                    self._play_alarm_sound(direction)
                except Exception:
                    pass
                try:
                    toast = tk.Toplevel(self)
                    toast.overrideredirect(True)
                    toast.configure(bg="#223066")
                    toast.geometry("280x36+50+50")
                    msg = tk.Label(toast, text=f"ALARM: {symbol} {direction} {tf_code}", bg="#223066", fg="#FFF", font=("Arial", 10))
                    msg.pack(fill="both", expand=True, padx=8, pady=6)
                    toast.after(1500, toast.destroy)
                except Exception:
                    pass
                self._alarm_triggered.add(key)
                # Eşleşen satır(lar)ı vurgula
                try:
                    for a in matches:
                        self._highlight_alarm_row(a.get('id'), True, direction)
                except Exception:
                    pass
        except Exception as e:
            print(f"[ALARM TRIGGER ERROR]: {e}")

    def _highlight_alarm_row(self, alarm_id, active=True, direction=None):
        """Alarm satırını vurgula/normalleştir. UP=yeşil, DOWN=kırmızı."""
        try:
            if not hasattr(self, "_alarm_row_map"):
                return
            row = self._alarm_row_map.get(alarm_id)
            if not row:
                return
            if active:
                if direction == "UP":
                    color = "#355E00"  # yeşil vurgusu
                elif direction == "DOWN":
                    color = "#6A1020"  # kırmızı vurgusu
                else:
                    color = "#355E00"
            else:
                color = "#151E4A"
            row.configure(fg_color=color)
        except Exception:
            pass

    def _toggle_alarm_enabled(self, alarm_id):
        """Verilen id'li alarmın enabled durumunu tersine çevir ve listeyi yenile."""
        try:
            with open(USER_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
        alarms = state.get("alarms", [])
        updated = False
        for a in alarms:
            if a.get("id") == alarm_id:
                a["enabled"] = not a.get("enabled", True)
                updated = True
                break
        if updated:
            state["alarms"] = alarms
            try:
                with open(USER_STATE_PATH, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[ALARM TOGGLE SAVE ERROR]: {e}")
        try:
            self._render_alarm_list_panel()
        except Exception:
            pass

    def _render_alarm_list_panel(self):
        """Sağdaki alarm panelinde kayıtlı alarmları listeler (self._alarm_list_frame içinde)."""
        if not hasattr(self, "_alarm_list_frame") or self._alarm_list_frame is None:
            return
        # Önce mevcut çocukları temizle
        try:
            for w in self._alarm_list_frame.winfo_children():
                w.destroy()
        except Exception:
            pass
        # Veriyi oku
        try:
            with open(USER_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
        alarms = state.get("alarms", [])
        if not alarms:
            # Yalnızca boşken başlığı göster
            header = ctk.CTkLabel(self._alarm_list_frame, text="Kayıtlı Alarmlar", font=("Arial", 14, "bold"), text_color="#FFD700", fg_color="#101A5A")
            header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 2))
            empty = ctk.CTkLabel(self._alarm_list_frame, text="Henüz alarm yok", font=("Arial", 12), text_color="#EEE", fg_color="#101A5A")
            empty.grid(row=1, column=0, sticky="w", padx=10, pady=6)
            return
        # İki sütunlu düzen
        try:
            self._alarm_list_frame.grid_columnconfigure(0, weight=1)
            self._alarm_list_frame.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        # Satır map'ini sıfırla
        self._alarm_row_map = {}
        # Satırları oluştur (iki sütuna zig-zag dağıt)
        for idx, alarm in enumerate(alarms, start=1):
            arrow = '↑' if alarm.get('direction') == 'UP' else '↓'
            text = f"{alarm.get('symbol','-')} {arrow} {alarm.get('tf','-')}"
            enabled = alarm.get('enabled', True)
            # Her alarm için bir satır çerçevesi oluştur (vurgulama için)
            row_frame = ctk.CTkFrame(self._alarm_list_frame, fg_color="#151E4A")
            # sütun/row hesapla: 0,1,0,1...
            col = 0 if (idx - 1) % 2 == 0 else 1
            row_grid = (idx - 1) // 2
            # Kenar boşluklarını minimuma indir (metin için alan aç)
            outer_padx = (0, 1) if col == 0 else (1, 0)
            row_frame.grid(row=row_grid, column=col, sticky="ew", padx=outer_padx, pady=1)
            row_frame.grid_columnconfigure(0, weight=1)
            row_frame.grid_columnconfigure(1, weight=0)
            row_frame.grid_columnconfigure(2, weight=0)
            row_frame.grid_columnconfigure(3, weight=0)
            self._alarm_row_map[alarm.get('id')] = row_frame
            lbl = ctk.CTkLabel(row_frame, text=text, font=("Arial", 11), text_color="#FFFFFF", fg_color="transparent")
            lbl.grid(row=0, column=0, sticky="ew", padx=(3, 1), pady=1)
            # Dur/Aktif Et butonu (mini pill, metinsiz)
            def make_toggle(a):
                return lambda: self._toggle_alarm_enabled(a.get('id'))
            toggle_color = "#FF8C00" if enabled else "#4CAF50"
            toggle_btn = ctk.CTkButton(
                row_frame, text="", width=16, height=14,
                fg_color=toggle_color, hover_color="#2746D3", text_color="#FFF",
                corner_radius=8, command=make_toggle(alarm)
            )
            toggle_btn.grid(row=0, column=1, sticky="e", padx=(2, 2), pady=1)
            # Test butonu
            def make_test(a):
                return lambda: self._play_alarm_sound(a.get('direction'))
            test_btn = ctk.CTkButton(row_frame, text="🔊", width=20, height=16, fg_color="#3355FF", hover_color="#2746D3", text_color="#FFF", command=make_test(alarm))
            test_btn.grid(row=0, column=2, sticky="e", padx=(2, 2), pady=1)
            # Sil butonu
            def make_delete(a):
                return lambda: self._delete_alarm(a.get('id'), a)
            btn = ctk.CTkButton(row_frame, text="X", width=16, height=14, fg_color="#FF5252", hover_color="#E04848", text_color="#FFF", command=make_delete(alarm))
            btn.grid(row=0, column=3, sticky="e", padx=(2, 4), pady=1)

    @staticmethod
    def _play_alarm_sound(direction):
        """Yön UP/DOWN'a göre uygun sesi çalar. Önce winsound, yoksa playsound (mevcutsa)."""
        sound_file = 'up_alert.wav' if (direction == 'UP') else 'down_alert.wav'
        base_dir = os.path.dirname(__file__)
        path = os.path.join(base_dir, 'sounds', sound_file)
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            try:
                import importlib.util
                if importlib.util.find_spec("playsound") is None:
                    raise ImportError("playsound not available")
                from playsound import playsound
                playsound(path, block=False)
            except Exception as inner:
                print(f"[ALARM SOUND ERROR]: {e} / fallback: {inner}")

    def _delete_alarm(self, alarm_id, alarm_fallback=None):
        """Verilen id'ye sahip alarmı sil ve paneli yenile."""
        if not alarm_id and not alarm_fallback:
            return
        try:
            with open(USER_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
        alarms = state.get("alarms", [])
        if alarm_id:
            new_alarms = [a for a in alarms if a.get('id') != alarm_id]
        else:
            sf = alarm_fallback or {}
            def same(a):
                return a.get('symbol') == sf.get('symbol') and a.get('direction') == sf.get('direction') and a.get('tf') == sf.get('tf')
            removed = False
            new_alarms = []
            for a in alarms:
                if not removed and same(a):
                    removed = True
                    continue
                new_alarms.append(a)
        state["alarms"] = new_alarms
        try:
            with open(USER_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ALARM DELETE ERROR]: {e}")
        try:
            toast = tk.Toplevel(self)
            toast.overrideredirect(True)
            toast.configure(bg="#223066")
            toast.geometry("220x32+40+80")
            msg = tk.Label(toast, text="Alarm silindi", bg="#223066", fg="#FFF", font=("Arial", 10))
            msg.pack(fill="both", expand=True, padx=8, pady=6)
            toast.after(1200, toast.destroy)
        except Exception:
            pass
        try:
            self._render_alarm_list_panel()
        except Exception:
            pass


if __name__ == "__main__":
    # Basit kontrol: Dosya başarıyla import ediliyor mu?
    print("Alarm popup snapshot hazır (mixin).")
