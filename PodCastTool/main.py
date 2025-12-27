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

# Đảm bảo các font này tồn tại hoặc thay bằng font hệ thống
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
    rect_y = H - 215
    center_x = W // 2

    def make_frame(t):
        # 1. Tạo ảnh RGBA hoàn toàn trong suốt
        img = Image.new("RGBA", (W, H), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        
        # 2. Vẽ khung nền phụ đề (Opaque trắng)
        draw.rectangle([(0, rect_y), (W, rect_y + 155)], fill=(255, 255, 255, 255))
        
        if selected_language == "Chinese":
            f_h = ImageFont.truetype(FONT_HANZI_PATH, 50)
            f_p = ImageFont.truetype(FONT_PINYIN_PATH, 30)
            f_e = ImageFont.truetype(FONT_LATIN_PATH, 30)
            draw_center_text(draw, args[0], f_h, center_x, rect_y + 15, W-160)
            draw_center_text(draw, args[1], f_p, center_x, rect_y + 75, W-160)
            draw_center_text(draw, args[2], f_e, center_x, rect_y + 115, W-160)
        else:
            font = ImageFont.truetype(FONT_LATIN_PATH, 35)
            draw_center_text(draw, args[0], font, center_x, rect_y + 40, W-160)
            draw_center_text(draw, args[1], font, center_x, rect_y + 95, W-160)
        
        # CHỐT: MoviePy cần RGB cho frame và Alpha riêng cho mask
        return np.array(img.convert("RGB"))

    def make_mask(t):
        # Tạo mask từ kênh Alpha (0-255 -> 0.0-1.0)
        img = Image.new("RGBA", (W, H), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, rect_y), (W, rect_y + 155)], fill=(255, 255, 255, 255))
        # Mask phải là grayscale (L) 
        return np.array(img.convert("L")) / 255.0

    return VideoClip(make_frame, duration=duration).set_mask(VideoClip(make_mask, ismask=True, duration=duration))

def make_waveform_clip(audio_path, duration):
    audio = AudioFileClip(audio_path)
    W_w, H_w = 400, 100
    
    def make_frame(t):
        # Tạo nền đen hoàn toàn
        img = Image.new("RGB", (W_w, H_w), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            # Lấy biên độ âm thanh
            sample = audio.get_frame(t)
            amplitude = np.mean(np.abs(sample))
        except: 
            amplitude = 0
            
        for i in range(25):
            # Tính toán chiều cao thanh dựa trên amplitude
            h = min(H_w, amplitude * 250 + np.random.randint(5, 15))
            x = (W_w - 25 * 8) // 2 + i * 8  # Center the bars
            # Vẽ thanh màu trắng (255, 255, 255)
            draw.rectangle([x, (H_w-h)/2, x+5, (H_w+h)/2], fill=(255, 255, 255))
        return np.array(img)

    def make_mask(t):
        # Lấy chính frame đó để làm mask
        frame = make_frame(t)
        # Chuyển về grayscale (L): Màu trắng (thanh waveform) sẽ thành 255, đen (nền) thành 0
        mask_img = Image.fromarray(frame).convert("L")
        # Chuẩn hóa về dải 0.0 - 1.0 (0.0 là trong suốt, 1.0 là hiện rõ)
        return np.array(mask_img) / 255.0

    wave = VideoClip(make_frame, duration=duration)
    return wave.set_mask(VideoClip(make_mask, ismask=True, duration=duration))

# ---------- MAIN BUILDER ----------
def build_video(dialogs, audio_files):
    video_clips = []
    audio_clips = []
    timeline = 0

    # Tính tổng duration chính xác
    total_duration = 0
    loaded_audios = []
    for f in audio_files:
        a = AudioFileClip(f)
        loaded_audios.append(a)
        total_duration += a.duration

    # Xử lý Background
    if selected_bg:
        if selected_bg.lower().endswith(".mp4"):
            bg = VideoFileClip(selected_bg).resize(VIDEO_SIZE).loop(duration=total_duration)
        else:
            bg = ImageClip(selected_bg).set_duration(total_duration).resize(VIDEO_SIZE)
    else:
        bg = ColorClip(size=VIDEO_SIZE, color=(30, 30, 30), duration=total_duration)

    for i, dialog in enumerate(dialogs):
        dur = loaded_audios[i].duration
        
        # Subtitle
        if selected_language == "Chinese":
            txt = animated_text(dialog[1], dialog[2], dialog[3], duration=dur).set_start(timeline)
        else:
            txt = animated_text(dialog[1], dialog[2], duration=dur).set_start(timeline)
        
        # Waveform
        wave = make_waveform_clip(audio_files[i], dur).set_start(timeline).set_position(('center', 410))

        video_clips.append(txt)
        video_clips.append(wave)
        audio_clips.append(loaded_audios[i].set_start(timeline))
        timeline += dur

    final_audio = CompositeAudioClip(audio_clips)
    final_video = CompositeVideoClip([bg] + video_clips, size=VIDEO_SIZE).set_audio(final_audio)
    
    out_path = os.path.join(OUTPUT_DIR, "final_podcast.mp4")
    final_video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True)
    
    # Clean up
    for a in loaded_audios: a.close()
    return out_path

# ---------- GUI FUNCTIONS ----------
def choose_background():
    global selected_bg
    path = filedialog.askopenfilename(filetypes=[("Media","*.jpg *.png *.mp4")])
    if path:
        selected_bg = path
        bg_label.config(text=os.path.basename(path))

async def generate_all_audio(dialogs):
    files = []
    for i, d in enumerate(dialogs):
        voice = selected_male_voice if d[0] == "M" else selected_female_voice
        path = f"{OUTPUT_DIR}/audio_{i}.mp3"
        await edge_tts.Communicate(d[1], voice).save(path)
        files.append(path)
    return files

def generate():
    global selected_language, selected_male_voice, selected_female_voice
    selected_language = lang_var.get()
    selected_male_voice = LANG_VOICES[selected_language]["male"]
    selected_female_voice = LANG_VOICES[selected_language]["female"]
    
    text = text_box.get("1.0", tk.END).strip()
    dialogs = parse_input(text)
    if not dialogs: return messagebox.showerror("Lỗi", "Vui lòng nhập đúng định dạng: Speaker|Text|Text")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_files = loop.run_until_complete(generate_all_audio(dialogs))
        out = build_video(dialogs, audio_files)
        messagebox.showinfo("Thành công", f"Video đã lưu tại: {out}")
    except Exception as e:
        messagebox.showerror("Lỗi Render", str(e))

# ---------- GUI LAYOUT ----------
root = tk.Tk()
root.title("AI Podcast Generator Fix")
lang_var = tk.StringVar(value="Vietnamese")
tk.OptionMenu(root, lang_var, "Vietnamese", "Spanish", "Chinese").pack()
tk.Button(root, text="Chọn Hình Nền", command=choose_background).pack()
bg_label = tk.Label(root, text="Chưa chọn nền")
bg_label.pack()
text_box = tk.Text(root, width=80, height=15)
text_box.pack()
tk.Button(root, text="BẮT ĐẦU TẠO VIDEO", command=generate, bg="blue", fg="white").pack(pady=10)
root.mainloop()