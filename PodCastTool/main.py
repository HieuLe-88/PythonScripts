import tkinter as tk
from tkinter import filedialog, messagebox
import asyncio
import os
import subprocess
import edge_tts

# ---------- CONFIG ----------
VIDEO_SIZE = "1920x1080"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Đường dẫn font cho FFmpeg (Lưu ý: FFmpeg cần đường dẫn kiểu C\\:/Windows/Fonts/...)
# Dùng font Latin cho Việt/Tây Ban Nha và font CJK cho tiếng Trung
FONT_LATIN = "C\\:/Windows/Fonts/arial.ttf"
FONT_CHINESE = "C\\:/Users/USER/AppData/Local/Microsoft/Windows/Fonts/NotoSansCJKsc-Regular.otf"

LANG_VOICES = {
    "Vietnamese": {"male": "vi-VN-NamMinhNeural", "female": "vi-VN-HoaiMyNeural"},
    "Spanish": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
    "Chinese": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
}

selected_bg = None

# ---------- HELPER FUNCTIONS ----------
def format_srt_time(seconds):
    td_h = int(seconds // 3600)
    td_m = int((seconds % 3600) // 60)
    td_s = int(seconds % 60)
    td_ms = int((seconds - int(seconds)) * 1000)
    return f"{td_h:02}:{td_m:02}:{td_s:02},{td_ms:03}"

def parse_input(text, lang):
    dialogs = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        parts = line.split("|")
        if lang == "Chinese" and len(parts) == 4:
            dialogs.append((parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()))
        elif lang != "Chinese" and len(parts) == 3:
            dialogs.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return dialogs

async def generate_assets(dialogs, lang, rate_str):
    speed_map = {
        "100%": "+0Hz",
        "90%": "-10%",
        "80%": "-20%",
        "70%": "-30%"
    }
    rate = speed_map.get(rate_str, "+0Hz")
    
    audio_files = []
    srt_content = ""
    timeline = 0.0
    
    for i, d in enumerate(dialogs):
        voice = LANG_VOICES[lang]["male"] if d[0] == "M" else LANG_VOICES[lang]["female"]
        audio_path = os.path.join(OUTPUT_DIR, f"audio_{i}.mp3")
        
        # 1. Gen Audio
        await edge_tts.Communicate(d[1], voice, rate=rate).save(audio_path)
        
        # 2. Get Duration (Dùng ffprobe để lấy chính xác nhất)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        dur = float(result.stdout)
        
        # 3. Build SRT
        start_t = format_srt_time(timeline)
        end_t = format_srt_time(timeline + dur)
        
        # Nếu tiếng Trung: Ghép Hán tự | Pinyin | Nghĩa vào sub
        main_text = d[1]
        font_size = calc_font_size(main_text)

        if lang == "Chinese":
            sub_text = (
                f"{{\\fs{font_size}}}{d[1]}"
                f"\\N{{\\fs{font_size-2}}}{d[2]}"
                f"\\N{{\\fs{font_size-4}}}{d[3]}"
            )
        else:
            sub_text = (
                f"{{\\fs{font_size}}}{d[1]}"
                f"\\N{{\\fs{font_size-2}}}{d[2]}"
            )
            
        srt_content += f"{i+1}\n{start_t} --> {end_t}\n{sub_text}\n\n"
        
        audio_files.append(audio_path)
        timeline += dur
        
    # Lưu file SRT
    srt_path = os.path.join(OUTPUT_DIR, "subs.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
        
    return audio_files, timeline

def calc_font_size(text):
    length = len(text)
    if length <= 40:
        return 17
    elif length <= 60:
        return 15
    elif length <= 80:
        return 13
    else:
        return 12
    
def build_video_ffmpeg(audio_files, total_dur, lang):
    # 1. Tạo file list để gộp audio
    list_path = os.path.join(OUTPUT_DIR, "audio_list.txt")
    with open(list_path, "w") as f:
        for audio in audio_files:
            f.write(f"file '{os.path.abspath(audio)}'\n")
            
    full_audio = os.path.join(OUTPUT_DIR, "full_audio.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", full_audio], check=True)

    # 2. Cấu hình Subtitle
    srt_path = os.path.join(OUTPUT_DIR, "subs.srt").replace("\\", "/")
    current_font = FONT_CHINESE if lang == "Chinese" else FONT_LATIN
    
    # Force_style: Nền xám trong suốt (BorderStyle=3, OutlineColour=&H99666666)
    sub_style = (f"subtitles='{srt_path}':force_style='Fontname={current_font},FontSize=16,"
                 f"PrimaryColour=&HFFFFFF,BorderStyle=3,OutlineColour=&H99333333,"
                 f"Alignment=2,MarginV=40'")

    # 3. Lệnh FFmpeg tổng hợp
    out_video = os.path.join(OUTPUT_DIR, "final_podcast.mp4")
    
    # Input Background
    if selected_bg and selected_bg.lower().endswith((".mp4", ".mov")):
        bg_input = ["-stream_loop", "-1", "-i", selected_bg]
    elif selected_bg:
        bg_input = ["-loop", "1", "-i", selected_bg]
    else:
        bg_input = ["-f", "lavfi", "-i", "color=c=black:s=1920x1080"]

    cmd = [
        "ffmpeg", "-y",
        *bg_input,
        "-i", full_audio,
        "-filter_complex",
        # Bước 1: Scale và Crop nền về 1080p
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];"
        # Bước 2: Tạo Waveform trắng (showwaves)
        f"[1:a]showwaves=s=800x200:mode=line:colors=white:draw=full[wave];"
        # Bước 3: Chồng waveform lên nền tại vị trí 650
        f"[bg][wave]overlay=(W-w)/2:600[v_wave];"
        # Bước 4: Chèn Subtitle
        f"[v_wave]{sub_style},fps=12[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-t", str(total_dur),
        out_video
    ]
    
    subprocess.run(cmd, check=True)

    # Cleanup
    try:
        for audio in audio_files:
            if os.path.exists(audio):
                os.remove(audio)

        if os.path.exists(full_audio):
            os.remove(full_audio)

        if os.path.exists(list_path):
            os.remove(list_path)

    except Exception as e:
        print("Cleanup warning:", e)

    return out_video    

# ---------- GUI FUNCTIONS ----------
def choose_background():
    global selected_bg
    path = filedialog.askopenfilename(filetypes=[("Media","*.jpg *.png *.mp4")])
    if path:
        selected_bg = path
        bg_label.config(text=os.path.basename(path))

def generate():
    lang = lang_var.get()
    text = text_box.get("1.0", tk.END).strip()
    dialogs = parse_input(text, lang)
    
    if not dialogs:
        return messagebox.showerror("Lỗi", "Vui lòng nhập đúng định dạng!")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 1. Tạo Audio và Subtitle file
        audio_files, total_dur = loop.run_until_complete(generate_assets(dialogs, lang, speed_var.get()))
        
        # 2. Render bằng FFmpeg
        out = build_video_ffmpeg(audio_files, total_dur, lang)
        
        messagebox.showinfo("Thành công", f"Video render siêu tốc đã lưu tại:\n{out}")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))

# ---------- GUI LAYOUT ----------
root = tk.Tk()
root.title("AI Podcast - FFmpeg Turbo Mode")

tk.Label(root, text="Chọn ngôn ngữ:").pack()
lang_var = tk.StringVar(value="Vietnamese")
tk.OptionMenu(root, lang_var, "Vietnamese", "Spanish", "Chinese").pack()

tk.Label(root, text="Tốc độ nói:").pack()
speed_var = tk.StringVar(value="100%")
tk.OptionMenu(root, speed_var, "100%", "90%", "80%", "70%").pack()

tk.Button(root, text="Chọn Hình Nền / Video Nền", command=choose_background).pack(pady=5)
bg_label = tk.Label(root, text="Chưa chọn nền")
bg_label.pack()

text_box = tk.Text(root, width=80, height=15)
text_box.pack(pady=10)
text_box.insert("1.0", "M|Xin chào các bạn|Chào mừng đến với Podcast\nF|Chào anh Nam|Rất vui được gặp anh")

tk.Button(root, text="BẮT ĐẦU RENDER", command=generate, bg="green", fg="white", font=('Arial', 10, 'bold')).pack(pady=10)

root.mainloop()