import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import whisper
import threading
import os

class AudioToSubTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio to Subtitle Exporter")
        self.root.geometry("550x400")

        self.audio_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        
        # Giao diện
        tk.Label(root, text="CHUYỂN AUDIO SANG FILE PHỤ ĐỀ", font=("Arial", 14, "bold")).pack(pady=15)

        # Khung chọn file audio
        self.create_input("Audio (MP3...):", self.audio_path, self.browse_audio)
        
        # Khung chọn thư mục đầu ra
        self.create_input("Thư mục lưu file:", self.output_dir, self.browse_directory)

        # Chọn model Whisper
        tk.Label(root, text="Chọn độ chính xác (Model AI):").pack(pady=(10, 0))
        self.model_var = tk.StringVar(value="base")
        model_menu = ttk.Combobox(root, textvariable=self.model_var, values=["tiny", "base", "small", "medium"])
        model_menu.pack(pady=5)

        # Nút Export
        self.btn_export = tk.Button(root, text="BẮT ĐẦU TRÍCH XUẤT SUBTITLE", 
                                   command=self.start_conversion_thread, 
                                   bg="#E91E63", fg="white", font=("Arial", 10, "bold"), padx=20, pady=10)
        self.btn_export.pack(pady=20)

        # Thanh trạng thái
        self.status_label = tk.Label(root, text="Sẵn sàng", fg="gray")
        self.status_label.pack()

    def create_input(self, text, var, command_func):
        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=30, pady=5)
        tk.Label(frame, text=text, width=15, anchor="w").pack(side="left")
        tk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(frame, text="Duyệt", command=command_func).pack(side="right")

    def browse_audio(self):
        filename = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a *.flac")])
        if filename:
            self.audio_path.set(filename)
            # Tự động gợi ý thư mục lưu cùng chỗ với audio nếu chưa chọn
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(filename))

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)

    def format_time(self, seconds):
        td = float(seconds)
        h = int(td // 3600)
        m = int((td % 3600) // 60)
        s = int(td % 60)
        ms = int((td - int(td)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def start_conversion_thread(self):
        if not self.audio_path.get() or not self.output_dir.get():
            messagebox.showwarning("Lỗi", "Vui lòng chọn đầy đủ file audio và thư mục lưu!")
            return
        
        self.btn_export.config(state="disabled")
        self.status_label.config(text="AI đang nhận diện giọng nói... Vui lòng đợi.", fg="blue")
        threading.Thread(target=self.export_subtitles, daemon=True).start()

    def export_subtitles(self):
        try:
            audio_file = self.audio_path.get()
            # Lấy tên file không có đuôi để đặt tên cho file sub
            file_name_only = os.path.splitext(os.path.basename(audio_file))[0]
            save_dir = self.output_dir.get()
            
            # 1. Tải model Whisper
            model = whisper.load_model(self.model_var.get())
            
            # 2. Nhận diện (Transcribe) - Tắt fp16 để chạy ổn định trên CPU
            result = model.transcribe(audio_file, fp16=False)

            # 3. Tạo file .SRT
            srt_path = os.path.join(save_dir, file_name_only + ".srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, segment in enumerate(result['segments'], start=1):
                    start = self.format_time(segment['start'])
                    end = self.format_time(segment['end'])
                    text = segment['text'].strip()
                    f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

            # 4. Tạo file .TXT
            txt_path = os.path.join(save_dir, file_name_only + ".txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(result['text'].strip())

            messagebox.showinfo("Thành công", f"Đã xuất file tại thư mục:\n{save_dir}")
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