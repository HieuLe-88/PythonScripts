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
        self.root.geometry("650x580")

        self.audio_path = tk.StringVar()
        self.srt_path = tk.StringVar()
        self.bg_path = tk.StringVar()
        self.output_dir = tk.StringVar()

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
        self.create_input_row(tab2, "Subtitle (SRT):", self.srt_path, lambda: self.srt_path.set(filedialog.askopenfilename()))
        self.create_input_row(tab2, "Hình nền (IMG):", self.bg_path, lambda: self.bg_path.set(filedialog.askopenfilename()))

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

    # --- LOGIC TAB 1: CHỈ TẠO SRT ---
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
            
            # Lấy tổng thời gian để tính %
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', self.audio_path.get()]
            total_duration = float(subprocess.check_output(dur_cmd).strip())

            self.sub_status.config(text="AI đang xử lý âm thanh...", fg="blue")
            result = model.transcribe(self.audio_path.get(), fp16=False)
            
            base_name = os.path.splitext(os.path.basename(self.audio_path.get()))[0]
            srt_full_path = os.path.join(self.output_dir.get(), base_name + ".srt")
            
            with open(srt_full_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(result['segments'], start=1):
                    f.write(f"{i}\n{self.format_time(seg['start'])} --> {self.format_time(seg['end'])}\n{seg['text'].strip()}\n\n")
                    # Cập nhật progress bar
                    prog = (seg['end'] / total_duration) * 100
                    self.sub_progress["value"] = prog
                    self.root.update_idletasks()

            self.sub_progress["value"] = 100
            self.srt_path.set(srt_full_path) # Tự động điền sang tab video
            self.sub_status.config(text="Đã hoàn thành file SRT!", fg="green")
            messagebox.showinfo("Thành công", f"Đã lưu phụ đề tại:\n{srt_full_path}")
            os.startfile(self.output_dir.get()) 
            
        except Exception as e:
            messagebox.showerror("Lỗi AI", str(e))
        finally:
            self.btn_sub.config(state="normal")

    # --- LOGIC TAB 2: RENDER VIDEO ---
    def start_render_thread(self):
        if not all([self.audio_path.get(), self.srt_path.get(), self.bg_path.get()]):
            return messagebox.showwarning("Lỗi", "Thiếu dữ liệu để render!")
        self.btn_render.config(state="disabled")
        self.video_progress["value"] = 0
        threading.Thread(target=self.run_ffmpeg, daemon=True).start()

    def run_ffmpeg(self):
        base_name = os.path.splitext(os.path.basename(self.audio_path.get()))[0]
        out_file = os.path.join(self.output_dir.get(), base_name + "_video.mp4")
        
        # Xử lý đường dẫn SRT cho FFmpeg (tránh lỗi font/path trên Windows)
        srt_fixed = os.path.abspath(self.srt_path.get()).replace("\\", "/").replace(":", "\\:")
        
        try:
            # 1. Lấy tổng thời lượng
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', self.audio_path.get()]
            total_dur = float(subprocess.check_output(dur_cmd).strip())
            
            # 2. Lệnh FFmpeg với Waveform
            # Giải thích filter_complex:
            # - [1:a] tạo sóng kích thước 1280x250, màu trắng, dạng line.
            # - [0:v] lấy hình nền, scale về chuẩn HD 1280x720.
            # - overlay đặt sóng tại tọa độ x=0, y=400 (nửa dưới video).
            # - subtitles vẽ chữ lên trên cùng.
            
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', self.bg_path.get(), # Input 0: Hình nền
                '-i', self.audio_path.get(),           # Input 1: Audio
                '-filter_complex', 
                "[1:a]showwaves=s=1280x250:mode=line:colors=white:rate=25[wave]; " +
                "[0:v]scale=1280:720,format=yuv420p[bg]; " +
                f"[bg][wave]overlay=0:400:shortest=1,subtitles='{srt_fixed}':force_style='FontSize=24,Alignment=2,MarginV=30'[v]",
                '-map', '[v]', 
                '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'ultrafast', 
                '-tune', 'stillimage', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-shortest', out_file
            ]

            process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
            
            for line in process.stdout:
                # Tìm kiếm pattern 'time=00:00:05.12' để cập nhật progress
                time_match = re.search(r"time=(\d{2}:\d{2}:\d{2})", line)
                if time_match:
                    h, m, s = map(int, time_match.group(1).split(':'))
                    percent = ((h * 3600 + m * 60 + s) / total_dur) * 100
                    if percent > 100: percent = 100
                    
                    self.video_progress["value"] = percent
                    self.video_status.config(text=f"Đang render (có sóng âm): {int(percent)}%")
                    self.root.update_idletasks()
            
            process.wait()
            self.video_progress["value"] = 100
            messagebox.showinfo("Xong!", f"Video có waveform đã sẵn sàng!\n{out_file}")
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