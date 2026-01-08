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
        self.root.title("Spanish Lesson - Single Read Mode")
        self.root.geometry("500x550")

        self.output_dir = tk.StringVar(value=os.getcwd())
        self.logo_path = tk.StringVar(value="")
        self.selected_voice = tk.StringVar(value="es-ES-AlvaroNeural (Male)")
        self.selected_speed = tk.StringVar(value="100%")

        tk.Label(root, text="Chế độ: Đọc Spanish 1 lần duy nhất", font=("Arial", 10, "bold")).pack(pady=10)

        # 1. Voice Selection
        tk.Label(root, text="Select Spanish Voice:").pack()
        voices = ["es-ES-AlvaroNeural (Male)", "es-ES-ElviraNeural (Female)", "es-MX-JorgeNeural (Male)", "es-MX-DaliaNeural (Female)"]
        self.voice_combo = ttk.Combobox(root, textvariable=self.selected_voice, values=voices, width=45, state="readonly")
        self.voice_combo.pack(pady=5)

        # 2. Speed Selection
        tk.Label(root, text="Speech Speed:").pack()
        self.speed_combo = ttk.Combobox(root, textvariable=self.selected_speed, values=["80%", "90%", "100%"], width=15, state="readonly")
        self.speed_combo.pack(pady=5)

        # 3. Logo & Folder
        tk.Button(root, text="Select Logo", command=self.browse_logo).pack(pady=5)
        tk.Button(root, text="Select Output Folder", command=self.browse_folder).pack(pady=5)

        # 4. Action Button
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
        pattern = r"(.+?)\s*\((\d+)\)\.\|(.+?)\s*\((\d+)\)\."
        match = re.search(pattern, line)
        if match:
            return {"es_text": match.group(1).strip(), "en_text": match.group(3).strip()}
        return None

    async def generate_audio(self, text, voice_str, speed_str, filename):
        rate = f"{int(speed_str.replace('%', '')) - 100:+d}%"
        voice = voice_str.split(" ")[0]
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
        img = Image.new('RGB', (width, height), color=(255, 245, 240))
        draw = ImageDraw.Draw(img)
        margin_x = 80
        
        # Draw Box
        main_box = [margin_x + 20, 180, width - margin_x - 20, 180 + 350]
        draw.rounded_rectangle([margin_x-20, 60, width-margin_x+20, 660], radius=35, fill="white", outline=(200, 200, 200), width=2)
        draw.rounded_rectangle(main_box, radius=25, fill=(255, 240, 235), outline=(0, 128, 0), width=4)

        # Fonts
        try:
            es_font = ImageFont.truetype("arial.ttf", 72)
            en_font = ImageFont.truetype("arial.ttf", 40)
        except:
            es_font = en_font = ImageFont.load_default()

        wrapped_es = self.wrap_text(es_text, es_font, (width - margin_x * 2) - 100)
        wrapped_en = self.wrap_text(en_text, en_font, (width - margin_x * 2) - 100)

        cx, cy = (main_box[0] + main_box[2]) // 2, (main_box[1] + main_box[3]) // 2
        draw.text((cx, cy - 40), wrapped_es, fill=(0, 100, 0), font=es_font, anchor="mm", align="center")
        draw.text((cx, cy + 60), wrapped_en, fill="black", font=en_font, anchor="mm", align="center")

        # Logo
        if self.logo_path.get() and os.path.exists(self.logo_path.get()):
            logo = Image.open(self.logo_path.get()).convert("RGBA")
            logo.thumbnail((100, 100))
            img.paste(logo, (width - 150, 20), logo)

        return np.array(img)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f.readlines() if line.strip()]

        all_segments = []
        out_folder = self.output_dir.get()
        final_output = os.path.join(out_folder, "final_lesson.mp4")

        for i, line in enumerate(lines):
            data = self.parse_line(line)
            if not data: continue

            # 1. Audio: Chỉ đọc 1 lần Spanish
            clean_audio_text = re.sub(r'[?/.()¿¡!]', '', data['es_text'])
            temp_audio = f"temp_{i}.mp3"
            asyncio.run(self.generate_audio(clean_audio_text, self.selected_voice.get(), self.selected_speed.get(), temp_audio))
            
            audio_clip = AudioFileClip(temp_audio)
            # Thêm 1 giây im lặng sau khi đọc để học viên kịp nhìn chữ
            silence = AudioClip(lambda t: [0, 0], duration=1.0, fps=44100)
            final_audio = concatenate_audioclips([audio_clip, silence])

            # 2. Visual: Tạo clip trực tiếp từ Image
            frame_rgb = self.create_frame(data['es_text'], data['en_text'])
            video_segment = ImageClip(frame_rgb).set_duration(final_audio.duration)
            video_segment = video_segment.set_audio(final_audio)
            
            all_segments.append(video_segment)

        if all_segments:
            final_video = concatenate_videoclips(all_segments, method="compose")
            final_video.write_videofile(final_output, codec="libx264", audio_codec="aac", fps=10)
            
            # Dọn dẹp
            for i in range(len(lines)):
                if os.path.exists(f"temp_{i}.mp3"): os.remove(f"temp_{i}.mp3")
            
            messagebox.showinfo("Xong!", f"Video đã lưu tại:\n{final_output}")

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