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
        self.lang_var = tk.StringVar(value="Spanish")
        # For Chinese mode: repeat counts (user-controlled)
        self.main_repeat = tk.IntVar(value=2)
        self.trans_repeat = tk.IntVar(value=1)
        # Chinese voice selection (basic)
        self.chinese_voice = tk.StringVar(value="zh-CN-XiaoxiaoNeural")

        # UI
        tk.Label(root, text="Pattern: ES -> 1.3s Gap -> EN -> ES -> ES", font=("Arial", 10, "italic")).pack(pady=10)

        # Language selector (Spanish or Chinese)
        lang_frame = tk.Frame(root)
        lang_frame.pack(pady=4)
        tk.Label(lang_frame, text="Language:").pack(side=tk.LEFT)
        ttk.Combobox(lang_frame, textvariable=self.lang_var, values=["Spanish", "Chinese"], width=12, state="readonly").pack(side=tk.LEFT, padx=6)

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

        # Chinese-specific repeat controls and voice (visible for Chinese use)
        chi_frame = tk.Frame(root)
        chi_frame.pack(pady=4)
        tk.Label(chi_frame, text="Chinese main repeats:").pack(side=tk.LEFT)
        tk.Spinbox(chi_frame, from_=1, to=10, textvariable=self.main_repeat, width=4).pack(side=tk.LEFT, padx=4)
        tk.Label(chi_frame, text="Trans repeats:").pack(side=tk.LEFT, padx=(8,0))
        tk.Spinbox(chi_frame, from_=0, to=10, textvariable=self.trans_repeat, width=4).pack(side=tk.LEFT, padx=4)
        tk.Label(chi_frame, text="CN Voice:").pack(side=tk.LEFT, padx=(8,0))
        # Expanded list of Chinese voices (add more as needed)
        chi_voices = [
            "zh-CN-XiaoxiaoNeural",
            "zh-CN-XiaoyiNeural",

            "zh-HK-HiuGaaiNeural",
            "zh-TW-HsiaoChenNeural",

            "zh-CN-YunxiNeural",
            "zh-CN-YunyangNeural",
            "zh-CN-YunjianNeural",
            "zh-TW-YunJheNeural",
        ]
        ttk.Combobox(chi_frame, textvariable=self.chinese_voice, values=chi_voices, width=22, state="readonly").pack(side=tk.LEFT, padx=4)

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
        # Keep existing Spanish format parser
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

    def parse_line_chinese(self, line):
        # Expect: Hanzi.|Pinyin.|English.  separated by '|'
        parts = [p.strip() for p in line.split('|') if p.strip()]
        if len(parts) >= 3:
            # remove trailing dots if present
            hanzi = parts[0].rstrip('.')
            pinyin = parts[1].rstrip('.')
            english = parts[2].rstrip('.')
            return {"hanzi": hanzi, "pinyin": pinyin, "english": english}
        return None

    def make_silence(self, duration):
        return AudioClip(lambda t: [0, 0], duration=max(0.1, duration), fps=15)

    async def generate_audio(self, text, voice_str, speed_str, filename):
        speed_val = int(speed_str.replace("%", ""))
        rate_val = speed_val - 100
        rate_str = f"{rate_val:+d}%" 
        # voice_str may be a display like 'es-ES-AlvaroNeural (Male)' or a raw voice id
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

    def create_frame(self, main_text, trans_text, pinyin_text=None, width=1280, height=720):
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

        # Boxes: colors differ by language; when Chinese mode, the top box will show Hanzi + Pinyin
        es_box = [margin_x + 20, 100, width - margin_x - 20, 100 + inner_box_height]
        en_box = [margin_x + 20, 380, width - margin_x - 20, 380 + inner_box_height]

        # If pinyin_text is provided, draw Chinese-style cards like the sample image
        if pinyin_text is not None:
            # Outer rounded frame (teal border)
            outer_pad = 8
            outer_x1 = es_box[0] - outer_pad
            outer_y1 = es_box[1] - outer_pad
            outer_x2 = en_box[2] + outer_pad
            outer_y2 = en_box[3] + outer_pad
            outer_radius = 26
            frame_color = (6, 95, 85)  # dark teal
            draw.rounded_rectangle([outer_x1, outer_y1, outer_x2, outer_y2], radius=outer_radius, fill=(252,250,248), outline=frame_color, width=6)

            # Inner top panel (pale teal)
            top_x1 = outer_x1 + 12
            top_y1 = outer_y1 + 12
            top_x2 = outer_x2 - 12
            top_y2 = top_y1 + int((outer_y2 - outer_y1) * 0.48)
            draw.rounded_rectangle([top_x1, top_y1, top_x2, top_y2], radius=18, fill=(201,234,231), outline=(190,220,215), width=1)

            # Inner bottom panel (white) with dashed border
            bot_x1 = top_x1
            bot_y1 = top_y2 + 12
            bot_x2 = top_x2
            bot_y2 = outer_y2 - 12
            draw.rounded_rectangle([bot_x1, bot_y1, bot_x2, bot_y2], radius=16, fill=(255,255,255), outline=(220,220,220), width=1)
            # dashed border effect
            dash_w = 10
            gap_w = 8
            x = bot_x1 + 12
            while x < bot_x2 - 12:
                x2 = min(x + dash_w, bot_x2 - 12)
                draw.line([(x, bot_y1+8), (x2, bot_y1+8)], fill=(180,180,180), width=2)
                draw.line([(x, bot_y2-8), (x2, bot_y2-8)], fill=(180,180,180), width=2)
                x += dash_w + gap_w

            # Fonts: try to use italic for pinyin and english, hanzi in bold-like
            top_height = top_y2 - top_y1
            bot_height = bot_y2 - bot_y1
            hanzi_size = 55# max(12, int(top_height * 0.5))
            pinyin_size = 22#  max(10, int(top_height * 0.18))
            eng_size = 35# max(12, int(bot_height * 0.35))
            try:
                hanzi_font = ImageFont.truetype("msyh.ttc", hanzi_size)
                pinyin_font = ImageFont.truetype("ariali.ttf", pinyin_size)
                eng_font = ImageFont.truetype("ariali.ttf", eng_size)
            except:
                hanzi_font = ImageFont.truetype("msyh.ttc", hanzi_size) if os.path.exists("C:\\Windows\\Fonts\\msyh.ttc") else ImageFont.load_default()
                try:
                    pinyin_font = ImageFont.truetype("ariali.ttf", pinyin_size)
                    eng_font = ImageFont.truetype("ariali.ttf", eng_size)
                except:
                    pinyin_font = ImageFont.load_default()
                    eng_font = ImageFont.load_default()

            # Wrap texts to fit within inner top/bottom areas
            text_max_w = (top_x2 - top_x1) - 48
            wrapped_pinyin = self.wrap_text(pinyin_text, pinyin_font, text_max_w)
            wrapped_hanzi = self.wrap_text(main_text, hanzi_font, text_max_w)
            wrapped_eng = self.wrap_text(trans_text, eng_font, (bot_x2 - bot_x1) - 40)

            # Positions: pinyin above hanzi, centered in top panel
            cx = (top_x1 + top_x2) // 2
            pinyin_y = top_y1 + int(top_height * 0.12)
            hanzi_y = pinyin_y + int(pinyin_size * 1.6) + 6
            draw.text((cx, pinyin_y), wrapped_pinyin, fill=(6,95,85), font=pinyin_font, anchor="ma", align="center")
            draw.text((cx, hanzi_y), wrapped_hanzi, fill=(5,70,65), font=hanzi_font, anchor="ma", align="center")

            # English centered in bottom panel, italic grey
            eng_cx = (bot_x1 + bot_x2) // 2
            eng_cy = bot_y1 + bot_height // 2
            draw.text((eng_cx, eng_cy), wrapped_eng, fill=(120,120,120), font=eng_font, anchor="mm", align="center")

        else:
            # Default Spanish layout (original behavior)
            draw.rounded_rectangle(es_box, radius=25, fill=(255, 240, 235), outline=(0, 128, 0), width=4)
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

            wrapped_es = self.wrap_text(main_text, es_font, inner_box_width)
            wrapped_en = self.wrap_text(trans_text, en_font, inner_box_width)

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
        # track temporary files and opened clip objects for proper cleanup
        temp_files = set()
        clip_objects = []
        fps = 4
        out_folder = self.output_dir.get()
        final_path = os.path.join(out_folder, "pattern_lesson_wrapped.mp4")

        for i, line in enumerate(lines):
            # Branch on language selection
            if self.lang_var.get() == "Chinese":
                data = self.parse_line_chinese(line)
                if not data:
                    continue

                # Clean punctuation for TTS generation
                clean_hanzi = re.sub(r'[?/.()¿¡!]', '', data['hanzi'])
                raw_eng = data['english']

                # Prepare temp tracking for Chinese/English parts
                cn_temp = f"cn_temp_{i}.mp3"
                en_part_files = []

                # Generate CN audio
                asyncio.run(self.generate_audio(clean_hanzi, self.chinese_voice.get(), self.selected_speed.get(), cn_temp))
                cn_audio = AudioFileClip(cn_temp)
                clip_objects.append(cn_audio)
                temp_files.add(cn_temp)

                # Split English on '/' to create parts; if no '/', create single part
                eng_parts = [p.strip() for p in re.split(r'/+', raw_eng) if p.strip()]
                if len(eng_parts) > 1:
                    for j, part in enumerate(eng_parts):
                        clean_part = re.sub(r'[?/.()¿¡!]', '', part)
                        part_file = f"en_temp_{i}_{j}.mp3"
                        asyncio.run(self.generate_audio(clean_part, "en-US-GuyNeural", self.selected_speed.get(), part_file))
                        en_part_files.append(part_file)
                        clip_objects.append(AudioFileClip(part_file))
                        temp_files.add(part_file)
                else:
                    en_single = f"en_temp_{i}.mp3"
                    clean_eng = re.sub(r'[?/.()¿¡!]', '', raw_eng)
                    asyncio.run(self.generate_audio(clean_eng, "en-US-GuyNeural", self.selected_speed.get(), en_single))
                    en_part_files.append(en_single)
                    en_audio = AudioFileClip(en_single)
                    clip_objects.append(en_audio)
                    temp_files.add(en_single)

                # Build audio pattern: CN -> 0.5s -> 1.3s -> EN parts (0.5s between parts) repeated -> CN repeats
                line_audio_list = [cn_audio, self.make_silence(0.5), self.make_silence(1.3)]
                for _ in range(self.trans_repeat.get()):
                    for k, part_file in enumerate(en_part_files):
                        part_clip = AudioFileClip(part_file)
                        clip_objects.append(part_clip)
                        line_audio_list.append(part_clip)
                        if k < len(en_part_files) - 1:
                            line_audio_list.append(self.make_silence(0.5))
                    line_audio_list.append(self.make_silence(0.5))

                if self.main_repeat.get() > 1:
                    for _ in range(self.main_repeat.get() - 1):
                        line_audio_list.extend([cn_audio, self.make_silence(0.5)])

                final_audio = concatenate_audioclips(line_audio_list)
                clip_objects.append(final_audio)
                temp_avi = f"video_temp_{i}.avi"
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out = cv2.VideoWriter(temp_avi, fourcc, fps, (1280, 720))

                # Visual: pass hanzi (main), english (trans), and pinyin
                frame = self.create_frame(data['hanzi'], data['english'], pinyin_text=data.get('pinyin'))
                for _ in range(int(final_audio.duration * fps) + 1):
                    out.write(frame)
                out.release()

                segment = VideoFileClip(temp_avi).set_audio(final_audio)
                clip_objects.append(segment)
                temp_files.add(temp_avi)
                all_video_segments.append(segment)

            else:
                # Spanish (existing behavior)
                data = self.parse_line(line)
                if not data:
                    continue
                # Validate expected keys to avoid KeyError on malformed lines
                if 'en_text' not in data or 'es_text' not in data:
                    continue

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
                clip_objects.extend([es_audio, en_audio])
                temp_files.update([es_temp, en_temp])

                line_audio_list = [es_audio, self.make_silence(0.5), self.make_silence(1.3)]
                
                for _ in range(data['en_count']):
                    line_audio_list.extend([en_audio, self.make_silence(0.5)])
                    
                if data['es_count'] > 1:
                    for _ in range(data['es_count'] - 1):
                        line_audio_list.extend([es_audio, self.make_silence(0.5)])
                
                final_audio = concatenate_audioclips(line_audio_list)
                clip_objects.append(final_audio)
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
                clip_objects.append(segment)
                temp_files.add(temp_avi)
                all_video_segments.append(segment)

        if all_video_segments:
            final_result = concatenate_videoclips(all_video_segments)
            final_result.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=fps)

            # Close moviepy clip objects to release file handles
            try:
                final_result.close()
            except Exception:
                pass

            for c in clip_objects:
                try:
                    c.close()
                except Exception:
                    pass

            # Remove all temporary files we tracked
            for f in list(temp_files):
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

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