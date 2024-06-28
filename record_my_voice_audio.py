import pyaudio
import wave
import tkinter as tk
from tkinter import messagebox
import threading

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.sample_rate = 44100
        self.chunk_size = 1024
        self.channels = 2

    def start_recording(self):
        self.is_recording = True
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=self.channels,
                                      rate=self.sample_rate,
                                      input=True,
                                      frames_per_buffer=self.chunk_size)
        self._record()

    def _record(self):
        while self.is_recording:
            data = self.stream.read(self.chunk_size)
            self.frames.append(data)

    def stop_recording(self, filename):
        self.is_recording = False
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()

        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(self.frames))


class RecorderApp:
    def __init__(self, root):
        self.recorder = AudioRecorder()
        self.root = root
        self.root.title("Audio Recorder")

        self.is_recording = False

        self.start_button = tk.Button(root, text="Start Recording", command=self.start_recording)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(root, text="Stop Recording", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.pack(pady=10)

    def start_recording(self):
        self.is_recording = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.recording_thread = threading.Thread(target=self.recorder.start_recording)
        self.recording_thread.start()

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.recorder.stop_recording("output.wav")
            self.recording_thread.join()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            messagebox.showinfo("Info", "Recording saved as output.wav")


if __name__ == "__main__":
    root = tk.Tk()
    app = RecorderApp(root)
    root.mainloop()
