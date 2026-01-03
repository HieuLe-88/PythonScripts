import numpy as np
import re
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips
from pypinyin import pinyin, Style

# --- Configuration ---
INPUT_FILE = "input.txt" # Just put Hanzi here, e.g., "你好，今天我们聊聊暑假的旅行计划吧。"
FONT_PATH = "C:\\Windows\\Fonts\\msyh.ttc" 
VIDEO_SIZE = (1280, 720)
DURATION = 5

def create_auto_aligned_frame(text_line):
    img = Image.new('RGB', VIDEO_SIZE, color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    h_font = ImageFont.truetype(FONT_PATH, 60)
    p_font = ImageFont.truetype(FONT_PATH, 30) # 50% size
    
    # 1. Automatically get Pinyin for each character
    # pinyin() returns a list of lists: [['nǐ'], ['hǎo'], ...]
    pinyin_data = pinyin(text_line, style=Style.TONE)
    
    # 2. Layout Settings
    char_spacing = 95
    line_height = 160
    chars_per_line = (VIDEO_SIZE[0] - 100) // char_spacing
    
    # 3. Split Hanzi and Pinyin into matching lines
    hanzi_chars = list(text_line.strip())
    lines_h = [hanzi_chars[i:i + chars_per_line] for i in range(0, len(hanzi_chars), chars_per_line)]
    lines_p = [pinyin_data[i:i + chars_per_line] for i in range(0, len(pinyin_data), chars_per_line)]
    
    total_h = len(lines_h) * line_height
    current_y = (VIDEO_SIZE[1] - total_h) // 2
    
    # 4. Drawing Loop
    for line_idx, h_line in enumerate(lines_h):
        p_line = lines_p[line_idx]
        
        # Center the line horizontally
        total_line_width = len(h_line) * char_spacing
        current_x = (VIDEO_SIZE[0] - total_line_width) // 2
        
        for i, char in enumerate(h_line):
            slot_center_x = current_x + (char_spacing // 2)
            
            # --- Draw Hanzi ---
            h_bbox = draw.textbbox((0, 0), char, font=h_font)
            h_w = h_bbox[2] - h_bbox[0]
            draw.text((slot_center_x - h_w/2, current_y + 40), char, font=h_font, fill="black")
            
            # --- Draw Pinyin (only if it's a Chinese character) ---
            if re.match(r'[\u4e00-\u9fff]', char):
                # p_line[i] is a list like ['nǐ'], so we take [0]
                p_text = p_line[i][0]
                p_bbox = draw.textbbox((0, 0), p_text, font=p_font)
                p_w = p_bbox[2] - p_bbox[0]
                draw.text((slot_center_x - p_w/2, current_y), p_text, font=p_font, fill="black")
            
            current_x += char_spacing
        current_y += line_height
        
    return np.array(img)

# --- Execute ---
clips = []
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        clean_line = line.strip()
        if clean_line:
            # If your input still has the "|" format, just take the first part
            hanzi_only = clean_line.split("|")[0]
            frame_data = create_auto_aligned_frame(hanzi_only)
            clips.append(ImageClip(frame_data).set_duration(DURATION))

if clips:
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile("auto_aligned_pinyin.mp4", fps=24)