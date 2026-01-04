import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import whisper
import subprocess
import os
import threading
import re

class PodcastVideoAllInOne:
    def __init__(self, root):
        self.root = root
        self.root.title("SpanishCorner - Podcast Video Creator Pro")
        self.root.geometry("650x750") # Tăng chiều cao để chứa thanh trượt logo

        self.audio_path = tk.StringVar()
        self.srt_path = tk.StringVar()
        self.bg_path = tk.StringVar()
        self.logo_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.has_sub = tk.BooleanVar(value=True)
        self.has_logo = tk.BooleanVar(value=False)
        # --- Biến lưu tỉ lệ Logo (Mặc định 15%) ---
        self.logo_size_percent = tk.IntVar(value=15)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.setup_sub_tab()
        self.setup_video_tab()

    def setup_sub_tab(self):
        tab1 = ttk.Frame(self.notebook)
        self.notebook.add(tab1, text=" Bước 1: Trích xuất Subtitle ")

        tk.Label(tab1, text="CHUYỂN AUDIO SANG FILE SRT", font=("Arial", 12, "bold")).pack(pady=15)
        self.create_input_row(tab1, "Audio Input:", self.audio_path, self.browse_audio)
        self.create_input_row(tab1, "Thư mục đầu ra:", self.output_dir, self.browse_directory)

        tk.Label(tab1, text="Độ chính xác AI (Model):").pack(pady=(10, 0))
        self.model_var = tk.StringVar(value="base")
        ttk.Combobox(tab1, textvariable=self.model_var, values=["tiny", "base", "small", "medium"]).pack(pady=5)

        tk.Label(tab1, text="Tiến độ trích xuất:").pack(pady=(15, 0))
        self.sub_progress = ttk.Progressbar(tab1, orient="horizontal", length=400, mode="determinate")
        self.sub_progress.pack(pady=5)

        self.btn_sub = tk.Button(tab1, text="TẠO FILE PHỤ ĐỀ (.SRT)", command=self.start_sub_thread, 
                                bg="#E91E63", fg="white", font=("Arial", 10, "bold"), padx=20, pady=10)
        self.btn_sub.pack(pady=20)
        self.sub_status = tk.Label(tab1, text="Sẵn sàng", fg="gray")
        self.sub_status.pack()

    def setup_video_tab(self):
        tab2 = ttk.Frame(self.notebook)
        self.notebook.add(tab2, text=" Bước 2: Render Video ")

        tk.Label(tab2, text="GHÉP PHỤ ĐỀ VÀO VIDEO TĨNH", font=("Arial", 12, "bold")).pack(pady=15)
        self.create_input_row(tab2, "Audio (MP3):", self.audio_path, self.browse_audio)
        self.create_input_row(tab2, "Hình nền (IMG):", self.bg_path, lambda: self.bg_path.set(filedialog.askopenfilename()))
        
        # --- Logo Setup ---
        logo_section = tk.LabelFrame(tab2, text=" Cấu hình Logo ", padx=10, pady=10)
        logo_section.pack(fill="x", padx=30, pady=5)

        check_row = tk.Frame(logo_section)
        check_row.pack(fill="x")
        tk.Checkbutton(check_row, text="Chèn Logo vào video", variable=self.has_logo).pack(side="left")
        
        self.create_input_row(logo_section, "Logo Path:", self.logo_path, lambda: self.logo_path.set(filedialog.askopenfilename()))

        size_row = tk.Frame(logo_section)
        size_row.pack(fill="x", pady=5)
        tk.Label(size_row, text="Kích thước Logo (%):", width=20, anchor="w").pack(side="left")
        tk.Scale(size_row, from_=10, to=100, orient="horizontal", variable=self.logo_size_percent).pack(side="left", fill="x", expand=True)

        # --- Subtitle Toggle ---
        sub_frame = tk.Frame(tab2)
        sub_frame.pack(fill="x", padx=30, pady=5)
        tk.Checkbutton(sub_frame, text="Chèn phụ đề vào video", variable=self.has_sub).pack(side="left")
        
        self.srt_row = tk.Frame(tab2)
        self.srt_row.pack(fill="x", padx=30, pady=5)
        tk.Label(self.srt_row, text="Subtitle (SRT):", width=15, anchor="w").pack(side="left")
        tk.Entry(self.srt_row, textvariable=self.srt_path).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(self.srt_row, text="Duyệt", command=lambda: self.srt_path.set(filedialog.askopenfilename())).pack(side="right")

        tk.Label(tab2, text="Tiến độ Render Video:").pack(pady=(10, 0))
        self.video_progress = ttk.Progressbar(tab2, orient="horizontal", length=400, mode="determinate")
        self.video_progress.pack(pady=5)

        self.btn_render = tk.Button(tab2, text="BẮT ĐẦU RENDER VIDEO", command=self.start_render_thread, 
                                   bg="#2196F3", fg="white", font=("Arial", 10, "bold"), padx=20, pady=10)
        self.btn_render.pack(pady=20)
        self.video_status = tk.Label(tab2, text="Đang chờ dữ liệu...", fg="blue")
        self.video_status.pack()

    def create_input_row(self, parent, text, var, cmd):
        frame = tk.Frame(parent)
        frame.pack(fill="x", padx=30, pady=5)
        tk.Label(frame, text=text, width=15, anchor="w").pack(side="left")
        tk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(frame, text="Duyệt", command=cmd).pack(side="right")

    def browse_audio(self):
        f = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
        if f:
            self.audio_path.set(f)
            if not self.output_dir.get(): self.output_dir.set(os.path.dirname(f))

    def browse_directory(self):
        d = filedialog.askdirectory()
        if d: self.output_dir.set(d)

    def format_time(self, seconds):
        td = float(seconds)
        h, m, s = int(td // 3600), int((td % 3600) // 60), int(td % 60)
        ms = int((td - int(td)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def start_sub_thread(self):
        if not self.audio_path.get() or not self.output_dir.get():
            return messagebox.showwarning("Lỗi", "Vui lòng chọn Audio và Thư mục lưu!")
        self.btn_sub.config(state="disabled")
        self.sub_progress["value"] = 0
        threading.Thread(target=self.process_sub, daemon=True).start()

    def process_sub(self):
        try:
            self.sub_status.config(text="Đang tải Model AI...", fg="blue")
            model = whisper.load_model(self.model_var.get())
            
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', self.audio_path.get()]
            total_duration = float(subprocess.check_output(dur_cmd).strip())

            self.sub_status.config(text="AI đang xử lý âm thanh...", fg="blue")
            result = model.transcribe(self.audio_path.get(), fp16=False)
            
            base_name = os.path.splitext(os.path.basename(self.audio_path.get()))[0]
            srt_full_path = os.path.join(self.output_dir.get(), base_name + ".srt")
            
            with open(srt_full_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(result['segments'], start=1):
                    f.write(f"{i}\n{self.format_time(seg['start'])} --> {self.format_time(seg['end'])}\n{seg['text'].strip()}\n\n")
                    prog = (seg['end'] / total_duration) * 100
                    self.sub_progress["value"] = prog
                    self.root.update_idletasks()

            self.sub_progress["value"] = 100
            self.srt_path.set(srt_full_path)
            self.sub_status.config(text="Đã hoàn thành file SRT!", fg="green")
            messagebox.showinfo("Thành công", f"Đã lưu phụ đề tại:\n{srt_full_path}")
            
        except Exception as e:
            messagebox.showerror("Lỗi AI", str(e))
        finally:
            self.btn_sub.config(state="normal")

    def start_render_thread(self):
        if self.has_sub.get() and not self.srt_path.get():
             return messagebox.showwarning("Lỗi", "Vui lòng chọn hoặc tạo file phụ đề trước!")
        if self.has_logo.get() and not self.logo_path.get():
             return messagebox.showwarning("Lỗi", "Vui lòng chọn Logo!")
        if not self.audio_path.get() or not self.bg_path.get():
            return messagebox.showwarning("Lỗi", "Thiếu Audio hoặc Hình nền!")

        self.btn_render.config(state="disabled")
        self.video_progress["value"] = 0
        threading.Thread(target=self.run_ffmpeg, daemon=True).start()

    def run_ffmpeg(self):
        base_name = os.path.splitext(os.path.basename(self.audio_path.get()))[0]
        out_file = os.path.join(self.output_dir.get(), base_name + "_final.mp4")
        
        try:
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', self.audio_path.get()]
            total_dur = float(subprocess.check_output(dur_cmd).strip())
            
            # --- BUILD FFMPEG COMMAND ---
            cmd = ['ffmpeg', '-y', '-loop', '1', '-i', self.bg_path.get(), '-i', self.audio_path.get()]
            
            # 1. Background & Audio Wave
            filter_str = "[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p[bg]; "
            filter_str += "[1:a]showfreqs=s=320x200:mode=bar:colors=white:fscale=log:ascale=sqrt[wave]; "
            
            # 2. Add Wave onto Background
            filter_str += "[bg][wave]overlay=480:260:shortest=1[v_intermediate]"
            last_v_tag = "[v_intermediate]"

            # 3. Add Logo if enabled
            if self.has_logo.get():
                cmd.extend(['-i', self.logo_path.get()])
                logo_idx = 2
                # Tính toán tỉ lệ thập phân (ví dụ: 15% -> 0.15)
                scale_val = self.logo_size_percent.get() / 100.0
                # Áp dụng scale tỉ lệ với iw (input width của logo)
                filter_str += f"; [{logo_idx}:v]scale=iw*{scale_val}:-1[logo]; {last_v_tag}[logo]overlay=main_w-overlay_w-20:20[v_with_logo]"
                last_v_tag = "[v_with_logo]"

            # 4. Add Subtitles if enabled
            if self.has_sub.get():
                srt_fixed = os.path.abspath(self.srt_path.get()).replace("\\", "/").replace(":", "\\:")
                filter_str += f"; {last_v_tag}subtitles='{srt_fixed}':force_style='FontSize=24,Alignment=2,MarginV=30'[v]"
                last_v_tag = "[v]"
            else:
                filter_str += f"; {last_v_tag}copy[v]"

            cmd.extend([
                '-filter_complex', filter_str,
                '-map', '[v]', 
                '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'ultrafast', 
                '-tune', 'stillimage', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-shortest', out_file
            ])

            process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
            
            for line in process.stdout:
                time_match = re.search(r"time=(\d{2}:\d{2}:\d{2})", line)
                if time_match:
                    h, m, s = map(int, time_match.group(1).split(':'))
                    percent = ((h * 3600 + m * 60 + s) / total_dur) * 100
                    self.video_progress["value"] = min(percent, 100)
                    self.video_status.config(text=f"Rendering: {int(self.video_progress['value'])}%")
                    self.root.update_idletasks()
            
            process.wait()
            self.video_progress["value"] = 100
            messagebox.showinfo("Xong!", f"Video đã sẵn sàng!\n{out_file}")
            os.startfile(self.output_dir.get())
            
        except Exception as e:
            messagebox.showerror("Lỗi Render", f"Chi tiết: {str(e)}")
        finally:
            self.btn_render.config(state="normal")
            self.video_status.config(text="Sẵn sàng")

if __name__ == "__main__":
    root = tk.Tk()
    app = PodcastVideoAllInOne(root)
    root.mainloop()