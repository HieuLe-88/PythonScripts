import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip
import os

# --- Configuration ---
chinese_text = "你好"
pinyin_text = "nǐ hǎo"
font_path = r"C:\Windows\Fonts\msyh.ttc"  # Microsoft YaHei
video_size = (1280, 720)
duration = 5

# Font Sizes
zh_size = 150
py_size = int(zh_size * 0.4) # 40% of Chinese size
spacing = 20 # Space between Pinyin and Chinese

# --- Processing ---
img = Image.new('RGB', video_size, color=(0, 0, 0))
draw = ImageDraw.Draw(img)

# Load Fonts
zh_font = ImageFont.truetype(font_path, zh_size)
py_font = ImageFont.truetype(font_path, py_size)

# Calculate Dimensions for Centering
def get_text_dims(text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

zh_w, zh_h = get_text_dims(chinese_text, zh_font)
py_w, py_h = get_text_dims(pinyin_text, py_font)

# Total height of the text block
total_h = py_h + spacing + zh_h

# Starting Y position (to center the whole block)
start_y = (video_size[1] - total_h) // 2

# Draw Pinyin (Top)
py_x = (video_size[0] - py_w) // 2
draw.text((py_x, start_y), pinyin_text, font=py_font, fill=(255, 255, 255))

# Draw Chinese (Bottom)
zh_x = (video_size[0] - zh_w) // 2
zh_y = start_y + py_h + spacing
draw.text((zh_x, zh_y), chinese_text, font=zh_font, fill=(255, 255, 255))

# --- Export to MP4 ---
numpy_img = np.array(img)
clip = ImageClip(numpy_img).set_duration(duration)
clip.write_videofile("chinese_pinyin.mp4", fps=24)

print("Video successfully created: chinese_pinyin.mp4")