import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import whisper
import threading
import os

class AudioToSubTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio to Subtitle Exporter")
        self.root.geometry("500x300")

        self.audio_path = tk.StringVar()
        
        # Giao diện
        tk.Label(root, text="CHUYỂN AUDIO SANG FILE PHỤ ĐỀ", font=("Arial", 12, "bold")).pack(pady=15)

        # Khung chọn file
        frame = tk.Frame(root)
        frame.pack(fill="x", padx=30, pady=10)
        tk.Entry(frame, textvariable=self.audio_path, width=40).pack(side="left", padx=5)
        tk.Button(frame, text="Chọn Audio", command=self.browse_audio).pack(side="left")

        # Chọn model Whisper
        tk.Label(root, text="Chọn độ chính xác (Model):").pack()
        self.model_var = tk.StringVar(value="base")
        model_menu = ttk.Combobox(root, textvariable=self.model_var, values=["tiny", "base", "small", "medium"])
        model_menu.pack(pady=5)

        # Nút Export
        self.btn_export = tk.Button(root, text="EXPORT SUBTITLE (.SRT & .TXT)", 
                                   command=self.start_conversion_thread, 
                                   bg="#E91E63", fg="white", font=("Arial", 10, "bold"), pady=10)
        self.btn_export.pack(pady=20)

        # Thanh trạng thái
        self.status_label = tk.Label(root, text="Sẵn sàng", fg="gray")
        self.status_label.pack()

    def browse_audio(self):
        filename = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a *.flac")])
        if filename:
            self.audio_path.set(filename)

    def format_time(self, seconds):
        """Chuyển đổi giây sang định dạng SRT (00:00:00,000)"""
        td = float(seconds)
        h = int(td // 3600)
        m = int((td % 3600) // 60)
        s = int(td % 60)
        ms = int((td - int(td)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def start_conversion_thread(self):
        if not self.audio_path.get():
            messagebox.showwarning("Lỗi", "Vui lòng chọn file audio!")
            return
        
        self.btn_export.config(state="disabled")
        self.status_label.config(text="Đang xử lý... (Vui lòng đợi giây lát)", fg="blue")
        threading.Thread(target=self.export_subtitles, daemon=True).start()

    def export_subtitles(self):
        try:
            audio_file = self.audio_path.get()
            base_name = os.path.splitext(audio_file)[0]
            
            # 1. Tải model Whisper
            model = whisper.load_model(self.model_var.get())
            
            # 2. Nhận diện (Transcribe) - Tắt fp16 nếu dùng CPU để tránh lỗi
            result = model.transcribe(audio_file, fp16=False)

            # 3. Tạo file .SRT
            srt_path = base_name + ".srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, segment in enumerate(result['segments'], start=1):
                    start = self.format_time(segment['start'])
                    end = self.format_time(segment['end'])
                    text = segment['text'].strip()
                    f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

            # 4. Tạo file .TXT (Văn bản thuần)
            txt_path = base_name + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(result['text'].strip())

            messagebox.showinfo("Thành công", f"Đã xuất file tại:\n{srt_path}\n{txt_path}")
            self.status_label.config(text="Hoàn tất!", fg="green")

        except Exception as e:
            messagebox.showerror("Lỗi", str(e))
            self.status_label.config(text="Thất bại", fg="red")
        finally:
            self.btn_export.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioToSubTool(root)
    root.mainloop()