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
        self.root.title("Multilingual Lesson Video Generator")
        self.root.geometry("700x950")

        # 1. Danh sách giọng đọc theo ngôn ngữ
        self.voices_data = {
            "Spanish": ["es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-MX-JorgeNeural", 
                        "es-MX-DaliaNeural", "es-US-AlonsoNeural", "es-US-PalomaNeural"],
            "Chinese": ["zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunjianNeural", 
                        "zh-CN-XiaoyiNeural", "zh-HK-HiuGaaiNeural", "zh-TW-HsiaoChenNeural"]
        }

        # 2. Các biến điều khiển
        self.lang_var = tk.StringVar(value="Spanish")
        self.voice_vars = {tag: tk.StringVar() for tag in ["M", "M1", "M2", "F", "F1", "F2"]}
        self.set_default_voices()

        self.pos_left_var = tk.StringVar(value="6.5,4")
        self.pos_right_var = tk.StringVar(value="6.5,12")
        self.bg_path = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.selected_speed = tk.StringVar(value="100%")

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
        # Chọn ngôn ngữ
        lang_frame = tk.LabelFrame(self.root, text=" 1. CHỌN NGÔN NGỮ ", font=("Arial", 10, "bold"), pady=10)
        lang_frame.pack(fill="x", padx=20, pady=5)
        ttk.Combobox(lang_frame, textvariable=self.lang_var, values=["Spanish", "Chinese"], 
                     state="readonly", width=20).pack()
        self.lang_var.trace("w", lambda *args: self.update_voice_options())

        # Cài đặt giọng đọc
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

        # Vị trí Box
        pos_frame = tk.LabelFrame(self.root, text=" 3. VỊ TRÍ BOX (y,x) ", font=("Arial", 10, "bold"), pady=10)
        pos_frame.pack(fill="x", padx=20, pady=5)
        tk.Label(pos_frame, text="Box Trái:").grid(row=0, column=0, padx=10)
        tk.Entry(pos_frame, textvariable=self.pos_left_var, width=10).grid(row=0, column=1)
        tk.Label(pos_frame, text="Box Phải:").grid(row=0, column=2, padx=10)
        tk.Entry(pos_frame, textvariable=self.pos_right_var, width=10).grid(row=0, column=3)

        # Nền & Tốc độ
        other_frame = tk.Frame(self.root)
        other_frame.pack(pady=10)
        tk.Label(other_frame, text="Tốc độ:").grid(row=0, column=0)
        ttk.Combobox(other_frame, textvariable=self.selected_speed, values=[f"{i}%" for i in range(50, 160, 10)], width=8).grid(row=0, column=1, padx=10)
        
        tk.Button(other_frame, text="Chọn Nền", command=self.browse_bg).grid(row=0, column=2, padx=5)
        tk.Button(other_frame, text="Thư Mục Lưu", command=self.browse_folder).grid(row=0, column=3, padx=5)

        # Bắt đầu
        self.btn = tk.Button(self.root, text="BẮT ĐẦU TẠO VIDEO", bg="#4CAF50", fg="white", 
                             font=("Arial", 12, "bold"), command=self.start_process, padx=40, pady=15)
        self.btn.pack(pady=20)
        self.status_label = tk.Label(self.root, text="Ready", fg="blue")
        self.status_label.pack()

    def browse_bg(self):
        f = filedialog.askopenfilename(); self.bg_path.set(f if f else "")
    def browse_folder(self):
        f = filedialog.askdirectory(); self.output_dir.set(f if f else "")

    def parse_line(self, line):
        parts = line.split("|")
        if len(parts) >= 3:
            tag = parts[0].strip().upper()
            pos_type = "LEFT" if tag in ["M", "M1", "F1"] else "RIGHT"
            voice = self.voice_vars.get(tag, self.voice_vars["M"]).get()
            return {
                "position_type": pos_type, 
                "voice": voice, 
                "main_text": parts[0].strip() if self.lang_var.get() == "Chinese" else parts[1].strip(), # Dự phòng logic tag
                "text_1": parts[0].strip(), # Chinese
                "text_2": parts[1].strip(), # Pinyin
                "text_3": parts[2].strip()  # English
            }
        return None

    def create_frame(self, data, width=1280, height=720):
        # 1. Background
        if self.bg_path.get() and os.path.exists(self.bg_path.get()):
            img = Image.open(self.bg_path.get()).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
        else:
            img = Image.new('RGB', (width, height), color=(255, 245, 240))
        
        draw = ImageDraw.Draw(img)
        is_chinese = (self.lang_var.get() == "Chinese")

        # 2. Tọa độ
        pos_str = self.pos_left_var.get() if data['position_type'] == "LEFT" else self.pos_right_var.get()
        try:
            y_r, x_r = map(float, pos_str.split(','))
        except:
            y_r, x_r = (6.5, 4) if data['position_type'] == "LEFT" else (6.5, 12)

        cx, cy = int(width * (x_r / 16)), int(height * (y_r / 9))
        box_w, box_h = 400, 180
        draw.rounded_rectangle([cx-box_w//2, cy-box_h//2, cx+box_w//2, cy+box_h//2], radius=15, fill=(255, 240, 235), outline=(0, 128, 0), width=3)

        # 3. Font chữ
        try:
            f_main = ImageFont.truetype("msyh.ttc" if is_chinese else "arial.ttf", 22) # Chữ chính
            f_sub = ImageFont.truetype("arial.ttf", 11)   # Pinyin (50%)
            f_eng = ImageFont.truetype("arial.ttf", 15)   # English (70%)
        except:
            f_main = f_sub = f_eng = ImageFont.load_default()

        def wrap(t, f, w):
            words = list(t) if is_chinese and f == f_main else t.split(' ')
            l, cur = [], []
            for wd in words:
                sep = "" if is_chinese and f == f_main else " "
                test = sep.join(cur + [wd]).strip()
                if f.getbbox(test)[2] <= w: cur.append(wd)
                else: l.append(sep.join(cur)); cur = [wd]
            l.append(sep.join(cur)); return '\n'.join(l)

        # 4. Vẽ chữ theo ngôn ngữ
        if is_chinese:
            # text_1: Chinese, text_2: Pinyin, text_3: English
            txt_pinyin = wrap(data['text_2'], f_sub, box_w - 40)
            txt_chinese = wrap(data['text_1'], f_main, box_w - 40)
            txt_english = wrap(data['text_3'], f_eng, box_w - 40)

            draw.text((cx, cy - 45), txt_pinyin, fill="#555555", font=f_sub, anchor="mm", align="center")
            draw.text((cx, cy - 5), txt_chinese, fill=(0, 100, 0), font=f_main, anchor="mm", align="center")
            draw.text((cx, cy + 45), txt_english, fill="black", font=f_eng, anchor="mm", align="center")
        else:
            # Chế độ Spanish cũ (text_1: tag, text_2: Spanish, text_3: English)
            txt_es = wrap(data['text_2'], f_main, box_w - 40)
            txt_en = wrap(data['text_3'], f_eng, box_w - 40)
            draw.text((cx, cy - 15), txt_es, fill=(0, 100, 0), font=f_main, anchor="mm", align="center")
            draw.text((cx, cy + 30), txt_en, fill="black", font=f_eng, anchor="mm", align="center")

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
            # Đọc text chính (Chinese hoặc Spanish)
            read_text = data['text_1'] if self.lang_var.get() == "Chinese" else data['text_2']
            clean_txt = re.sub(r'[?/.()¿¡!]', '', read_text)
            
            asyncio.run(self.generate_audio(clean_txt, data['voice'], self.selected_speed.get(), temp_audio))
            
            a_clip = AudioFileClip(temp_audio)
            silence = AudioClip(lambda t: [0, 0], duration=0.9, fps=44100)
            final_a = concatenate_audioclips([a_clip, silence])
            
            frame_rgb = self.create_frame(data)
            v_seg = ImageClip(frame_rgb).set_duration(final_a.duration).set_audio(final_a)
            all_segments.append(v_seg)

        if all_segments:
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_path = os.path.join(self.output_dir.get(), f"output_{self.lang_var.get()}_{time_str}.mp4")
            concatenate_videoclips(all_segments, method="compose").write_videofile(final_path, codec="libx264", audio_codec="aac", fps=10)
            for i in range(len(lines)):
                if os.path.exists(f"temp_{i}.mp3"): os.remove(f"temp_{i}.mp3")
            messagebox.showinfo("Thành công", f"Video lưu tại: {final_path}")

    def start_process(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.status_label.config(text="Đang xử lý...", fg="red"); self.root.update()
            try: self.process_video(file)
            except Exception as e: messagebox.showerror("Lỗi", str(e))
            self.status_label.config(text="Ready", fg="blue")

if __name__ == "__main__":
    root = tk.Tk(); app = VideoGenerator(root); root.mainloop()