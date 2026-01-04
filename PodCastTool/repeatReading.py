import asyncio
import edge_tts
import os
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips, AudioClip

class VideoGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Language Lesson - Pattern Mode")
        self.root.geometry("400x200")
        
        self.label = tk.Label(root, text="Pattern: ES -> 2s Gap -> EN -> ES -> ES", wraplength=300)
        self.label.pack(pady=20)
        self.btn = tk.Button(root, text="Select File & Generate", command=self.start_process)
        self.btn.pack(pady=10)

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
        return AudioClip(lambda t: [0, 0], duration=max(0.1, duration), fps=5)

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

    async def generate_single_audio(self, text, voice, filename):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f.readlines() if line.strip()]

        all_video_segments = []
        fps = 5

        for i, line in enumerate(lines):
            data = self.parse_line(line)
            if not data: continue

            es_temp = f"es_temp_{i}.mp3"
            en_temp = f"en_temp_{i}.mp3"
            
            asyncio.run(self.generate_single_audio(data['es_text'], "es-ES-AlvaroNeural", es_temp))
            asyncio.run(self.generate_single_audio(data['en_text'], "en-US-GuyNeural", en_temp))

            es_audio = AudioFileClip(es_temp)
            en_audio = AudioFileClip(en_temp)

            # --- CUSTOM PATTERN LOGIC ---
            line_audio_list = []
            
            # 1. First Spanish Repetition (Slot 1)
            line_audio_list.append(es_audio)
            line_audio_list.append(self.make_silence(0.5)) 

            # 2. Forced 1.3s Silence Gap
            line_audio_list.append(self.make_silence(1.3))

            # 3. English Repetition(s) (e.g., Slot 1)
            for _ in range(data['en_count']):
                line_audio_list.append(en_audio)
                line_audio_list.append(self.make_silence(0.5))

            # 4. Remaining Spanish Repetitions (Slots 2 and 3)
            if data['es_count'] > 1:
                for _ in range(data['es_count'] - 1):
                    line_audio_list.append(es_audio)
                    line_audio_list.append(self.make_silence(0.5))
            
            final_audio_for_line = concatenate_audioclips(line_audio_list)
            total_duration = final_audio_for_line.duration

            # Video generation
            temp_avi = f"video_temp_{i}.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(temp_avi, fourcc, fps, (1280, 720))
            frame = self.create_frame(data['es_text'], data['en_text'])
            
            for _ in range(int(total_duration * fps)):
                out.write(frame)
            out.release()

            clip = VideoFileClip(temp_avi).set_audio(final_audio_for_line)
            all_video_segments.append(clip)

        if all_video_segments:
            final_result = concatenate_videoclips(all_video_segments)
            final_result.write_videofile("pattern_lesson.mp4", codec="libx264", audio_codec="aac", fps=fps)

            # Cleanup
            for i in range(len(lines)):
                for f in [f"es_temp_{i}.mp3", f"en_temp_{i}.mp3", f"video_temp_{i}.avi"]:
                    if os.path.exists(f): 
                        try: os.remove(f)
                        except: pass
            
            messagebox.showinfo("Success", "Video saved as pattern_lesson.mp4")

    def start_process(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.label.config(text="Generating Pattern Video...")
            self.root.update()
            try:
                self.process_video(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred: {e}")
            self.label.config(text="Select a .txt file")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGenerator(root)
    root.mainloop()