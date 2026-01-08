import asyncio
import edge_tts
import os
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from moviepy.editor import AudioFileClip, concatenate_videoclips, concatenate_audioclips, AudioClip, ImageClip

class VideoGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Spanish Lesson - Custom Box Position")
        self.root.geometry("650x950")

        # 1. Biến giọng đọc
        self.voice_vars = {
            "M":  tk.StringVar(value="es-ES-AlvaroNeural"),
            "M1": tk.StringVar(value="es-MX-JorgeNeural"),
            "M2": tk.StringVar(value="es-US-AlonsoNeural"),
            "F":  tk.StringVar(value="es-ES-ElviraNeural"),
            "F1": tk.StringVar(value="es-MX-DaliaNeural"),
            "F2": tk.StringVar(value="es-US-PalomaNeural")
        }
        
        # 2. Biến vị trí Box (Mặc định theo yêu cầu)
        # Format: "y,x"
        self.pos_left_var = tk.StringVar(value="6.5,4")
        self.pos_right_var = tk.StringVar(value="6.5,12")

        self.bg_path = tk.StringVar(value="")
        self.logo_path = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.selected_speed = tk.StringVar(value="100%")

        voices = ["es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-MX-JorgeNeural", 
                  "es-MX-DaliaNeural", "es-US-AlonsoNeural", "es-US-PalomaNeural"]

        # GUI - Cài đặt giọng
        tk.Label(root, text=" CÀI ĐẶT GIỌNG ĐỌC", font=("Arial", 11, "bold")).pack(pady=5)
        v_frame = tk.Frame(root); v_frame.pack()
        row = 0
        for tag, var in self.voice_vars.items():
            tk.Label(v_frame, text=f"Giọng {tag}:").grid(row=row, column=0, padx=5, pady=2, sticky="e")
            ttk.Combobox(v_frame, textvariable=var, values=voices, width=25).grid(row=row, column=1, padx=5, pady=2)
            row += 1

        tk.Frame(root, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=20, pady=10)

        # --- GUI - TÙY CHỈNH VỊ TRÍ BOX (MỚI) ---
        tk.Label(root, text=" TÙY CHỈNH VỊ TRÍ BOX (Tỉ lệ 9:16)", font=("Arial", 11, "bold")).pack()
        pos_frame = tk.Frame(root); pos_frame.pack(pady=5)
        
        tk.Label(pos_frame, text="Box Trái (y,x):").grid(row=0, column=0, padx=5)
        tk.Entry(pos_frame, textvariable=self.pos_left_var, width=10).grid(row=0, column=1, padx=5)
        
        tk.Label(pos_frame, text="Box Phải (y,x):").grid(row=0, column=2, padx=5)
        tk.Entry(pos_frame, textvariable=self.pos_right_var, width=10).grid(row=0, column=3, padx=5)
        
        tk.Label(root, text="Ví dụ: 2.5,4 nghĩa là y=2.5/9 và x=4/16", font=("Arial", 8, "italic"), fg="gray").pack()

        # GUI - Các phần khác
        tk.Label(root, text="Tốc độ đọc:").pack(pady=(10,0))
        ttk.Combobox(root, textvariable=self.selected_speed, values=[f"{i}%" for i in range(50, 160, 10)], width=10).pack()

        bg_f = tk.Frame(root); bg_f.pack(pady=10)
        tk.Label(bg_f, text="Nền:").pack(side=tk.LEFT); tk.Entry(bg_f, textvariable=self.bg_path, width=30).pack(side=tk.LEFT, padx=5)
        tk.Button(bg_f, text="Mở", command=self.browse_bg).pack(side=tk.LEFT)

        tk.Button(root, text="Chọn Thư Mục Lưu", command=self.browse_folder).pack()

        self.btn = tk.Button(root, text="BẮT ĐẦU TẠO VIDEO", bg="#4CAF50", fg="white", 
                             font=("Arial", 12, "bold"), command=self.start_process, padx=30, pady=10)
        self.btn.pack(pady=15)
        self.status_label = tk.Label(root, text="Ready", fg="blue"); self.status_label.pack()

    def browse_bg(self):
        f = filedialog.askopenfilename(); self.bg_path.set(f if f else "")
    def browse_logo(self):
        f = filedialog.askopenfilename(); self.logo_path.set(f if f else "")
    def browse_folder(self):
        f = filedialog.askdirectory(); self.output_dir.set(f if f else "")

    def parse_line(self, line):
        parts = line.split("|")
        if len(parts) >= 3:
            tag = parts[0].strip().upper()
            pos_type = "LEFT" if tag in ["M", "M1", "F1"] else "RIGHT"
            voice = self.voice_vars.get(tag, self.voice_vars["M"]).get()
            return {"position_type": pos_type, "voice": voice, "es_text": parts[1].strip(), "en_text": parts[2].strip()}
        return None

    def create_frame(self, es_text, en_text, position_type, width=1280, height=720):
        # 1. Tạo nền
        if self.bg_path.get() and os.path.exists(self.bg_path.get()):
            img = Image.open(self.bg_path.get()).convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
        else:
            img = Image.new('RGB', (width, height), color=(255, 245, 240))
        
        draw = ImageDraw.Draw(img)

        # 2. Xử lý tọa độ từ GUI
        try:
            if position_type == "LEFT":
                raw_pos = self.pos_left_var.get().split(',')
            else:
                raw_pos = self.pos_right_var.get().split(',')
            
            y_ratio = float(raw_pos[0])
            x_ratio = float(raw_pos[1])
        except:
            # Fallback nếu user nhập sai format
            y_ratio, x_ratio = (2.5, 4) if position_type == "LEFT" else (2.5, 12)

        cx = int(width * (x_ratio / 16))
        cy = int(height * (y_ratio / 9))

        # 3. Vẽ Box
        box_w, box_h = 350, 150
        draw.rounded_rectangle([cx-box_w//2, cy-box_h//2, cx+box_w//2, cy+box_h//2], radius=15, fill=(255, 240, 235), outline=(0, 128, 0), width=3)

        try:
            es_f, en_f = ImageFont.truetype("arial.ttf", 26), ImageFont.truetype("arial.ttf", 18)
        except:
            es_f = en_f = ImageFont.load_default()

        def wrap(t, f, w):
            words = t.split(' '); l, cur = [], []
            for wd in words:
                if f.getbbox(' '.join(cur + [wd]))[2] <= w: cur.append(wd)
                else: l.append(' '.join(cur)); cur = [wd]
            l.append(' '.join(cur)); return '\n'.join(l)

        draw.text((cx, cy-20), wrap(es_text, es_f, box_w-40), fill=(0, 100, 0), font=es_f, anchor="mm", align="center")
        draw.text((cx, cy+25), wrap(en_text, en_f, box_w-40), fill="black", font=en_f, anchor="mm", align="center")

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
            clean_txt = re.sub(r'[?/.()¿¡!]', '', data['es_text'])
            asyncio.run(self.generate_audio(clean_txt, data['voice'], self.selected_speed.get(), temp_audio))
            a_clip = AudioFileClip(temp_audio)
            silence = AudioClip(lambda t: [0, 0], duration=0.9, fps=44100)
            final_a = concatenate_audioclips([a_clip, silence])
            frame_rgb = self.create_frame(data['es_text'], data['en_text'], data['position_type'])
            v_seg = ImageClip(frame_rgb).set_duration(final_a.duration).set_audio(final_a)
            all_segments.append(v_seg)

        if all_segments:
            final_path = os.path.join(self.output_dir.get(), "custom_pos_video.mp4")
            concatenate_videoclips(all_segments, method="compose").write_videofile(final_path, codec="libx264", audio_codec="aac", fps=5)
            for i in range(len(lines)):
                if os.path.exists(f"temp_{i}.mp3"): os.remove(f"temp_{i}.mp3")
            messagebox.showinfo("Xong!", f"Video đã lưu tại: {final_path}")

    def start_process(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.status_label.config(text="Đang tạo...", fg="red"); self.root.update()
            try: self.process_video(file)
            except Exception as e: messagebox.showerror("Lỗi", str(e))
            self.status_label.config(text="Ready", fg="blue")

if __name__ == "__main__":
    root = tk.Tk(); app = VideoGenerator(root); root.mainloop()