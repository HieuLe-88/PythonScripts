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

# Đường dẫn font (Hãy đảm bảo các font này tồn tại trên máy bạn)
FONT_LATIN = "C\\:/Windows/Fonts/arial.ttf"
FONT_CHINESE = "C\\:/Users/USER/AppData/Local/Microsoft/Windows/Fonts/NotoSansCJKsc-Regular.otf"

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
        "Tomas & Elena (Argentina)": {"male": "es-AR-TomasNeural", "female": "es-AR-ElenaNeural"},
        "Jorge & Dalia (Mexico)": {"male": "es-MX-JorgeNeural", "female": "es-MX-DaliaNeural"},
        "Lorenzo & Paloma (Colombia-US)": {"male": "es-CL-LorenzoNeural", "female": "es-US-PalomaNeural"},
    }
}

WAVE_MODES = {
    "Dạng vạch (Line)": "showwaves=s=800x200:mode=line:colors=white:draw=full",
    "Dạng cột đặc (P2P)": "showwaves=s=800x200:mode=p2p:colors=white:draw=full",
    "Dạng đối xứng (Center line)": "showwaves=s=800x200:mode=cline:colors=white:draw=full",
    "Dạng điểm (Point)": "showwaves=s=800x200:mode=point:colors=white",
    "Dạng sóng mảnh": "showwaves=s=800x200:mode=line:colors=white:draw=none",
    "Dạng sóng mờ": "showwaves=s=800x200:mode=line:colors=white@0.4:draw=full",
    "Dạng sóng dày": "showwaves=s=800x200:mode=line:colors=white,white:draw=full",
    "Dạng thanh âm lượng (Bars)": "showvolume=f=0.5:w=800:h=200:t=0:b=4:v=0:c=white",
    "Dạng thanh âm lượng mịn": "showvolume=f=0.1:w=800:h=200:t=0:b=2:v=0:c=white",
}

selected_bg = None
selected_logo = None

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
    speed_map = {"100%": "+0%", "90%": "-10%", "80%": "-20%", "70%": "-30%"}
    rate = speed_map.get(rate_str, "+0%")
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
            stdout=subprocess.PIPE, text=True
        )
        dur = float(result.stdout)
        start_t, end_t = format_srt_time(timeline), format_srt_time(timeline + dur)
        
        main_text = d[1]
        f_size = 17 if len(main_text) <= 40 else 14
        sub_text = f"{{\\fs{f_size}}}{d[1]}\\N{{\\fs{f_size-2}}}{d[2]}"
        if lang == "Chinese": sub_text += f"\\N{{\\fs{f_size-4}}}{d[3]}"
            
        srt_content += f"{i+1}\n{start_t} --> {end_t}\n{sub_text}\n\n"
        audio_files.append(audio_path)
        timeline += dur
        
    with open(os.path.join(OUTPUT_DIR, "subs.srt"), "w", encoding="utf-8") as f:
        f.write(srt_content)
    return audio_files, timeline

def build_video_ffmpeg_with_progress(audio_files, total_dur, lang, show_subtitles, wave_mode_key, progress_callback):
    list_path = os.path.join(OUTPUT_DIR, "audio_list.txt")
    with open(list_path, "w") as f:
        for audio in audio_files: f.write(f"file '{os.path.abspath(audio)}'\n")
            
    full_audio = os.path.join(OUTPUT_DIR, "full_audio.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", full_audio], check=True)

    srt_path = os.path.join(OUTPUT_DIR, "subs.srt").replace("\\", "/")
    current_font = FONT_CHINESE if lang == "Chinese" else FONT_LATIN
    sub_style = (f"subtitles='{srt_path}':force_style='Fontname={current_font},FontSize=16,"
                 f"PrimaryColour=&HFFFFFF,BorderStyle=3,OutlineColour=&H99333333,Alignment=2,MarginV=40'")

    wave_filter = WAVE_MODES[wave_mode_key]

    # --- XÂY DỰNG CHUỖI FILTER PHỨC TẠP ---
    # Đầu vào 0: Video nền
    # Đầu vào 1: Audio (để tạo sóng)
    # Đầu vào 2 (nếu có): Logo
    
    # 1. Xử lý nền và sóng âm
    filter_chain = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[bg];"
        f"[1:a]{wave_filter}[wave];"
        f"[bg][wave]overlay=(W-w)/2:600[v_base];"
    )

    logo_input = []
    current_v = "[v_base]"

    # 2. Xử lý chèn Logo nếu được chọn
    # iw*0.25 = 25% chiều rộng ảnh gốc. W-w-50:50 = cách lề phải 50px, lề trên 50px
    if selected_logo:
        logo_input = ["-i", selected_logo]
        filter_chain += f"[2:v]scale=iw*0.25:-1[logo_scaled];"
        filter_chain += f"{current_v}[logo_scaled]overlay=W-w-50:50[v_logo];"
        current_v = "[v_logo]"

    # 3. Xử lý phụ đề
    if show_subtitles: 
        filter_chain += f"{current_v}{sub_style},fps=5[v]"
    else: 
        filter_chain += f"{current_v}fps=5[v]"

    # Cấu hình Input cho FFmpeg
    bg_input = ["-f", "lavfi", "-i", "color=c=black:s=1920x1080"]
    if selected_bg:
        if selected_bg.lower().endswith((".mp4", ".mov")): bg_input = ["-stream_loop", "-1", "-i", selected_bg]
        else: bg_input = ["-loop", "1", "-i", selected_bg]

    cmd = ["ffmpeg", "-y", *bg_input, "-i", full_audio, *logo_input, 
           "-filter_complex", filter_chain,
           "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast",
           "-t", str(total_dur), os.path.join(OUTPUT_DIR, f"podcast_{lang}.mp4")]
    
    process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
    time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})")

    while True:
        line = process.stdout.readline()
        if not line: break
        match = time_pattern.search(line)
        if match:
            current_seconds = get_seconds(match.group(1))
            progress_callback(min(int((current_seconds / total_dur) * 100), 100))
    process.wait()

    # Dọn dẹp
    try:
        for audio in audio_files:
            if os.path.exists(audio): os.remove(audio)
        if os.path.exists(full_audio): os.remove(full_audio)
        if os.path.exists(list_path): os.remove(list_path)
    except: pass

    return cmd[-1]

