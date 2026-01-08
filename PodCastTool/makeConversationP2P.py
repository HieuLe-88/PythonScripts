import asyncio
import edge_tts
import os
import re
import numpy as np
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
            "Spanish": ["es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-MX-JorgeNeural", 
                        "es-MX-DaliaNeural", "es-US-AlonsoNeural", "es-US-PalomaNeural"],
            "Chinese": ["zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunjianNeural", 
                        "zh-CN-XiaoyiNeural", "zh-HK-HiuGaaiNeural", "zh-TW-HsiaoChenNeural"]
        }

        # Biến điều khiển giao diện
        self.lang_var = tk.StringVar(value="Spanish")
        self.voice_vars = {tag: tk.StringVar() for tag in ["M", "M1", "M2", "F", "F1", "F2"]}
        
        # Vị trí và Kích thước Box
        self.pos_left_var = tk.StringVar(value="6.5,4")
        self.pos_right_var = tk.StringVar(value="6.5,12")
        self.box_width_var = tk.StringVar(value="400")   # Mặc định rộng 400
        self.box_height_var = tk.StringVar(value="180")  # Mặc định cao 180
        
        self.bg_path = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.selected_speed = tk.StringVar(value="100%")

        self.set_default_voices()
        self.setup_gui()

    def set_default_voices(self):
        lang = self.lang_var.get()
        v_list = self.voices_data[lang]
        for i, tag in enumerate(["M", "M1", "M2", "F", "F1", "F2"]):
            self.voice_vars[tag].set(v_list[i % len(v_list)])

    def update_voice_options(self, event=None):
        lang = self.lang_var.get()
        new_values = self.voices_data[lang]
        for cb in self.voice_combos:
            cb['values'] = new_values
        self.set_default_voices()

    def setup_gui(self):
        # 1. CHỌN NGÔN NGỮ
        lang_frame = tk.LabelFrame(self.root, text=" 1. CHỌN NGÔN NGỮ ", font=("Arial", 10, "bold"), pady=10)
        lang_frame.pack(fill="x", padx=20, pady=5)
        ttk.Combobox(lang_frame, textvariable=self.lang_var, values=["Spanish", "Chinese"], 
                     state="readonly", width=20).pack()
        self.lang_var.trace("w", lambda *args: self.update_voice_options())

        # 2. CÀI ĐẶT GIỌNG ĐỌC
        v_frame = tk.LabelFrame(self.root, text=" 2. CÀI ĐẶT GIỌNG ĐỌC ", font=("Arial", 10, "bold"), pady=10)
        v_frame.pack(fill="x", padx=20, pady=5)
        self.voice_combos = []
        container = tk.Frame(v_frame)
        container.pack()
        tags = ["M", "M1", "M2", "F", "F1", "F2"]
        for i, tag in enumerate(tags):
            r, c = divmod(i, 2)
            tk.Label(container, text=f"Giọng {tag}:").grid(row=r, column=c*2, padx=5, pady=2, sticky="e")
            cb = ttk.Combobox(container, textvariable=self.voice_vars[tag], values=self.voices_data[self.lang_var.get()], width=20)
            cb.grid(row=r, column=c*2+1, padx=5, pady=2)
            self.voice_combos.append(cb)

        # 3. THIẾT KẾ BOX (VỊ TRÍ & KÍCH THƯỚC)
        design_frame = tk.LabelFrame(self.root, text=" 3. THIẾT KẾ BOX (VỊ TRÍ & KÍCH THƯỚC) ", font=("Arial", 10, "bold"), pady=10)
        design_frame.pack(fill="x", padx=20, pady=5)
        
        # Vị trí
        tk.Label(design_frame, text="Y,X Box Trái:").grid(row=0, column=0, padx=10, pady=5)
        tk.Entry(design_frame, textvariable=self.pos_left_var, width=10).grid(row=0, column=1)
        tk.Label(design_frame, text="Y,X Box Phải:").grid(row=0, column=2, padx=10, pady=5)
        tk.Entry(design_frame, textvariable=self.pos_right_var, width=10).grid(row=0, column=3)

        # Kích thước
        tk.Label(design_frame, text="Chiều Rộng:").grid(row=1, column=0, padx=10, pady=5)
        tk.Entry(design_frame, textvariable=self.box_width_var, width=10).grid(row=1, column=1)
        tk.Label(design_frame, text="Chiều Cao:").grid(row=1, column=2, padx=10, pady=5)
        tk.Entry(design_frame, textvariable=self.box_height_var, width=10).grid(row=1, column=3)

        # 4. CẤU HÌNH KHÁC
        other_frame = tk.Frame(self.root)
        other_frame.pack(pady=10)
        tk.Label(other_frame, text="Tốc độ:").grid(row=0, column=0)
        ttk.Combobox(other_frame, textvariable=self.selected_speed, values=[f"{i}%" for i in range(50, 160, 10)], width=8).grid(row=0, column=1, padx=10)
        tk.Button(other_frame, text="Chọn Ảnh Nền", command=self.browse_bg).grid(row=0, column=2, padx=5)
        tk.Button(other_frame, text="Thư Mục Lưu", command=self.browse_folder).grid(row=0, column=3, padx=5)

        # NÚT BẮT ĐẦU
        self.btn = tk.Button(self.root, text="BẮT ĐẦU TẠO VIDEO", bg="#4CAF50", fg="white", 
                             font=("Arial", 12, "bold"), command=self.start_process, padx=40, pady=15)
        self.btn.pack(pady=20)
        self.status_label = tk.Label(self.root, text="Sẵn sàng", fg="blue")
        self.status_label.pack()

    def browse_bg(self):
        f = filedialog.askopenfilename()
        if f: self.bg_path.set(f)
        
    def browse_folder(self):
        f = filedialog.askdirectory()
        if f: self.output_dir.set(f)

    def parse_line(self, line):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            tag = parts[0].upper()
            pos_type = "LEFT" if tag in ["M", "M1", "F1"] else "RIGHT"
            voice = self.voice_vars.get(tag, self.voice_vars["M"]).get()
            
            return {
                "position_type": pos_type, 
                "voice": voice, 
                "text_1": parts[1], 
                "text_2": parts[2], 
                "text_3": parts[3] if len(parts) > 3 else "" 
            }
        return None

    def create_frame(self, data, width=1280, height=720):
        # Tạo nền
        if self.bg_path.get() and os.path.exists(self.bg_path.get()):
            img = Image.open(self.bg_path.get()).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
        else:
            img = Image.new('RGB', (width, height), color=(255, 245, 240))
        
        draw = ImageDraw.Draw(img)
        is_chinese = (self.lang_var.get() == "Chinese")

        # Lấy kích thước Box từ GUI
        try:
            b_w = int(self.box_width_var.get())
            b_h = int(self.box_height_var.get())
        except:
            b_w, b_h = 400, 180

        # Lấy tọa độ Box
        pos_str = self.pos_left_var.get() if data['position_type'] == "LEFT" else self.pos_right_var.get()
        try:
            y_r, x_r = map(float, pos_str.split(','))
        except:
            y_r, x_r = (6.5, 4) if data['position_type'] == "LEFT" else (6.5, 12)

        cx, cy = int(width * (x_r / 16)), int(height * (y_r / 9))
        
        # Vẽ Box
        draw.rounded_rectangle([cx - b_w//2, cy - b_h//2, cx + b_w//2, cy + b_h//2], 
                               radius=15, fill=(255, 240, 235), outline=(0, 128, 0), width=3)

        # Font (Ưu tiên font hỗ trợ tiếng Trung)
        def get_font(size):
            font_names = ["msyh.ttc", "simhei.ttf", "arial.ttf"]
            for f in font_names:
                try: return ImageFont.truetype(f, size)
                except: continue
            return ImageFont.load_default()

        f_main = get_font(22) 
        f_sub = get_font(11) 
        f_eng = get_font(15)

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
        if is_chinese:
            txt_pinyin = wrap(data['text_2'], f_sub, b_w - padding)
            txt_hanzi = wrap(data['text_1'], f_main, b_w - padding)
            txt_eng = wrap(data['text_3'], f_eng, b_w - padding)

            draw.text((cx, cy - 45), txt_pinyin, fill="#555555", font=f_sub, anchor="mm", align="center")
            draw.text((cx, cy - 5), txt_hanzi, fill=(0, 100, 0), font=f_main, anchor="mm", align="center")
            draw.text((cx, cy + 45), txt_eng, fill="black", font=f_eng, anchor="mm", align="center")
        else:
            txt_main = wrap(data['text_1'], f_main, b_w - padding)
            txt_en = wrap(data['text_2'], f_eng, b_w - padding)
            draw.text((cx, cy - 15), txt_main, fill=(0, 100, 0), font=f_main, anchor="mm", align="center")
            draw.text((cx, cy + 25), txt_en, fill="black", font=f_eng, anchor="mm", align="center")

        return np.array(img)

    async def generate_audio(self, text, voice, speed_str, filename):
        rate = f"{int(speed_str.replace('%', '')) - 100:+d}%"
        await edge_tts.Communicate(text, voice, rate=rate).save(filename)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [l for l in f.readlines() if l.strip()]

        all_segments = []
        for i, line in enumerate(lines):
            data = self.parse_line(line)
            if not data: continue
            
            temp_audio = f"temp_{i}.mp3"
            clean_txt = re.sub(r'[?/.()¿¡!]', '', data['text_1'])
            
            asyncio.run(self.generate_audio(clean_txt, data['voice'], self.selected_speed.get(), temp_audio))
            
            a_clip = AudioFileClip(temp_audio)
            silence = AudioClip(lambda t: [0, 0], duration=0.9, fps=44100)
            final_a = concatenate_audioclips([a_clip, silence])
            
            frame_rgb = self.create_frame(data)
            v_seg = ImageClip(frame_rgb).set_duration(final_a.duration).set_audio(final_a)
            all_segments.append(v_seg)

        if all_segments:
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = f"output_{self.lang_var.get()}_{time_str}.mp4"
            final_path = os.path.join(self.output_dir.get(), final_name)
            
            concatenate_videoclips(all_segments, method="compose").write_videofile(
                final_path, codec="libx264", audio_codec="aac", fps=10)
            
            for i in range(len(lines)):
                if os.path.exists(f"temp_{i}.mp3"): os.remove(f"temp_{i}.mp3")
            messagebox.showinfo("Xong!", f"Video đã lưu: {final_path}")

    def start_process(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.status_label.config(text="Đang xử lý... Vui lòng đợi", fg="red")
            self.root.update()
            try:
                self.process_video(file)
            except Exception as e:
                messagebox.showerror("Lỗi", str(e))
            self.status_label.config(text="Sẵn sàng", fg="blue")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGenerator(root)
    root.mainloop()