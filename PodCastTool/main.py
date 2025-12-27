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
VIDEO_SIZE = (1920, 1080) 
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONT_HANZI_PATH = "C:/Users/USER/AppData/Local/Microsoft/Windows/Fonts/NotoSansCJKsc-Regular.otf"
FONT_PINYIN_PATH = "fonts/arial.ttf"
FONT_LATIN_PATH = "fonts/arial.ttf"

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

# ---------- HELPER FUNCTIONS ----------
def parse_input(text):
    dialogs = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        parts = line.split("|")
        if selected_language == "Chinese" and len(parts) == 4:
            dialogs.append((parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()))
        elif selected_language != "Chinese" and len(parts) == 3:
            dialogs.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return dialogs

def draw_center_text(draw, text, font, center_x, y, max_width, fill=(0,0,0,255)):
    if not text: return
    lines = []
    words = list(text) if selected_language == "Chinese" else text.split(' ')
    current_line = ""
    for unit in words:
        sep = "" if selected_language == "Chinese" else " "
        test_line = current_line + (sep if current_line else "") + unit
        if draw.textlength(test_line, font=font) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = unit
    lines.append(current_line)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        draw.text((center_x - line_w/2, y + i * (font.size + 8)), line, font=font, fill=fill)

# ---------- CLIP GENERATORS ----------
def animated_text(*args, duration=None):
    W, H = VIDEO_SIZE
    rect_height = 200
    rect_y = H - 300 
    center_x = W // 2

    def make_frame(t):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, rect_y), (W, rect_y + rect_height)], fill=(100, 100, 100, 255))
        text_color = (255, 255, 255, 255)

        if selected_language == "Chinese":
            f_h = ImageFont.truetype(FONT_HANZI_PATH, 75)
            f_p = ImageFont.truetype(FONT_PINYIN_PATH, 45)
            f_e = ImageFont.truetype(FONT_LATIN_PATH, 45)
            draw_center_text(draw, args[0], f_h, center_x, rect_y + 20, W-200, fill=text_color)
            draw_center_text(draw, args[1], f_p, center_x, rect_y + 105, W-200, fill=text_color)
            draw_center_text(draw, args[2], f_e, center_x, rect_y + 155, W-200, fill=text_color)
        else:
            font = ImageFont.truetype(FONT_LATIN_PATH, 55)
            draw_center_text(draw, args[0], font, center_x, rect_y + 40, W-200, fill=text_color)
            draw_center_text(draw, args[1], font, center_x, rect_y + 115, W-200, fill=text_color)
        return np.array(img.convert("RGB"))

    def make_mask(t):
        img = Image.new("L", (W, H), 0)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, rect_y), (W, rect_y + rect_height)], fill=153)
        if selected_language == "Chinese":
            f_h = ImageFont.truetype(FONT_HANZI_PATH, 75)
            f_p = ImageFont.truetype(FONT_PINYIN_PATH, 45)
            f_e = ImageFont.truetype(FONT_LATIN_PATH, 45)
            draw_center_text(draw, args[0], f_h, center_x, rect_y + 20, W-200, fill=255)
            draw_center_text(draw, args[1], f_p, center_x, rect_y + 105, W-200, fill=255)
            draw_center_text(draw, args[2], f_e, center_x, rect_y + 155, W-200, fill=255)
        else:
            font = ImageFont.truetype(FONT_LATIN_PATH, 55)
            draw_center_text(draw, args[0], font, center_x, rect_y + 40, W-200, fill=255)
            draw_center_text(draw, args[1], font, center_x, rect_y + 115, W-200, fill=255)
        return np.array(img) / 255.0

    return VideoClip(make_frame, duration=duration).set_mask(VideoClip(make_mask, ismask=True, duration=duration))

