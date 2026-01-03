import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont
import os
import re 

# --- CÁC HÀM HỖ TRỢ XỬ LÝ VĂN BẢN ---

def get_text_dimensions(text, font):
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def wrap_text_to_lines(text, font, max_width):
    words = text.split()
    lines = []
    current = []
    for w in words:
        test = ' '.join(current + [w]) if current else w
        w_pixels, _ = get_text_dimensions(test, font)
        if w_pixels <= max_width:
            current.append(w)
        else:
            if current:
                lines.append(' '.join(current))
            current = [w]
    if current:
        lines.append(' '.join(current))
    # If only one line and it fits, return as a single line (no forced break)
    if len(lines) > 1 and all(get_text_dimensions(line, font)[0] <= max_width for line in lines):
        joined = ' '.join(lines)
        if get_text_dimensions(joined, font)[0] <= max_width:
            return [joined]
    return lines

# --- HÀM MỚI: TẠO BẢNG MAPPING RIÊNG BIỆT ---
def create_sentence_map(parts):
    """
    Tạo một bảng mapping giữa các câu gốc và câu dịch.
    Ví dụ: sentence_lookup_map["ABC CD ."] = "EGF GD."
    """
    global sentence_lookup_map
    sentence_lookup_map = {}
    for top, bottom in sentence_pairs:
        if top:
            sentence_lookup_map[top] = bottom

# --- HÀM MỚI: TRUY XUẤT TEXT BOX DƯỚI ---
def get_bottom_text(current_top_full_sentence):
    """
    Dựa trên câu đang highlight ở Box trên, trả về câu dịch tương ứng.
    """
    return sentence_lookup_map.get(current_top_full_sentence, "")

def wrap_and_paginate_with_mapping(sentence_pairs, font_path, base_size, max_width, max_height):
    pages = []
    combined_top_sentences = []
    combined_bottom = ""
    combined_bottom_sentences = []
    line_spacing = 10

    for top_sent, bottom_sent in sentence_pairs:
        # try adding this top sentence to the current page candidate and compute height by per-sentence fits
        candidate_top_sentences = combined_top_sentences + [top_sent]
        cand_total_h = 0
        for s in candidate_top_sentences:
            _, _, lh, total_h = fit_sentence_font(s, font_path, base_size, max_width)
            cand_total_h += total_h

        if combined_top_sentences and cand_total_h > max_height:
            # push current page built from combined_top_sentences
            top_combined_text = " ".join(combined_top_sentences).strip()
            pages.append({
                'top_lines': wrap_text_to_lines(top_combined_text, ImageFont.truetype(font_path, base_size), max_width),
                'top_full_text': top_combined_text,
                'bottom_full_text': combined_bottom,
                'top_sentences': combined_top_sentences.copy(),
                'bottom_sentences': combined_bottom_sentences.copy()
            })
            # start new page
            combined_top_sentences = [top_sent]
            combined_bottom = bottom_sent
            combined_bottom_sentences = [bottom_sent]
        else:
            combined_top_sentences = candidate_top_sentences
            combined_bottom = (combined_bottom + " " + bottom_sent).strip() if combined_bottom else bottom_sent
            combined_bottom_sentences.append(bottom_sent)

    if combined_top_sentences:
        top_combined_text = " ".join(combined_top_sentences).strip()
        pages.append({
            'top_lines': wrap_text_to_lines(top_combined_text, ImageFont.truetype(font_path, base_size), max_width),
            'top_full_text': top_combined_text,
            'bottom_full_text': combined_bottom,
            'top_sentences': combined_top_sentences.copy(),
            'bottom_sentences': combined_bottom_sentences.copy()
        })
    return pages

# --- HÀM XỬ LÝ CHÍNH KHI NHẤN NÚT ---
def fit_sentence_font(text, font_path, base_size, max_width, max_height=None, min_size=12):
    line_spacing = 10
    size = base_size
    while size >= min_size:
        f = ImageFont.truetype(font_path, size)
        lines = wrap_text_to_lines(text, f, max_width)
        _, lh = get_text_dimensions("Ay", f)
        total_h = len(lines) * (lh + line_spacing)
        if all(get_text_dimensions(line, f)[0] <= max_width for line in lines) and (max_height is None or total_h <= max_height):
            return f, lines, lh, total_h
        size -= 2
    f = ImageFont.truetype(font_path, min_size)
    lines = wrap_text_to_lines(text, f, max_width)
    _, lh = get_text_dimensions("Ay", f)
    return f, lines, lh, len(lines) * (lh + line_spacing)

