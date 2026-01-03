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

# Optional: pypinyin for automatic pinyin generation when input does not provide it
try:
    from pypinyin import pinyin as _pypinyin_pinyin, Style as _pypinyin_Style
    HAVE_PYPINYIN = True
except Exception:
    _pypinyin_pinyin = None
    _pypinyin_Style = None
    HAVE_PYPINYIN = False

# GUI voice/speed options
VOICE_OPTIONS = {
    "Jenny (EN)": "en-US-JennyNeural",
    "Guy (EN)": "en-US-GuyNeural",
    "Alvaro (ES)": "es-ES-AlvaroNeural",
    "Elvira (ES)": "es-ES-ElviraNeural",
    "NamMinh (VI)": "vi-VN-NamMinhNeural",
    "HoaiMy (VI)": "vi-VN-HoaiMyNeural",
    "Yunxi (ZH)": "zh-CN-YunxiNeural",
    "Yunjian (ZH)": "zh-CN-YunjianNeural",
}
SPEED_OPTIONS = ["100%", "90%", "80%", "70%", "60%", "50%"]

# Helper: locate a Chinese-capable font on this system
def _can_render_glyph(path, glyph='你'):
    try:
        f = ImageFont.truetype(path, 32)
        img = Image.new('L', (64, 64), color=255)
        d = ImageDraw.Draw(img)
        d.text((0, 0), glyph, font=f, fill=0)
        return img.getbbox() is not None
    except Exception:
        return False


