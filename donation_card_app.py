import os
import sys
import json
import math
import time
import shutil
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import fitz  # PyMuPDF
from PIL import Image, ImageTk

# --- Helper Functions for Myanmar Formatting & Typography ---

MYANMAR_DIGITS = {'0': '၀', '1': '၁', '2': '၂', '3': '၃', '4': '၄', '5': '၅', '6': '၆', '7': '၇', '8': '၈', '9': '၉'}

def to_myanmar_digits(text: str) -> str:
    """Converts Western digits (0-9) in a string to Myanmar numerals (၀-၉)."""
    if pd.isna(text) or text is None:
        return ""
    text_str = str(text)
    for eng, mm in MYANMAR_DIGITS.items():
        text_str = text_str.replace(eng, mm)
    return text_str

def format_currency_number(amount: any, suffix: str = "  - ကျပ်") -> str:
    """Formats numeric amount with commas and Myanmar digits."""
    if pd.isna(amount) or amount is None or str(amount).strip() == "":
        return ""
    try:
        num = float(amount)
        if num.is_integer():
            formatted_num = f"{int(num):,}"
        else:
            formatted_num = f"{num:,.2f}"
    except (ValueError, TypeError):
        formatted_num = str(amount)
    
    mm_num = to_myanmar_digits(formatted_num)
    if suffix and not pd.isna(suffix):
        return f"{mm_num}{suffix}"
    return mm_num

def wrap_myanmar_text(text: str, max_chars: int = 40) -> list:
    """Wraps Myanmar text into multiple lines."""
    if pd.isna(text) or text is None or str(text).strip() == "":
        return [""]
    text_str = str(text).strip()
    if "\n" in text_str or "\\n" in text_str:
        raw_lines = text_str.replace("\\n", "\n").split("\n")
        final_lines = []
        for line in raw_lines:
            final_lines.extend(wrap_single_line(line, max_chars))
        return final_lines
    else:
        return wrap_single_line(text_str, max_chars)

