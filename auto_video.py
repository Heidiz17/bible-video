import os
import re
import asyncio
import sys
import time
import urllib.request
import edge_tts
from pydub import AudioSegment
from PIL import Image, ImageDraw, ImageFont

VOICE = 'zh-HK-HiuMaanNeural'

TAG_AUDIO_MAP = {
    '[雷雨]': 'thunder.mp3', '[雷聲]': 'thunder.mp3', '[雨聲雷鳴]': 'thunder.mp3',
    '[風雨雷電]': 'thunder.mp3', '[下雨]': 'rain.mp3', '[雨聲]': 'rain.mp3',
    '[海洋]': 'wave.mp3', '[海浪]': 'wave.mp3', '[海浪風鈴]': 'wave.mp3',
    '[柴火]': 'fire.mp3', '[溫暖]': 'fire.mp3', '[森林]': 'forest.mp3',
    '[天地]': 'forest.mp3', '[森林鳥鳴]': 'forest.mp3', '[風鈴]': 'windbell.mp3',
    '[海鳥]': 'windbell.mp3', '[溪流]': 'stream.mp3', '[流水]': 'stream.mp3',
    '[戰爭]': 'war.mp3', '[交戰]': 'war.mp3', '[洞穴]': 'cave.mp3', '[水滴]': 'cave.mp3'
}

MUSIC_MAP = {
    'happy': 'music_happy.mp3',
    'sad': 'music_sad.mp3',
    'calm': 'music_calm.mp3'
}

def download_chinese_font():
    font_path = "CustomFont.ttf"
    if not os.path.exists(font_path):
        print("📥 正在下載中文字型檔 (Noto Sans CJK)...")
        font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChineseHK/NotoSansCJKhk-Bold.otf"
        try:
            urllib.request.urlretrieve(font_url, font_path)
            print("✅ 字型下載完成！")
        except Exception as e:
            print(f"⚠️ 字型下載失敗: {e}")
    return font_path if os.path.exists(font_path) else None

