import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import asyncio
import os
import subprocess
import edge_tts
import threading
import re

# ---------- CONFIG ----------
VIDEO_SIZE = "1920x1080"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Đường dẫn font
FONT_LATIN = "C\\:/Windows/Fonts/arial.ttf"
FONT_CHINESE = "C\\:/Users/USER/AppData/Local/Microsoft/Windows/Fonts/NotoSansCJKsc-Regular.otf"

# DANH SÁCH GIỌNG NÓI MỞ RỘNG
LANG_VOICES = {
    "Vietnamese": {
        "Mặc định (Nam Minh & Hoài My)": {
            "male": "vi-VN-NamMinhNeural", 
            "female": "vi-VN-HoaiMyNeural"
        }
    },
    "Chinese": {
        "Yunxi & Xiaoxiao (Phổ thông)": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
        "Yunjian & Xiaoyi (Sâu lắng)": {"male": "zh-CN-YunjianNeural", "female": "zh-CN-XiaoyiNeural"},
        "Yunfeng & Xiaoni (Tươi vui)": {"male": "zh-CN-YunfengNeural", "female": "zh-CN-XiaoniNeural"},
    },
    "Spanish": {
        "Alvaro & Elvira (Tây Ban Nha)": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
        "Arnau & Estrella (Tây Ban Nha)": {"male": "es-ES-ArnauNeural", "female": "es-ES-EstrellaNeural"},
        "Jorge & Dalia (Mexico)": {"male": "es-MX-JorgeNeural", "female": "es-MX-DaliaNeural"},
    }
}

selected_bg = None

# ---------- HELPER FUNCTIONS ----------
def get_seconds(time_str):
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

async def generate_assets(dialogs, lang, voice_pack_name, rate_str):
    speed_map = {
    "100%": "+0%",
    "90%": "-10%",
    "80%": "-20%",
    "70%": "-30%"
    }
    
    rate = speed_map.get(rate_str, "+0Hz")
    
    # Lấy pack giọng đã chọn
    pack = LANG_VOICES[lang][voice_pack_name]
    
    audio_files = []
    srt_content = ""
    timeline = 0.0
    
    for i, d in enumerate(dialogs):
        voice = pack["male"] if d[0] == "M" else pack["female"]
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

def build_video_ffmpeg_with_progress(audio_files, total_dur, lang, show_subtitles, progress_callback):
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

    filter_chain = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];"
        f"[1:a]showwaves=s=800x200:mode=line:colors=white:draw=full[wave];"
        f"[bg][wave]overlay=(W-w)/2:600[v_wave];"
    )

    if show_subtitles:
        filter_chain += f"[v_wave]{sub_style},fps=12[v]"
    else:
        filter_chain += "[v_wave]fps=12[v]"

    out_video = os.path.join(OUTPUT_DIR, f"podcast_{lang}.mp4")
    
    bg_input = ["-f", "lavfi", "-i", "color=c=black:s=1920x1080"]
    if selected_bg:
        if selected_bg.lower().endswith((".mp4", ".mov")):
            bg_input = ["-stream_loop", "-1", "-i", selected_bg]
        else:
            bg_input = ["-loop", "1", "-i", selected_bg]

    cmd = [
        "ffmpeg", "-y",
        *bg_input,
        "-i", full_audio,
        "-filter_complex", filter_chain,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-t", str(total_dur),
        out_video
    ]
    process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
    time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})")

    while True:
        line = process.stdout.readline()
        if not line: break
        match = time_pattern.search(line)
        if match:
            current_seconds = get_seconds(match.group(1))
            percentage = min(int((current_seconds / total_dur) * 100), 100)
            progress_callback(percentage)

    process.wait()

    # Dọn dẹp file
    try:
        for audio in audio_files:
            if os.path.exists(audio): os.remove(audio)
        if os.path.exists(full_audio): os.remove(full_audio)
        if os.path.exists(list_path): os.remove(list_path)
    except: pass

    return out_video

