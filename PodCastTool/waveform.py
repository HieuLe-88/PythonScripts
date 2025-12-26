import tkinter as tk
from tkinter import filedialog, messagebox
import os
import numpy as np
from moviepy.editor import VideoClip, AudioFileClip, ColorClip

class WaveformGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Waveform Generator 2025")
        self.root.geometry("400x250")

        self.audio_path = tk.StringVar()
        
        # UI Elements
        tk.Label(root, text="CHƯƠNG TRÌNH TẠO SÓNG NHẠC", font=("Arial", 12, "bold")).pack(pady=10)
        
        tk.Button(root, text="Chọn file Audio (MP3/WAV)", command=self.select_audio).pack(pady=5)
        tk.Label(root, textvariable=self.audio_path, fg="blue", wraplength=350).pack(pady=5)
        
        self.btn_run = tk.Button(root, text="BẮT ĐẦU TẠO VIDEO", command=self.generate_waveform, 
                                 bg="green", fg="white", state="disabled")
        self.btn_run.pack(pady=20)

    def select_audio(self):
        file = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav")])
        if file:
            self.audio_path.set(file)
            self.btn_run.config(state="normal")

    def make_waveform_clip(self, audio_clip, size=(1280, 720)):
        W, H = size
        fps = 24
        duration = audio_clip.duration
        
        # Trích xuất dữ liệu âm thanh (fps thấp hơn để xử lý nhanh)
        sound_array = audio_clip.to_soundarray(fps=22050)
        if sound_array.ndim > 1:
            sound_array = sound_array.mean(axis=1) # Chuyển về Mono

        def make_frame(t):
            # Tạo frame đen
            frame = np.zeros((H, W, 3), dtype=np.uint8)
            
            # Lấy vị trí mẫu âm thanh tương ứng với thời gian t
            idx = int(t * 22050)
            chunk = sound_array[idx : idx + 1000] # Lấy 1 đoạn nhỏ để tính biên độ
            
            if len(chunk) > 0:
                # Tính toán biên độ trung bình
                amplitude = np.sqrt(np.mean(chunk**2))
                # Độ cao của sóng (nhân với hệ số nhạy)
                h = int(amplitude * 800)
                h = min(h, H // 3) # Giới hạn độ cao tối đa
                
                # Vẽ các thanh sóng (Bars)
                color = (0, 255, 127) # Màu xanh neon
                for x in range(100, W - 100, 15):
                    # Vẽ thanh bar dọc ở giữa màn hình
                    y_center = H // 2
                    frame[y_center - h : y_center + h, x : x + 8] = color
            
            return frame

        return VideoClip(make_frame, duration=duration)

    def generate_waveform(self):
        input_audio = self.audio_path.get()
        output_video = "waveform_output.mp4"
        
        try:
            audio = AudioFileClip(input_audio)
            
            # 1. Tạo nền (Background) màu xám đậm
            bg = ColorClip(size=(1280, 720), color=(20, 20, 20), duration=audio.duration)
            
            # 2. Tạo lớp sóng nhạc
            wave = self.make_waveform_clip(audio)
            
            # 3. Ghép nền và sóng nhạc
            # Dùng mask hoặc overlay đơn giản (vì wave trả về frame có nền đen)
            from moviepy.editor import CompositeVideoClip
            final_video = CompositeVideoClip([bg, wave.set_position("center")])
            final_video = final_video.set_audio(audio)
            
            # 4. Xuất file
            messagebox.showinfo("Thông báo", "Đang bắt đầu xử lý video... Vui lòng đợi trong giây lát.")
            final_video.write_videofile(output_video, fps=24, codec="libx264", audio_codec="aac")
            
            messagebox.showinfo("Thành công", f"Video đã được lưu tại:\n{os.path.abspath(output_video)}")
            audio.close()
            
        except Exception as e:
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = WaveformGenerator(root)
    root.mainloop()