def draw_frame(img_path, title_text, subtitle_phrase, zoom_factor=1.0):
    try:
        font_file = download_chinese_font()
        img = Image.open(img_path).convert("RGBA")
        width, height = img.size

        if zoom_factor != 1.0:
            new_w, new_h = int(width * zoom_factor), int(height * zoom_factor)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - width) // 2
            top = (new_h - height) // 2
            img = img.crop((left, top, left + width, top + height))

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        
        margin = int(height * 0.02)
        box_w, box_h = int(width * 0.32), int(height * 0.12)
        draw_overlay.rounded_rectangle([(margin, margin), (margin + box_w, margin + box_h)], radius=12, fill=(0, 0, 0, 170))

        if subtitle_phrase:
            sub_h = int(height * 0.11)
            draw_overlay.rectangle([(0, height - sub_h), (width, height)], fill=(0, 0, 0, 185))

        img = Image.alpha_composite(img, overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        font_brand = ImageFont.truetype(font_file, int(height * 0.032)) if font_file else ImageFont.load_default()
        font_title = ImageFont.truetype(font_file, int(height * 0.038)) if font_file else ImageFont.load_default()
        font_sub = ImageFont.truetype(font_file, int(height * 0.042)) if font_file else ImageFont.load_default()

        center_x = margin + (box_w / 2)
        draw.text((center_x, margin + (box_h * 0.28)), "★ 廣東話聖經劇場 ★", font=font_brand, fill=(255, 215, 0), anchor="mm")
        draw.text((center_x, margin + (box_h * 0.72)), title_text, font=font_title, fill=(255, 255, 255), anchor="mm")
            
        if subtitle_phrase:
            clean_sub = re.sub(r'\[.*?\]', '', subtitle_phrase).strip()
            draw.text((width / 2, height - (int(height * 0.11) / 2)), clean_sub, font=font_sub, fill=(255, 255, 255), anchor="mm")

        out_img = f"dyn_frame.png"
        img.save(out_img)
        return out_img
    except Exception as e:
        print(f"⚠️ 畫面繪製失敗: {e}")
        return img_path

async def generate_tts(text, output_mp3):
    clean_text = re.sub(r'\[.*?\]', '', text).strip()
    if not clean_text: return False
    for attempt in range(8):
        try:
            communicate = edge_tts.Communicate(clean_text, VOICE, rate='-20%')
            await communicate.save(output_mp3)
            if os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 1000:
                return True
        except Exception:
            await asyncio.sleep(3)
    return False

def mix_chapter_audio(text_file, output_audio_filename):
    with open(text_file, 'r', encoding='utf-8') as f:
        raw_content = f.read()

    pattern_sfx = r'(\[雷雨\]|\[雷聲\]|\[雨聲雷鳴\]|\[風雨雷電\]|\[下雨\]|\[雨聲\]|\[海洋\]|\[海浪\]|\[海浪風鈴\]|\[柴火\]|\[溫暖\]|\[森林\]|\[天地\]|\[森林鳥鳴\]|\[風鈴\]|\[海鳥\]|\[溪流\]|\[流水\]|\[戰爭\]|\[交戰\]|\[洞穴\]|\[水滴\])'
    parts = re.split(pattern_sfx, raw_content)

    parsed_segments = []
    current_bgm_type = 'calm'
    current_sfx_tag = None

    for part in parts:
        if not part.strip(): continue
        bgm_match = re.search(r'\[BGM\s*:\s*(happy|calm|sad)\]', part, re.IGNORECASE)
        if bgm_match:
            current_bgm_type = bgm_match.group(1).lower()
            clean_part = re.sub(r'\[BGM\s*:\s*(happy|calm|sad)\]', '', part, re.IGNORECASE).strip()
            if clean_part:
                if clean_part in TAG_AUDIO_MAP: current_sfx_tag = clean_part
                else: parsed_segments.append((current_sfx_tag, clean_part, current_bgm_type))
        elif part in TAG_AUDIO_MAP:
            current_sfx_tag = part
        elif not re.match(r'\[TITLE\s*:', part, re.IGNORECASE) and not re.match(r'\[IMG\s*:', part, re.IGNORECASE):
            parsed_segments.append((current_sfx_tag, part.strip(), current_bgm_type))

    combined_voice = AudioSegment.silent(duration=0)
    created_temp_files = []
    segment_durations = []

    for idx, (sfx_tag, text_tts, bgm_type) in enumerate(parsed_segments):
        seg_dur = 0
        if text_tts:
            temp_file = f"temp_tts_{idx}.mp3"
            created_temp_files.append(temp_file)
            success = asyncio.run(generate_tts(text_tts, temp_file))
            if success and os.path.exists(temp_file):
                raw_voice = AudioSegment.from_file(temp_file)
                combined_voice += raw_voice + AudioSegment.silent(duration=1200)
                seg_dur = len(raw_voice) + 1200
        segment_durations.append((seg_dur, sfx_tag, bgm_type))

    for t_file in created_temp_files:
        if os.path.exists(t_file): os.remove(t_file)

    total_duration = len(combined_voice)
    if total_duration == 0: return False

    first_bgm_type = segment_durations[0][2] if segment_durations else 'calm'
    bgm_filename = MUSIC_MAP.get(first_bgm_type, 'music_calm.mp3')
    if os.path.exists(bgm_filename):
        raw_bgm = AudioSegment.from_file(bgm_filename)
        raw_bgm = raw_bgm.apply_gain(-22.0 - raw_bgm.dBFS)
        combined_bgm = (raw_bgm * (int(total_duration / len(raw_bgm)) + 2))[:total_duration]
    else:
        combined_bgm = AudioSegment.silent(duration=total_duration)

    combined_sfx = AudioSegment.silent(duration=0)
    for dur, sfx_tag, bgm_type in segment_durations:
        if dur > 0 and sfx_tag and sfx_tag in TAG_AUDIO_MAP and os.path.exists(TAG_AUDIO_MAP[sfx_tag]):
            snd = AudioSegment.from_file(TAG_AUDIO_MAP[sfx_tag])
            combined_sfx += (snd * (int(dur / len(snd)) + 2))[:dur] - 20
        else:
            combined_sfx += AudioSegment.silent(duration=dur)

    final_mix = combined_bgm.overlay(combined_sfx).overlay(combined_voice, position=1000)
    final_mix.export(output_audio_filename, format="mp3")
    return True

def generate_multi_image_mp4(audio_file, video_output, text_file="video.txt"):
    """相容圖片 Slow Push，並根據配音字數與停頓時間，做到 1:1 字幕語音精準同步"""
    try:
        try:
            from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
        except ImportError:
            from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        audio_clip = AudioFileClip(audio_file)
        total_duration = audio_clip.duration
        title_text = "創世記 第一章"

        with open(text_file, 'r', encoding='utf-8') as f:
            content = f.read()

        img_blocks = re.split(r'\[IMG\s*:\s*.*?\]', content)
        img_tags = re.findall(r'\[IMG\s*:\s*(.*?)\]', content, re.IGNORECASE)
        num_images = len(img_tags) if img_tags else 7
        dur_per_img = total_duration / num_images

        all_clips = []
        print(f"🎬 正在壓製相片慢推 + 廣東話字幕精準對齊影片...")

        for idx in range(1, num_images + 1):
            base_img = f"{idx}.png"
            if not os.path.exists(base_img): base_img = f"pic{idx}.png"
            if not os.path.exists(base_img): base_img = '1.png' if os.path.exists('1.png') else 'cover.png'

            blk_text = img_blocks[idx] if idx < len(img_blocks) else ""
            clean_blk = re.sub(r'\[.*?\]', '', blk_text).strip()
            
            lines = [line.strip() for line in clean_blk.split('\n') if line.strip()]
            phrases = []
            for line in lines:
                sub_parts = re.split(r'(?<=……)\s*', line)
                for sp in sub_parts:
                    if sp.strip(): phrases.append(sp.strip())

            if not phrases: phrases = [clean_blk] if clean_blk else ["創世記 第一章"]

            # 根據字數與停頓加權計算字幕停留時間，防止跑快
            phrase_weights = []
            for p in phrases:
                w = len(p) + (p.count('……') * 4) + (p.count('，') * 2) + (p.count('。') * 2)
                phrase_weights.append(max(w, 3))
            
            total_w = sum(phrase_weights)

            # 相片慢推 + 精準字幕
            for p_idx, phrase in enumerate(phrases):
                p_dur = (phrase_weights[p_idx] / total_w) * dur_per_img
                
                zoom_start = 1 + 0.04 * ((p_idx) / len(phrases))
                frame_path = draw_frame(base_img, title_text, phrase, zoom_factor=zoom_start)
                
                try:
                    sub_clip = ImageClip(frame_path).with_duration(p_dur)
                except AttributeError:
                    sub_clip = ImageClip(frame_path).set_duration(p_dur)
                
                all_clips.append(sub_clip)

        final_video = concatenate_videoclips(all_clips, method="compose")
        try: final_video = final_video.with_audio(audio_clip)
        except AttributeError: final_video = final_video.set_audio(audio_clip)

        final_video.write_videofile(video_output, fps=24, codec='libx264', audio_codec='aac')
        print(f"✅ 成功生成純相片精準對齊字幕影片: {video_output}")

        audio_clip.close()
        final_video.close()
        if os.path.exists(audio_file): os.remove(audio_file)

    except Exception as e:
        print(f"⚠️ MP4 壓製失敗: {e}")

if __name__ == "__main__":
    script_file = "video.txt"
    temp_audio = "temp_full_mix.mp3"
    output_video = "genesis_ch1_Pgirl.mp4"

    if os.path.exists(script_file):
        success = mix_chapter_audio(script_file, temp_audio)
        if success and os.path.exists(temp_audio):
            generate_multi_image_mp4(temp_audio, output_video, script_file)
