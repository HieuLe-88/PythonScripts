import tkinter as tk
from tkinter import filedialog, messagebox
from pytube import YouTube
import os

# Function to download video
def download_video():
    url = url_entry.get()
    if not url:
        messagebox.showerror("Error", "Please enter a YouTube URL")
        return

    save_path = filedialog.askdirectory()
    if not save_path:
        return
    
    try:
        yt = YouTube(url)
        stream = yt.streams.get_highest_resolution()
        stream.download(save_path)
        messagebox.showinfo("Success", f"Downloaded '{yt.title}' successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to download video: {e}")

# Setting up the GUI
root = tk.Tk()
root.title("YouTube Video Downloader")

canvas = tk.Canvas(root, height=200, width=400)
canvas.pack()

frame = tk.Frame(root)
frame.place(relwidth=1, relheight=1)

label = tk.Label(frame, text="Enter YouTube URL:")
label.pack(pady=10)

url_entry = tk.Entry(frame, width=50)
url_entry.pack(pady=5)

download_button = tk.Button(frame, text="Download", command=download_video)
download_button.pack(pady=20)

root.mainloop()
