import tkinter as tk
from tkinter import filedialog, messagebox
import eyed3

def add_lyrics_to_mp3(mp3_file_path, lyrics):
    try:
        audiofile = eyed3.load(mp3_file_path)
        if audiofile.tag is None:
            audiofile.initTag()
        audiofile.tag.lyrics.set(lyrics)
        audiofile.tag.save()
        messagebox.showinfo("Success", "Lyrics added successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to add lyrics: {e}")

def browse_file():
    file_path = filedialog.askopenfilename(
        filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")]
    )
    if file_path:
        mp3_path_entry.delete(0, tk.END)
        mp3_path_entry.insert(0, file_path)

def submit():
    mp3_file_path = mp3_path_entry.get()
    lyrics = lyrics_text.get("1.0", tk.END).strip()
    if not mp3_file_path or not lyrics:
        messagebox.showwarning("Input Error", "Please provide both MP3 file and lyrics.")
        return
    add_lyrics_to_mp3(mp3_file_path, lyrics)

# Create the main application window
root = tk.Tk()
root.title("MP3 Lyrics Adder")

# Create and place the widgets
tk.Label(root, text="MP3 File Path:").grid(row=0, column=0, padx=10, pady=10)
mp3_path_entry = tk.Entry(root, width=50)
mp3_path_entry.grid(row=0, column=1, padx=10, pady=10)
browse_button = tk.Button(root, text="Browse", command=browse_file)
browse_button.grid(row=0, column=2, padx=10, pady=10)

tk.Label(root, text="Lyrics:").grid(row=1, column=0, padx=10, pady=10)
lyrics_text = tk.Text(root, width=60, height=15)
lyrics_text.grid(row=1, column=1, columnspan=2, padx=10, pady=10)

submit_button = tk.Button(root, text="Add Lyrics", command=submit)
submit_button.grid(row=2, column=1, columnspan=2, pady=20)

# Run the application
root.mainloop()