def find_chinese_font():
    # First try a few well-known paths
    candidates = [
        "C:/Users/USER/AppData/Local/Microsoft/Windows/Fonts/NotoSansCJKsc-Regular.otf",
        "C:/Windows/Fonts/msyh.ttf",
        "C:/Windows/Fonts/SimHei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for p in candidates:
        if os.path.exists(p) and _can_render_glyph(p):
            return p

    # Fallback: scan all fonts in Windows Fonts folder and test rendering
    fonts_dir = "C:/Windows/Fonts"
    try:
        for fname in os.listdir(fonts_dir):
            if not fname.lower().endswith(('.ttf', '.ttc', '.otf')):
                continue
            p = os.path.join(fonts_dir, fname)
            if _can_render_glyph(p):
                return p
    except Exception:
        pass

    # last resort: try system font path entries from known places
    try:
        import matplotlib.font_manager as fm
        for fpath in fm.findSystemFonts():
            try:
                if _can_render_glyph(fpath):
                    return fpath
            except Exception:
                continue
    except Exception:
        pass

    return None

# Cache chosen chinese font at module load so GUI can display/debug it
CHINESE_FONT = find_chinese_font()

# If the cached font does not render, attempt a dynamic search the first time we need it
def get_working_chinese_font():
    global CHINESE_FONT
    if CHINESE_FONT and _can_render_glyph(CHINESE_FONT):
        return CHINESE_FONT
    CHINESE_FONT = find_chinese_font()
    return CHINESE_FONT

def check_chinese_font():
    """Check whether the chosen Chinese font can render a test glyph and show result."""
    font_path = CHINESE_FONT or find_chinese_font()
    if not font_path:
        messagebox.showwarning("Chinese font", "No Chinese-capable font found on this system. Please install NotoSansCJK or MSYH.")
        return
    try:
        test_char = '你'
        f = ImageFont.truetype(font_path, 32)
        img = Image.new('L', (64, 64), color=255)
        d = ImageDraw.Draw(img)
        d.text((0, 0), test_char, font=f, fill=0)
        bbox = img.getbbox()
        if bbox:
            messagebox.showinfo("Chinese font", f"Font found: {font_path}\nGlyph renders OK (bbox={bbox}).")
        else:
            messagebox.showwarning("Chinese font", f"Font found: {font_path}\nBut glyph did not render (appears blank).")
    except Exception as e:
        messagebox.showerror("Chinese font test error", str(e))


# --- CÁC HÀM HỖ TRỢ XỬ LÝ VĂN BẢN ---

def get_text_dimensions(text, font):
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def normalize_pinyin_tokens(py_text, ch_text):
    """Normalize a pinyin string into a list of tokens aligned to Chinese characters when possible.

    Strategy:
    - If pinyin has spaces and token count == Chinese character count, use them.
    - Otherwise, flatten the pinyin and perform a segmentation into ch_count pieces.
    - Prefer segmentations where each piece contains a vowel and each segment (except maybe the first) starts with a consonant.
    """
    if not py_text:
        return []
    tokens = [t for t in py_text.split() if t.strip()]
    ch_count = sum(1 for ch in ch_text if not ch.isspace())
    if ch_count == 0:
        return tokens
    if len(tokens) == ch_count:
        return tokens

    s = ''.join(tokens)
    s = s.strip()
    if not s:
        return [''] * ch_count

    vowels = set(list('aeiouüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜAEIOUÜĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙǕǗǙǛ'))

    def has_vowel(seg):
        return any(ch in vowels for ch in seg)

    def is_consonant(ch):
        return ch.lower() not in 'aeiouüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜAEIOUÜĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙǕǗǙǛ'

    # Backtracking segmentation: try to split s into ch_count parts where each has at least one vowel
    L = len(s)
    memo = {}

    def backtrack(start, parts_left):
        key = (start, parts_left)
        if key in memo:
            return memo[key]
        if parts_left == 1:
            seg = s[start:]
            if seg and has_vowel(seg):
                return [seg]
            else:
                return None
        # heuristic: try longer first to avoid tiny prefixes (prefer natural syllables)
        best = None
        # maximum possible end to leave enough chars for remaining parts
        for end in range(L - (parts_left - 1), start, -1):
            seg = s[start:end]
            # each segment must contain a vowel
            if not has_vowel(seg):
                continue
            rest = backtrack(end, parts_left - 1)
            if rest is not None:
                candidate = [seg] + rest
                # prefer candidate where next segments start with consonant (more natural), compute score
                score = 0
                # +1 for each subsequent part that starts with consonant
                for r in candidate[1:]:
                    if r and is_consonant(r[0]):
                        score += 1
                # prefer higher score and prefer balanced lengths
                # We'll keep the first candidate with maximal score; for ties, keep existing
                if best is None:
                    best = (candidate, score)
                else:
                    if score > best[1]:
                        best = (candidate, score)
        memo[key] = best[0] if best else None
        return memo[key]

    parts = backtrack(0, ch_count)
    if parts:
        return parts

    # Fallback: even slicing
    total = len(s)
    if total == 0:
        return [''] * ch_count
    if ch_count > total:
        parts = list(s) + [''] * (ch_count - total)
        return parts
    avg = total // ch_count
    rem = total % ch_count
    parts = []
    i = 0
    for k in range(ch_count):
        take = avg + (1 if k < rem else 0)
        parts.append(s[i:i+take])
        i += take
    return parts


def get_pinyin_for_chinese(ch_text):
    """Return a space-separated pinyin string for a Chinese text using pypinyin if available."""
    if not ch_text:
        return ''
    if not HAVE_PYPINYIN:
        return ''
    try:
        toks = _pypinyin_pinyin(ch_text, style=_pypinyin_Style.TONE, errors='default')
        return ' '.join(t[0] for t in toks)
    except Exception:
        return ''


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
            # top may be a tuple (chinese, pinyin) or a string
            key = top[0] if isinstance(top, tuple) else top
            sentence_lookup_map[key] = bottom

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

    def top_text_for_measure(item):
        # item may be a string or a tuple (chinese, pinyin)
        if isinstance(item, tuple):
            ch, py = item
            return (ch + " " + py).strip()
        return str(item)

    # attempt to find a Chinese-capable font for measurements
    chinese_font_path = get_working_chinese_font() or font_path

    for top_sent, bottom_sent in sentence_pairs:
        # try adding this top sentence to the current page candidate and compute height using combined text and pinyin if present
        candidate_top_sentences = combined_top_sentences + [top_sent]
        top_combined_candidate = " ".join(top_text_for_measure(s) for s in candidate_top_sentences).strip()
        f_cand, lines_cand, lh_cand, total_h_cand = fit_sentence_font(top_combined_candidate, chinese_font_path if chinese_font_path else font_path, base_size, max_width)

        # compute pinyin height for candidate if any tuple entries present
        pinyin_text = " ".join([s[1] for s in candidate_top_sentences if isinstance(s, tuple) and s[1]])
        pinyin_h = 0
        if pinyin_text:
            p_font = ImageFont.truetype(font_path, max(10, base_size//2))
            p_lines = wrap_text_to_lines(pinyin_text, p_font, max_width)
            _, p_lh = get_text_dimensions("Ay", p_font)
            pinyin_h = len(p_lines) * (p_lh + 6)

        cand_total_h = total_h_cand + pinyin_h

        if combined_top_sentences and cand_total_h > max_height:
            # push current page built from combined_top_sentences
            top_combined_text = " ".join(top_text_for_measure(s) for s in combined_top_sentences).strip()
            f_top, lines_top, lh_top, total_h_top = fit_sentence_font(top_combined_text, chinese_font_path if chinese_font_path else font_path, base_size, max_width)

            # compute pinyin lines for the page
            page_pinyin_text = " ".join([s[1] for s in combined_top_sentences if isinstance(s, tuple) and s[1]])
            page_pinyin_lines = []
            if page_pinyin_text:
                p_font = ImageFont.truetype(font_path, max(10, base_size//2))
                page_pinyin_lines = wrap_text_to_lines(page_pinyin_text, p_font, max_width)

            pages.append({
                'top_lines': lines_top,
                'top_full_text': top_combined_text,
                'bottom_full_text': combined_bottom,
                'top_sentences': combined_top_sentences.copy(),
                'bottom_sentences': combined_bottom_sentences.copy(),
                'pinyin_lines': page_pinyin_lines
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
        top_combined_text = " ".join(top_text_for_measure(s) for s in combined_top_sentences).strip()
        f_top, lines_top, lh_top, total_h_top = fit_sentence_font(top_combined_text, chinese_font_path if chinese_font_path else font_path, base_size, max_width)
        page_pinyin_text = " ".join([s[1] for s in combined_top_sentences if isinstance(s, tuple) and s[1]])
        page_pinyin_lines = []
        if page_pinyin_text:
            p_font = ImageFont.truetype(font_path, max(10, base_size//2))
            page_pinyin_lines = wrap_text_to_lines(page_pinyin_text, p_font, max_width)
        pages.append({
            'top_lines': lines_top,
            'top_full_text': top_combined_text,
            'bottom_full_text': combined_bottom,
            'top_sentences': combined_top_sentences.copy(),
            'bottom_sentences': combined_bottom_sentences.copy(),
            'pinyin_lines': page_pinyin_lines
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

def preview_voice():
    """Synthesize a short preview using the selected voice and speed and play it."""
    try:
        selected_voice = VOICE_OPTIONS.get(voice_var.get(), list(VOICE_OPTIONS.values())[0])
        try:
            speed_percent = int(speed_var.get().strip('%'))
        except Exception:
            speed_percent = 100
        rate = f"{speed_percent - 100:+d}%"
        preview_file = "tts_preview.mp3"
        async def synth_preview():
            await edge_tts.Communicate("This is a voice preview.", selected_voice, rate=rate).save(preview_file)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(synth_preview())
        # play using default app (Windows) or open with system default
        if os.name == 'nt':
            os.startfile(preview_file)
        else:
            subprocess.run(["xdg-open", preview_file])
    except Exception as e:
        messagebox.showerror("Preview error", str(e))

def generate_video():
    txt_path = entry_path.get()
    if not os.path.exists(txt_path):
        messagebox.showwarning("Cảnh báo", "Vui lòng chọn file .txt!")
        return

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            raw = f.read().strip()

            # If the file uses pipe separators (e.g., Chinese|Pinyin|English per-line), parse per-line
            if '|' in raw:
                sentence_pairs = []
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                for line in lines:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) == 3:
                        # Chinese|Pinyin|English -> prefer auto-generated pinyin for Chinese tops
                        ch = parts[0]
                        if re.search(r'[\u4e00-\u9fff]', ch):
                            auto_py = get_pinyin_for_chinese(ch)
                            py_to_use = auto_py if auto_py else parts[1]
                            sentence_pairs.append(((ch, py_to_use), parts[2]))
                        else:
                            sentence_pairs.append(((parts[0], parts[1]), parts[2]))
                    elif len(parts) == 2:
                        # top|bottom -> if top is Chinese, generate pinyin
                        if re.search(r'[\u4e00-\u9fff]', parts[0]):
                            py = get_pinyin_for_chinese(parts[0])
                            sentence_pairs.append(((parts[0], py), parts[1]))
                        else:
                            sentence_pairs.append((parts[0], parts[1]))
                    elif len(parts) == 1:
                        # single column: decide by script detection
                        only = parts[0]
                        if re.search(r'[\u4e00-\u9fff]', only):
                            py = get_pinyin_for_chinese(only)
                            sentence_pairs.append(((only, py), ''))
                        else:
                            sentence_pairs.append(('', only))
            else:
                # Remove pipes so we can split into sentences reliably (legacy behavior)
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
            chinese_font_path = find_chinese_font() or font_path
            for s in top_sentences:
                if isinstance(s, tuple):
                    # s = (chinese_text, pinyin)
                    ch_text, py_text = s
                    f_s, lines_s, lh_s, _ = fit_sentence_font(ch_text, chinese_font_path, base_font_size, max_box_width)
                    # split pinyin tokens into per-character tokens when possible (use normalization heuristics)
                    p_tokens = normalize_pinyin_tokens(py_text, ch_text)
                    top_sentence_draws.append({'font': f_s, 'font_path': chinese_font_path, 'font_size': getattr(f_s, 'size', base_font_size), 'lines': lines_s, 'line_h': lh_s, 'is_chinese': True, 'pinyin_tokens': p_tokens})
                else:
                    f_s, lines_s, lh_s, _ = fit_sentence_font(s, font_path, base_font_size, max_box_width)
                    top_sentence_draws.append({'font': f_s, 'font_path': font_path, 'font_size': getattr(f_s, 'size', base_font_size), 'lines': lines_s, 'line_h': lh_s, 'is_chinese': False})

            # Build word list and sentence word counts (Chinese: per-character; others: per-space word)
            sent_word_counts = []
            for sdraw in top_sentence_draws:
                if sdraw.get('is_chinese'):
                    cnt = 0
                    for line in sdraw['lines']:
                        cnt += sum(1 for ch in line if not ch.isspace())
                    sent_word_counts.append(cnt)
                else:
                    sent_word_counts.append(sum(len(line.split()) for line in sdraw['lines']))
            total_top_words = sum(sent_word_counts)

                # --- Synthesize per-sentence TTS and compute frames-per-word distribution for this page ---
            page_word_frame_counts = []
            page_tts_files = []
            pinyins_for_page = []
            for s_idx, s_text in enumerate(top_sentences):
                # s_text may be a tuple (chinese, pinyin) or a plain string
                if isinstance(s_text, tuple):
                    ch_text, py_text = s_text
                    pinyins_for_page.append(py_text)
                else:
                    ch_text = s_text
                    py_text = ""

                # synthesize tts for this sentence into a temp file
                safe_name = f"tts_p{page_index}_s{s_idx}.mp3"
                try:
                    # honor GUI selections if present, otherwise fall back to automatic choice
                    selected_voice = VOICE_OPTIONS.get(voice_var.get()) if 'voice_var' in globals() else choose_voice(ch_text)
                    try:
                        speed_percent = int(speed_var.get().strip('%')) if 'speed_var' in globals() else 100
                    except Exception:
                        speed_percent = 100
                    rate = f"{speed_percent - 100:+d}%"  # e.g., 80% -> -20%

                    async def synth():
                        await edge_tts.Communicate(ch_text, selected_voice, rate=rate).save(safe_name)
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
                # ensure word_count is at least 1 to avoid division/modulo by zero
                word_count = sent_word_counts[s_idx] if s_idx < len(sent_word_counts) else 0
                if word_count <= 0:
                    word_count = 1
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

            # track per-sentence character position so we can map pinyin tokens to characters
            char_pos = {i: 0 for i in range(len(top_sentence_draws))}
            for s_idx, sdraw in enumerate(top_sentence_draws):
                f_s = sdraw['font']
                for s_line in sdraw['lines']:
                    if sdraw.get('is_chinese'):
                        # treat each non-space character as a token for highlighting and attach pinyin if available
                        for ch in s_line:
                            if ch.isspace():
                                continue
                            raw_w, raw_h = get_text_dimensions(ch, f_s)
                            pad = max(4, int(sdraw.get('font_size', getattr(f_s, 'size', base_font_size)) * 0.12))
                            ww = raw_w + pad
                            # compute glyph bounding box to get accurate visual width and left offset
                            try:
                                temp_img = Image.new('L', (raw_w + 40, raw_h + 40), color=255)
                                temp_draw = ImageDraw.Draw(temp_img)
                                temp_draw.text((20, 0), ch, font=f_s, fill=0)
                                bbox = temp_img.getbbox()
                                if bbox:
                                    glyph_x0 = bbox[0] - 20
                                    glyph_w = bbox[2] - bbox[0]
                                else:
                                    glyph_x0 = 0
                                    glyph_w = raw_w
                            except Exception:
                                glyph_x0 = 0
                                glyph_w = raw_w

                            # attempt to get corresponding pinyin token
                            p_token = None
                            p_tokens = sdraw.get('pinyin_tokens', [])
                            pos = char_pos.get(s_idx, 0)
                            if pos < len(p_tokens):
                                p_token = p_tokens[pos]
                            # build token with pinyin and font size for later use; include raw_width, pad and glyph metrics
                            item = {'word': ch, 'font': f_s, 'font_path': sdraw.get('font_path'), 'idx': global_idx, 'width': ww, 'raw_width': raw_w, 'pad': pad, 'glyph_x0': glyph_x0, 'glyph_width': glyph_w, 's_idx': s_idx, 'pinyin': p_token, 'font_size': sdraw.get('font_size', getattr(f_s, 'size', base_font_size))}
                            if current_width == 0 or current_width + ww <= max_box_width:
                                current_line.append(item)
                                current_width += ww
                            else:
                                lines_render.append(current_line)
                                current_line = [item]
                                current_width = ww
                            global_idx += 1
                            char_pos[s_idx] = pos + 1
                    else:
                        for w in s_line.split():
                            ww = get_text_dimensions(w + " ", f_s)[0]
                            # if the word fits on current line, append it, otherwise push current and start new line
                            if current_width == 0 or current_width + ww <= max_box_width:
                                current_line.append({'word': w, 'font': f_s, 'idx': global_idx, 'width': ww, 's_idx': s_idx, 'font_size': getattr(f_s, 'size', base_font_size)})
                                current_width += ww
                            else:
                                lines_render.append(current_line)
                                current_line = [{'word': w, 'font': f_s, 'idx': global_idx, 'width': ww, 's_idx': s_idx, 'font_size': getattr(f_s, 'size', base_font_size)}]
                                current_width = ww
                            global_idx += 1

            if current_line:
                lines_render.append(current_line)

            # prepare pinyin lines for this page (draw after Chinese lines)
            pinyin_lines = page.get('pinyin_lines', [])
            p_font = ImageFont.truetype(font_path, max(10, base_font_size//2)) if pinyin_lines else None

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

                    # draw words with active word in red and pinyin above each Chinese character when available
                    xt = 80

                    # Prepare a single pinyin font and baseline for this line so all pinyin share the same y position
                    p_fs_line = None
                    p_y_line = None
                    if any(item.get('pinyin') for item in line):
                        p_fs_size_line = max(max(10, int(item.get('font_size', base_font_size) * 0.45)) for item in line if item.get('pinyin'))
                        try:
                            p_fs_line = ImageFont.truetype('arial.ttf', p_fs_size_line)
                        except Exception:
                            try:
                                p_fs_line = ImageFont.truetype(font_path, p_fs_size_line)
                            except Exception:
                                p_fs_line = ImageFont.truetype(font_path, max(10, base_font_size//2))
                        _, p_h_line = get_text_dimensions("Ay", p_fs_line)
                        p_y_line = yt - p_h_line - 4

                    for item in line:
                        # determine char draw x: center the actual glyph inside the token's reserved width when possible
                        if 'raw_width' in item:
                            char_x = xt + (item['width'] - item['raw_width']) / 2
                        else:
                            char_x = xt

                        # draw per-token pinyin (centered above the actual glyph) if available
                        if item.get('pinyin') and p_fs_line:
                            p_text = item['pinyin']
                            p_w, p_h = get_text_dimensions(p_text, p_fs_line)
                            g_x0 = item.get('glyph_x0', 0)
                            g_w = item.get('glyph_width', item.get('raw_width', item['width']))
                            # glyph's absolute x is char_x + glyph_x0
                            p_x = char_x + g_x0 + (g_w - p_w) / 2
                            draw.text((int(p_x), int(p_y_line)), p_text, font=p_fs_line, fill=(0, 0, 0))

                        color = (255, 0, 0) if item['idx'] == w_idx else (0, 0, 0)
                        draw.text((int(char_x), yt), item['word'], font=item['font'], fill=color)
                        xt += item['width']

                    yt += line_h + 10

                # if we have per-token pinyin we already drew it; otherwise fall back to page-level pinyin lines
                any_token_pinyin = any(any(item.get('pinyin') for item in l) for l in lines_render)
                if not any_token_pinyin and pinyin_lines and p_font:
                    for pline in pinyin_lines:
                        lw, _ = get_text_dimensions(pline, p_font)
                        draw.text((400 - lw//2, yt), pline, font=p_font, fill=(0, 0, 0))
                        _, plh = get_text_dimensions("Ay", p_font)
                        yt += plh + 6

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
root.geometry("700x380")

# Audio settings in a clear boxed area so it's obvious
audio_frame = tk.LabelFrame(root, text="Audio Settings", padx=10, pady=8)
audio_frame.pack(pady=10, fill='x', padx=20)

tk.Label(audio_frame, text="Voice:").pack(side=tk.LEFT)
voice_var = tk.StringVar(value=list(VOICE_OPTIONS.keys())[0])
voice_menu = tk.OptionMenu(audio_frame, voice_var, *VOICE_OPTIONS.keys())
voice_menu.pack(side=tk.LEFT, padx=(6, 20))

tk.Label(audio_frame, text="Speed:").pack(side=tk.LEFT)
speed_var = tk.StringVar(value=SPEED_OPTIONS[0])
speed_menu = tk.OptionMenu(audio_frame, speed_var, *SPEED_OPTIONS)
speed_menu.pack(side=tk.LEFT, padx=6)

# Quick preview button (auditions selected voice+speed for short sample)
preview_btn = tk.Button(audio_frame, text="Preview Voice", command=lambda: preview_voice(), bg="#2196F3", fg="white")
preview_btn.pack(side=tk.RIGHT)

# Button to check which Chinese font is selected and whether it renders glyphs
check_font_btn = tk.Button(audio_frame, text="Check Chinese Font", command=lambda: check_chinese_font(), bg="#FF9800", fg="black")
check_font_btn.pack(side=tk.RIGHT, padx=(8,0))

# File selection
tk.Label(root, text="Chọn file text để tạo video:", font=("Arial", 11)).pack(pady=6)

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