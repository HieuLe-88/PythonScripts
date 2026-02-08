import asyncio
import edge_tts
import os
import re
import numpy as np
import glob
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from moviepy.editor import AudioFileClip, concatenate_videoclips, concatenate_audioclips, AudioClip, ImageClip

class VideoGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Multilingual Lesson Video Generator - Pro Version")
        self.root.geometry("750x980")

        # Dữ liệu giọng đọc
        self.voices_data = {
            "Spanish": {
                "male": [
                    "es-ES-AlvaroNeural",
                    "es-MX-JorgeNeural",
                    "es-US-AlonsoNeural",
                    "es-ES-GonzaloNeural",
                    "es-MX-LibertoNeural"
                ],
                "female": [
                    "es-ES-ElviraNeural",
                    "es-MX-DaliaNeural",
                    "es-US-PalomaNeural",
                    "es-AR-ElenaNeural",
                    "es-CO-SalomeNeural"                    
                ]
            },
            "Chinese": {
                "male": [
                    "zh-CN-YunxiNeural",
                    "zh-CN-YunjianNeural",
                    "zh-CN-YunzeNeural",
                    "zh-TW-YunJheNeural",
                    "zh-CN-YunyangNeural"
                ],
                "female": [
                    "zh-CN-XiaoxiaoNeural",
                    "zh-HK-HiuGaaiNeural",
                    "zh-TW-HsiaoChenNeural",
                    "zh-CN-XiaoniniNeural",
                    "zh-CN-XiaoyiNeural"
                ]
            }
        }

        # Biến điều khiển
        self.lang_var = tk.StringVar(value="Spanish")
        self.voice_vars = {tag: tk.StringVar() for tag in ["M", "M1", "M2", "F", "F1", "F2"]}
        
        self.pos_left_var = tk.StringVar(value="6.5,4")
        self.pos_right_var = tk.StringVar(value="6.5,12")
        self.box_width_var = tk.StringVar(value="400")   
        self.box_height_var = tk.StringVar(value="120")  
        # Single-reader mode: show single full-width bottom box
        self.single_reader_var = tk.BooleanVar(value=False)
        
        # Text box style selection (three sample styles)
        self.textbox_style_var = tk.StringVar(value="Style1")
        # Biến cho LOGO
        self.logo_path = tk.StringVar(value="")
        self.logo_size_var = tk.StringVar(value="9") # % so với chiều rộng video
        self.logo_pos_var = tk.StringVar(value="0.7,15.3") # Y,X (Mặc định góc trên bên phải)

        self.bg_path = tk.StringVar(value="")
        # Support multiple title-specific images: mapping titlekey -> filepath
        self.bg_images = {}
        self.bg_images_var = tk.StringVar(value="")
        # Toggle display of subtitle/text box
        self.show_sub_var = tk.BooleanVar(value=True)
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.selected_speed = tk.StringVar(value="100%")
        # Engine selection: Edge TTS (legacy) or Gemini (use external audio + SRT)
        self.engine_var = tk.StringVar(value="Edge TTTS")
        # Gemini inputs
        self.gemini_audio = tk.StringVar(value="")
        self.gemini_srt = tk.StringVar(value="")

        # Thêm biến điều khiển vị trí F
        self.f_left_var = tk.StringVar(value="LEFT")  # "LEFT" hoặc "RIGHT"

        self.set_default_voices()
        self.setup_gui()

    def set_default_voices(self):
        lang = self.lang_var.get()
        males = self.voices_data[lang]["male"]
        females = self.voices_data[lang]["female"]
        mapping = {
            "M":  males[0],
            "M1": males[0],
            "M2": males[1],
            "F":  females[0],
            "F1": females[0],
            "F2": females[4]
        }
        for tag in mapping:
            if tag in self.voice_vars:
                self.voice_vars[tag].set(mapping[tag])


    def update_voice_options(self, event=None):
        lang = self.lang_var.get()
        males = self.voices_data[lang]["male"]
        females = self.voices_data[lang]["female"]
        tags = ["M", "M1", "M2", "F", "F1", "F2"]
        for i, tag in enumerate(tags):
            gender = "male" if tag.startswith("M") else "female"
            values = males if gender == "male" else females
            self.voice_combos[i]['values'] = values
            # Nếu giá trị hiện tại không còn hợp lệ, reset về mặc định
            if self.voice_vars[tag].get() not in values:
                self.voice_vars[tag].set(values[0])

    def setup_gui(self):
        # 1. CHỌN NGÔN NGỮ
        lang_frame = tk.LabelFrame(self.root, text=" 1. CHỌN NGÔN NGỮ ", font=("Arial", 10, "bold"), pady=10)
        lang_frame.pack(fill="x", padx=20, pady=5)
        ttk.Combobox(lang_frame, textvariable=self.lang_var, values=["Spanish", "Chinese"], 
                      state="readonly", width=20).pack()
        self.lang_var.trace("w", lambda *args: self.update_voice_options())

        # 1.1. Chọn vị trí F
        posF_frame = tk.Frame(self.root)
        posF_frame.pack(pady=2)
        tk.Label(posF_frame, text="Vị trí F:").pack(side="left")
        ttk.Combobox(posF_frame, textvariable=self.f_left_var, values=["LEFT", "RIGHT"], state="readonly", width=8).pack(side="left")
        tk.Label(posF_frame, text="(F bên trái thì M sẽ bên phải và ngược lại)").pack(side="left")

        # 2. CÀI ĐẶT GIỌNG ĐỌC
        v_frame = tk.LabelFrame(self.root, text=" 2. CÀI ĐẶT GIỌNG ĐỌC ", font=("Arial", 10, "bold"), pady=10)
        v_frame.pack(fill="x", padx=20, pady=5)
        self.voice_combos = []
        container = tk.Frame(v_frame)
        container.pack()
        tags = ["M", "M1", "M2", "F", "F1", "F2"]
        for i, tag in enumerate(tags):
            r, c = divmod(i, 2)
            gender = "male" if tag.startswith("M") else "female"
            values = self.voices_data[self.lang_var.get()][gender]
            tk.Label(container, text=f"{tag}:").grid(row=r, column=c*2, padx=5, pady=2, sticky="e")
            cb = ttk.Combobox(container, textvariable=self.voice_vars[tag], values=values, width=25)
            cb.grid(row=r, column=c*2+1, padx=5, pady=2)
            self.voice_combos.append(cb)

        # 3. THIẾT KẾ BOX
        design_frame = tk.LabelFrame(self.root, text=" 3. THIẾT KẾ BOX (VỊ TRÍ & KÍCH THƯỚC) ", font=("Arial", 10, "bold"), pady=10)
        design_frame.pack(fill="x", padx=20, pady=5)
        
        tk.Label(design_frame, text="Y,X Box Trái:").grid(row=0, column=0, padx=10, pady=5)
        self.pos_left_entry = tk.Entry(design_frame, textvariable=self.pos_left_var, width=10)
        self.pos_left_entry.grid(row=0, column=1)
        tk.Label(design_frame, text="Y,X Box Phải:").grid(row=0, column=2, padx=10, pady=5)
        self.pos_right_entry = tk.Entry(design_frame, textvariable=self.pos_right_var, width=10)
        self.pos_right_entry.grid(row=0, column=3)

        tk.Label(design_frame, text="Chiều Rộng:").grid(row=1, column=0, padx=10, pady=5)
        self.box_width_entry = tk.Entry(design_frame, textvariable=self.box_width_var, width=10)
        self.box_width_entry.grid(row=1, column=1)
        tk.Label(design_frame, text="Chiều Cao:").grid(row=1, column=2, padx=10, pady=5)
        self.box_height_entry = tk.Entry(design_frame, textvariable=self.box_height_var, width=10)
        self.box_height_entry.grid(row=1, column=3)
        tk.Checkbutton(design_frame, text="1 người đọc (box cố định ở đáy, full-width)", variable=self.single_reader_var).grid(row=2, column=0, columnspan=4, pady=6)
        # When single-reader toggles, enable/disable position/size inputs
        self.single_reader_var.trace("w", lambda *args: self.update_single_reader_ui())
        # Initialize state
        self.update_single_reader_ui()

        tk.Checkbutton(design_frame, text="Hiển thị subtitle / box", variable=self.show_sub_var).grid(row=3, column=0, columnspan=4, pady=6)

        # 3.1 Text box style options
        style_frame = tk.Frame(self.root)
        style_frame.pack(fill="x", padx=30, pady=2)
        tk.Label(style_frame, text="Text Box Style:").pack(side="left")
        styles = [("Clean (Style1)", "Style1"), ("Modern Dark (Style2)", "Style2"), ("Minimal (Style3)", "Style3")]
        for txt, val in styles:
            tk.Radiobutton(style_frame, text=txt, variable=self.textbox_style_var, value=val).pack(side="left", padx=6)
        # 4. CÀI ĐẶT LOGO
        logo_frame = tk.LabelFrame(self.root, text=" 4. CÀI ĐẶT LOGO ", font=("Arial", 10, "bold"), pady=10)
        logo_frame.pack(fill="x", padx=20, pady=5)
        
        tk.Button(logo_frame, text="Chọn File Logo", command=self.browse_logo).grid(row=0, column=0, padx=10)
        tk.Label(logo_frame, textvariable=self.logo_path, fg="gray", width=30).grid(row=0, column=1, columnspan=3)
        
        tk.Label(logo_frame, text="Size (%):").grid(row=1, column=0, pady=5)
        tk.Entry(logo_frame, textvariable=self.logo_size_var, width=10).grid(row=1, column=1)
        tk.Label(logo_frame, text="Tọa độ Y,X:").grid(row=1, column=2)
        tk.Entry(logo_frame, textvariable=self.logo_pos_var, width=10).grid(row=1, column=3)

        # 5. CẤU HÌNH KHÁC
        other_frame = tk.Frame(self.root)
        other_frame.pack(pady=10)
        tk.Label(other_frame, text="Tốc độ:").grid(row=0, column=0)
        ttk.Combobox(
            other_frame,
            textvariable=self.selected_speed,
            values=[f"{i}%" for i in range(50, 145, 5)],
            width=8
        ).grid(row=0, column=1, padx=5)
        tk.Button(other_frame, text="Chọn Ảnh Nền / Ảnh theo title", command=self.browse_bg).grid(row=0, column=2, padx=5)
        tk.Label(other_frame, textvariable=self.bg_images_var, fg="gray", width=28).grid(row=0, column=4, padx=6)
        tk.Button(other_frame, text="Thư Mục Lưu", command=self.browse_folder).grid(row=0, column=3, padx=5)

        self.btn = tk.Button(self.root, text="BẮT ĐẦU TẠO VIDEO", bg="#4CAF50", fg="white", 
                               font=("Arial", 12, "bold"), command=self.start_process, padx=40, pady=15)
        self.btn.pack(pady=20)
        self.status_label = tk.Label(self.root, text="Sẵn sàng", fg="blue")
        self.status_label.pack()

        # 6. ENGINE SELECTION (Edge TTTS or Gemini)
        engine_frame = tk.LabelFrame(self.root, text=" 6. CHỌN ENGINE ", font=("Arial", 10, "bold"), pady=8)
        engine_frame.pack(fill="x", padx=20, pady=5)
        ttk.Combobox(engine_frame, textvariable=self.engine_var, values=["Edge TTTS", "Gemini"], state="readonly", width=20).pack(side="left", padx=8)
        tk.Button(engine_frame, text="Chọn Gemini Audio", command=self.browse_gemini_audio).pack(side="left", padx=6)
        tk.Label(engine_frame, textvariable=self.gemini_audio, fg="gray", width=28).pack(side="left")
        tk.Button(engine_frame, text="Chọn Gemini SRT", command=self.browse_gemini_srt).pack(side="left", padx=6)
        tk.Label(engine_frame, textvariable=self.gemini_srt, fg="gray", width=28).pack(side="left")
        self.engine_var.trace("w", lambda *args: self.update_engine_ui())
        self.update_engine_ui()

    def browse_logo(self):
        f = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")])
        if f: self.logo_path.set(f)

    def browse_bg(self):
        # Allow selecting one background image or multiple title-specific images
        files = filedialog.askopenfilenames(title="Chọn 1 hoặc nhiều ảnh (tên: title1, title2, ...)",
                                            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")])
        if not files:
            return
        files = list(files)
        if len(files) == 1:
            # single image -> use as default background
            self.bg_path.set(files[0])
            self.bg_images.clear()
            self.bg_images_var.set(os.path.basename(files[0]))
        else:
            # multiple images -> populate mapping by filename (basename without ext)
            self.bg_path.set("")
            self.bg_images.clear()
            added = []
            for f in files:
                name = os.path.splitext(os.path.basename(f))[0]
                key = re.sub(r"\W+", "", name).lower()
                if key:
                    self.bg_images[key] = f
                    added.append(f"{key}")
            if added:
                self.bg_images_var.set(f"{len(added)} images: " + ",".join(added))
            else:
                self.bg_images_var.set("No valid title images selected")
        
    def browse_folder(self):
        f = filedialog.askdirectory()
        if f: self.output_dir.set(f)

    def parse_line(self, line):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            tag = parts[0].upper()
            # Xác định vị trí: F1/M1 bên trái, F2/M2 bên phải
            if tag in ["F1", "M1"]:
                pos_type = self.f_left_var.get()
            elif tag in ["F2", "M2"]:
                pos_type = "RIGHT" if self.f_left_var.get() == "LEFT" else "LEFT"
            elif tag.startswith("F"):
                pos_type = self.f_left_var.get()
            elif tag.startswith("M"):
                pos_type = "RIGHT" if self.f_left_var.get() == "LEFT" else "LEFT"
            else:
                pos_type = "LEFT"
            # Lấy đúng voice theo tag, fallback về "M"
            voice = self.voice_vars.get(tag, self.voice_vars["M"]).get()
            return {
                "position_type": pos_type,
                "voice": voice,
                "text_1": parts[1],
                "text_2": parts[2],
                "text_3": parts[3] if len(parts) > 3 else ""
            }
        return None

    def browse_gemini_audio(self):
        f = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.flac")])
        if f: self.gemini_audio.set(f)

    def browse_gemini_srt(self):
        f = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt *.txt")])
        if f: self.gemini_srt.set(f)

    def update_engine_ui(self):
        # Enable/disable gemini file labels/buttons depending on selection
        # (We keep the controls visible; selection affects behavior on start)
        pass

    def update_single_reader_ui(self):
        try:
            disabled = 'disabled' if self.single_reader_var.get() else 'normal'
        except Exception:
            disabled = 'normal'
        for w in ['pos_left_entry', 'pos_right_entry', 'box_width_entry', 'box_height_entry']:
            ew = getattr(self, w, None)
            if ew:
                try:
                    ew.config(state=disabled)
                except Exception:
                    pass

    def parse_srt(self, srt_path):
        # Returns list of {start, end, text}
        cues = []
        if not os.path.exists(srt_path):
            return cues
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = re.split(r"\n\s*\n", content.strip())
        for p in parts:
            lines = [l.strip() for l in p.splitlines() if l.strip()]
            if len(lines) >= 2:
                # second line is timing
                timing = lines[1]
                m = re.match(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})", timing)
                text = ' '.join(lines[2:]) if len(lines) > 2 else lines[-1]
                if m:
                    def parse_time(s):
                        s = s.replace(',', '.')
                        hh, mm, rest = s.split(':')
                        ss = float(rest)
                        return int(hh)*3600 + int(mm)*60 + ss
                    start = parse_time(m.group(1))
                    end = parse_time(m.group(2))
                    cues.append({"start": start, "end": end, "text": text})
        return cues

    def process_video_gemini(self, text_file, audio_file, srt_file):
        # Read text input -> map chinese text to pinyin and english
        with open(text_file, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        # Support title markers like: [Title 1] ... and attach title_key to parsed entries
        mapping = {}
        current_title = None
        for line in lines:
            m = re.match(r"\s*\[([^\]]+)\]", line)
            if m:
                title_raw = m.group(1)
                current_title = re.sub(r"\W+", "", title_raw).lower()
                continue
            parsed = self.parse_line(line)
            if parsed:
                parsed['title_key'] = current_title
                key = parsed['text_1'].strip()
                mapping[key] = parsed

        cues = self.parse_srt(srt_file)
        if not cues:
            messagebox.showerror("Lỗi", "Không tìm thấy cue trong SRT")
            return

        audio_clip = AudioFileClip(audio_file)
        all_segments = []
        for i, cue in enumerate(cues):
            txt = cue['text'].strip()
            # try exact match or trimmed match
            key = txt
            data = mapping.get(key)
            # If not exact, try simplified whitespace/punctuation normalization
            if not data:
                norm = re.sub(r'[\s\n\r]+', '', txt)
                for k in mapping:
                    if re.sub(r'[\s\n\r]+', '', k) == norm:
                        data = mapping[k]
                        break
            # If still not found, create fallback data
            if not data:
                data = {'text_1': txt, 'text_2': '', 'text_3': '', 'position_type': 'LEFT', 'voice': self.voice_vars['M'].get()}

            duration = max(0.1, cue['end'] - cue['start'])
            frame_rgb = self.create_frame(data)
            # clip audio for this cue
            try:
                audio_sub = audio_clip.subclip(cue['start'], cue['end'])
            except Exception:
                # fallback: clip from start for duration
                audio_sub = audio_clip.subclip(0, min(duration, audio_clip.duration))
            v_seg = ImageClip(frame_rgb).set_duration(duration).set_audio(audio_sub)
            all_segments.append(v_seg)

        if all_segments:
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = f"output_Gemini_{time_str}.mp4"
            final_path = os.path.join(self.output_dir.get(), final_name)
            concatenate_videoclips(all_segments, method="compose").write_videofile(final_path, codec="libx264", audio_codec="aac", fps=10)
            messagebox.showinfo("Xong!", f"Video đã lưu: {final_path}")

    def create_frame(self, data, width=1280, height=720):
        # Determine background image: prefer title-specific image if provided
        title_img = None
        if data and data.get('title_key') and data.get('title_key') in self.bg_images:
            candidate = self.bg_images.get(data.get('title_key'))
            if candidate and os.path.exists(candidate):
                title_img = candidate

        if title_img:
            img = Image.open(title_img).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
        elif self.bg_path.get() and os.path.exists(self.bg_path.get()):
            img = Image.open(self.bg_path.get()).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
        else:
            img = Image.new('RGB', (width, height), color=(255, 245, 240))
        
        draw = ImageDraw.Draw(img)
        # Treat as Chinese (show pinyin) when language is Chinese or when the data contains pinyin text
        is_chinese = (self.lang_var.get() == "Chinese") or bool(data.get('text_2'))

        # Decide whether to draw subtitle/text box
        show_sub = getattr(self, 'show_sub_var', None) and self.show_sub_var.get()

        if show_sub:
            # Vẽ Box văn bản
            try:
                b_w = int(self.box_width_var.get())
                b_h = int(self.box_height_var.get())
            except:
                b_w, b_h = 400, 180

            # If single-reader mode is enabled, ignore position/width GUI settings
            if getattr(self, 'single_reader_var', None) and self.single_reader_var.get():
                margin = 20
                b_w = width - margin * 2
                b_h = 120
                cx = width // 2
                cy = height - b_h // 2 - margin
            else:
                pos_str = self.pos_left_var.get() if data['position_type'] == "LEFT" else self.pos_right_var.get()
                try:
                    y_r, x_r = map(float, pos_str.split(','))
                except:
                    y_r, x_r = (6.5, 4) if data['position_type'] == "LEFT" else (6.5, 12)

                cx, cy = int(width * (x_r / 16)), int(height * (y_r / 9))
            # Text box style rendering (3 sample styles)
            style = getattr(self, 'textbox_style_var', None) and self.textbox_style_var.get() or "Style1"
            box_radius = 15
            box_outline = (0, 0, 0)
            box_fill = (255, 240, 235)
            if style == "Style1":
                # Speech-bubble look: outer pale-blue rounded rect + inner white rounded rect
                box_radius = 18
                outer_fill = (217, 230, 242)
                outer_outline = (120, 120, 125)
                inner_fill = (255, 255, 255)
                inner_outline = (210, 210, 210)
                inset = 8
                # outer
                draw.rounded_rectangle([cx - b_w//2, cy - b_h//2, cx + b_w//2, cy + b_h//2], 
                                        radius=box_radius, fill=outer_fill, outline=outer_outline, width=1)
                # inner (white) inset
                draw.rounded_rectangle([cx - b_w//2 + inset, cy - b_h//2 + inset, cx + b_w//2 - inset, cy + b_h//2 - inset], 
                                        radius=max(6, box_radius-6), fill=inner_fill, outline=inner_outline, width=1)
            elif style == "Style2":
                # Modern light: soft shadow + light rounded box + subtle outline
                box_radius = 20
                shadow_color = (210, 210, 210)
                # draw shadow slightly offset (soft, light)
                draw.rounded_rectangle([cx - b_w//2 + 6, cy - b_h//2 + 6, cx + b_w//2 + 6, cy + b_h//2 + 6], 
                                        radius=box_radius+3, fill=shadow_color)
                box_fill = (245, 248, 250)
                box_outline = (200, 200, 200)
            elif style == "Style3":
                # Minimal: pale background with subtle border
                box_radius = 12
                box_fill = (250, 250, 250)
                box_outline = (200, 200, 200)

            # For Style1 we already drew outer+inner; for others, draw the single rectangle
            if style != "Style1":
                draw.rounded_rectangle([cx - b_w//2, cy - b_h//2, cx + b_w//2, cy + b_h//2], 
                                        radius=box_radius, fill=box_fill, outline=box_outline, width=1)

        # Chèn LOGO
        if self.logo_path.get() and os.path.exists(self.logo_path.get()):
            try:
                logo = Image.open(self.logo_path.get()).convert("RGBA")
                l_scale = int(self.logo_size_var.get()) / 100
                l_width = int(width * l_scale)
                w_percent = (l_width / float(logo.size[0]))
                l_height = int((float(logo.size[1]) * float(w_percent)))
                logo = logo.resize((l_width, l_height), Image.Resampling.LANCZOS)
                ly_r, lx_r = map(float, self.logo_pos_var.get().split(','))
                lx, ly = int(width * (lx_r / 16)) - l_width//2, int(height * (ly_r / 9)) - l_height//2
                img.paste(logo, (lx, ly), logo)
            except Exception as e:
                print(f"Lỗi chèn logo: {e}")

        # CẬP NHẬT FONT CHỮ VÀ KÍCH THƯỚC
        def get_font(name, size):
            # Ưu tiên tìm font trong hệ thống Windows
            paths = [
                f"C:\\Windows\\Fonts\\{name}",
                name
            ]
            for p in paths:
                try: return ImageFont.truetype(p, size)
                except: continue
            return ImageFont.load_default()

        # Determine text colors and font sizes based on selected style
        style = getattr(self, 'textbox_style_var', None) and self.textbox_style_var.get() or "Style1"
        # Base font sizes
        base_main_size = 23
        base_pinyin_size = 15
        base_eng_size = 16
        # If Style2 selected, increase Hanzi size by 20%
        if style == "Style2":
            main_size = int(base_main_size * 1.2)
        else:
            main_size = base_main_size

        # For Spanish, reduce main text size by 20%
        if self.lang_var.get() == "Spanish":
            main_size = int(main_size * 0.8)

        # Create fonts with computed sizes
        f_main = get_font("msyh.ttc", main_size)
        f_pinyin = get_font("arial.ttf", base_pinyin_size)
        f_eng = get_font("arial.ttf", base_eng_size)

        # Colors per style
        if style == "Style1":
            main_color = "black"
            pinyin_color = "#555555"
            eng_color = "black"
        elif style == "Style2":
            main_color = (48, 36, 28)  # brown-black mix
            pinyin_color = "#666666"
            eng_color = "#222222"
        elif style == "Style3":
            main_color = (0, 100, 0)
            pinyin_color = "#666666"
            eng_color = "black"
        else:
            main_color = (0, 100, 0)
            pinyin_color = "#555555"
            eng_color = "black"

        def wrap(t, f, max_w):
            if not t: return ""
            words = list(t) if is_chinese and f == f_main else t.split(' ')
            lines, cur = [], []
            for wd in words:
                sep = "" if is_chinese and f == f_main else " "
                test = sep.join(cur + [wd]).strip()
                if f.getbbox(test)[2] <= max_w: cur.append(wd)
                else: 
                    lines.append(sep.join(cur))
                    cur = [wd]
            lines.append(sep.join(cur))
            return '\n'.join(lines)

        padding = 40
        if getattr(self, 'show_sub_var', None) and self.show_sub_var.get():
            if is_chinese:
                txt_pinyin = wrap(data['text_2'], f_pinyin, b_w - padding)
                txt_hanzi = wrap(data['text_1'], f_main, b_w - padding)
                txt_eng = wrap(data['text_3'], f_eng, b_w - padding)
                # Style-specific vertical offsets so layout matches sample bubble
                if style == "Style1":
                    pinyin_off, main_off, eng_off = -36, -6, 40
                elif style == "Style2":
                    pinyin_off, main_off, eng_off = -45, -5, 45
                else:
                    pinyin_off, main_off, eng_off = -45, -5, 45
                draw.text((cx, cy + pinyin_off), txt_pinyin, fill=pinyin_color, font=f_pinyin, anchor="mm", align="center")
                draw.text((cx, cy + main_off), txt_hanzi, fill=main_color, font=f_main, anchor="mm", align="center")
                draw.text((cx, cy + eng_off), txt_eng, fill=eng_color, font=f_eng, anchor="mm", align="center")
            else:
                txt_main = wrap(data['text_1'], f_main, b_w - padding)
                txt_en = wrap(data['text_2'], f_eng, b_w - padding)
                draw.text((cx, cy - 6), txt_main, fill=main_color, font=f_main, anchor="mm", align="center")
                draw.text((cx, cy + 40), txt_en, fill=eng_color, font=f_eng, anchor="mm", align="center")

        return np.array(img)

    async def generate_audio(self, text, voice, speed_str, filename):
        rate = f"{int(speed_str.replace('%', '')) - 100:+d}%"
        await edge_tts.Communicate(text, voice, rate=rate).save(filename)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        all_segments = []
        current_title = None
        seg_index = 0
        for line in lines:
            m = re.match(r"\s*\[([^\]]+)\]", line)
            if m:
                current_title = re.sub(r"\W+", "", m.group(1)).lower()
                continue
            data = self.parse_line(line)
            if not data:
                continue
            data['title_key'] = current_title
            i = seg_index
            seg_index += 1
            
            # Handle Spanish sentence splitting with pauses
            if self.lang_var.get() == "Spanish" and '.' in data['text_1']:
                sentences = [s.strip() for s in data['text_1'].split('.') if s.strip()]
                # Clean and filter out empty sentences
                sentences = [re.sub(r'[?/.()¿¡!]', '', s).strip() for s in sentences]
                sentences = [s for s in sentences if s]
                if sentences:
                    audio_clips = []
                    for j, sent in enumerate(sentences):
                        temp_audio = f"temp_{i}_{j}.mp3"
                        asyncio.run(self.generate_audio(sent, data['voice'], self.selected_speed.get(), temp_audio))
                        a_clip = AudioFileClip(temp_audio)
                        audio_clips.append(a_clip)
                        # Add 0.1s pause between sentences, but not after the last one
                        if j < len(sentences) - 1:
                            silence_pause = AudioClip(lambda t: [0, 0], duration=0.1, fps=44100)
                            audio_clips.append(silence_pause)
                    # Add the standard 0.1s silence at the end
                    silence_end = AudioClip(lambda t: [0, 0], duration=0.1, fps=44100)
                    audio_clips.append(silence_end)
                    final_a = concatenate_audioclips(audio_clips)
                else:
                    # Fallback if no valid sentences
                    temp_audio = f"temp_{i}.mp3"
                    clean_txt = re.sub(r'[?/.()¿¡!]', '', data['text_1'])
                    asyncio.run(self.generate_audio(clean_txt, data['voice'], self.selected_speed.get(), temp_audio))
                    a_clip = AudioFileClip(temp_audio)
                    silence = AudioClip(lambda t: [0, 0], duration=0.1, fps=44100)
                    final_a = concatenate_audioclips([a_clip, silence])
            else:
                # Default behavior for Chinese or no periods
                temp_audio = f"temp_{i}.mp3"
                clean_txt = re.sub(r'[?/.()¿¡!]', '', data['text_1'])
                asyncio.run(self.generate_audio(clean_txt, data['voice'], self.selected_speed.get(), temp_audio))
                a_clip = AudioFileClip(temp_audio)
                silence = AudioClip(lambda t: [0, 0], duration=0.1, fps=44100)
                final_a = concatenate_audioclips([a_clip, silence])
            frame_rgb = self.create_frame(data)
            v_seg = ImageClip(frame_rgb).set_duration(final_a.duration).set_audio(final_a)
            all_segments.append(v_seg)

        if all_segments:
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = f"output_{self.lang_var.get()}_{time_str}.mp4"
            final_path = os.path.join(self.output_dir.get(), final_name)
            concatenate_videoclips(all_segments, method="compose").write_videofile(final_path, codec="libx264", audio_codec="aac", fps=10)
            # Clean up all temp audio files
            for temp_file in glob.glob("temp_*.mp3"):
                try:
                    os.remove(temp_file)
                except:
                    pass
            messagebox.showinfo("Xong!", f"Video đã lưu: {final_path}")

    def start_process(self):
        # Choose main text file (same format as before)
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if not file:
            return
        self.status_label.config(text="Đang xử lý... Vui lòng đợi", fg="red")
        self.root.update()
        try:
            if self.engine_var.get() == "Gemini":
                # Ensure gemini audio and srt are provided; if not, prompt
                if not self.gemini_audio.get():
                    f = filedialog.askopenfilename(title="Chọn Gemini Audio", filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.flac")])
                    if f: self.gemini_audio.set(f)
                if not self.gemini_srt.get():
                    s = filedialog.askopenfilename(title="Chọn Gemini SRT", filetypes=[("SRT files", "*.srt *.txt")])
                    if s: self.gemini_srt.set(s)
                if not self.gemini_audio.get() or not self.gemini_srt.get():
                    messagebox.showerror("Thiếu file", "Vui lòng cung cấp file audio và SRT cho Gemini")
                else:
                    self.process_video_gemini(file, self.gemini_audio.get(), self.gemini_srt.get())
            else:
                # Legacy Edge TTTS behavior
                self.process_video(file)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))
        # Clean up any remaining temp audio files
        for temp_file in glob.glob("temp_*.mp3"):
            try:
                os.remove(temp_file)
            except:
                pass
        self.status_label.config(text="Sẵn sàng", fg="blue")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGenerator(root)
    root.mainloop()