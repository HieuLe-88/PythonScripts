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
        self.root.title("Spanish Lesson - Auto Gender Voice")
        self.root.geometry("500x550")

        self.output_dir = tk.StringVar(value=os.getcwd())
        self.logo_path = tk.StringVar(value="")
        self.selected_speed = tk.StringVar(value="100%")

        # Định nghĩa giọng mặc định cho M và F
        self.male_voice = "es-ES-AlvaroNeural"
        self.female_voice = "es-ES-ElviraNeural"

        tk.Label(root, text="Input Format: M|Spanish|English hoặc F|Spanish|English", font=("Arial", 10, "italic")).pack(pady=10)

        # 1. Speed Selection
        tk.Label(root, text="Speech Speed:").pack()
        self.speed_combo = ttk.Combobox(root, textvariable=self.selected_speed, values=["80%", "90%", "100%"], width=15, state="readonly")
        self.speed_combo.pack(pady=5)

        # 2. Logo & Folder
        tk.Button(root, text="Select Logo", command=self.browse_logo).pack(pady=5)
        tk.Button(root, text="Select Output Folder", command=self.browse_folder).pack(pady=5)

        # 3. Action Button
        self.btn = tk.Button(root, text="START GENERATION", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), command=self.start_process, padx=10, pady=10)
        self.btn.pack(pady=30)
        self.status_label = tk.Label(root, text="Ready", fg="blue")
        self.status_label.pack()

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder: self.output_dir.set(folder)

    def browse_logo(self):
        file = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg")])
        if file: self.logo_path.set(file)

    def parse_line(self, line):
        # Tách dòng dựa trên dấu gạch đứng "|"
        # Ví dụ: M|Entro.|Enter. -> ['M', 'Entro.', 'Enter.']
        parts = line.split("|")
        if len(parts) >= 3:
            gender = parts[0].strip().upper()
            es_part = parts[1].strip()
            en_part = parts[2].strip()

            # Làm sạch text (xóa số trong ngoặc nếu có)
            clean_es = re.sub(r'\s*\(\d+\)', '', es_part)
            clean_en = re.sub(r'\s*\(\d+\)', '', en_part)
            
            # Chọn giọng dựa trên giới tính
            voice = self.male_voice if gender == 'M' else self.female_voice
            
            return {
                "voice": voice,
                "es_text": clean_es,
                "en_text": clean_en
            }
        return None
    
    async def generate_audio(self, text, voice, speed_str, filename):
        rate = f"{int(speed_str.replace('%', '')) - 100:+d}%"
        await edge_tts.Communicate(text, voice, rate=rate).save(filename)

    def wrap_text(self, text, font, max_width):
        words = text.split(' ')
        lines, current_line = [], []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.getbbox(test_line)[2] <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        return '\n'.join(lines)

    def create_frame(self, es_text, en_text, width=1280, height=720):
        # 1. Main Background: Seashell White
        img = Image.new('RGB', (width, height), color=(255, 245, 240))
        draw = ImageDraw.Draw(img)
        margin_x = 80
        
        # 2. Container lớn (giữ nguyên để làm khung nền)
        draw.rounded_rectangle([margin_x-20, 60, width-margin_x+20, 660], radius=35, fill="white", outline=(200, 200, 200), width=2)

        # 3. THAY ĐỔI: Box nhỏ thu lại còn 1/4 (Chiều rộng và cao đều giảm)
        # Kích thước box cũ khoảng 1080x350 -> Box mới khoảng 270x88
        box_w = 270
        box_h = 90
        cx, cy = width // 2, height // 2 # Tâm màn hình
        
        main_box = [cx - box_w//2, cy - box_h//2, cx + box_w//2, cy + box_h//2]
        draw.rounded_rectangle(main_box, radius=10, fill=(255, 240, 235), outline=(0, 128, 0), width=2)

        # 4. THAY ĐỔI: Fonts giảm còn 1/4
        # es_font: 60 -> 15 | en_font: 35 -> 9
        try:
            es_font = ImageFont.truetype("arial.ttf", 15) 
            en_font = ImageFont.truetype("arial.ttf", 9)
        except:
            es_font = en_font = ImageFont.load_default()

        # Giới hạn chiều rộng text theo box mới
        max_text_width = box_w - 20
        wrapped_es = self.wrap_text(es_text, es_font, max_text_width)
        wrapped_en = self.wrap_text(en_text, en_font, max_text_width)

        # 5. Vẽ chữ vào tâm của box nhỏ
        # Khoảng cách dòng cũng thu nhỏ lại
        draw.text((cx, cy - 10), wrapped_es, fill=(0, 100, 0), font=es_font, anchor="mm", align="center")
        draw.text((cx, cy + 12), wrapped_en, fill="black", font=en_font, anchor="mm", align="center")

        # 6. Logo (giữ nguyên hoặc thu nhỏ thêm tùy bạn)
        if self.logo_path.get() and os.path.exists(self.logo_path.get()):
            try:
                logo = Image.open(self.logo_path.get()).convert("RGBA")
                logo.thumbnail((50, 50)) # Thu nhỏ logo cho hợp với style mới
                img.paste(logo, (width - 150, 20), logo)
            except: pass

        return np.array(img)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f.readlines() if line.strip()]

        all_segments = []
        out_folder = self.output_dir.get()
        final_output = os.path.join(out_folder, "gender_lesson.mp4")

        for i, line in enumerate(lines):
            data = self.parse_line(line)
            if not data: continue

            # 1. Âm thanh: Sử dụng giọng đã parse (M hoặc F)
            clean_audio_text = re.sub(r'[?/.()¿¡!]', '', data['es_text'])
            temp_audio = f"temp_{i}.mp3"
            
            asyncio.run(self.generate_audio(clean_audio_text, data['voice'], self.selected_speed.get(), temp_audio))
            
            audio_clip = AudioFileClip(temp_audio)
            silence = AudioClip(lambda t: [0, 0], duration=1.5, fps=44100)
            final_audio = concatenate_audioclips([audio_clip, silence])

            # 2. Hình ảnh
            frame_rgb = self.create_frame(data['es_text'], data['en_text'])
            
            video_segment = ImageClip(frame_rgb).set_duration(final_audio.duration)
            video_segment = video_segment.set_audio(final_audio)
            
            all_segments.append(video_segment)

        if all_segments:
            final_video = concatenate_videoclips(all_segments, method="compose")
            final_video.write_videofile(final_output, codec="libx264", audio_codec="aac", fps=10, preset="ultrafast")
            
            for i in range(len(lines)):
                f_path = f"temp_{i}.mp3"
                if os.path.exists(f_path):
                    try: os.remove(f_path)
                    except: pass
            
            messagebox.showinfo("Success", f"Video created:\n{final_output}")

    def start_process(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.status_label.config(text="Processing...", fg="red")
            self.root.update()
            try:
                self.process_video(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"Lỗi: {e}")
            self.status_label.config(text="Ready", fg="blue")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGenerator(root)
    root.mainloop()