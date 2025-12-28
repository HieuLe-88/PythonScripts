import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import whisper
import subprocess
import os
import threading
import re
import shutil

class PodcastVideoAllInOne:
    def __init__(self, root):
        self.root = root
        self.root.title("SpanishCorner - Podcast Video Creator Pro")
        self.root.geometry("650x580")

        # Khởi tạo các biến
        self.audio_path = tk.StringVar()
        self.srt_path = tk.StringVar()
        self.bg_path = tk.StringVar()
        self.output_dir = tk.StringVar()

        # Notebook UI
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.setup_sub_tab()
        self.setup_video_tab()

    def setup_sub_tab(self):
        """Bước 1: Tạo file phụ đề"""
        tab1 = ttk.Frame(self.notebook)
        self.notebook.add(tab1, text=" Bước 1: Trích xuất Subtitle ")

        tk.Label(tab1, text="CHUYỂN AUDIO SANG SRT & TXT", font=("Arial", 12, "bold")).pack(pady=15)
        self.create_input_row(tab1, "Audio Input:", self.audio_path, self.browse_audio)
        self.create_input_row(tab1, "Thư mục đầu ra:", self.output_dir, self.browse_directory)

        tk.Label(tab1, text="Độ chính xác AI (Model):").pack(pady=(10, 0))
        self.model_var = tk.StringVar(value="base")
        ttk.Combobox(tab1, textvariable=self.model_var, values=["tiny", "base", "small", "medium"]).pack(pady=5)

        self.btn_sub = tk.Button(tab1, text="1. TẠO FILE SUBTITLE", command=self.start_sub_thread, 
                                bg="#E91E63", fg="white", font=("Arial", 10, "bold"), padx=20, pady=10)
        self.btn_sub.pack(pady=20)
        self.sub_status = tk.Label(tab1, text="Sẵn sàng", fg="gray")
        self.sub_status.pack()

    def setup_video_tab(self):
        """Bước 2: Tạo Video"""
        tab2 = ttk.Frame(self.notebook)
        self.notebook.add(tab2, text=" Bước 2: Render Video ")

        tk.Label(tab2, text="GHÉP PHỤ ĐỀ VÀO VIDEO TĨNH", font=("Arial", 12, "bold")).pack(pady=15)
        self.create_input_row(tab2, "Audio (MP3):", self.audio_path, self.browse_audio)
        self.create_input_row(tab2, "Subtitle (SRT):", self.srt_path, lambda: self.srt_path.set(filedialog.askopenfilename()))
        self.create_input_row(tab2, "Hình nền (IMG):", self.bg_path, lambda: self.bg_path.set(filedialog.askopenfilename()))

        tk.Label(tab2, text="Tiến độ Render:").pack(pady=(10, 0))
        self.progress = ttk.Progressbar(tab2, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=5)

        self.btn_render = tk.Button(tab2, text="2. BẮT ĐẦU RENDER VIDEO", command=self.start_render_thread, 
                                   bg="#2196F3", fg="white", font=("Arial", 10, "bold"), padx=20, pady=10)
        self.btn_render.pack(pady=20)
        self.video_status = tk.Label(tab2, text="Đang chờ dữ liệu...", fg="blue")
        self.video_status.pack()

    # --- HÀM GIAO DIỆN ---
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

    # --- LOGIC XỬ LÝ ---
    def start_sub_thread(self):
        if not self.audio_path.get() or not self.output_dir.get():
            return messagebox.showwarning("Lỗi", "Vui lòng chọn Audio và Thư mục lưu!")
        self.btn_sub.config(state="disabled")
        threading.Thread(target=self.process_sub, daemon=True).start()

    def process_sub(self):
        try:
            self.sub_status.config(text="AI đang lắng nghe và tạo sub...", fg="blue")
            model = whisper.load_model(self.model_var.get())
            result = model.transcribe(self.audio_path.get(), fp16=False)
            
            base_name = os.path.splitext(os.path.basename(self.audio_path.get()))[0]
            srt_full_path = os.path.join(self.output_dir.get(), base_name + ".srt")
            txt_full_path = os.path.join(self.output_dir.get(), base_name + ".txt")
            
            # Xuất file SRT
            with open(srt_full_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(result['segments'], start=1):
                    start = self.format_time(seg['start'])
                    end = self.format_time(seg['end'])
                    f.write(f"{i}\n{start} --> {end}\n{seg['text'].strip()}\n\n")
            
            # Xuất file TXT
            with open(txt_full_path, "w", encoding="utf-8") as f:
                f.write(result['text'].strip())
            
            self.srt_path.set(srt_full_path) # Chuyển link sang Tab 2
            self.sub_status.config(text=f"Đã xong! File SRT và TXT nằm ở thư mục Output.", fg="green")
            messagebox.showinfo("Thành công", f"Đã trích xuất xong phụ đề vào thư mục đầu ra!")
        except Exception as e:
            messagebox.showerror("Lỗi AI", str(e))
        finally:
            self.btn_sub.config(state="normal")

    def format_time(self, seconds):
        td = float(seconds)
        h, m, s = int(td // 3600), int((td % 3600) // 60), int(td % 60)
        ms = int((td - int(td)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def start_render_thread(self):
        if not all([self.audio_path.get(), self.srt_path.get(), self.bg_path.get(), self.output_dir.get()]):
            return messagebox.showwarning("Lỗi", "Vui lòng điền đủ thông tin file SRT, Audio và Ảnh!")
        self.btn_render.config(state="disabled")
        threading.Thread(target=self.run_ffmpeg, daemon=True).start()

    def run_ffmpeg(self):
        base_name = os.path.splitext(os.path.basename(self.audio_path.get()))[0]
        out_file = os.path.join(self.output_dir.get(), base_name + "_video.mp4")
        srt_fixed = os.path.abspath(self.srt_path.get()).replace("\\", "/").replace(":", "\\:")
        
        try:
            # Lấy thời lượng
            dur_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', self.audio_path.get()]
            total_dur = float(subprocess.check_output(dur_cmd).strip())
            
            cmd = [
                'ffmpeg', '-y', '-loop', '1', '-r', '5', '-i', self.bg_path.get(),
                '-i', self.audio_path.get(),
                '-vf', f"subtitles='{srt_fixed}':force_style='FontSize=22,Alignment=2,MarginV=35'",
                '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage',
                '-c:a', 'copy', '-shortest', '-pix_fmt', 'yuv420p', out_file
            ]

            process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf-8')
            for line in process.stdout:
                time_match = re.search(r"time=(\d{2}:\d{2}:\d{2})", line)
                if time_match:
                    h, m, s = map(int, time_match.group(1).split(':'))
                    current_s = h * 3600 + m * 60 + s
                    percent = (current_s / total_dur) * 100
                    self.progress["value"] = percent
                    self.video_status.config(text=f"Đang ghép video: {int(percent)}%")
                    self.root.update_idletasks()
            
            process.wait()
            self.video_status.config(text="Render hoàn tất!", fg="green")
            messagebox.showinfo("Hoàn tất", f"Thư mục đầu ra hiện có:\n1. Video (.mp4)\n2. Phụ đề (.srt)\n3. Văn bản (.txt)")
            
        except Exception as e:
            messagebox.showerror("Lỗi Render", str(e))
        finally:
            self.btn_render.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = PodcastVideoAllInOne(root)
    root.mainloop()