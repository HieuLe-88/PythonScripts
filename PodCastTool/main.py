import tkinter as tk
from tkinter import filedialog, messagebox
import asyncio
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    VideoClip,
    ColorClip
)
import edge_tts

# ---------- CONFIG ----------
VIDEO_SIZE = (1280, 720)
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Fonts (update đường dẫn chính xác trên máy bạn)
FONT_HANZI_PATH = "C:/Users/USER/AppData/Local/Microsoft/Windows/Fonts/NotoSansCJKsc-Regular.otf"  # Cập nhật đúng đường dẫn font # Chinese Hán tự
FONT_PINYIN_PATH = "fonts/arial.ttf"                  # Chinese Pinyin
FONT_LATIN_PATH = "fonts/arial.ttf"                   # Vietnamese / Spanish

# TTS Voices
LANG_VOICES = {
    "Vietnamese": {"male": "vi-VN-NamMinhNeural", "female": "vi-VN-HoaiMyNeural"},
    "Spanish": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
    "Chinese": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
}

# ---------- GLOBALS ----------
selected_language = "Vietnamese"
selected_male_voice = LANG_VOICES[selected_language]["male"]
selected_female_voice = LANG_VOICES[selected_language]["female"]
selected_bg = None

# ---------- PARSE INPUT ----------
def parse_input(text):
    dialogs = []
    if selected_language == "Chinese":
        for line in text.split("\n"):
            line = line.strip()
            parts = line.split("|")
            if len(parts) == 4:  # Speaker|Hanzi|Pinyin|English
                speaker, hanzi, pinyin, english = parts
                dialogs.append((speaker.strip(), hanzi.strip(), pinyin.strip(), english.strip()))
    else:
        for line in text.split("\n"):
            line = line.strip()
            parts = line.split("|")
            if len(parts) == 3:  # Speaker|Original|English
                speaker, original, english = parts
                dialogs.append((speaker.strip(), original.strip(), english.strip()))
    return dialogs

# ---------- DRAW MULTILINE ----------
def draw_multiline(draw, text, font, x, y, max_width, fill=(255,255,255)):
    if not text:
        return
    lines = []
    line = ""
    for ch in text:
        if draw.textlength(line + ch, font=font) > max_width:
            lines.append(line)
            line = ch
        else:
            line += ch
    lines.append(line)
    for i, l in enumerate(lines):
        draw.text((x, y + i * (font.size + 5)), l, font=font, fill=fill)

# ---------- ANIMATED TEXT ----------
def animated_text(*args, duration=None, side="left", speaker="M"):
    W, H = VIDEO_SIZE
    max_width = W - 160
    sub_height = 155  # chiều cao khung sub 
    rect_y = H - sub_height - 60
    
    # Căn giữa: x là điểm bắt đầu, để draw_multiline căn giữa ta tính x là trung tâm
    center_x = W // 2

    if selected_language == "Chinese":
        hanzi, pinyin, english_text = args
        # Tăng size font thêm 20%
        font_hanzi = ImageFont.truetype(FONT_HANZI_PATH, int(42 * 1.2))
        font_pinyin = ImageFont.truetype(FONT_PINYIN_PATH, int(28 * 1.2))
        font_en = ImageFont.truetype(FONT_LATIN_PATH, int(28 * 1.2))

        def make_frame(t):
            img = Image.new("RGBA", (W, H), (0,0,0,0))
            draw = ImageDraw.Draw(img)
            draw.rectangle([ (0, rect_y), (W, rect_y + sub_height) ], fill=(255,255,255,255))
            
            # Sử dụng hàm vẽ căn giữa
            draw_center_text(draw, hanzi, font_hanzi, center_x, rect_y + 15, max_width, fill=(0,0,0,255))
            draw_center_text(draw, pinyin, font_pinyin, center_x, rect_y + 75, max_width, fill=(0,0,0,255))
            draw_center_text(draw, english_text, font_en, center_x, rect_y + 120, max_width, fill=(0,0,0,255))
            return np.array(img.convert("RGB"))

    else:
        original_text, english_text = args
        # Tăng size font thêm 20%
        font_size = int(28 * 1.2)
        font = ImageFont.truetype(FONT_LATIN_PATH, font_size)
        font_en = ImageFont.truetype(FONT_LATIN_PATH, font_size)

        def make_frame(t):
            img = Image.new("RGBA", (W, H), (0,0,0,0))
            draw = ImageDraw.Draw(img)
            draw.rectangle([ (0, rect_y), (W, rect_y + sub_height) ], fill=(255,255,255,255))
            
            draw_center_text(draw, original_text, font, center_x, rect_y + 40, max_width, fill=(0,0,0,255))
            draw_center_text(draw, english_text, font_en, center_x, rect_y + 95, max_width, fill=(0,0,0,255))
            return np.array(img.convert("RGB"))

    return VideoClip(make_frame, duration=duration).set_position("center")

