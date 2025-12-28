import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import threading
import re

class SrtToMp4FastTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Fast Video Renderer - Progress Bar")
        self.root.geometry("550x450")

        self.audio_path = tk.StringVar()
        self.srt_path = tk.StringVar()
        self.bg_path = tk.StringVar()

        tk.Label(root, text="RENDER VIDEO SIÊU TỐC", font=("Arial", 14, "bold")).pack(pady=10)

        # Input Fields
        self.create_input("Audio (MP3):", self.audio_path)
        self.create_input("Subtitle (SRT):", self.srt_path)
        self.create_input("Background (IMG):", self.bg_path)

        # Progress UI
        tk.Label(root, text="Tiến độ xử lý:").pack(pady=(20, 0))
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=5)
        
        self.status_label = tk.Label(root, text="Chưa bắt đầu", fg="blue")
        self.status_label.pack()

        self.btn_render = tk.Button(root, text="BẮT ĐẦU RENDER", command=self.start_thread, 
                                   bg="#2196F3", fg="white", font=("Arial", 10, "bold"), padx=20, pady=10)
        self.btn_render.pack(pady=20)

    def create_input(self, text, var):
        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=30, pady=5)
        tk.Label(frame, text=text, width=15, anchor="w").pack(side="left")
        tk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(frame, text="Mở", command=lambda: var.set(filedialog.askopenfilename())).pack(side="right")

    def start_thread(self):
        if not all([self.audio_path.get(), self.srt_path.get(), self.bg_path.get()]):
            messagebox.showwarning("Thiếu file", "Vui lòng chọn đầy đủ 3 file đầu vào!")
            return
        
        self.btn_render.config(state="disabled")
        threading.Thread(target=self.run_ffmpeg, daemon=True).start()

    def run_ffmpeg(self):
        audio = self.audio_path.get()
        srt = self.srt_path.get()
        image = self.bg_path.get()
        output = "podcast_optimized.mp4"

        # Chuẩn hóa đường dẫn
        srt_fixed = os.path.abspath(srt).replace("\\", "/").replace(":", "\\:")
        
        # 1. Lấy thời lượng để tính % (Dùng ffprobe)
        try:
            duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio]
            total_duration = float(subprocess.check_output(duration_cmd).strip())
        except:
            total_duration = 1 

        # 2. Lệnh FFmpeg tối ưu: giảm FPS xuống 5 và dùng preset siêu tốc
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1', 
            '-r', '5',                       # Tối ưu: Chỉ 5 khung hình trên giây
            '-i', image,
            '-i', audio,
            '-vf', f"subtitles='{srt_fixed}':force_style='FontSize=22,Alignment=2,MarginV=35'",
            '-c:v', 'libx264', 
            '-preset', 'ultrafast',         # Nén cực nhanh
            '-tune', 'stillimage',          # Tối ưu riêng cho hình nền tĩnh
            '-c:a', 'copy',                 # Tối ưu: Copy nguyên audio gốc, không nén lại (giữ chất lượng 100%)
            '-shortest',
            '-pix_fmt', 'yuv420p',
            output
        ]

        process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, encoding='utf-8')

        for line in process.stdout:
            time_match = re.search(r"time=(\d{2}:\d{2}:\d{2})", line)
            if time_match:
                time_str = time_match.group(1)
                h, m, s = map(int, time_str.split(':'))
                current_time = h * 3600 + m * 60 + s
                percent = (current_time / total_duration) * 100
                self.progress["value"] = percent
                self.status_label.config(text=f"Đang render: {int(percent)}% (Tốc độ sẽ rất nhanh)")
                self.root.update_idletasks()

        process.wait()
        
        if process.returncode == 0:
            self.progress["value"] = 100
            self.status_label.config(text="Hoàn tất!", fg="green")
            messagebox.showinfo("Xong", f"Video đã được tạo thành công!\n{output}")
        else:
            self.status_label.config(text="Lỗi render!", fg="red")
        
        self.btn_render.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = SrtToMp4FastTool(root)
    root.mainloop()