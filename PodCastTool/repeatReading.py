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
        self.root.title("Language Lesson - Pattern Mode")
        self.root.geometry("500x480")

        # Variables
        self.output_dir = tk.StringVar(value=os.getcwd())
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

        # 3. Output Folder
        tk.Label(root, text="Output Folder:").pack(pady=(10, 0))
        folder_frame = tk.Frame(root)
        folder_frame.pack(pady=5)
        tk.Entry(folder_frame, textvariable=self.output_dir, width=40).pack(side=tk.LEFT, padx=5)
        tk.Button(folder_frame, text="Browse", command=self.browse_folder).pack(side=tk.LEFT)

        # 4. Action Button (Fixed the padding error here)
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
        return AudioClip(lambda t: [0, 0], duration=max(0.1, duration), fps=44100)

    def create_frame(self, es_text, en_text, width=1280, height=720):
        img = Image.new('RGB', (width, height), color=(20, 20, 30))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 45)
        except:
            font = ImageFont.load_default()
        draw.text((width//2, height//3), es_text, fill="white", font=font, anchor="mm")
        draw.text((width//2, 2*height//3), en_text, fill="yellow", font=font, anchor="mm")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    async def generate_audio(self, text, voice_str, speed_str, filename):
        # Format speed: "80%" -> "-20%"
        speed_val = int(speed_str.replace("%", ""))
        rate = f"{speed_val - 100}%"
        # Extract voice ID
        voice = voice_str.split(" ")[0]
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(filename)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f.readlines() if line.strip()]

        all_video_segments = []
        fps = 5 # Low FPS for static text videos saves processing time
        out_folder = self.output_dir.get()
        final_path = os.path.join(out_folder, "pattern_lesson.mp4")

        for i, line in enumerate(lines):
            data = self.parse_line(line)
            if not data: continue

            es_temp = f"es_temp_{i}.mp3"
            en_temp = f"en_temp_{i}.mp3"
            
            asyncio.run(self.generate_audio(data['es_text'], self.selected_voice.get(), self.selected_speed.get(), es_temp))
            asyncio.run(self.generate_audio(data['en_text'], "en-US-GuyNeural", self.selected_speed.get(), en_temp))

            es_audio = AudioFileClip(es_temp)
            en_audio = AudioFileClip(en_temp)

            # Build Audio Sequence: ES -> 1.3s Gap -> EN -> ES -> ES
            line_audio_list = []
            
            # Spanish 1
            line_audio_list.append(es_audio)
            line_audio_list.append(self.make_silence(0.5)) 
            # Gap
            line_audio_list.append(self.make_silence(1.3))
            # English
            for _ in range(data['en_count']):
                line_audio_list.append(en_audio)
                line_audio_list.append(self.make_silence(0.5))
            # Spanish Remaining
            if data['es_count'] > 1:
                for _ in range(data['es_count'] - 1):
                    line_audio_list.append(es_audio)
                    line_audio_list.append(self.make_silence(0.5))
            
            final_audio = concatenate_audioclips(line_audio_list)
            
            temp_avi = f"video_temp_{i}.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(temp_avi, fourcc, fps, (1280, 720))
            frame = self.create_frame(data['es_text'], data['en_text'])
            
            for _ in range(int(final_audio.duration * fps) + 1):
                out.write(frame)
            out.release()

            segment = VideoFileClip(temp_avi).set_audio(final_audio)
            all_video_segments.append(segment)

        if all_video_segments:
            final_result = concatenate_videoclips(all_video_segments)
            final_result.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=fps)
            
            # Cleanup
            for i in range(len(lines)):
                for f in [f"es_temp_{i}.mp3", f"en_temp_{i}.mp3", f"video_temp_{i}.avi"]:
                    if os.path.exists(f):
                        try: os.remove(f)
                        except: pass
            
            messagebox.showinfo("Success", f"Video saved to:\n{final_path}")

    def start_process(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.status_label.config(text="Generating... please wait.", fg="red")
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