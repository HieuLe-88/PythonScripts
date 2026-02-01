

# 1. Cấu hình API Key (Hãy chắc chắn dùng Key MỚI và còn hạn mức)
#API_KEY = "AIzaSyD4liSp1M5A7G6Yhkdpx4T43VuA7fbMaEw" 
import tkinter as tk
from tkinter import messagebox
import google.generativeai as genai
import os

# 1. Cấu hình API Key
# Nhớ dùng Key mới bạn vừa tạo trong Google AI Studio nhé!
API_KEY = "AIzaSyD4liSp1M5A7G6Yhkdpx4T43VuA7fbMaEw"
genai.configure(api_key=API_KEY)

def generate_gemini_voice():
    text = text_input.get("1.0", tk.END).strip()
    if not text:
        messagebox.showwarning("Thông báo", "Vui lòng nhập văn bản!")
        return

    try:
        # 2. Sử dụng model phiên bản ổn định nhất
        # Nếu 'gemini-1.5-flash' vẫn lỗi 404, bạn hãy thử thay bằng 'gemini-1.5-flash-latest'
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 3. Gửi yêu cầu kèm cấu hình giọng nói
        # Lưu ý: Chúng ta dùng tham số generation_config để chỉ định voice
        response = model.generate_content(
            text,
            generation_config={
                "response_modalities": ["audio"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Puck" # Các giọng: Puck, Charon, Kore, Fenrir
                        }
                    }
                }
            }
        )

        # 4. Kiểm tra và trích xuất file âm thanh
        audio_data = None
        for part in response.candidates[0].content.parts:
            # Kiểm tra nếu part chứa dữ liệu inline (âm thanh)
            if hasattr(part, 'inline_data'):
                audio_data = part.inline_data.data
            elif hasattr(part, 'file_data'): # Đề phòng cấu hình khác
                audio_data = part.file_data.data
        
        if audio_data:
            filename = "gemini_voice.wav"
            with open(filename, "wb") as f:
                f.write(audio_data)
            
            messagebox.showinfo("Thành công", f"Gemini đã đọc xong!\nGiọng: Puck")
            
            # Mở file nhạc
            if os.name == 'nt': os.startfile(filename)
            else: os.system(f"open {filename}")
        else:
            # Trường hợp AI chỉ trả về text (thường do Quota hoặc lỗi vùng miền)
            print("AI Response:", response.text)
            messagebox.showwarning("Lưu ý", "AI trả về văn bản nhưng không kèm âm thanh. Có thể model này tại vùng của bạn chưa hỗ trợ xuất Audio.")

    except Exception as e:
        error_str = str(e)
        if "404" in error_str:
            messagebox.showerror("Lỗi 404", "Model này không tồn tại. Hãy thử đổi tên thành 'gemini-1.5-flash-latest' trong code.")
        elif "429" in error_str:
            messagebox.showerror("Lỗi 429", "Hết lượt dùng miễn phí. Hãy đợi 1 phút rồi thử lại.")
        else:
            messagebox.showerror("Lỗi", f"Chi tiết: {error_str}")

# --- Giao diện GUI ---
root = tk.Tk()
root.title("Gemini Voice AI - 2026")
root.geometry("400x350")

tk.Label(root, text="Nhập văn bản cần Gemini đọc:", font=("Arial", 10, "bold")).pack(pady=10)
text_input = tk.Text(root, height=10, width=45)
text_input.pack(pady=5)

btn = tk.Button(root, text="Tạo giọng nói Gemini", command=generate_gemini_voice, 
                bg="#1a73e8", fg="white", font=("Arial", 10, "bold"), padx=10, pady=5)
btn.pack(pady=15)

root.mainloop()