def make_waveform_clip(audio_path, duration):
    audio = AudioFileClip(audio_path)
    W_w, H_w = 600, 150 
    def get_raw_frame(t):
        img = Image.new("RGB", (W_w, H_w), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            sample = audio.get_frame(t)
            amplitude = np.mean(np.abs(sample))
        except: amplitude = 0
        for i in range(30):
            h = min(H_w, amplitude * 350 + np.random.randint(10, 20))
            x = (W_w - 30 * 12) // 2 + i * 12
            draw.rectangle([x, (H_w-h)/2, x + 8, (H_w+h)/2], fill=(255, 255, 255))
        return img
    def make_frame(t): return np.array(get_raw_frame(t))
    def make_mask(t):
        img = get_raw_frame(t).convert("L")
        mask_array = np.array(img.point(lambda p: 255 if p > 50 else 0))
        return mask_array / 255.0
    wave = VideoClip(make_frame, duration=duration)
    return wave.set_mask(VideoClip(make_mask, ismask=True, duration=duration))

# ---------- MAIN BUILDER ----------
def build_video(dialogs, audio_files):
    video_clips = []
    audio_clips = []
    timeline = 0
    total_duration = 0
    loaded_audios = []
    for f in audio_files:
        a = AudioFileClip(f)
        loaded_audios.append(a)
        total_duration += a.duration

    if selected_bg:
        if selected_bg.lower().endswith(".mp4"):
            bg = VideoFileClip(selected_bg).resize(height=VIDEO_SIZE[1])
            if bg.w > VIDEO_SIZE[0]: bg = bg.crop(x_center=bg.w/2, width=VIDEO_SIZE[0])
            bg = bg.loop(duration=total_duration)
        else:
            bg = ImageClip(selected_bg).set_duration(total_duration).resize(height=VIDEO_SIZE[1])
            if bg.w < VIDEO_SIZE[0]: bg = bg.resize(width=VIDEO_SIZE[0])
            bg = bg.crop(x_center=bg.w/2, y_center=bg.h/2, width=VIDEO_SIZE[0], height=VIDEO_SIZE[1])
    else:
        bg = ColorClip(size=VIDEO_SIZE, color=(30, 30, 30), duration=total_duration)

    for i, dialog in enumerate(dialogs):
        dur = loaded_audios[i].duration
        if selected_language == "Chinese":
            txt = animated_text(dialog[1], dialog[2], dialog[3], duration=dur).set_start(timeline)
        else:
            txt = animated_text(dialog[1], dialog[2], duration=dur).set_start(timeline)
        
        wave = make_waveform_clip(audio_files[i], dur).set_start(timeline).set_position(('center', 650))
        video_clips.append(txt)
        video_clips.append(wave)
        audio_clips.append(loaded_audios[i].set_start(timeline))
        timeline += dur

    final_audio = CompositeAudioClip(audio_clips)
    final_video = CompositeVideoClip([bg] + video_clips, size=VIDEO_SIZE).set_audio(final_audio)
    
    out_path = os.path.join(OUTPUT_DIR, "final_podcast.mp4")
    final_video.write_videofile(out_path, fps=12, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast")
    
    for a in loaded_audios: a.close()
    return out_path

# ---------- GUI FUNCTIONS ----------
def choose_background():
    global selected_bg
    path = filedialog.askopenfilename(filetypes=[("Media","*.jpg *.png *.mp4")])
    if path:
        selected_bg = path
        bg_label.config(text=os.path.basename(path))

async def generate_all_audio(dialogs, rate_str):
    files = []
    # Chuyển đổi từ % sang định dạng của edge-tts (ví dụ 90% -> -10%)
    speed_map = {"100%": "+0Hz", "90%": "-10%", "80%": "-20%"}
    rate = speed_map.get(rate_str, "+0Hz")
    
    for i, d in enumerate(dialogs):
        voice = selected_male_voice if d[0] == "M" else selected_female_voice
        path = f"{OUTPUT_DIR}/audio_{i}.mp3"
        # Thêm tham số rate vào Communicate
        await edge_tts.Communicate(d[1], voice, rate=rate).save(path)
        files.append(path)
    return files

def generate():
    global selected_language, selected_male_voice, selected_female_voice
    selected_language = lang_var.get()
    selected_male_voice = LANG_VOICES[selected_language]["male"]
    selected_female_voice = LANG_VOICES[selected_language]["female"]
    
    text = text_box.get("1.0", tk.END).strip()
    dialogs = parse_input(text)
    if not dialogs: return messagebox.showerror("Lỗi", "Định dạng sai!")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Truyền tốc độ nói từ GUI vào
        audio_files = loop.run_until_complete(generate_all_audio(dialogs, speed_var.get()))
        out = build_video(dialogs, audio_files)
        messagebox.showinfo("Thành công", f"Video đã lưu tại: {out}")
    except Exception as e:
        messagebox.showerror("Lỗi Render", str(e))

# ---------- GUI LAYOUT ----------
root = tk.Tk()
root.title("AI Podcast Generator Speed Mode")

# Ngôn ngữ
tk.Label(root, text="Chọn ngôn ngữ:").pack()
lang_var = tk.StringVar(value="Vietnamese")
tk.OptionMenu(root, lang_var, "Vietnamese", "Spanish", "Chinese").pack()

# Tốc độ nói (Mới thêm)
tk.Label(root, text="Tốc độ nói:").pack()
speed_var = tk.StringVar(value="100%")
tk.OptionMenu(root, speed_var, "100%", "90%", "80%").pack()

tk.Button(root, text="Chọn Hình Nền", command=choose_background).pack()
bg_label = tk.Label(root, text="Chưa chọn nền")
bg_label.pack()

text_box = tk.Text(root, width=80, height=15)
text_box.pack()

tk.Button(root, text="BẮT ĐẦU TẠO VIDEO", command=generate, bg="blue", fg="white").pack(pady=10)
root.mainloop()