def wrap_single_line(line: str, max_chars: int) -> list:
    line = line.strip()
    if len(line) <= max_chars:
        return [line]
    words = line.split(" ")
    if len(words) == 1:
        return [line[i:i+max_chars] for i in range(0, len(line), max_chars)]
    chunks = []
    current_chunk = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_len = len(word)
        else:
            current_chunk.append(word)
            current_len += len(word) + 1
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def find_chromium_browser():
    """Locates Microsoft Edge or Google Chrome executable on Windows."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    for name in ['msedge', 'chrome']:
        p = shutil.which(name)
        if p: return p
    return None


# --- Advanced HTML/CSS to PDF Card Generator (Flawless OpenType Shaping) ---

class PDFCardGenerator:
    def __init__(self, font_path: str, bg_image_path: str = None):
        self.font_path = font_path
        self.bg_image_path = bg_image_path
        self.width = 595.44
        self.height = 841.68
        
        self.fields = {
            'amount_num': {'left': 74.4, 'w': 138.2, 'y': 421.0},
            'amount_let': {'left': 224.4, 'w': 288.2, 'y': 421.0},
            'name_start': {'left': 155.8, 'w': 282.0, 'y': 553.0},
            'address': {'left': 155.8, 'w': 282.0, 'y': 642.0},
            'date': {'left': 441.0, 'w': 100.0, 'y': 765.0}
        }

    def generate_pdf(self, donors: list, output_pdf: str, mode: str = "overlay", 
                     offset_x: float = 0.0, offset_y: float = 0.0, 
                     line_height: float = 24.0, color_hex: str = "#0066cc",
                     align: str = "center", base_font_size: float = 14.0,
                     font_weight: str = "normal"):
        browser_exe = find_chromium_browser()
        if not browser_exe:
            raise RuntimeError("Microsoft Edge သို့မဟုတ် Google Chrome ဘရောက်ဆာကို စက်ထဲတွင် ရှာမတွေ့ပါ။ (Browser required for OpenType font shaping)")

        abs_font_path = os.path.abspath(self.font_path).replace('\\', '/')
        if not abs_font_path.startswith('/'):
            abs_font_path = '/' + abs_font_path
        font_url = f"file://{abs_font_path}"

        abs_bg_path = os.path.abspath(self.bg_image_path).replace('\\', '/') if self.bg_image_path else ""
        if abs_bg_path and not abs_bg_path.startswith('/'):
            abs_bg_path = '/' + abs_bg_path
        bg_url = f"file://{abs_bg_path}" if abs_bg_path else ""
        
        pages_html = []
        for donor in donors:
            bg_html = ""
            if mode == "full" and bg_url and os.path.exists(self.bg_image_path):
                bg_html = f"<img src='{bg_url}' style='position: absolute; top:0; left:0; width: 595.44pt; height: 841.68pt; z-index: 1;' />"
            
            def get_field_div(text_str: str, field_key: str, custom_y: float = None):
                if not text_str or str(text_str).strip() == "": return ""
                f_info = self.fields[field_key]
                left_pos = round(f_info['left'] + offset_x, 2)
                top_pos = round((custom_y if custom_y is not None else f_info['y']) + offset_y, 2)
                width_pos = f_info['w']
                
                # Scale date proportionally (date is normally 12pt when base is 14pt)
                fs = base_font_size if field_key != 'date' else round(base_font_size * (12.0 / 14.0), 1)
                
                return f"<div class='txt' style='top: {top_pos}pt; left: {left_pos}pt; width: {width_pos}pt; font-size: {fs}pt; text-align: {align}; font-weight: {font_weight};'>{text_str}</div>"

            items = []
            items.append(get_field_div(donor['formatted_amount_num'], 'amount_num'))
            items.append(get_field_div(donor['formatted_amount_let'], 'amount_let'))
            
            name_lines = wrap_myanmar_text(donor['donater_name'], max_chars=40)
            for idx, line in enumerate(name_lines[:2]):
                curr_y = self.fields['name_start']['y'] + (idx * line_height)
                items.append(get_field_div(line, 'name_start', custom_y=curr_y))
                
            items.append(get_field_div(donor['address'], 'address'))
            items.append(get_field_div(donor['formatted_date'], 'date'))
            
            page_content = f"<div class='page'>{bg_html}{''.join(items)}</div>"
            pages_html.append(page_content)
            
        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<style>
@page {{ size: A4; margin: 0; }}
@font-face {{ font-family: 'PrinterFont'; src: url('{font_url}'); }}
body {{ margin: 0; padding: 0; font-family: 'PrinterFont', sans-serif; box-sizing: border-box; }}
.page {{ width: 595.44pt; height: 841.68pt; position: relative; page-break-after: always; background: white; overflow: hidden; }}
.txt {{ position: absolute; color: {color_hex}; z-index: 2; line-height: 1.2; white-space: nowrap; }}
</style>
</head>
<body>
{''.join(pages_html)}
</body>
</html>"""

        temp_html = os.path.join(os.path.dirname(output_pdf), "~temp_print.html")
        abs_output_pdf = os.path.abspath(output_pdf)
        
        try:
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(full_html)
                
            cmd = [
                browser_exe,
                '--headless',
                '--disable-gpu',
                '--no-pdf-header-footer',
                f'--print-to-pdf={abs_output_pdf}',
                os.path.abspath(temp_html)
            ]
            
            res = subprocess.run(cmd, capture_output=True, text=True)
            if not os.path.exists(abs_output_pdf):
                raise RuntimeError(f"PDF ဖန်တီးမှု မအောင်မြင်ပါ: {res.stderr}")
        finally:
            if os.path.exists(temp_html):
                try: os.remove(temp_html)
                except Exception: pass


# --- Premium Tkinter Desktop GUI Application ---

class DonationCardGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("မြန်မာ အလှူခံကတ် ပရင့်ထုတ်စနစ် (Myanmar Donation Card Printer)")
        self.root.geometry("1280x820")
        self.root.minsize(1050, 720)
        
        # --- Modern Premium Design System & Tokens ---
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        BG_COLOR = "#f8fafc"       # Crisp slate off-white
        CARD_BG = "#ffffff"        # Pure white for containers
        ACCENT_PRIMARY = "#2563eb" # Premium Royal Blue
        ACCENT_HOVER = "#1d4ed8"   # Deeper blue on hover
        TEXT_MAIN = "#0f172a"      # Dark slate for headers
        TEXT_MUTED = "#475569"     # Elegant gray for body text
        BORDER_LIGHT = "#e2e8f0"   # Subtle divider lines
        
        # Configure global styles
        self.style.configure('TFrame', background=BG_COLOR)
        self.style.configure('TLabel', background=BG_COLOR, font=('Segoe UI', 10), foreground=TEXT_MAIN)
        self.style.configure('Card.TFrame', background=CARD_BG)
        self.style.configure('Header.TLabel', font=('Segoe UI', 18, 'bold'), foreground=ACCENT_PRIMARY, background=BG_COLOR)
        self.style.configure('SubHeader.TLabel', font=('Segoe UI', 11), foreground=TEXT_MUTED, background=BG_COLOR)
        
        self.style.configure('TLabelframe', background=BG_COLOR, font=('Segoe UI', 11, 'bold'), foreground=TEXT_MAIN, borderwidth=1, bordercolor=BORDER_LIGHT)
        self.style.configure('TLabelframe.Label', font=('Segoe UI', 11, 'bold'), foreground=ACCENT_PRIMARY, background=BG_COLOR)
        
        self.style.configure('TButton', font=('Segoe UI', 10, 'bold'), padding=8, background="#f1f5f9", foreground=TEXT_MAIN, borderwidth=1)
        self.style.map('TButton', background=[('active', '#e2e8f0')])
        
        self.style.configure('Accent.TButton', font=('Segoe UI', 12, 'bold'), padding=12, background=ACCENT_PRIMARY, foreground='white', borderwidth=0)
        self.style.map('Accent.TButton', background=[('active', ACCENT_HOVER)])
        
        # Treeview Styling
        self.style.configure('Treeview', font=('Segoe UI', 10), rowheight=30, background=CARD_BG, fieldbackground=CARD_BG, foreground=TEXT_MAIN, borderwidth=0)
        self.style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background="#f1f5f9", foreground=TEXT_MAIN, padding=8)
        self.style.map('Treeview', background=[('selected', '#eff6ff')], foreground=[('selected', ACCENT_PRIMARY)])
        
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_excel_file = os.path.join(self.base_dir, "DonorsData.xlsx")
        self.excel_file = self.default_excel_file
        self.default_font_file = os.path.join(self.base_dir, "KoZ 008 Font", "008.ttf")
        self.template_file = os.path.join(self.base_dir, "blank_card_template.jpg")
        self.config_file = os.path.join(self.base_dir, "printer_config.json")
        
        self.donors_data = []
        self.generator = PDFCardGenerator(self.default_font_file, self.template_file)
        self.fonts_map = self.get_available_fonts()
        
        self.colors_map = {
            "အပြာရင့် (Royal Blue)": "#0066cc",
            "အပြာတောက်တောက် (Electric Blue)": "#007aff",
            "အပြာမှိုင်း (Deep Navy Blue)": "#1e3a8a",
            "အနက်ရောင် (Standard Black)": "#000000",
            "အနီရောင် (Dark Red)": "#b91c1c",
            "အစိမ်းရောင် (Forest Green)": "#15803d",
            "ရွှေအိုရောင် (Antique Gold)": "#b45309"
        }
        
        self.load_config_initial()
        self._build_ui()
        self.load_excel_data()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config_initial(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                if 'excel_file' in cfg and os.path.exists(cfg['excel_file']):
                    self.excel_file = cfg['excel_file']
            except Exception: pass

    def get_available_fonts(self):
        fonts_dict = {
            "KoZ 008 Uni Regular (Default)": self.default_font_file
        }
        win_fonts_dir = r"C:\Windows\Fonts"
        if os.path.exists(win_fonts_dir):
            prio_fonts = [
                ("Pyidaungsu Regular", "Pyidaungsu-2.5.3_Regular.ttf"),
                ("Pyidaungsu Bold", "Pyidaungsu-2.5.3_Bold.ttf"),
                ("Myanmar Text Regular", "mmrtext.ttf"),
                ("Myanmar Text Bold", "mmrtextb.ttf"),
            ]
            for name, fn in prio_fonts:
                path = os.path.join(win_fonts_dir, fn)
                if os.path.exists(path):
                    fonts_dict[name] = path
            try:
                for f in sorted(os.listdir(win_fonts_dir)):
                    if f.lower().endswith(('.ttf', '.otf')):
                        path = os.path.join(win_fonts_dir, f)
                        fname = os.path.splitext(f)[0]
                        if fname not in [p[1].split('.')[0] for p in prio_fonts] and f != "008.ttf":
                            fonts_dict[f"Windows: {fname}"] = path
            except Exception: pass
        return fonts_dict

    def browse_custom_font(self):
        path = filedialog.askopenfilename(
            title="ဖောင့်ဖိုင် ရွေးချယ်ပါ (Select Font File)",
            filetypes=[("Font Files", "*.ttf *.otf")]
        )
        if path and os.path.exists(path):
            basename = os.path.basename(path)
            display_name = f"Custom: {basename}"
            self.fonts_map[display_name] = path
            self.font_cbb.config(values=list(self.fonts_map.keys()))
            self.font_cbb.set(display_name)
            self.save_config()
            self.status_var.set(f"✅ ဖောင့်အသစ် ရွေးချယ်ပြီးပါပြီ: {basename}")

    def browse_excel_file(self):
        path = filedialog.askopenfilename(
            title="အလှူရှင်စာရင်း Excel ဖိုင် ရွေးချယ်ပါ (Select Donors Excel File)",
            filetypes=[("Excel Files", "*.xlsx *.xls")]
        )
        if path and os.path.exists(path):
            self.excel_file = path
            self.save_config()
            self.load_excel_data()
            self.status_var.set(f"📂 Excel ဖိုင်အသစ် ဖွင့်လိုက်ပါပြီ: {os.path.basename(path)}")

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                if 'x_offset' in cfg: self.x_offset_var.set(float(cfg['x_offset']))
                if 'y_offset' in cfg: self.y_offset_var.set(float(cfg['y_offset']))
                if 'line_height' in cfg: self.line_height_var.set(float(cfg['line_height']))
                if 'output_mode' in cfg: self.output_mode.set(cfg['output_mode'])
                if 'align' in cfg: self.align_var.set(cfg['align'])
                if 'color_name' in cfg: self.color_cbb.set(cfg['color_name'])
                if 'font_size' in cfg: self.font_size_var.set(float(cfg['font_size']))
                if 'font_weight' in cfg:
                    self.weight_cbb.set("စာလုံးမည်း (Bold)" if cfg['font_weight'] == 'bold' else "ပုံမှန် (Normal)")
                if 'font_name' in cfg:
                    fn = cfg['font_name']
                    if fn in self.fonts_map or fn == "KoZ 008 Uni Regular (Default)":
                        self.font_cbb.set(fn)
                    elif 'custom_font_path' in cfg and os.path.exists(cfg['custom_font_path']):
                        self.fonts_map[fn] = cfg['custom_font_path']
                        self.font_cbb.config(values=list(self.fonts_map.keys()))
                        self.font_cbb.set(fn)
                        
                self.x_val_label.config(text=f"{self.x_offset_var.get():+.1f} pt")
                self.y_val_label.config(text=f"{self.y_offset_var.get():+.1f} pt")
                self.status_var.set("⚙️ ယခင်သတ်မှတ်ထားသော ဆက်တင်များ (Saved Settings) ကို အလိုအလျောက် ဖွင့်ပေးထားပါသည်။")
            except Exception: pass

    def save_config(self):
        cfg = {
            'x_offset': self.x_offset_var.get(),
            'y_offset': self.y_offset_var.get(),
            'line_height': self.line_height_var.get(),
            'output_mode': self.output_mode.get(),
            'align': self.align_var.get(),
            'color_name': self.color_cbb.get(),
            'font_name': self.font_cbb.get(),
            'font_size': float(self.font_size_var.get()),
            'font_weight': "bold" if "Bold" in self.weight_cbb.get() or "မည်း" in self.weight_cbb.get() else "normal",
            'excel_file': self.excel_file
        }
        fn = self.font_cbb.get()
        if fn in self.fonts_map:
            cfg['custom_font_path'] = self.fonts_map[fn]
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=4)
        except Exception: pass

    def on_closing(self):
        self.save_config()
        self.root.destroy()

    def _build_ui(self):
        root_container = ttk.Frame(self.root, padding="20 20 20 20")
        root_container.pack(fill=tk.BOTH, expand=True)

        # --- Top Header ---
        header_frame = ttk.Frame(root_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_box = ttk.Frame(header_frame)
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text="အလှူရှင် အချက်အလက်များနှင့် ပရင့်ထုတ်စနစ် (Donation Card Printing System)", style='Header.TLabel').pack(anchor="w")
        ttk.Label(title_box, text="Professional Headless Chromium Engine with DirectWrite OpenType Font Shaping", style='SubHeader.TLabel').pack(anchor="w")
        
        btn_box = ttk.Frame(header_frame)
        btn_box.pack(side=tk.RIGHT, anchor="center")
        ttk.Button(btn_box, text="📂 Excel ဖိုင်ရွေးမည် (Select File)", command=self.browse_excel_file).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_box, text="🔄 ဒေတာပြန်ဖွင့်မည် (Reload)", command=self.load_excel_data).pack(side=tk.LEFT)

        # --- Main Layout (Left: Table, Right: Controls) ---
        main_grid = ttk.Frame(root_container)
        main_grid.pack(fill=tk.BOTH, expand=True)
        main_grid.columnconfigure(0, weight=6)
        main_grid.columnconfigure(1, weight=4)

        # --- Left Table Box ---
        table_container = ttk.LabelFrame(main_grid, text=" ဇယားရှိ အလှူရှင်စာရင်း (Donors List from Excel) ", padding="12 12 12 12")
        table_container.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        top_select_bar = ttk.Frame(table_container)
        top_select_bar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(top_select_bar, text="☑ အားလုံးရွေးမည် (Select All)", command=self.select_all).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top_select_bar, text="☐ ရွေးချယ်မှုဖြုတ်မည် (Deselect All)", command=self.deselect_all).pack(side=tk.LEFT)
        
        self.excel_badge = ttk.Label(top_select_bar, text=f"📂 {os.path.basename(self.excel_file)}", font=('Segoe UI', 10, 'bold'), foreground="#2563eb")
        self.excel_badge.pack(side=tk.RIGHT, padx=(0, 5))

        columns = ("selected", "id", "name", "amount", "address", "date")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", height=16)
        
        self.tree.heading("selected", text="ပရင့်ထုတ်မည်")
        self.tree.heading("id", text="စဉ် (ID)")
        self.tree.heading("name", text="အလှူရှင်အမည် (Name)")
        self.tree.heading("amount", text="လှူဒါန်းငွေ (Amount)")
        self.tree.heading("address", text="နေရပ်လိပ်စာ (Address)")
        self.tree.heading("date", text="ရက်စွဲ (Date)")
        
        self.tree.column("selected", width=95, anchor="center")
        self.tree.column("id", width=65, anchor="center")
        self.tree.column("name", width=260, anchor="w")
        self.tree.column("amount", width=145, anchor="e")
        self.tree.column("address", width=190, anchor="w")
        self.tree.column("date", width=110, anchor="center")
        
        self.tree.tag_configure('evenrow', background='#ffffff')
        self.tree.tag_configure('oddrow', background='#f8fafc')
        
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        
        scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Right Control Box ---
        controls_container = ttk.Frame(main_grid)
        controls_container.grid(row=0, column=1, sticky="nsew")

        # 1. Output Mode Group
        mode_frame = ttk.LabelFrame(controls_container, text=" ၁။ ပရင့်မုဒ် ရွေးချယ်ခြင်း (Output Mode) ", padding="14 14 14 14")
        mode_frame.pack(fill=tk.X, pady=(0, 15))

        self.output_mode = tk.StringVar(value="overlay")
        self.output_mode.trace_add("write", lambda *a: self.save_config())
        
        ttk.Radiobutton(mode_frame, text="ကတ်အလွတ်ပေါ်ထပ်ရိုက်မည် (Print Overlay Mode)\n* အသင့်ရိုက်နှိပ်ထားသော ကတ်အလွတ်များအတွက်", variable=self.output_mode, value="overlay").pack(anchor="w", pady=(0, 8))
        ttk.Radiobutton(mode_frame, text="ဒီဇိုင်းနောက်ခံပါ ပရင့်ထုတ်မည် (Full Certificate Mode)\n* ဒီဂျစ်တယ်ကတ် သို့မဟုတ် စစ်ဆေးရန်", variable=self.output_mode, value="full").pack(anchor="w")

        # 2. Typography & Style Group
        style_frame = ttk.LabelFrame(controls_container, text=" ၂။ ဖောင့်နှင့် စာသား နေရာချထားမှု (Typography & Style) ", padding="14 14 14 14")
        style_frame.pack(fill=tk.X, pady=(0, 15))
        
        row1 = ttk.Frame(style_frame)
        row1.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row1, text="စာသား ဖောင့် (Font):").pack(side=tk.LEFT)
        ttk.Button(row1, text="📂 ဖိုင်ရွေးမည်", command=self.browse_custom_font, padding=4).pack(side=tk.RIGHT, padx=(6, 0))
        self.font_cbb = ttk.Combobox(row1, values=list(self.fonts_map.keys()), state="readonly", width=22)
        self.font_cbb.set("KoZ 008 Uni Regular (Default)")
        self.font_cbb.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        self.font_cbb.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        row2 = ttk.Frame(style_frame)
        row2.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row2, text="စာလုံးအရွယ် (Size):").pack(side=tk.LEFT)
        self.font_size_var = tk.DoubleVar(value=14.0)
        size_spin = ttk.Spinbox(row2, from_=10.0, to=28.0, increment=1.0, textvariable=self.font_size_var, width=6, command=self.save_config)
        size_spin.bind("<KeyRelease>", lambda e: self.save_config())
        size_spin.pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(row2, text="အထူအပါး (Weight):").pack(side=tk.LEFT)
        self.weight_cbb = ttk.Combobox(row2, values=["ပုံမှန် (Normal)", "စာလုံးမည်း (Bold)"], state="readonly", width=18)
        self.weight_cbb.set("ပုံမှန် (Normal)")
        self.weight_cbb.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        self.weight_cbb.pack(side=tk.LEFT, padx=(5, 0))
        
        row3 = ttk.Frame(style_frame)
        row3.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row3, text="စာသားအရောင် (Color):").pack(side=tk.LEFT)
        self.color_cbb = ttk.Combobox(row3, values=list(self.colors_map.keys()), state="readonly", width=25)
        self.color_cbb.set("အပြာရင့် (Royal Blue)")
        self.color_cbb.bind("<<ComboboxSelected>>", lambda e: self.save_config())
        self.color_cbb.pack(side=tk.RIGHT)
        
        row4 = ttk.Frame(style_frame)
        row4.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row4, text="စာသားနေရာ (Alignment):").pack(side=tk.LEFT)
        self.align_var = tk.StringVar(value="center")
        self.align_var.trace_add("write", lambda *a: self.save_config())
        ttk.Radiobutton(row4, text="မျဉ်းအလယ် (Center)", variable=self.align_var, value="center").pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Radiobutton(row4, text="ဘယ်ကပ် (Left)", variable=self.align_var, value="left").pack(side=tk.RIGHT)
        
        row5 = ttk.Frame(style_frame)
        row5.pack(fill=tk.X)
        ttk.Label(row5, text="စာကြောင်း(၂)ကြောင်း အကွာအဝေး (Line Spacing):").pack(side=tk.LEFT)
        self.line_height_var = tk.DoubleVar(value=24.0)
        spin = ttk.Spinbox(row5, from_=18.0, to=36.0, increment=1.0, textvariable=self.line_height_var, width=8, command=self.save_config)
        spin.bind("<KeyRelease>", lambda e: self.save_config())
        spin.pack(side=tk.RIGHT)
        ttk.Label(row5, text="pt").pack(side=tk.RIGHT, padx=(0, 5))

        # 3. Calibration Group
        cal_frame = ttk.LabelFrame(controls_container, text=" ၃။ မျဉ်းပေါ် အတိအကျကျစေရန် ချိန်ညှိခြင်း (Fine-tune Position) ", padding="14 14 14 14")
        cal_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(cal_frame, text="ဘယ်/ညာ ရွှေ့ရန် (Horizontal Offset - X points):").pack(anchor="w", pady=(0, 2))
        self.x_offset_var = tk.DoubleVar(value=0.0)
        x_slider_box = ttk.Frame(cal_frame)
        x_slider_box.pack(fill=tk.X, pady=(0, 12))
        
        def on_x_slide(v): self.x_val_label.config(text=f"{float(v):+.1f} pt")
        def on_slide_release(e): self.save_config()
            
        x_scale = ttk.Scale(x_slider_box, from_=-100.0, to=100.0, variable=self.x_offset_var, command=on_x_slide)
        x_scale.bind("<ButtonRelease-1>", on_slide_release)
        x_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.x_val_label = ttk.Label(x_slider_box, text="+0.0 pt", width=8, anchor="e", font=('Segoe UI', 10, 'bold'), foreground="#2563eb")
        self.x_val_label.pack(side=tk.RIGHT, padx=(8, 0))

        ttk.Label(cal_frame, text="အထက်/အောက် ရွှေ့ရန် (Vertical Offset - Y points):").pack(anchor="w", pady=(0, 2))
        self.y_offset_var = tk.DoubleVar(value=0.0)
        y_slider_box = ttk.Frame(cal_frame)
        y_slider_box.pack(fill=tk.X, pady=(0, 12))
        
        def on_y_slide(v): self.y_val_label.config(text=f"{float(v):+.1f} pt")
            
        y_scale = ttk.Scale(y_slider_box, from_=-100.0, to=100.0, variable=self.y_offset_var, command=on_y_slide)
        y_scale.bind("<ButtonRelease-1>", on_slide_release)
        y_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.y_val_label = ttk.Label(y_slider_box, text="+0.0 pt", width=8, anchor="e", font=('Segoe UI', 10, 'bold'), foreground="#2563eb")
        self.y_val_label.pack(side=tk.RIGHT, padx=(8, 0))
        
        ttk.Button(cal_frame, text="သုညသို့ ပြန်ထားမည် (Reset Offsets)", command=self.reset_offsets).pack(fill=tk.X)

        # 4. Actions Group
        action_frame = ttk.LabelFrame(controls_container, text=" လုပ်ဆောင်ချက်များ (Actions) ", padding="14 14 14 14")
        action_frame.pack(fill=tk.X, expand=True)

        generate_btn = ttk.Button(action_frame, text="🖨️ ပရင့်ထုတ်မည့် PDF ဖန်တီးမည် (Generate Print PDF)", style="Accent.TButton", command=self.generate_cards_action)
        generate_btn.pack(fill=tk.X, pady=(0, 10))
        
        open_folder_btn = ttk.Button(action_frame, text="📁 ထွက်ပေါ်လာသော ဖိုင်တွဲဖွင့်မည် (Open Output Folder)", command=self.open_output_folder)
        open_folder_btn.pack(fill=tk.X)

        # --- Status Bar ---
        status_box = ttk.Frame(root_container, padding="10 6 10 6", style="Card.TFrame")
        status_box.pack(fill=tk.X, pady=(15, 0))
        
        self.status_var = tk.StringVar(value="🟢 အသင့်ဖြစ်ပါပြီ (Ready).")
        ttk.Label(status_box, textvariable=self.status_var, font=('Segoe UI', 10), foreground="#334155").pack(side=tk.LEFT)

        self.load_config()

    def on_tree_click(self, event):
        region = self.tree.identify("item", event.x, event.y)
        if region:
            col = self.tree.identify_column(event.x)
            if col == "#1":
                item = self.tree.focus()
                vals = list(self.tree.item(item, "values"))
                vals[0] = "☐ မထုတ်ပါ" if vals[0].startswith("☑") else "☑ ထုတ်မည်"
                self.tree.item(item, values=vals)

    def select_all(self):
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, "values"))
            vals[0] = "☑ ထုတ်မည်"
            self.tree.item(item, values=vals)

    def deselect_all(self):
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, "values"))
            vals[0] = "☐ မထုတ်ပါ"
            self.tree.item(item, values=vals)

    def reset_offsets(self):
        self.x_offset_var.set(0.0)
        self.y_offset_var.set(0.0)
        self.x_val_label.config(text="+0.0 pt")
        self.y_val_label.config(text="+0.0 pt")
        self.save_config()

    def load_excel_data(self):
        self.tree.delete(*self.tree.get_children())
        self.donors_data.clear()
        
        if hasattr(self, 'excel_badge'):
            self.excel_badge.config(text=f"📂 {os.path.basename(self.excel_file)}")
        
        if not os.path.exists(self.excel_file):
            self.status_var.set(f"❌ Excel ဖိုင်မတွေ့ပါ: {self.excel_file}")
            messagebox.showerror("Error", f"Excel file not found at:\n{self.excel_file}")
            return

        try:
            df = pd.read_excel(self.excel_file)
            count = 0
            for idx, row in df.iterrows():
                if pd.isna(row.get('ID')) or str(row.get('ID')).strip() == "":
                    continue
                
                donor_id = row['ID']
                amt_num = row.get('Amount_Num', '')
                amt_suffix = row.get('2-num', '  - ကျပ်')
                amt_let = row.get('Amount_Let', '')
                name = row.get('Donater_Name', '')
                addr = row.get('Address', '')
                raw_date = row.get('Date', '')
                
                fmt_amt_num = format_currency_number(amt_num, amt_suffix)
                fmt_date = to_myanmar_digits(str(raw_date)) if not pd.isna(raw_date) else ""
                
                donor_obj = {
                    'raw_id': donor_id,
                    'donater_name': str(name) if not pd.isna(name) else "",
                    'address': str(addr) if not pd.isna(addr) else "",
                    'formatted_amount_num': fmt_amt_num,
                    'formatted_amount_let': str(amt_let) if not pd.isna(amt_let) else "",
                    'formatted_date': fmt_date
                }
                self.donors_data.append(donor_obj)
                
                tag = 'evenrow' if count % 2 == 0 else 'oddrow'
                self.tree.insert("", tk.END, values=(
                    "☐ မထုတ်ပါ",
                    to_myanmar_digits(str(int(donor_id) if isinstance(donor_id, (int, float)) and not pd.isna(donor_id) else donor_id)),
                    donor_obj['donater_name'].replace("\n", " / "),
                    fmt_amt_num,
                    donor_obj['address'],
                    fmt_date
                ), tags=(tag,))
                count += 1
                
            children = self.tree.get_children()
            if children:
                last_item = children[-1]
                vals = list(self.tree.item(last_item, "values"))
                vals[0] = "☑ ထုတ်မည်"
                self.tree.item(last_item, values=vals)
                self.tree.selection_set(last_item)
                self.tree.see(last_item)
                
            self.status_var.set(f"🟢 Excel ဖိုင်မှ အလှူရှင် ({count}) ဦး ဖတ်ပြီးပါပြီ။ (နောက်ဆုံးအလှူရှင်ကိုသာ ရွေးထားပေးပါသည်)")
        except Exception as e:
            self.status_var.set(f"❌ Excel ဖတ်ရှုရာတွင် ချို့ယွင်းချက်ဖြစ်ပေါ်နေပါသည်: {str(e)}")
            messagebox.showerror("Excel Error", f"Error reading Excel file:\n{str(e)}")

    def generate_cards_action(self):
        selected_donors = []
        for i, item in enumerate(self.tree.get_children()):
            vals = self.tree.item(item, "values")
            if vals[0].startswith("☑"):
                selected_donors.append(self.donors_data[i])
                
        if not selected_donors:
            messagebox.showwarning("သတိပေးချက်", "ပရင့်ထုတ်ရန် အလှူရှင် အနည်းဆုံးတစ်ဦး ရွေးချယ်ပါ။ (Select at least 1 donor)")
            return

        self.save_config()

        selected_font_name = self.font_cbb.get()
        selected_font_path = self.fonts_map.get(selected_font_name, self.default_font_file)
        if not os.path.exists(selected_font_path):
            messagebox.showerror("Error", f"ရွေးချယ်ထားသော ဖောင့်ဖိုင် မတွေ့ပါ:\n{selected_font_path}")
            return
            
        self.generator.font_path = selected_font_path

        mode_str = self.output_mode.get()
        mode_label = "Overlay" if mode_str == "overlay" else "FullCertificate"
        
        ver_id = int(time.time()) % 100000
        output_filename = f"DonationCards_{mode_label}_{len(selected_donors)}donors_v{ver_id}.pdf"
        output_path = os.path.join(self.base_dir, output_filename)
        
        selected_color_name = self.color_cbb.get()
        hex_color = self.colors_map.get(selected_color_name, "#0066cc")
        align_str = self.align_var.get()
        line_height_val = float(self.line_height_var.get())
        font_size_val = float(self.font_size_var.get())
        weight_str = "bold" if "Bold" in self.weight_cbb.get() or "မည်း" in self.weight_cbb.get() else "normal"
        
        self.status_var.set("⏳ PDF ဖန်တီးနေပါသည်... (Generating OpenType-shaped PDF...)")
        self.root.update_idletasks()
        
        try:
            self.generator.generate_pdf(
                donors=selected_donors,
                output_pdf=output_path,
                mode=mode_str,
                offset_x=self.x_offset_var.get(),
                offset_y=self.y_offset_var.get(),
                line_height=line_height_val,
                color_hex=hex_color,
                align=align_str,
                base_font_size=font_size_val,
                font_weight=weight_str
            )
            self.status_var.set(f"🎉 အောင်မြင်ပါသည်။ ဖိုင်ကိုသိမ်းဆည်းလိုက်ပါပြီ: {output_filename}")
            
            resp = messagebox.askyesno("အောင်မြင်ပါသည် (Success)", f"အလှူရှင် ({len(selected_donors)}) ဦးအတွက် အတိအကျမှန်ကန်သော နေရာနှင့် ဖောင့်ဖြင့် PDF ဖန်တီးပြီးပါပြီ။\nဖိုင်ကို ယခုဖွင့်ကြည့်လိုပါသလား?\n\nFile: {output_filename}")
            if resp:
                webbrowser.open(output_path)
                
        except Exception as e:
            self.status_var.set(f"❌ PDF ဖန်တီးရာတွင် အမှားဖြစ်ပေါ်နေပါသည်: {str(e)}")
            messagebox.showerror("PDF Error", f"Error generating PDF:\n{str(e)}")

    def open_output_folder(self):
        try: os.startfile(self.base_dir)
        except Exception: subprocess.Popen(['explorer', self.base_dir])

if __name__ == "__main__":
    root = tk.Tk()
    app = DonationCardGUI(root)
    root.mainloop()
