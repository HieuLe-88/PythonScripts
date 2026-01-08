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
        parts = line.split("|")
        if len(parts) >= 3:
            raw_tag = parts[0].strip().upper() # Ví dụ: "M1", "M2", "F"
            
            # Tách lấy chữ cái đầu (M hoặc F) để chọn giọng
            gender_letter = re.findall(r'[MF]', raw_tag)
            gender_letter = gender_letter[0] if gender_letter else 'M'
            
            # Xác định vị trí dựa trên tag
            # Trái nếu là: M, M1, F1
            # Phải nếu là: M2, F2, F (hoặc bất kỳ cái gì khác)
            if raw_tag in ["M", "M1", "F1"]:
                position = "LEFT"
            else:
                position = "RIGHT"

            voice = self.male_voice if gender_letter == 'M' else self.female_voice
            
            return {
                "position": position,
                "voice": voice,
                "es_text": re.sub(r'\s*\(\d+\)', '', parts[1].strip()),
                "en_text": re.sub(r'\s*\(\d+\)', '', parts[2].strip())
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

    def create_frame(self, es_text, en_text, position, width=1280, height=720):
        img = Image.new('RGB', (width, height), color=(255, 245, 240))
        draw = ImageDraw.Draw(img)
        
        center_screen = width // 2
        # Di chuyển dựa trên position đã xác định ở parse_line
        if position == "LEFT":
            cx = center_screen - (width // 4)
        else:
            cx = center_screen + (width // 4)
        
        cy = height // 2
        box_w, box_h = 320, 120
        main_box = [cx - box_w//2, cy - box_h//2, cx + box_w//2, cy + box_h//2]
        
        draw.rounded_rectangle(main_box, radius=15, fill=(255, 240, 235), outline=(0, 128, 0), width=3)

        try:
            es_font = ImageFont.truetype("arial.ttf", 24) 
            en_font = ImageFont.truetype("arial.ttf", 16)
        except:
            es_font = en_font = ImageFont.load_default()

        wrapped_es = self.wrap_text(es_text, es_font, box_w - 40)
        wrapped_en = self.wrap_text(en_text, en_font, box_w - 40)
        
        draw.text((cx, cy - 15), wrapped_es, fill=(0, 100, 0), font=es_font, anchor="mm", align="center")
        draw.text((cx, cy + 20), wrapped_en, fill="black", font=en_font, anchor="mm", align="center")

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

            # Tạo audio (giữ nguyên)
            clean_audio_text = re.sub(r'[?/.()¿¡!]', '', data['es_text'])
            temp_audio = f"temp_{i}.mp3"
            asyncio.run(self.generate_audio(clean_audio_text, data['voice'], self.selected_speed.get(), temp_audio))
            
            audio_clip = AudioFileClip(temp_audio)
            silence = AudioClip(lambda t: [0, 0], duration=1.5, fps=44100)
            final_audio = concatenate_audioclips([audio_clip, silence])

            # Truyền data['position'] vào đây
            frame_bgr = self.create_frame(data['es_text'], data['en_text'], data['position'])
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            
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