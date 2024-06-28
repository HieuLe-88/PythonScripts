import tkinter as tk
from tkinter import ttk
import pyautogui
import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import time
import cv2
import os
import sys
import screeninfo

class ScreenRecorder:
    def __init__(self, screen_index, fps=6):  # Reduced fps to 6 for 5x slowdown
        self.screen_index = screen_index
        self.fps = fps
        self.is_recording = False
        self.record_num = 1  # Initialize record number
        self.screen = pyautogui.size()
        self.screen_width, self.screen_height = self.screen.width, self.screen.height

    def start_recording(self):
        self.is_recording = True
        threading.Thread(target=self._record_screen).start()
        threading.Thread(target=self._record_audio).start()

    def stop_recording(self):
        self.is_recording = False
        self.record_num += 1  # Increment record number

    def _record_screen(self):
        screen = screeninfo.get_monitors()[self.screen_index]
        screen_width, screen_height = screen.width, screen.height
        video_writer = cv2.VideoWriter(f"output_{self.record_num}.avi", cv2.VideoWriter_fourcc(*"XVID"), self.fps, (screen_width, screen_height))

        start_time = time.time()
        while self.is_recording:
            screenshot = pyautogui.screenshot(region=(screen.x, screen.y, screen.width, screen.height))
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            video_writer.write(frame)

            # Calculate next frame time
            next_frame_time = start_time + (1 / self.fps)
            wait_time = next_frame_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time)
            else:
                print("Warning: Frame took too long to process.")

        video_writer.release()

    def _record_audio(self):
        duration = 1.0 / self.fps
        filename = f"output_{self.record_num}.wav"
        audio_data = []

        def audio_callback(indata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            if self.is_recording:
                audio_data.append(indata.copy())

        with sd.InputStream(callback=audio_callback):
            while self.is_recording:
                time.sleep(duration)

        audio_data = np.concatenate(audio_data)
        sf.write(filename, audio_data, 44100, 'PCM_16')

def start_recording():
    global recorder
    screen_index = screen_combobox.current()
    recorder = ScreenRecorder(screen_index)
    recorder.start_recording()

def stop_recording():
    global recorder
    recorder.stop_recording()

def save():
    global recorder
    recorder.stop_recording()
    root.destroy()

# GUI
root = tk.Tk()
root.title("Screen Recorder")

# Screen selection
screens = screeninfo.get_monitors()
screen_names = [f"Screen {i+1}" for i in range(len(screens))]
screen_combobox = ttk.Combobox(root, values=screen_names, state="readonly")
screen_combobox.current(0)
screen_combobox.grid(row=0, column=1, padx=5, pady=5)

# Buttons
start_button = tk.Button(root, text="Start Recording", command=start_recording)
start_button.grid(row=0, column=0, padx=5, pady=5)
stop_button = tk.Button(root, text="Stop Recording", command=stop_recording)
stop_button.grid(row=0, column=2, padx=5, pady=5)
save_button = tk.Button(root, text="Save", command=save)
save_button.grid(row=0, column=3, padx=5, pady=5)

root.mainloop()