# ---------- GUI FUNCTIONS ----------
def update_voice_options(*args):
    lang = lang_var.get()
    packs = list(LANG_VOICES[lang].keys())
    voice_pack_var.set(packs[0])
    menu = voice_menu['menu']
    menu.delete(0, 'end')
    for pack in packs:
        menu.add_command(label=pack, command=lambda p=pack: voice_pack_var.set(p))

def run_processing():
    lang, voice_pack = lang_var.get(), voice_pack_var.get()
    text = text_box.get("1.0", tk.END).strip()
    dialogs = parse_input(text, lang)
    if not dialogs: return messagebox.showerror("Lỗi", "Định dạng sai!")

    try:
        percent_label.config(text="Đang tạo giọng nói...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_files, total_dur = loop.run_until_complete(generate_assets(dialogs, lang, voice_pack, speed_var.get()))
        
        out = build_video_ffmpeg_with_progress(
            audio_files, total_dur, lang, show_sub_var.get(), wave_var.get(),
            lambda v: (progress_bar.configure(value=v), percent_label.config(text=f"Đang Render: {v}%"), root.update_idletasks())
        )
        messagebox.showinfo("Thành công", f"Video lưu tại:\n{out}")
    except Exception as e: messagebox.showerror("Lỗi", str(e))
    finally:
        generate_btn.config(state=tk.NORMAL)
        percent_label.config(text="Sẵn sàng")

def generate():
    generate_btn.config(state=tk.DISABLED)
    threading.Thread(target=run_processing, daemon=True).start()

def choose_background():
    global selected_bg
    path = filedialog.askopenfilename()
    if path:
        selected_bg = path
        bg_label.config(text=os.path.basename(path))

def choose_logo():
    global selected_logo
    path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
    if path:
        selected_logo = path
        logo_label.config(text=os.path.basename(path))

# ---------- GUI LAYOUT ----------
root = tk.Tk()
root.title("AI Podcast Generator - Logo & Waveform")
root.geometry("750x750")

cfg_frame = tk.LabelFrame(root, text=" Cấu hình ", padx=10, pady=10)
cfg_frame.pack(pady=10, fill="x", padx=20)

tk.Label(cfg_frame, text="Ngôn ngữ:").grid(row=0, column=0, sticky="w")
lang_var = tk.StringVar(value="Vietnamese")
lang_var.trace('w', update_voice_options)
tk.OptionMenu(cfg_frame, lang_var, *LANG_VOICES.keys()).grid(row=0, column=1, sticky="w")

tk.Label(cfg_frame, text="Giọng:").grid(row=0, column=2, padx=10, sticky="w")
voice_pack_var = tk.StringVar()
voice_menu = tk.OptionMenu(cfg_frame, voice_pack_var, "")
voice_menu.grid(row=0, column=3, sticky="w")

tk.Label(cfg_frame, text="Dạng Waveform:").grid(row=1, column=0, pady=5, sticky="w")
wave_var = tk.StringVar(value="Dạng vạch (Line)")
tk.OptionMenu(cfg_frame, wave_var, *WAVE_MODES.keys()).grid(row=1, column=1, sticky="w")

tk.Label(cfg_frame, text="Tốc độ:").grid(row=1, column=2, padx=10, sticky="w")
speed_var = tk.StringVar(value="100%")
tk.OptionMenu(cfg_frame, speed_var, "100%", "90%", "80%", "70%").grid(row=1, column=3, sticky="w")

show_sub_var = tk.BooleanVar(value=True)
tk.Checkbutton(cfg_frame, text="Hiện Subtitle", variable=show_sub_var).grid(row=2, column=0, sticky="w")

update_voice_options()

# Frame chọn File Nền & Logo
file_frame = tk.Frame(root)
file_frame.pack(pady=5)

# Background
tk.Button(file_frame, text="Chọn Nền (Ảnh/Video)", command=choose_background).grid(row=0, column=0, padx=5)
bg_label = tk.Label(file_frame, text="Chưa chọn nền", fg="blue", width=25, anchor="w")
bg_label.grid(row=0, column=1)

# Logo
tk.Button(file_frame, text="Chọn Logo (25% size)", command=choose_logo).grid(row=1, column=0, padx=5, pady=5)
logo_label = tk.Label(file_frame, text="Chưa chọn logo", fg="green", width=25, anchor="w")
logo_label.grid(row=1, column=1)

text_box = tk.Text(root, width=85, height=12, font=("Consolas", 10))
text_box.pack(pady=10, padx=20)
text_box.insert("1.0", "M|Chào bạn|Hôm nay thế nào?\nF|Tôi khỏe|Cảm ơn bạn.")

progress_bar = ttk.Progressbar(root, orient="horizontal", length=500, mode="determinate")
progress_bar.pack(pady=5)
percent_label = tk.Label(root, text="Sẵn sàng")
percent_label.pack()

generate_btn = tk.Button(root, text="BẮT ĐẦU RENDER", command=generate, bg="#27ae60", fg="white", font=('Arial', 12, 'bold'), height=2, width=30)
generate_btn.pack(pady=15)

root.mainloop()