def select_file():
    file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
    if file_path:
        entry_path.delete(0, tk.END)
        entry_path.insert(0, file_path)

def generate_video():
    txt_path = entry_path.get()
    if not os.path.exists(txt_path):
        messagebox.showwarning("Cảnh báo", "Vui lòng chọn file .txt!")
        return

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            raw = f.read().replace('\n', ' ').replace('\r', ' ').strip()
            # Remove pipes so we can split into sentences reliably
            raw_nopipes = raw.replace('|', ' ')

            # Split into sentence-like segments (keeps punctuation)
            segs = [s.strip() for s in re.split(r'(?<=[.!?])\s*', raw_nopipes) if s.strip()]

            # Simple Spanish detector (accented chars or common Spanish words)
            def is_spanish_sentence(s):
                if re.search(r'[áéíóúñüÁÉÍÓÚÑÜ]', s):
                    return True
                spanish_words = {'estoy', 'hola', 'mundo', 'también', 'entonces', 'gracias', 'yo', 'tú', 'usted'}
                tokens = re.findall(r'\w+', s.lower())
                return any(t in spanish_words for t in tokens)

            sentence_pairs = []
            i = 0
            while i < len(segs):
                s = segs[i]
                if is_spanish_sentence(s):
                    # pair this spanish sentence with the next non-spanish (english) sentence
                    j = i + 1
                    while j < len(segs) and is_spanish_sentence(segs[j]):
                        j += 1
                    if j < len(segs):
                        sentence_pairs.append((s, segs[j]))
                        i = j + 1
                    else:
                        sentence_pairs.append((s, ""))
                        i = j
                else:
                    # current is English; find next Spanish and pair (fallback)
                    j = i + 1
                    while j < len(segs) and not is_spanish_sentence(segs[j]):
                        j += 1
                    if j < len(segs):
                        sentence_pairs.append((segs[j], s))
                        i = j + 1
                    else:
                        sentence_pairs.append(("", s))
                        i = j


        font_path = "arial.ttf"
        font = ImageFont.truetype(font_path, 32)
        _, single_line_h = get_text_dimensions("Ay", font)   # ← ADD THIS LINE

        base_font_size = 32
        pages_data = wrap_and_paginate_with_mapping(sentence_pairs, font_path, base_font_size, 640, 165)
        
        file_name = "output_map_function.mp4"
        width, height = 800, 450
        fps, frames_per_word = 24, 12 
        out = cv2.VideoWriter(file_name, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

        # base font size (keep same as used earlier)
        base_font_size = 32
        max_box_width = 640  # same width used for wrapping top sentences

        for page in pages_data:
            top_sentences = page.get('top_sentences', [])
            bottom_sentences = page.get('bottom_sentences', [])

            # Precompute fitted font + wrapped lines for each top sentence
            top_sentence_draws = []
            for s in top_sentences:
                f_s, lines_s, lh_s, _ = fit_sentence_font(s, font_path, base_font_size, max_box_width)
                top_sentence_draws.append({'font': f_s, 'lines': lines_s, 'line_h': lh_s})

            # Build word list and sentence word counts
            sent_word_counts = [sum(len(line.split()) for line in sdraw['lines']) for sdraw in top_sentence_draws]
            total_top_words = sum(sent_word_counts)
            for target_idx in range(total_top_words):
                # Find which sentence contains the active word
                cum = 0
                sent_idx = 0
                for i, cnt in enumerate(sent_word_counts):
                    if target_idx < cum + cnt:
                        sent_idx = i
                        break
                    cum += cnt
                # corresponding bottom sentence (if any)
                current_box_bottom_text = bottom_sentences[sent_idx] if sent_idx < len(bottom_sentences) else ""

                base_frame = np.full((height, width, 3), (40, 40, 40), dtype=np.uint8)
                cv2.rectangle(base_frame, (50, 50), (750, 245), (204, 255, 255), -1)
                cv2.rectangle(base_frame, (50, 315), (750, 380), (204, 255, 255), -1)

                img_pil = Image.fromarray(cv2.cvtColor(base_frame, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(img_pil)

                # draw the bottom text (centered), use fitted font so it fits
                if current_box_bottom_text:
                    f_b, b_lines, bh, _ = fit_sentence_font(current_box_bottom_text, font_path, base_font_size, max_box_width)
                    bw, bhw = get_text_dimensions(" ".join(b_lines), f_b)
                    # center single-line; if multi-line, draw each line centered
                    yb = 347 - (len(b_lines)*(bh + 10))//2
                    for line in b_lines:
                        lw, _ = get_text_dimensions(line, f_b)
                        draw.text((400 - lw//2, yb), line, font=f_b, fill=(0, 0, 0))
                        yb += bh + 10

                # --- draw blue background for the active sentence (per-word runs) ---
                # compute start/end word index for active sentence
                start_word = sum(sent_word_counts[:sent_idx]) if sent_word_counts else 0
                end_word = start_word + sent_word_counts[sent_idx] - 1 if sent_idx < len(sent_word_counts) else start_word

                # --- Build packed lines (allow multiple sentences on one line when space permits) ---
                # --- Build packed lines (word-by-word, so sentences continue on same line when possible) ---
                lines_render = []
                current_line = []
                current_width = 0
                global_idx = 0

                for s_idx, sdraw in enumerate(top_sentence_draws):
                    f_s = sdraw['font']
                    for s_line in sdraw['lines']:
                        for w in s_line.split():
                            ww = get_text_dimensions(w + " ", f_s)[0]
                            # if the word fits on current line, append it, otherwise push current and start new line
                            if current_width == 0 or current_width + ww <= max_box_width:
                                current_line.append({'word': w, 'font': f_s, 'idx': global_idx, 'width': ww, 's_idx': s_idx})
                                current_width += ww
                            else:
                                lines_render.append(current_line)
                                current_line = [{'word': w, 'font': f_s, 'idx': global_idx, 'width': ww, 's_idx': s_idx}]
                                current_width = ww
                            global_idx += 1

                if current_line:
                    lines_render.append(current_line)

                # --- Draw packed lines: blue background runs and then text (active word red) ---
                yt = 70
                for line in lines_render:
                    # line height = max font line height in this line
                    line_h = max(get_text_dimensions("Ay", item['font'])[1] for item in line)
                    xt = 80

                    # draw blue background for runs belonging to active sentence (start_word..end_word)
                    in_run = False
                    run_x1 = run_x2 = None
                    padding = 6
                    for item in line:
                        if start_word <= item['idx'] <= end_word:
                            if not in_run:
                                in_run = True
                                run_x1 = xt
                                run_x2 = xt + item['width']
                            else:
                                run_x2 = xt + item['width']
                        else:
                            if in_run:
                                draw.rectangle([run_x1 - padding, yt - 5, run_x2 + padding, yt + line_h + 5], fill=(173, 216, 230))
                                in_run = False
                        xt += item['width']
                    if in_run:
                        draw.rectangle([run_x1 - padding, yt - 5, run_x2 + padding, yt + line_h + 5], fill=(173, 216, 230))

                    # draw words with active word in red
                    xt = 80
                    for item in line:
                        color = (255, 0, 0) if item['idx'] == target_idx else (0, 0, 0)
                        draw.text((xt, yt), item['word'], font=item['font'], fill=color)
                        xt += item['width']

                    yt += line_h + 10

                final_frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                for _ in range(frames_per_word):
                    out.write(final_frame)

        out.release()
        messagebox.showinfo("Thành công", "Video Mapping Function hoàn tất!")
        if os.name == 'nt': os.startfile(file_name)
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))

# --- PHẦN KHỞI CHẠY GIAO DIỆN (BẮT BUỘC PHẢI CÓ) ---

root = tk.Tk()
root.title("Video Pagination Tool")
root.geometry("500x250")

tk.Label(root, text="Chọn file text để tạo video:", font=("Arial", 11)).pack(pady=20)

frame_row = tk.Frame(root)
frame_row.pack(fill='x', padx=30)

entry_path = tk.Entry(frame_row)
entry_path.pack(side=tk.LEFT, expand=True, fill='x', padx=(0, 10))

btn_browse = tk.Button(frame_row, text="Browse", command=select_file)
btn_browse.pack(side=tk.RIGHT)

btn_main = tk.Button(root, text="GENERATE VIDEO", command=generate_video, 
                     bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), pady=10)
btn_main.pack(pady=30)

# Lệnh này giữ cho cửa sổ luôn hiển thị
root.mainloop()