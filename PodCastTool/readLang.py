import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont
import os
import re 
import asyncio
import subprocess
import edge_tts

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
        # try adding this top sentence to the current page candidate and compute height using combined text to reflect shared lines
        candidate_top_sentences = combined_top_sentences + [top_sent]
        top_combined_candidate = " ".join(candidate_top_sentences).strip()
        _, _, lh, cand_total_h = fit_sentence_font(top_combined_candidate, font_path, base_size, max_width)

        if combined_top_sentences and cand_total_h > max_height:
            # push current page built from combined_top_sentences
            top_combined_text = " ".join(combined_top_sentences).strip()
            f_top, lines_top, lh_top, total_h_top = fit_sentence_font(top_combined_text, font_path, base_size, max_width)
            pages.append({
                'top_lines': lines_top,
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
        f_top, lines_top, lh_top, total_h_top = fit_sentence_font(top_combined_text, font_path, base_size, max_width)
        pages.append({
            'top_lines': lines_top,
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
        
        # Prepare video + per-sentence TTS audio so the final mp4 includes speech and accurate timings
        width, height = 800, 450
        fps = 24
        default_frames_per_word = 12  # fallback if TTS/duration fails

        # Helper to choose voice
        def choose_voice(text):
            if re.search(r"[áéíóúñüÁÉÍÓÚÑÜ]|\b(hola|estoy|gracias|mundo)\b", text.lower()):
                return 'es-ES-AlvaroNeural'
            return 'en-US-JennyNeural'

        # We'll generate per-sentence TTS files and durations, then concatenate them into a single audio for muxing
        tts_files = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        temp_video = "output_map_function_noaudio.mp4"
        final_video = "output_map_function.mp4"
        out = cv2.VideoWriter(temp_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

        # base font size (keep same as used earlier)
        base_font_size = 32
        max_box_width = 640  # same width used for wrapping top sentences

        for page_index, page in enumerate(pages_data):
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

            # --- Synthesize per-sentence TTS and compute frames-per-word distribution for this page ---
            page_word_frame_counts = []
            page_tts_files = []
            for s_idx, s_text in enumerate(top_sentences):
                # synthesize tts for this sentence into a temp file
                safe_name = f"tts_p{page_index}_s{s_idx}.mp3"
                try:
                    voice = choose_voice(s_text)
                    async def synth():
                        await edge_tts.Communicate(s_text, voice).save(safe_name)
                    loop.run_until_complete(synth())
                    # measure duration
                    result = subprocess.run([
                        "ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", safe_name
                    ], stdout=subprocess.PIPE, text=True, check=True)
                    audio_dur = float(result.stdout.strip())
                except Exception:
                    # fallback duration estimation proportional to default frames_per_word
                    audio_dur = max(0.1, (sent_word_counts[s_idx] * default_frames_per_word) / fps)
                    safe_name = None

                # convert duration to frame budget for this sentence
                word_count = sent_word_counts[s_idx] if s_idx < len(sent_word_counts) else 1
                frames_for_sentence = max(1, int(round(audio_dur * fps)))
                base = frames_for_sentence // word_count
                rem = frames_for_sentence % word_count
                for w_i in range(word_count):
                    page_word_frame_counts.append(base + (1 if w_i < rem else 0))

                if safe_name:
                    page_tts_files.append(safe_name)

            # extend global tts list in order
            tts_files.extend(page_tts_files)

            # --- Build packed lines (allow multiple sentences on one line when space permits) ---
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

            # Now render frames for each word using the per-word frame counts
            word_global_idx = 0
            for w_idx, frames_for_word in enumerate(page_word_frame_counts):
                # determine which sentence the word belongs to (for bottom box)
                cum = 0
                sent_idx = 0
                for i, cnt in enumerate(sent_word_counts):
                    if w_idx < cum + cnt:
                        sent_idx = i
                        break
                    cum += cnt
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

                # compute start/end word index for active sentence's blue background
                start_word = sum(sent_word_counts[:sent_idx]) if sent_word_counts else 0
                end_word = start_word + sent_word_counts[sent_idx] - 1 if sent_idx < len(sent_word_counts) else start_word

                # draw packed lines: blue background runs and text (active word red)
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
                        color = (255, 0, 0) if item['idx'] == w_idx else (0, 0, 0)
                        draw.text((xt, yt), item['word'], font=item['font'], fill=color)
                        xt += item['width']

                    yt += line_h + 10

                final_frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                for _ in range(frames_for_word):
                    out.write(final_frame)
                word_global_idx += 1

        out.release()
        final_path = temp_video

        # If we generated per-sentence TTS files, concatenate into one audio and mux
        tts_audio = None
        if tts_files:
            concat_list = "tts_concat_list.txt"
            try:
                with open(concat_list, "w", encoding="utf-8") as lf:
                    for t in tts_files:
                        lf.write(f"file '{os.path.abspath(t)}'\n")
                tts_audio = "tts_output.mp3"
                subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", tts_audio], check=True)
            except Exception as e:
                messagebox.showwarning("Lưu ý", f"Không thể ghép âm thanh: {e}\nVideo sẽ không có âm thanh.")
            finally:
                try: os.remove(concat_list)
                except: pass

        if tts_audio and os.path.exists(tts_audio):
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", temp_video, "-i", tts_audio,
                    "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", final_video
                ], check=True)
                try:
                    os.remove(temp_video)
                except:
                    pass
                final_path = final_video
            except Exception as e:
                messagebox.showwarning("Lưu ý", f"Không thể ghép âm thanh: {e}\nVideo không có âm thanh sẽ được sử dụng.")

        # cleanup per-sentence tts tmp files
        for f in tts_files:
            try:
                if os.path.exists(f): os.remove(f)
            except: pass
        # cleanup combined tts if generated
        try:
            if tts_audio and os.path.exists(tts_audio): pass
        except: pass

        messagebox.showinfo("Thành công", f"Video Mapping Function hoàn tất!\nTệp: {final_path}")
        if os.name == 'nt': os.startfile(final_path)
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