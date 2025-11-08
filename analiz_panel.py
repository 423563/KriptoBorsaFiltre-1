import customtkinter as ctk

class AnalizPanel(ctk.CTkFrame):
    def __init__(self, master, width=340, height=600, *args, **kwargs):
        super().__init__(master, fg_color="#16224A", corner_radius=12, width=width, height=height, *args, **kwargs)
        self.pack_propagate(False)
        self.grid_rowconfigure(0, weight=0)
        for i in range(1, 16):
            self.grid_rowconfigure(i, weight=1)
        self.analiz_headers = ["Sembol", "Sinyal", "Trend", "RSI", "MACD", "Hacim", "Risk"]
        for i, h in enumerate(self.analiz_headers):
            header = ctk.CTkLabel(self, text=h, font=("Arial", 13, "bold"), text_color="#FFD700", fg_color="#223066", width=60)
            header.grid(row=0, column=i, padx=2, pady=3, sticky="nsew")
        self.data_labels = []
        self.max_rows = 12
        self._init_empty_grid()

    def _init_empty_grid(self):
        # Başlık altına boş grid hazırla
        for row in range(1, self.max_rows+1):
            row_labels = []
            for col in range(len(self.analiz_headers)):
                empty = ctk.CTkLabel(self, text="", font=("Arial", 12), fg_color="#16224A", width=60)
                empty.grid(row=row, column=col, padx=2, pady=1, sticky="nsew")
                row_labels.append(empty)
            self.data_labels.append(row_labels)

    def update_signals(self, signal_list):
        # signal_list: [{"Sembol":..., "Sinyal":..., ..., "Renk": "kırmızı"/"yeşil"}]
        # Önce tüm hücreleri temizle
        for row_labels in self.data_labels:
            for lbl in row_labels:
                lbl.configure(text="", fg_color="#16224A")
        # Yeni veriyi yaz
        for row_idx, signal in enumerate(signal_list[:self.max_rows]):
            row_color = "#16224A"  # Varsayılan
            if signal.get("Renk") == "kırmızı":
                row_color = "#8B0000"  # Koyu kırmızı
            elif signal.get("Renk") == "yeşil":
                row_color = "#006400"  # Koyu yeşil
            for col_idx, key in enumerate(self.analiz_headers):
                val = signal.get(key, "")
                self.data_labels[row_idx][col_idx].configure(text=str(val), fg_color=row_color)
