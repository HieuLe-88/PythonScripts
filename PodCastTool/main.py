import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import asyncio
import os
import subprocess
import edge_tts
import threading
import re  # Thêm re để xử lý chuỗi log

# ---------- CONFIG ----------
VIDEO_SIZE = "1920x1080"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONT_LATIN = "C\\:/Windows/Fonts/arial.ttf"
FONT_CHINESE = "C\\:/Users/USER/AppData/Local/Microsoft/Windows/Fonts/NotoSansCJKsc-Regular.otf"

LANG_VOICES = {
    "Vietnamese": {"male": "vi-VN-NamMinhNeural", "female": "vi-VN-HoaiMyNeural"},
    "Spanish": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
    "Chinese": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
}

selected_bg = None

# ---------- HELPER FUNCTIONS ----------
def get_seconds(time_str):
    """Chuyển đổi HH:MM:SS.ms thành giây"""
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

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
    speed_map = {"100%": "+0Hz", "90%": "-10%", "80%": "-20%", "70%": "-30%"}
    rate = speed_map.get(rate_str, "+0Hz")
    
    audio_files = []
    srt_content = ""
    timeline = 0.0
    
    for i, d in enumerate(dialogs):
        voice = LANG_VOICES[lang]["male"] if d[0] == "M" else LANG_VOICES[lang]["female"]
        audio_path = os.path.join(OUTPUT_DIR, f"audio_{i}.mp3")
        await edge_tts.Communicate(d[1], voice, rate=rate).save(audio_path)
        
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        dur = float(result.stdout)
        
        start_t = format_srt_time(timeline)
        end_t = format_srt_time(timeline + dur)
        
        main_text = d[1]
        length = len(main_text)
        font_size = 17 if length <= 40 else 15 if length <= 60 else 13 if length <= 80 else 12

        if lang == "Chinese":
            sub_text = f"{{\\fs{font_size}}}{d[1]}\\N{{\\fs{font_size-2}}}{d[2]}\\N{{\\fs{font_size-4}}}{d[3]}"
        else:
            sub_text = f"{{\\fs{font_size}}}{d[1]}\\N{{\\fs{font_size-2}}}{d[2]}"
            
        srt_content += f"{i+1}\n{start_t} --> {end_t}\n{sub_text}\n\n"
        audio_files.append(audio_path)
        timeline += dur
        
    with open(os.path.join(OUTPUT_DIR, "subs.srt"), "w", encoding="utf-8") as f:
        f.write(srt_content)
        
    return audio_files, timeline

def build_video_ffmpeg_with_progress(audio_files, total_dur, lang, progress_callback):
    list_path = os.path.join(OUTPUT_DIR, "audio_list.txt")
    with open(list_path, "w") as f:
        for audio in audio_files:
            f.write(f"file '{os.path.abspath(audio)}'\n")
            
    full_audio = os.path.join(OUTPUT_DIR, "full_audio.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", full_audio], check=True)

    srt_path = os.path.join(OUTPUT_DIR, "subs.srt").replace("\\", "/")
    current_font = FONT_CHINESE if lang == "Chinese" else FONT_LATIN
    sub_style = (f"subtitles='{srt_path}':force_style='Fontname={current_font},FontSize=16,"
                 f"PrimaryColour=&HFFFFFF,BorderStyle=3,OutlineColour=&H99333333,"
                 f"Alignment=2,MarginV=40'")

    out_video = os.path.join(OUTPUT_DIR, "final_podcast.mp4")
    
    bg_input = ["-f", "lavfi", "-i", "color=c=black:s=1920x1080"]
    if selected_bg:
        if selected_bg.lower().endswith((".mp4", ".mov")):
            bg_input = ["-stream_loop", "-1", "-i", selected_bg]
        else:
            bg_input = ["-loop", "1", "-i", selected_bg]

    cmd = [
        "ffmpeg", "-y", *bg_input, "-i", full_audio,
        "-filter_complex",
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];"
        f"[1:a]showwaves=s=800x200:mode=line:colors=white:draw=full[wave];"
        f"[bg][wave]overlay=(W-w)/2:600[v_wave];"
        f"[v_wave]{sub_style},fps=12[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-t", str(total_dur),
        out_video
    ]
    
    # Chạy FFmpeg và bắt log stderr
    process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf-8')

    # Regex để tìm thời gian hiện tại trong log: time=00:00:05.12
    time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})")

    while True:
        line = process.stdout.readline()
        if not line:
            break
        
        match = time_pattern.search(line)
        if match:
            current_time_str = match.group(1)
            current_seconds = get_seconds(current_time_str)
            percentage = min(int((current_seconds / total_dur) * 100), 100)
            progress_callback(percentage)

    process.wait()

# ---------- BẮT ĐẦU XÓA FILE TẠM ----------
    print("Đang dọn dẹp file tạm...")
    try:
        # Xóa các file audio nhỏ
        for audio in audio_files:
            if os.path.exists(audio):
                os.remove(audio)
        
        # Xóa file audio tổng hợp
        if os.path.exists(full_audio):
            os.remove(full_audio)
            
        # Xóa file danh sách audio
        if os.path.exists(list_path):
            os.remove(list_path)
        
    except Exception as e:
        print(f"Lỗi khi xóa file: {e}")
    # ---------- KẾT THÚC XÓA ----------

    return out_video

# ---------- GUI FUNCTIONS ----------
def update_progress(val):
    progress_bar['value'] = val
    percent_label.config(text=f"{val}%")
    root.update_idletasks()

def run_processing():
    lang = lang_var.get()
    text = text_box.get("1.0", tk.END).strip()
    dialogs = parse_input(text, lang)
    
    if not dialogs:
        generate_btn.config(state=tk.NORMAL)
        return messagebox.showerror("Lỗi", "Vui lòng nhập đúng định dạng!")

    try:
        update_progress(0)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Bước 1: Audio (giả định chiếm 10% quá trình)
        percent_label.config(text="Đang tạo giọng nói...")
        audio_files, total_dur = loop.run_until_complete(generate_assets(dialogs, lang, speed_var.get()))
        
        # Bước 2: Render Video (chiếm từ 10% đến 100%)
        out = build_video_ffmpeg_with_progress(audio_files, total_dur, lang, update_progress)
        
        update_progress(100)
        messagebox.showinfo("Thành công", f"Video đã lưu tại:\n{out}")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))
    finally:
        generate_btn.config(state=tk.NORMAL)
        percent_label.config(text="Sẵn sàng")

def generate():
    generate_btn.config(state=tk.DISABLED)
    threading.Thread(target=run_processing, daemon=True).start()

def choose_background():
    global selected_bg
    path = filedialog.askopenfilename(filetypes=[("Media","*.jpg *.png *.mp4")])
    if path:
        selected_bg = path
        bg_label.config(text=os.path.basename(path))

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

text_box = tk.Text(root, width=80, height=12)
text_box.pack(pady=10)
text_box.insert("1.0", "M|Xin chào các bạn|Chào mừng đến với Podcast\nF|Chào anh Nam|Rất vui được gặp anh")

# Progress Bar với %
progress_frame = tk.Frame(root)
progress_frame.pack(pady=10)

progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate")
progress_bar.pack(side=tk.LEFT, padx=5)

percent_label = tk.Label(progress_frame, text="0%", width=20)
percent_label.pack(side=tk.LEFT)

generate_btn = tk.Button(root, text="BẮT ĐẦU RENDER", command=generate, bg="#27ae60", fg="white", font=('Arial', 10, 'bold'), height=2, width=20)
generate_btn.pack(pady=10)

root.mainloop()