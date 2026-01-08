import asyncio
import edge_tts
import os
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from moviepy.editor import AudioFileClip, concatenate_videoclips, concatenate_audioclips, AudioClip, ImageClip

class VideoGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Spanish Lesson - 6 Voices & Custom Background")
        self.root.geometry("650x850")

        # 1. Khai báo biến
        self.voice_vars = {
            "M":  tk.StringVar(value="es-ES-AlvaroNeural"),
            "M1": tk.StringVar(value="es-MX-JorgeNeural"),
            "M2": tk.StringVar(value="es-US-AlonsoNeural"),
            "F":  tk.StringVar(value="es-ES-ElviraNeural"),
            "F1": tk.StringVar(value="es-MX-DaliaNeural"),
            "F2": tk.StringVar(value="es-US-PalomaNeural")
        }
        self.bg_path = tk.StringVar(value="")
        self.logo_path = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.selected_speed = tk.StringVar(value="100%")

        voices = ["es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-MX-JorgeNeural", 
                  "es-MX-DaliaNeural", "es-US-AlonsoNeural", "es-US-PalomaNeural"]

        # 2. Giao diện chọn giọng
        tk.Label(root, text=" CÀI ĐẶT GIỌNG ĐỌC", font=("Arial", 12, "bold")).pack(pady=10)
        v_frame = tk.Frame(root)
        v_frame.pack()
        row = 0
        for tag, var in self.voice_vars.items():
            tk.Label(v_frame, text=f"Giọng {tag}:").grid(row=row, column=0, padx=5, pady=2, sticky="e")
            ttk.Combobox(v_frame, textvariable=var, values=voices, width=25).grid(row=row, column=1, padx=5, pady=2)
            row += 1

        # 3. Giao diện chọn File Nền & Logo
        tk.Frame(root, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=20, pady=15)
        
        # Background Chọn
        bg_frame = tk.Frame(root)
        bg_frame.pack(pady=5)
        tk.Label(bg_frame, text="Background Image:").pack(side=tk.LEFT)
        tk.Entry(bg_frame, textvariable=self.bg_path, width=30).pack(side=tk.LEFT, padx=5)
        tk.Button(bg_frame, text="Browse", command=self.browse_bg).pack(side=tk.LEFT)

        # Logo Chọn
        logo_frame = tk.Frame(root)
        logo_frame.pack(pady=5)
        tk.Label(logo_frame, text="Watermark Logo:  ").pack(side=tk.LEFT)
        tk.Entry(logo_frame, textvariable=self.logo_path, width=30).pack(side=tk.LEFT, padx=5)
        tk.Button(logo_frame, text="Browse", command=self.browse_logo).pack(side=tk.LEFT)

        # Folder lưu
        tk.Button(root, text="Select Output Folder", command=self.browse_folder).pack(pady=10)

        # 4. Nút bắt đầu
        self.btn = tk.Button(root, text="START GENERATION", bg="#2196F3", fg="white", 
                             font=("Arial", 12, "bold"), command=self.start_process, padx=30, pady=10)
        self.btn.pack(pady=20)
        self.status_label = tk.Label(root, text="Ready", fg="blue")
        self.status_label.pack()

    def browse_bg(self):
        file = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if file: self.bg_path.set(file)

    def browse_logo(self):
        file = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg")])
        if file: self.logo_path.set(file)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder: self.output_dir.set(folder)

    def parse_line(self, line):
        parts = line.split("|")
        if len(parts) >= 3:
            tag = parts[0].strip().upper()
            pos = "LEFT" if tag in ["M", "M1", "F1"] else "RIGHT"
            voice = self.voice_vars.get(tag, self.voice_vars["M"]).get()
            return {
                "position": pos, "voice": voice,
                "es_text": re.sub(r'\s*\(\d+\)', '', parts[1].strip()),
                "en_text": re.sub(r'\s*\(\d+\)', '', parts[2].strip())
            }
        return None

    def create_frame(self, es_text, en_text, position, width=1280, height=720):
        # Kiểm tra nếu có background tùy chỉnh
        if self.bg_path.get() and os.path.exists(self.bg_path.get()):
            img = Image.open(self.bg_path.get()).convert('RGB')
            img = img.resize((width, height), Image.Resampling.LANCZOS)
        else:
            img = Image.new('RGB', (width, height), color=(255, 245, 240))
        
        draw = ImageDraw.Draw(img)
        cx = (width // 4) if position == "LEFT" else (3 * width // 4)
        cy = height // 2
        box_w, box_h = 320, 120
        main_box = [cx - box_w//2, cy - box_h//2, cx + box_w//2, cy + box_h//2]

        # Vẽ Box (có độ trong suốt nhẹ nếu dùng nền ảnh)
        draw.rounded_rectangle(main_box, radius=15, fill=(255, 240, 235), outline=(0, 128, 0), width=3)

        try:
            es_font = ImageFont.truetype("arial.ttf", 24)
            en_font = ImageFont.truetype("arial.ttf", 16)
        except:
            es_font = en_font = ImageFont.load_default()

        # Chia dòng và vẽ chữ
        def wrap(t, f, w):
            words = t.split(' ')
            l, cur = [], []
            for wd in words:
                if f.getbbox(' '.join(cur + [wd]))[2] <= w: cur.append(wd)
                else: l.append(' '.join(cur)); cur = [wd]
            l.append(' '.join(cur))
            return '\n'.join(l)

        w_es = wrap(es_text, es_font, box_w - 40)
        w_en = wrap(en_text, en_font, box_w - 40)
        draw.text((cx, cy - 15), w_es, fill=(0, 100, 0), font=es_font, anchor="mm", align="center")
        draw.text((cx, cy + 20), w_en, fill="black", font=en_font, anchor="mm", align="center")

        # Vẽ Logo
        if self.logo_path.get() and os.path.exists(self.logo_path.get()):
            logo = Image.open(self.logo_path.get()).convert("RGBA")
            logo.thumbnail((70, 70))
            img.paste(logo, (width - 100, 30), logo)

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
            silence = AudioClip(lambda t: [0, 0], duration=1.5, fps=44100)
            final_a = concatenate_audioclips([a_clip, silence])

            frame_bgr = self.create_frame(data['es_text'], data['en_text'], data['position'])
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            
            v_seg = ImageClip(frame_rgb).set_duration(final_a.duration).set_audio(final_a)
            all_segments.append(v_seg)

        if all_segments:
            final_path = os.path.join(self.output_dir.get(), "lesson_with_bg.mp4")
            concatenate_videoclips(all_segments, method="compose").write_videofile(final_path, codec="libx264", fps=10)
            for i in range(len(lines)):
                if os.path.exists(f"temp_{i}.mp3"): os.remove(f"temp_{i}.mp3")
            messagebox.showinfo("Xong!", f"Video lưu tại: {final_path}")

    def start_process(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.status_label.config(text="Đang tạo video...", fg="red")
            self.root.update()
            try: self.process_video(file)
            except Exception as e: messagebox.showerror("Lỗi", str(e))
            self.status_label.config(text="Ready", fg="blue")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGenerator(root)
    root.mainloop()