# ---------- GUI FUNCTIONS ----------
def update_voice_options(*args):
    """Cập nhật dropdown giọng nói khi đổi ngôn ngữ"""
    lang = lang_var.get()
    packs = list(LANG_VOICES[lang].keys())
    voice_pack_var.set(packs[0]) # Reset về cái đầu tiên
    menu = voice_menu['menu']
    menu.delete(0, 'end')
    for pack in packs:
        menu.add_command(label=pack, command=lambda p=pack: voice_pack_var.set(p))

def update_progress(val):
    progress_bar['value'] = val
    percent_label.config(text=f"{val}%")
    root.update_idletasks()

def run_processing():
    lang = lang_var.get()
    voice_pack = voice_pack_var.get()
    text = text_box.get("1.0", tk.END).strip()
    dialogs = parse_input(text, lang)
    
    if not dialogs:
        generate_btn.config(state=tk.NORMAL)
        return messagebox.showerror("Lỗi", "Vui lòng nhập đúng định dạng!")

    try:
        update_progress(0)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        percent_label.config(text="Đang tạo giọng nói...")
        audio_files, total_dur = loop.run_until_complete(generate_assets(dialogs, lang, voice_pack, speed_var.get()))
        
        out = build_video_ffmpeg_with_progress(
            audio_files,
            total_dur,
            lang,
            show_sub_var.get(),
            update_progress
        )
        
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
root.geometry("700x650")

# Frame cấu hình
cfg_frame = tk.LabelFrame(root, text=" Cấu hình Voice & Ngôn ngữ ", padx=10, pady=10)
cfg_frame.pack(pady=10, fill="x", padx=20)

tk.Label(cfg_frame, text="Ngôn ngữ:").grid(row=0, column=0, sticky="w")
lang_var = tk.StringVar(value="Vietnamese")
lang_var.trace('w', update_voice_options)
tk.OptionMenu(cfg_frame, lang_var, *LANG_VOICES.keys()).grid(row=0, column=1, padx=10, sticky="w")

tk.Label(cfg_frame, text="Bộ giọng (Pack):").grid(row=1, column=0, sticky="w")
voice_pack_var = tk.StringVar()
voice_menu = tk.OptionMenu(cfg_frame, voice_pack_var, "")
voice_menu.grid(row=1, column=1, padx=10, sticky="w")

tk.Label(cfg_frame, text="Tốc độ:").grid(row=0, column=2, padx=20, sticky="w")
speed_var = tk.StringVar(value="100%")
tk.OptionMenu(cfg_frame, speed_var, "100%", "90%", "80%", "70%").grid(row=0, column=3, sticky="w")

show_sub_var = tk.BooleanVar(value=True)

tk.Checkbutton(
    cfg_frame,
    text="Hiển thị Subtitle",
    variable=show_sub_var
).grid(row=1, column=2, columnspan=2, sticky="w")

# Cập nhật giọng nói lần đầu
update_voice_options()

# Frame Nền
bg_frame = tk.Frame(root)
bg_frame.pack(pady=5)
tk.Button(bg_frame, text="Chọn Hình Nền / Video Nền", command=choose_background).pack(side=tk.LEFT)
bg_label = tk.Label(bg_frame, text="Chưa chọn nền", fg="blue", padx=10)
bg_label.pack(side=tk.LEFT)

# Text Box
text_box = tk.Text(root, width=80, height=12, font=("Consolas", 10))
text_box.pack(pady=10, padx=20)
text_box.insert("1.0", "M|Xin chào các bạn|Chào mừng đến với Podcast\nF|Chào anh Nam|Rất vui được gặp anh")

# Progress Bar
progress_frame = tk.Frame(root)
progress_frame.pack(pady=10)
progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate")
progress_bar.pack(side=tk.LEFT, padx=5)
percent_label = tk.Label(progress_frame, text="Sẵn sàng", width=25)
percent_label.pack(side=tk.LEFT)

# Nút Render
generate_btn = tk.Button(root, text="BẮT ĐẦU RENDER", command=generate, bg="#27ae60", fg="white", font=('Arial', 11, 'bold'), height=2, width=30)
generate_btn.pack(pady=15)

root.mainloop()