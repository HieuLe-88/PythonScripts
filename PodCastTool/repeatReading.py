import asyncio
import edge_tts
import os
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips, AudioClip

class VideoGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Language Lesson - Pattern Mode with Logo")
        self.root.geometry("500x550")

        # Variables
        self.output_dir = tk.StringVar(value=os.getcwd())
        self.logo_path = tk.StringVar(value="")
        self.selected_voice = tk.StringVar(value="es-ES-AlvaroNeural (Male)")
        self.selected_speed = tk.StringVar(value="100%")

        # UI
        tk.Label(root, text="Pattern: ES -> 1.3s Gap -> EN -> ES -> ES", font=("Arial", 10, "italic")).pack(pady=10)

        # 1. Voice Selection
        tk.Label(root, text="Select Spanish Voice:").pack()
        voices = [
            "es-ES-AlvaroNeural (Male)", "es-ES-ElviraNeural (Female)",
            "es-MX-JorgeNeural (Male)", "es-MX-DaliaNeural (Female)",
            "es-US-AlonsoNeural (Male)", "es-US-PalomaNeural (Female)",
            "es-AR-TomasNeural (Male)", "es-CL-LorenzoNeural (Male)"
        ]
        self.voice_combo = ttk.Combobox(root, textvariable=self.selected_voice, values=voices, width=45, state="readonly")
        self.voice_combo.pack(pady=5)

        # 2. Speed Selection
        tk.Label(root, text="Speech Speed:").pack()
        speeds = ["60%", "70%", "80%", "90%", "100%"]
        self.speed_combo = ttk.Combobox(root, textvariable=self.selected_speed, values=speeds, width=15, state="readonly")
        self.speed_combo.pack(pady=5)

        # 3. Logo Selection
        tk.Label(root, text="Watermark Logo (Optional):").pack(pady=(10, 0))
        logo_frame = tk.Frame(root)
        logo_frame.pack(pady=5)
        tk.Entry(logo_frame, textvariable=self.logo_path, width=40).pack(side=tk.LEFT, padx=5)
        tk.Button(logo_frame, text="Select Logo", command=self.browse_logo).pack(side=tk.LEFT)

        # 4. Output Folder
        tk.Label(root, text="Output Folder:").pack(pady=(10, 0))
        folder_frame = tk.Frame(root)
        folder_frame.pack(pady=5)
        tk.Entry(folder_frame, textvariable=self.output_dir, width=40).pack(side=tk.LEFT, padx=5)
        tk.Button(folder_frame, text="Browse", command=self.browse_folder).pack(side=tk.LEFT)

        # 5. Action Button
        self.btn = tk.Button(root, text="Select TXT & Start Generation", 
                             bg="#4CAF50", fg="white", font=("Arial", 11, "bold"),
                             command=self.start_process, padx=10, pady=10)
        self.btn.pack(pady=30)

        self.status_label = tk.Label(root, text="Ready", fg="blue")
        self.status_label.pack()

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir.set(folder)

    def browse_logo(self):
        file = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
        if file:
            self.logo_path.set(file)

    def parse_line(self, line):
        pattern = r"(.+?)\s*\((\d+)\)\.\|(.+?)\s*\((\d+)\)\."
        match = re.search(pattern, line)
        if match:
            return {
                "es_text": match.group(1).strip(),
                "es_count": int(match.group(2)),
                "en_text": match.group(3).strip(),
                "en_count": int(match.group(4))
            }
        return None

    def make_silence(self, duration):
        return AudioClip(lambda t: [0, 0], duration=max(0.1, duration), fps=25)

    async def generate_audio(self, text, voice_str, speed_str, filename):
        speed_val = int(speed_str.replace("%", ""))
        rate_val = speed_val - 100
        rate_str = f"{rate_val:+d}%" 
        voice = voice_str.split(" ")[0]
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        await communicate.save(filename)

    def wrap_text(self, text, font, max_width):
        """Helper to split text into lines that fit the box width."""
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            # getbbox returns (left, top, right, bottom)
            w = font.getbbox(test_line)[2]
            if w <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        return '\n'.join(lines)

    def create_frame(self, es_text, en_text, width=1280, height=720):
        # 1. Main Background: Seashell White (RGB: 255, 245, 240)
        img = Image.new('RGB', (width, height), color=(255, 245, 240))
        draw = ImageDraw.Draw(img)

        # 2. Dimensions and Positioning
        margin_x = 80
        container_padding = 40
        box_width = width - (margin_x * 2)
        inner_box_width = box_width - (container_padding * 2)
        inner_box_height = 220 
        
        # 3. Outer Container Box (Large white box covering everything)
        # Positioned to fit both inner boxes plus padding
        container_box = [margin_x - 20, 60, width - margin_x + 20, 660]
        draw.rounded_rectangle(container_box, radius=35, fill="white", outline=(200, 200, 200), width=2)

        # 4. Spanish Box (Rose White: 255, 240, 235)
        es_box = [margin_x + 20, 100, width - margin_x - 20, 100 + inner_box_height]
        draw.rounded_rectangle(es_box, radius=25, fill=(255, 240, 235), outline=(0, 128, 0), width=4)

        # 5. English Box (Periwinkle Blue: 178, 191, 255)
        en_box = [margin_x + 20, 380, width - margin_x - 20, 380 + inner_box_height]
        draw.rounded_rectangle(en_box, radius=25, fill=(178, 191, 255), outline=(50, 50, 50), width=2)

        # 6. Fonts and Text Wrapping
        en_size = 48
        es_size = int(en_size * 1.5)
        try:
            es_font = ImageFont.truetype("arial.ttf", es_size)
            en_font = ImageFont.truetype("arial.ttf", en_size)
        except:
            es_font = ImageFont.load_default()
            en_font = ImageFont.load_default()

        wrapped_es = self.wrap_text(es_text, es_font, (width - margin_x * 2) - 100)
        wrapped_en = self.wrap_text(en_text, en_font, (width - margin_x * 2) - 100)

        # 7. Center Text
        es_pos = (es_box[0] + (es_box[2] - es_box[0]) // 2, es_box[1] + inner_box_height // 2)
        en_pos = (en_box[0] + (en_box[2] - en_box[0]) // 2, en_box[1] + inner_box_height // 2)

        draw.text(es_pos, wrapped_es, fill=(0, 100, 0), font=es_font, anchor="mm", align="center")
        draw.text(en_pos, wrapped_en, fill="black", font=en_font, anchor="mm", align="center")

        # 8. Logo Logic
        if self.logo_path.get() and os.path.exists(self.logo_path.get()):
            try:
                logo = Image.open(self.logo_path.get()).convert("RGBA")
                logo_w = int(width * 0.08)
                w_percent = (logo_w / float(logo.size[0]))
                logo_h = int((float(logo.size[1]) * float(w_percent)))
                logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
                img.paste(logo, (width - logo_w - 45, 15), logo)
            except: pass

        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f.readlines() if line.strip()]

        all_video_segments = []
        fps = 5 
        out_folder = self.output_dir.get()
        final_path = os.path.join(out_folder, "pattern_lesson_wrapped.mp4")

        for i, line in enumerate(lines):
            data = self.parse_line(line)
            if not data: continue

            # --- AUDIO CLEANING STEP ---
            # We remove punctuation ONLY for the audio generation so it's not read aloud
            # This regex replaces ?, /, ., (, ), and other symbols with an empty space
            clean_es_audio = re.sub(r'[?/.()¿¡!]', '', data['es_text'])
            clean_en_audio = re.sub(r'[?/.()¿¡!]', '', data['en_text'])

            es_temp = f"es_temp_{i}.mp3"
            en_temp = f"en_temp_{i}.mp3"
            
            # Use the 'clean' versions for audio generation
            asyncio.run(self.generate_audio(clean_es_audio, self.selected_voice.get(), self.selected_speed.get(), es_temp))
            asyncio.run(self.generate_audio(clean_en_audio, "en-US-GuyNeural", self.selected_speed.get(), en_temp))

            es_audio = AudioFileClip(es_temp)
            en_audio = AudioFileClip(en_temp)

            line_audio_list = [es_audio, self.make_silence(0.5), self.make_silence(1.3)]
            
            for _ in range(data['en_count']):
                line_audio_list.extend([en_audio, self.make_silence(0.5)])
                
            if data['es_count'] > 1:
                for _ in range(data['es_count'] - 1):
                    line_audio_list.extend([es_audio, self.make_silence(0.5)])
            
            final_audio = concatenate_audioclips(line_audio_list)
            temp_avi = f"video_temp_{i}.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(temp_avi, fourcc, fps, (1280, 720))
            
            # --- VISUAL STEP ---
            # We use the ORIGINAL 'data' text for the frame so the punctuation STILL SHOWS
            frame = self.create_frame(data['es_text'], data['en_text'])
            
            for _ in range(int(final_audio.duration * fps) + 1):
                out.write(frame)
            out.release()

            segment = VideoFileClip(temp_avi).set_audio(final_audio)
            all_video_segments.append(segment)

        if all_video_segments:
            final_result = concatenate_videoclips(all_video_segments)
            final_result.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=fps)
            
            for i in range(len(lines)):
                for f in [f"es_temp_{i}.mp3", f"en_temp_{i}.mp3", f"video_temp_{i}.avi"]:
                    if os.path.exists(f):
                        try: os.remove(f)
                        except: pass
            
            messagebox.showinfo("Success", f"Video saved to:\n{final_path}")

    def start_process(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.status_label.config(text="Generating branded video...", fg="red")
            self.root.update()
            try:
                self.process_video(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")
            self.status_label.config(text="Ready", fg="blue")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGenerator(root)
    root.mainloop()