def draw_center_text(draw, text, font, center_x, y, max_width, fill=(255,255,255)):
    if not text:
        return
    
    # Chia dòng
    lines = []
    words = text.split(' ') if ' ' in text else list(text) # Tách từ cho Latin hoặc tách ký tự cho Chinese
    
    current_line = ""
    for unit in words:
        test_line = current_line + (" " if current_line and ' ' in text else "") + unit
        if draw.textlength(test_line, font=font) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = unit
    lines.append(current_line)

    # Vẽ từng dòng căn giữa
    for i, line in enumerate(lines):
        # Tính toán anchor 'mm' (middle-middle) để căn giữa hoàn hảo
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        line_x = center_x - (line_width / 2)
        draw.text((line_x, y + i * (font.size + 8)), line, font=font, fill=fill)

# ---------- GENERATE TTS ----------
async def tts_generate(text, voice, out_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_file)

async def generate_all_audio(dialogs):
    audio_files = []
    for i, dialog in enumerate(dialogs):
        speaker = dialog[0]
        voice = selected_male_voice if speaker=="M" else selected_female_voice
        out = f"{OUTPUT_DIR}/audio_{i}.mp3"
        text_to_read = dialog[1] if selected_language!="Chinese" else dialog[1]  # chỉ đọc Hán tự
        await tts_generate(text_to_read, voice, out)
        audio_files.append(out)
    return audio_files

#---------- WAVEFORM CLIP ----------#
def make_waveform_clip(audio_path, duration, size=(400, 100)):
    audio = AudioFileClip(audio_path)
    # Lấy mẫu âm thanh (20 khung hình mỗi giây để mượt mà)
    fps = 20
    n_frames = int(duration * fps)
    
    # Hàm vẽ từng frame waveform
    def make_frame(t):
        w, h = size
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Lấy biên độ tại thời điểm t
        # audio.get_frame(t) trả về mảng [trái, phải], ta lấy trung bình
        try:
            sample = audio.get_frame(t)
            amplitude = np.mean(np.abs(sample)) 
        except:
            amplitude = 0
            
        # Vẽ 24 thanh waveform đơn giản
        num_bars = 24
        bar_width = w // num_bars - 4
        for i in range(num_bars):
            # Tạo hiệu ứng ngẫu nhiên nhẹ dựa trên biên độ để trông "nhảy" hơn
            bar_h = min(h, amplitude * h * 2.5 + np.random.randint(5, 15))
            x0 = i * (bar_width + 4)
            y0 = (h - bar_h) / 2
            x1 = x0 + bar_width
            y1 = y0 + bar_h
            draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255, 200)) # Màu trắng đục
            
        return np.array(img.convert("RGB"))

    return VideoClip(make_frame, duration=duration).set_opacity(0.8)

