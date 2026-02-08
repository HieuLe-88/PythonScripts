"""
Generate a 5-second animated waveform and export to MP4.

Usage:
  python test.py

Requirements:
  pip install moviepy numpy pillow

Notes:
  - MoviePy needs ffmpeg available on PATH. The workspace includes an ffmpeg build
	(installTool/ffmpeg-.../bin). Add it to PATH if MoviePy can't find ffmpeg.
"""

import numpy as np
# Prefer editor.VideoClip, but fall back to top-level names if necessary
try:
	from moviepy.editor import VideoClip
except Exception:
	try:
		from moviepy import VideoClip
	except Exception:
		VideoClip = None

# AudioArrayClip may be available under moviepy.audio.AudioClip or at package level
try:
	from moviepy.audio.AudioClip import AudioArrayClip
except Exception:
	try:
		from moviepy import AudioArrayClip
	except Exception:
		try:
			from moviepy.editor import AudioArrayClip
		except Exception:
			AudioArrayClip = None
from PIL import Image, ImageDraw


def make_audio(duration=5.0, sr=44100):
	t = np.linspace(0, duration, int(sr * duration), endpoint=False)
	# Layer several sine waves to make a richer waveform
	audio = 0.6 * np.sin(2 * np.pi * 220 * t)
	audio += 0.3 * np.sin(2 * np.pi * 440 * t)
	audio += 0.1 * np.sin(2 * np.pi * 880 * t) * np.sin(2 * np.pi * 0.25 * t)
	# add subtle amplitude modulation for visual movement
	audio *= (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t))
	# normalize
	audio = audio / np.max(np.abs(audio))
	return (audio.astype(np.float32), sr)


def gradient_color(i, n):
	# map index to an RGB color across a rainbow-like gradient
	# i in [0, n-1]
	ratio = i / max(1, n - 1)
	from math import sin, pi
	r = int(127.5 * (1 + sin(2 * pi * ratio + 0)))
	g = int(127.5 * (1 + sin(2 * pi * ratio + 2 * pi / 3)))
	b = int(127.5 * (1 + sin(2 * pi * ratio + 4 * pi / 3)))
	return (r, g, b)


def create_waveform_video(filename="waveform.mp4", duration=5.0, fps=30, width=1280, height=360, n_bars=48):
	audio, sr = make_audio(duration=duration)
	audio_clip = AudioArrayClip(audio.reshape((-1, 1)), fps=sr)

	# Precompute colors for bars
	colors = [gradient_color(i, n_bars) for i in range(n_bars)]

	half_h = height // 2
	bar_w = int(width / n_bars)

	# Make a frame generator using the audio's FFT around time t
	def make_frame(t):
		# get a short window of audio around t
		center = int(t * sr)
		win = 2048
		start = max(0, center - win // 2)
		segment = audio[start:start + win]
		if len(segment) < 2:
			segment = np.pad(segment, (0, max(0, 2 - len(segment))))

		# compute magnitude per frequency band
		fft = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
		freqs = np.fft.rfftfreq(len(segment), d=1.0 / sr)

		# split into n_bars bands
		mags = np.zeros(n_bars)
		maxf = sr / 2
		band_edges = np.linspace(0, maxf, n_bars + 1)
		for i in range(n_bars):
			lo, hi = band_edges[i], band_edges[i + 1]
			mask = (freqs >= lo) & (freqs < hi)
			if np.any(mask):
				mags[i] = fft[mask].mean()

		# normalize magnitudes
		mags = mags / (np.max(mags) + 1e-9)
		# amplify low frequencies a bit for visual balance
		mags = mags ** 0.8

		# Create an image and draw vertical bars
		img = Image.new("RGB", (width, height), (12, 12, 12))
		draw = ImageDraw.Draw(img)

		for i, mag in enumerate(mags):
			bw = bar_w - 2
			x0 = i * bar_w + 1
			x1 = x0 + bw
			h = int(mag * (height * 0.95))
			y0 = half_h - h // 2
			y1 = half_h + h // 2
			draw.rectangle([x0, y0, x1, y1], fill=colors[i])

		return np.asarray(img)

	clip = VideoClip(make_frame, duration=duration)
	if hasattr(clip, "set_fps"):
		clip = clip.set_fps(fps)
	elif hasattr(clip, "with_fps"):
		clip = clip.with_fps(fps)

	if hasattr(clip, "set_audio"):
		clip = clip.set_audio(audio_clip)
	elif hasattr(clip, "with_audio"):
		clip = clip.with_audio(audio_clip)

	# Write file (MoviePy uses ffmpeg under the hood)
	clip.write_videofile(filename, fps=fps, codec="libx264", audio_codec="aac")


if __name__ == "__main__":
	print("Creating 5s waveform video -> waveform.mp4")
	create_waveform_video("waveform.mp4", duration=5.0)

