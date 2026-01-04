import asyncio
import edge_tts
import os
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip

class VideoGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Language Repeater (No ImageMagick)")
        self.root.geometry("400x200")
        
        self.label = tk.Label(root, text="Select a .txt file to begin", wraplength=300)
        self.label.pack(pady=20)

        self.btn = tk.Button(root, text="Select File & Generate", command=self.start_process)
        self.btn.pack(pady=10)

    def parse_line(self, line):
        # Matches: Text (Num).|Text (Num).
        pattern = r"(.+?)\s*\((\d+)\)\.\|(.+?)\s*\((\d+)\)\."
        match = re.search(pattern, line)
        if match:
            return {
                "es_text": match.group(1).strip(),
                "es_count": int(match.group(2)), # X times
                "en_text": match.group(3).strip(),
                "en_count": int(match.group(4))  # Y times
            }
        return None

    def create_frame(self, es_text, en_text, width=1280, height=720):
        img = Image.new('RGB', (width, height), color=(20, 20, 20)) # Dark grey bg
        draw = ImageDraw.Draw(img)
        
        try:
            # Using a slightly larger font for clarity
            font = ImageFont.truetype("arial.ttf", 45)
        except:
            font = ImageFont.load_default()

        # Wrap text if it's too long
        def draw_wrapped_text(text, y_pos, color):
            lines = [text[i:i+50] for i in range(0, len(text), 50)] # Simple wrap
            current_y = y_pos
            for l in lines:
                draw.text((width//2, current_y), l, fill=color, font=font, anchor="mm")
                current_y += 60

        draw_wrapped_text(es_text, height//4, "white")
        draw_wrapped_text(en_text, 3*height//4, "yellow")
        
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    async def generate_audio(self, text, count, voice, filename):
        # Repeat the text 'count' times with a small pause
        repeated_text = " . ".join([text] * count)
        communicate = edge_tts.Communicate(repeated_text, voice)
        await communicate.save(filename)

    def process_video(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        video_segments = []
        fps = 24

        for i, line in enumerate(lines):
            data = self.parse_line(line)
            if not data: continue

            es_audio_file = f"es_{i}.mp3"
            en_audio_file = f"en_{i}.mp3"
            temp_avi = f"temp_{i}.avi"

            # 1. Generate Repeated Audio
            asyncio.run(self.generate_audio(data['es_text'], data['es_count'], "es-ES-AlvaroNeural", es_audio_file))
            asyncio.run(self.generate_audio(data['en_text'], data['en_count'], "en-US-GuyNeural", en_audio_file))

            # Load audio to get actual durations
            aud_es = AudioFileClip(es_audio_file)
            aud_en = AudioFileClip(en_audio_file)
            
            # 2. Create Video Frame Sequence
            total_dur = aud_es.duration + aud_en.duration + 0.5 # Total duration of both audio clips
            
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(temp_avi, fourcc, fps, (1280, 720))
            
            frame = self.create_frame(data['es_text'], data['en_text'])
            for _ in range(int(total_dur * fps)):
                out.write(frame)
            out.release()

            # 3. Combine Audio and Video
            clip = VideoFileClip(temp_avi)
            # Offset English audio to start after Spanish finishes
            aud_en_offset = aud_en.set_start(aud_es.duration)
            
            final_audio = CompositeAudioClip([aud_es, aud_en_offset])
            clip = clip.set_audio(final_audio)
            video_segments.append(clip)

        # Final Export
        if video_segments:
            final_video = concatenate_videoclips(video_segments)
            final_video.write_videofile("lesson_output.mp4", codec="libx264", audio_codec="aac")
            
            # Cleanup
            for i in range(len(lines)):
                for ext in [f"es_{i}.mp3", f"en_{i}.mp3", f"temp_{i}.avi"]:
                    if os.path.exists(ext): os.remove(ext)
            
            messagebox.showinfo("Success", "Video generated successfully!")
        else:
            messagebox.showwarning("Warning", "No valid lines found in file.")

    def start_process(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.label.config(text="Generating... please wait.")
            self.root.update()
            try:
                self.process_video(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")
            self.label.config(text="Select a .txt file to begin")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGenerator(root)
    root.mainloop()