# ---------- BUILD VIDEO ----------
def build_video(dialogs, audio_files):
    clips = []
    audio_clips = []
    current_time = 0

    for i, dialog in enumerate(dialogs):
        # Nạp audio trước để lấy duration chính xác
        audio = AudioFileClip(audio_files[i])
        dur = audio.duration
        
        speaker = dialog[0]
        if selected_language == "Chinese":
            txt_clip = animated_text(dialog[1], dialog[2], dialog[3], duration=dur, speaker=speaker).set_start(current_time)
        else:
            txt_clip = animated_text(dialog[1], dialog[2], duration=dur, speaker=speaker).set_start(current_time)


        # 2. Tạo Waveform Clip ở giữa màn hình
        wave_clip = make_waveform_clip(audio_files[i], dur, size=(300, 80))
        wave_clip = wave_clip.set_start(current_time).set_position(('center', 410)) # 430 là tọa độ Y (ở giữa-trên)

        clips.append(txt_clip)
        clips.append(wave_clip) # Thêm waveform vào danh sách clip
        audio_clips.append(audio.set_start(current_time))
        current_time += dur

    # Tạo Audio tổng hợp
    final_audio = CompositeAudioClip(audio_clips)
    
    # Render audio ra một file tạm hoặc xử lý để tránh lỗi to_soundarray
    # (MoviePy đôi khi lỗi khi lấy soundarray trực tiếp từ CompositeAudioClip)
    
    # 1. Background
    if selected_bg:
        if selected_bg.lower().endswith(".mp4"):
            bg = VideoFileClip(selected_bg).resize(VIDEO_SIZE).loop(duration=current_time)
        else:
            bg = ImageClip(selected_bg).set_duration(current_time).resize(VIDEO_SIZE)
    else:
        bg = ColorClip(size=VIDEO_SIZE, color=(20, 20, 20), duration=current_time)

    # 2. Kết hợp theo thứ tự lớp: Background -> Subtitles
    all_video_layers = [bg] + clips
    
    final_video = CompositeVideoClip(all_video_layers, size=VIDEO_SIZE)
    final_video = final_video.set_audio(final_audio).set_duration(current_time)

    out_path = os.path.join(OUTPUT_DIR, "final_podcast.mp4")
    final_video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
    
    return out_path


# ---------- GUI ----------
root = tk.Tk()
root.title("Multi-language Podcast Generator")

# Language Selection
lang_frame = tk.Frame(root)
lang_frame.pack(pady=5)
tk.Label(lang_frame, text="Select Language:").pack(side="left", padx=5)
lang_var = tk.StringVar(value="Vietnamese")
for lang in ["Vietnamese","Spanish","Chinese"]:
    tk.Radiobutton(lang_frame, text=lang, variable=lang_var, value=lang).pack(side="left", padx=5)

# Voice Selection
voice_frame = tk.Frame(root)
voice_frame.pack(pady=5)
tk.Label(voice_frame, text="Male voice:").grid(row=0, column=0)
tk.Label(voice_frame, text="Female voice:").grid(row=0, column=2)
male_var = tk.StringVar(value="Male")
female_var = tk.StringVar(value="Female")
male_menu = tk.OptionMenu(voice_frame, male_var, "Male")
female_menu = tk.OptionMenu(voice_frame, female_var, "Female")
male_menu.grid(row=0, column=1, padx=5)
female_menu.grid(row=0, column=3, padx=5)

# Background Selection
bg_frame = tk.Frame(root)
bg_frame.pack(pady=5)
bg_btn = tk.Button(bg_frame, text="Choose Background", command=lambda: choose_background())
bg_btn.pack(side="left")
bg_label = tk.Label(bg_frame, text="No background selected")
bg_label.pack(side="left", padx=10)

# Text Input
text_box = tk.Text(root, width=100, height=20)
text_box.pack(pady=5)

# ---------- GUI FUNCTIONS ----------
def choose_background():
    global selected_bg
    path = filedialog.askopenfilename(title="Choose background", filetypes=[("Image/Video","*.jpg *.png *.mp4")])
    if path:
        selected_bg = path
        bg_label.config(text=os.path.basename(path))

def generate():
    global selected_male_voice, selected_female_voice, selected_language
    selected_language = lang_var.get()
    voices = LANG_VOICES[selected_language]
    selected_male_voice = voices["male"]
    selected_female_voice = voices["female"]

    text = text_box.get("1.0", tk.END).strip()
    if not text:
        messagebox.showerror("Error", "Input is empty")
        return

    dialogs = parse_input(text)
    if not dialogs:
        messagebox.showerror("Error", "Wrong format")
        return

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_files = loop.run_until_complete(generate_all_audio(dialogs))
        out = build_video(dialogs, audio_files)
        messagebox.showinfo("Done", f"Video generated:\n{out}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Generate Button
gen_btn = tk.Button(root, text="Generate Video", command=generate)
gen_btn.pack(pady=10)

root.mainloop()
