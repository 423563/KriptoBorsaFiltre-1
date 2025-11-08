# chat_panel.py
# Basit bir sohbet (chat) paneli bileşeni: kullanıcıdan metin alır, cevap üretir ve gösterir

import customtkinter as ctk

class ChatPanel(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="#101A5A")
        self.grid_rowconfigure(0, weight=1)  # Cevap kutusu tüm boşluğu alsın
        self.grid_rowconfigure(1, weight=0)  # Giriş kutusu sabit kalsın
        self.grid_columnconfigure(0, weight=1)
        self._img_refs = []  # Görsel referansları burada tutulacak
        self._pending_image = None  # WhatsApp tarzı gönderilmemiş görsel yolu

        import tkinter as tk
        self.text_area = tk.Text(self, bg="#16226A", fg="#FFF", wrap="word", font=("Arial", 12), borderwidth=0, highlightthickness=0)
        self.text_area.grid(row=0, column=0, sticky="nsew", padx=18, pady=(10,2))
        self.text_area.tag_configure("right", justify="right", lmargin1=120, rmargin=8)
        self.text_area.tag_configure("left", justify="left", lmargin1=8, rmargin=120)
        self.text_area.tag_configure("user_bubble", justify="right", lmargin1=120, rmargin=8, background="#16226A", foreground="#FFD700", font=("Arial", 15, "bold"))
        self.text_area.tag_configure("bot_bubble", justify="left", lmargin1=8, rmargin=120, background="#4CAF50", foreground="#000000", font=("Arial", 15, "bold"))
        self.text_area.tag_configure("emoji_gold", foreground="#FFD700", font=("Arial", 26, "bold"))
        self.text_area.insert("end", "Yapay Zeka Asistanına hoş geldin! Sorunu yazabilirsin...\n", ("left","bot_bubble"))
        self.text_area.config(state="disabled")

        # --- Kopyala/Yapıştır/Seçme desteği ---
        def _enable_copy_paste():
            # Metin seçimi zaten aktif, sadece kopyala/yapıştır kısayolları ve sağ tık menüsü ekle
            def copy(_event=None):
                try:
                    self.text_area.clipboard_clear()
                    text = self.text_area.get("sel.first", "sel.last")
                    self.text_area.clipboard_append(text)
                except tk.TclError:  # Seçili metin yoksa hata verme, sessizce geç
                    pass
                return "break"
            def paste(_event=None):
                # Sohbet geçmişi salt okunur, yapıştırmayı engelle
                return "break"
            def cut(_event=None):
                # Sohbet geçmişi salt okunur, kesmeyi engelle
                return "break"
            # Sağ tık menüsü
            menu = tk.Menu(self.text_area, tearoff=0)
            menu.add_command(label="Kopyala", command=copy)
            menu.add_command(label="Yapıştır", command=paste)
            menu.add_command(label="Kes", command=cut)
            def show_menu(event):
                menu.tk_popup(event.x_root, event.y_root)
            self.text_area.bind("<Button-3>", show_menu)
            # Kısayollar
            self.text_area.bind("<Control-c>", copy)
            self.text_area.bind("<Control-C>", copy)
            self.text_area.bind("<Control-v>", paste)
            self.text_area.bind("<Control-V>", paste)
            self.text_area.bind("<Control-x>", cut)
            self.text_area.bind("<Control-X>", cut)
        _enable_copy_paste()

        # --- Alt panel: WhatsApp tarzı, sade ve koyu mavi arka plan ---
        self.bottom_frame = ctk.CTkFrame(
            self, fg_color="#18206A", border_width=0, height=52
        )
        # Alt yazı alanını panelin altından 1.5 cm (~24px) yukarıda konumlandır
        self.bottom_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(6,48))
        # --- Sola hizalı ikonlar ve minimum boşluk ---
        self.bottom_frame.grid_columnconfigure(0, weight=0)
        self.bottom_frame.grid_columnconfigure(1, weight=0)
        self.bottom_frame.grid_columnconfigure(2, weight=0)
        self.bottom_frame.grid_columnconfigure(3, weight=1)  # Entry maksimum genişlik
        self.bottom_frame.grid_columnconfigure(4, weight=0)

        self.emoji_btn = ctk.CTkButton(
            self.bottom_frame, text="😊", width=24, height=24, fg_color="#16226A", text_color="#FFF", corner_radius=6, command=self.open_emoji_popup
        )
        self.emoji_btn.grid(row=0, column=0, padx=(2,2), pady=3)

        self.add_image_btn = ctk.CTkButton(
            self.bottom_frame, text="+", width=24, height=24, fg_color="#16226A", text_color="#FFF", corner_radius=6, command=self.on_add_image
        )
        self.add_image_btn.grid(row=0, column=1, padx=(2,2), pady=3)

        self.memory_btn = ctk.CTkButton(
            self.bottom_frame, text="🧠", width=24, height=24, fg_color="#16226A", text_color="#FFD700", corner_radius=6, command=self.open_memory_popup
        )
        self.memory_btn.grid(row=0, column=2, padx=(2,2), pady=3)

        # Entry hemen ikonların yanında başlasın
        self.entry = ctk.CTkEntry(
            self.bottom_frame, fg_color="#1B2A6A", text_color="#FFF", placeholder_text="Mesajınızı yazın..."
        )
        self.entry.grid(row=0, column=3, sticky="ew", padx=(2,2), pady=3)
        self.entry.bind("<Return>", self.on_enter)

        self.send_icon = "\u27A4"  # Unicode ok simgesi
        self.send_btn = ctk.CTkButton(
            self.bottom_frame, text=self.send_icon, width=32, height=28, fg_color="#3355FF", text_color="#FFF", corner_radius=14, command=self.on_send_click, font=("Arial", 14, "bold")
        )
        self.send_btn.grid(row=0, column=4, padx=(2,8), pady=3)

    def open_memory_popup(self):
        import tkinter as tk
        import json
        import os
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)  # Tamamen borderless, başlık yok
        popup.resizable(True, True)   # Köşeden büyütülebilir
        popup.configure(bg="#18206A")
        popup.geometry("1000x700+150+50")  # Daha büyük ve ortalanmış pencere
        # Ana frame
        frame = tk.Frame(popup, bg="#18206A", bd=0, highlightthickness=0)
        frame.pack(fill="both", expand=True)
        label = tk.Label(frame, text="Yapay zekaya özel kurallarını ve kendini tanıtan bilgileri madde madde yazabilirsin:", bg="#18206A", fg="#FFD700", font=("Arial", 14, "bold"))
        label.pack(pady=(18, 7))
        text_area = tk.Text(frame, wrap="word", bg="#223066", fg="#FFF", font=("Arial", 14), relief="flat", borderwidth=0)
        text_area.pack(fill="both", expand=True, padx=24, pady=(0,18))
        # Var olan memory varsa yükle
        memory_path = os.path.join(os.path.dirname(__file__), "memory.json")
        if os.path.exists(memory_path):
            try:
                with open(memory_path, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                content = memory.get("content", "")
                if not content.strip():
                    text_area.insert("1.0", "1- ")
                else:
                    text_area.insert("1.0", content)
            except Exception as err:
                print(f"[MEMORY LOAD ERROR]: {err}")
        else:
            text_area.insert("1.0", "1- ")
        # Butonlar alt kısımda, ortada ve her zaman görünür
        btn_frame = tk.Frame(frame, bg="#18206A")
        btn_frame.pack(side="bottom", pady=(0, 14))
        save_btn = tk.Button(btn_frame, text="Kaydet", command=lambda: save_memory(), bg="#4CAF50", fg="#FFF", font=("Arial", 13, "bold"), width=10)
        save_btn.pack(side="left", padx=12)
        close_btn = tk.Button(btn_frame, text="Kapat", command=popup.destroy, bg="#444", fg="#FFF", font=("Arial", 12), width=10)
        close_btn.pack(side="left", padx=12)
        def save_memory():
            file_content = text_area.get("1.0", "end").strip()
            try:
                with open(memory_path, "w", encoding="utf-8") as file_obj:
                    json.dump({"content": file_content}, file_obj, ensure_ascii=False, indent=2)
                popup.destroy()
            except Exception as save_err:
                print(f"[MEMORY SAVE ERROR]: {save_err}")

    def open_emoji_popup(self):
        # Borderless emoji popup, dışarı tıklayınca kapanır, temel yüz emojileri gösterir
        import tkinter as tk
        import json
        import os
        self.update_idletasks()
        # Temel yüz ifadeleri (emoji_list.json'a ihtiyaç olmadan doğrudan listede):
        emoji_list = [
            "😀", "😁", "😂", "😊", "😍", "😘", "😜", "🤔", "😎", "😢", "😡", "😱", "😇", "🥳", "🥺", "🙃", "😅", "😏", "😴"
        ]
        cols = 6
        rows = (len(emoji_list) + cols - 1) // cols
        panel_x = self.winfo_rootx()
        panel_y = self.winfo_rooty()
        panel_width = self.winfo_width()
        entry_y = self.entry.winfo_rooty() - panel_y
        popup_width = min(panel_width - 24, cols * 60)
        popup_height = rows * 60 + 24
        popup_x = panel_x + (panel_width - popup_width) // 2
        popup_y = panel_y + entry_y - popup_height - 8
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)  # Borderless, başlık ve simge yok
        popup.configure(bg="#101A5A")  # Lacivert arka plan
        popup.geometry(f"{popup_width}x{popup_height}+{popup_x}+{popup_y}")
        # Emoji butonlarını oluştur (sade, renksiz, küçük boyut)
        for idx, char in enumerate(emoji_list):
            row = idx // cols
            col = idx % cols
            btn = tk.Button(
                popup,
                text=char,
                font=("Arial", 22),
                width=2, height=1,
                command=lambda e=char: self.insert_emoji(e),  # Sadece emoji ekle, popup kapanmasın
                bg="#101A5A", fg="#FFD700", relief="flat", activebackground="#223399", borderwidth=0, highlightthickness=0
            )
            btn.grid(row=row, column=col, padx=4, pady=4)
        # Dışarı tıklayınca popup kapanır
        def click_outside(event):
            if not (popup.winfo_rootx() <= event.x_root <= popup.winfo_rootx() + popup.winfo_width() and
                    popup.winfo_rooty() <= event.y_root <= popup.winfo_rooty() + popup.winfo_height()):
                popup.destroy()
        popup.bind_all("<Button-1>", click_outside)
        popup.focus_set()
        popup.wait_window()

    def insert_emoji(self, emoji):
        current = self.entry.get()
        self.entry.delete(0, "end")
        self.entry.insert(0, current + emoji)

    def on_enter(self, _event=None):
        from PIL import Image, ImageTk
        import re
        user_input = self.entry.get().strip()
        has_image = bool(self._pending_image)
        emoji_pattern = r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+"
        has_emoji = bool(re.search(emoji_pattern, user_input))
        has_text = bool(user_input.strip())
        if not has_text and not has_image:
            return
        self.entry.delete(0, "end")
        self.text_area.config(state="normal")
        # Önce görsel ekle (varsa)
        if has_image:
            try:
                pil_img = Image.open(self._pending_image)
                pil_img.thumbnail((180, 120))
                tk_img = ImageTk.PhotoImage(pil_img)
                self._img_refs.append(tk_img)
                self.text_area.insert("end", " " * 68)
                self.text_area.image_create("end", image=tk_img)
                self.text_area.insert("end", "\n", ("right","user_bubble"))
            except Exception as e:
                print(f"[IMG LOAD ERROR]: {e}")
                self.text_area.insert("end", f"[Görsel yüklenemedi: {self._pending_image}]\n", ("right","user_bubble"))
            self._pending_image = None
        # Sonra metni ekle (varsa)
        if has_text:
            last_idx = 0
            for match in re.finditer(emoji_pattern, user_input):
                start, end = match.span()
                if start > last_idx:
                    self.text_area.insert("end", user_input[last_idx:start], ("right","user_bubble"))
                self.text_area.insert("end", user_input[start:end], ("right","user_bubble","emoji_gold"))
                last_idx = end
            if last_idx < len(user_input):
                self.text_area.insert("end", user_input[last_idx:], ("right","user_bubble"))
            self.text_area.insert("end", "\n")
        self.text_area.config(state="disabled")
        self.text_area.see("end")
        # Bot cevabı (duyarlı)
        if has_image and not has_text:
            # Görsel dosya adı üzerinden grafik olup olmadığını algıla
            img_path = str(self._pending_image) if self._pending_image else ""
            lower_img = img_path.lower()
            if any(word in lower_img for word in ["chart", "grafik", "screenshot", "tradingview"]):
                response = "Bir coin grafik görseli aldım! Otomatik analiz özelliği şu an aktif değil, ama yakında görselden analiz yapabileceğim."
            else:
                response = "Bir görsel aldım! İstersen bu görsel hakkında yorum yapabilirim."
        elif has_emoji and not (has_image or (user_input.strip().replace(re.findall(emoji_pattern, user_input)[0], '') if has_emoji else '').strip()):
            # Emojiye göre duygu analizi
            emoji = re.findall(emoji_pattern, user_input)[0]
            emoji_feelings = {
                "mutlu": ["😊", "😄", "😃", "😁", "🙂", "😸", "😺"],
                "üzgün": ["😢", "😭", "😞", "😔", "😿"],
                "aşk": ["😍", "🥰", "❤️", "😘", "💕"],
                "öfke": ["😡", "😠", "🤬", "😾"],
                "şaşkın": ["😮", "😯", "😲", "😳", "🤔", "😕"],
                "kutlama": ["🎉", "🥳", "🎊"],
                "alkış": ["👏", "🙌", "👍", "👌"],
                "nötr": ["😐", "🤖", "😶"]
            }
            feeling_reply = {
                "mutlu": "Ne güzel bir gülümseme! Senin de günün güzel geçsin 😊",
                "üzgün": "Üzgün görünüyorsun, yanında olduğumu bil lütfen…",
                "aşk": "Çok sıcak bir mesaj, teşekkürler! ❤️",
                "öfke": "Sanırım biraz kızgınsın. Dertleşmek istersen buradayım.",
                "şaşkın": "Kafanda soru işaretleri mi var? Yardımcı olabilirim!",
                "kutlama": "Kutlama zamanı! Tebrikler! 🎉",
                "alkış": "Alkışlar sana! 👏",
                "nötr": "Buradayım, her zaman dinliyorum! 🤖"
            }
            found = False
            for feeling, emojilist in emoji_feelings.items():
                if emoji in emojilist:
                    response = feeling_reply[feeling]
                    found = True
                    break
            if not found:
                response = f"Emoji gönderdin! {emoji}"
        elif has_image and has_text:
            response = "Hem görsel hem de metin gönderdin! Metin için analiz başlatıyorum, görseli kaydettim."
            # İsteğe bağlı: metin analizini de ekleyebilirsin
        else:
            response = self.generate_response(user_input)
        self.after(300, self.add_bot_reply, response)

    def add_bot_reply(self, text):
        self.text_area.config(state="normal")
        # Emoji karakterlerini altın sarısı ile işaretle
        import re
        emoji_pattern = r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+"
        last_idx = 0
        for match in re.finditer(emoji_pattern, text):
            start, end = match.span()
            if start > last_idx:
                self.text_area.insert("end", text[last_idx:start], ("left","bot_bubble"))
            self.text_area.insert("end", text[start:end], ("left","bot_bubble","emoji_gold"))
            last_idx = end
        if last_idx < len(text):
            self.text_area.insert("end", text[last_idx:], ("left","bot_bubble"))
        self.text_area.insert("end", "\n")
        self.text_area.config(state="disabled")
        self.text_area.see("end")

    @staticmethod
    def generate_response(user_input):
        import os
        import json
        import requests

        # Memory'den context oku
        memory_path = os.path.join(os.path.dirname(__file__), "memory.json")
        memory_content = ""
        if os.path.exists(memory_path):
            try:
                with open(memory_path, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                memory_content = memory.get("content", "").strip()
            except (OSError, json.JSONDecodeError):  # Dosya okunamazsa veya json bozuksa hafızayı boş bırak
                memory_content = ""

        # Prompt oluştur
        if memory_content:
            prompt = f"Kullanıcı kendini şöyle tanıttı ve kurallar yazdı:\n{memory_content}\n---\nSoru: {user_input}\nCevabın bu hafıza kurallarını dikkate almalı."
        else:
            prompt = user_input

        # Ollama API endpoint
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "[Ollama'dan yanıt alınamadı]")
            else:
                return f"[Ollama API Hatası: {response.status_code}]"
        except Exception as e:
            return f"[Ollama bağlantı hatası: {str(e)}]"

    def on_send_click(self):
        self.on_enter()

    def on_add_image(self):
        # Görsel seçildiğinde küçük bir önizleme paneli aç, ekstra buton yok
        import tkinter as tk
        import tkinter.filedialog as fd
        from PIL import Image, ImageTk
        filetypes = [
            ("Resim dosyaları", "*.png *.jpg *.jpeg *.gif *.bmp"),
            ("Tüm dosyalar", "*.*")
        ]
        filename = fd.askopenfilename(title="Görsel seç", filetypes=filetypes)
        if not filename:
            return
        # Seçilen görselin yolunu sakla
        self._pending_image = filename
        # Görseli yükle ve boyutunu al
        try:
            pil_img = Image.open(filename)
            pil_img.thumbnail((240, 140))
            tk_img = ImageTk.PhotoImage(pil_img)
            img_w, img_h = pil_img.size
        except Exception as e:
            print(f"[IMG PREVIEW ERROR]: {e}")
            tk_img = None
            img_w, img_h = 120, 80
        # Panel boyutunu görseli saracak şekilde ayarla (minimum padding)
        pad_x, pad_y = 8, 8  # minimum padding
        popup_width = img_w + pad_x * 2
        popup_height = img_h + pad_y * 2
        # Paneli konumlandır: chat panelinin hemen üstünde, ortalanmış
        self.update_idletasks()
        panel_x = self.winfo_rootx()
        panel_y = self.winfo_rooty()
        panel_width = self.winfo_width()
        entry_y = self.entry.winfo_rooty() - panel_y
        popup_x = panel_x + (panel_width - popup_width) // 2
        popup_y = panel_y + entry_y - popup_height - 8
        preview = tk.Toplevel(self)
        preview.title("Görsel Önizleme")
        preview.overrideredirect(True)
        preview.geometry(f"{popup_width}x{popup_height}+{popup_x}+{popup_y}")
        preview.configure(bg="#101A5A")
        # Görseli preview panelinin sağında göster
        img_label = tk.Label(preview, image=tk_img, bg="#101A5A")
        img_label.image = tk_img
        img_label.place(x=popup_width - img_w - pad_x, y=pad_y)
        # Panel sadece tıklanınca kapanacak, otomatik kapanma yok
        def close_preview(_event=None):
            preview.destroy()
        preview.bind("<Button-1>", close_preview)
        preview.focus_set()
        preview.wait_window()

if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Sohbet Paneli Test")
    chat = ChatPanel(root)
    chat.pack(fill="both", expand=True)
    root.mainloop()
