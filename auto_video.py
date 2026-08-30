import os
import re
import asyncio
import sys
import time
import urllib.request
import edge_tts
from pydub import AudioSegment
from PIL import Image, ImageDraw, ImageFont

# 曉曼粵語 Neural 語音
VOICE = 'zh-HK-HiuMaanNeural'

# ⚡ 語速控制：'+20%' 舒服自然黃金語速
SPEECH_RATE = '+20%'

TAG_AUDIO_MAP = {
    '[雷雨]': 'thunder.mp3', '[雷聲]': 'thunder.mp3', '[雨聲雷鳴]': 'thunder.mp3',
    '[風雨雷電]': 'thunder.mp3', '[下雨]': 'rain.mp3', '[雨聲]': 'rain.mp3',
    '[海洋]': 'wave.mp3', '[海浪]': 'wave.mp3', '[海浪風鈴]': 'wave.mp3',
    '[柴火]': 'fire.mp3', '[溫暖]': 'fire.mp3', '[森林]': 'forest.mp3',
    '[森林鳥鳴]': 'forest.mp3', '[風鈴]': 'windbell.mp3',
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

def draw_static_frame(img_path, title_text, subtitle_phrase):
    """生成穩定高清靜態畫面"""
    try:
        font_file = download_chinese_font()
        img = Image.open(img_path).convert("RGBA")
        width, height = img.size

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

        out_img = f"static_frame.png"
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
            communicate = edge_tts.Communicate(clean_text, VOICE, rate=SPEECH_RATE)
            await communicate.save(output_mp3)
            if os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 1000:
                return True
        except Exception:
            await asyncio.sleep(3)
    return False

def process_script_and_audio(text_file, output_audio_filename):
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()

    script_data = []
    current_bgm = 'calm'
    current_sfx_list = []
    
    raw_sections = re.split(r'(\[IMG\s*:\s*.*?\])', content)
    img_idx = 0
    combined_voice = AudioSegment.silent(duration=0)
    
    print(f"🔊 正在以 +20% 語速 ({SPEECH_RATE}) 分析曉曼語音，並進行全程無縫音效混音...")
    created_temp_files = []

    for section in raw_sections:
        if not section.strip(): continue
        
        img_match = re.search(r'\[IMG\s*:\s*(.*?)\]', section, re.IGNORECASE)
        if img_match:
            img_idx += 1
            current_sfx_list = []
            continue
            
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        for line in lines:
            bgm_m = re.search(r'\[BGM\s*:\s*(happy|calm|sad)\]', line, re.IGNORECASE)
            if bgm_m:
                current_bgm = bgm_m.group(1).lower()
                line = re.sub(r'\[BGM\s*:\s*(happy|calm|sad)\]', '', line, re.IGNORECASE).strip()
            
            if not line: continue
            
            found_tags = re.findall(r'\[.*?\]', line)
            valid_tags = [t for t in found_tags if t in TAG_AUDIO_MAP]
            if valid_tags:
                current_sfx_list = list(set(current_sfx_list + valid_tags))
                continue
                
            if re.match(r'\[TITLE\s*:', line, re.IGNORECASE): continue

            phrases = [p.strip() for p in re.split(r'(?<=……)\s*', line) if p.strip()]
            for p in phrases:
                temp_f = f"temp_phrase_{len(script_data)}.mp3"
                created_temp_files.append(temp_f)
                success = asyncio.run(generate_tts(p, temp_f))
                
                if success and os.path.exists(temp_f):
                    raw_audio = AudioSegment.from_file(temp_f)
                    dur_ms = len(raw_audio) + 700
                    combined_voice += raw_audio + AudioSegment.silent(duration=700)
                    script_data.append({
                        'img_idx': max(img_idx, 1),
                        'phrase': p,
                        'duration': dur_ms / 1000.0,
                        'sfx_list': list(current_sfx_list)
                    })

    for tf in created_temp_files:
        if os.path.exists(tf): os.remove(tf)

    total_duration = len(combined_voice)
    if total_duration == 0: return False, []

    # BGM 全程長播
    bgm_filename = MUSIC_MAP.get(current_bgm, 'music_calm.mp3')
    if os.path.exists(bgm_filename):
        raw_bgm = AudioSegment.from_file(bgm_filename)
        raw_bgm = raw_bgm.apply_gain(-22.0 - raw_bgm.dBFS)
        combined_bgm = (raw_bgm * (int(total_duration / len(raw_bgm)) + 2))[:total_duration]
    else:
        combined_bgm = AudioSegment.silent(duration=total_duration)

    # 🎛️ 完美解決方案：音效無縫連續長播（絕不因語音停頓而卡頓）
    combined_sfx = AudioSegment.silent(duration=0)
    for item in script_data:
        dur_ms = int(item['duration'] * 1000)
        tags = item['sfx_list']
        
        phrase_sfx_mix = AudioSegment.silent(duration=dur_ms)
        if tags:
            for tag in tags:
                sfx_file = TAG_AUDIO_MAP.get(tag)
                if sfx_file and os.path.exists(sfx_file):
                    snd = AudioSegment.from_file(sfx_file) - 20
                    # 計算長度循環鋪滿，確保連停頓位都有自然音效
                    loop_snd = (snd * (int(dur_ms / len(snd)) + 5))[:dur_ms]
                    phrase_sfx_mix = phrase_sfx_mix.overlay(loop_snd)
        
        combined_sfx += phrase_sfx_mix

    final_mix = combined_bgm.overlay(combined_sfx).overlay(combined_voice, position=1000)
    final_mix.export(output_audio_filename, format="mp3")
    print(f"🎉 音效全程無縫流暢版廣播劇合成完成: {output_audio_filename}")
    return True, script_data

def generate_multi_image_mp4(audio_file, video_output, script_data):
    try:
        try:
            from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
        except ImportError:
            from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        audio_clip = AudioFileClip(audio_file)
        title_text = "創世記 第一章"
        all_clips = []
        
        print("🎬 正在壓製影片...")

        for item in script_data:
            img_num = item['img_idx']
            phrase = item['phrase']
            p_dur = item['duration']

            base_img_path = f"{img_num}.png"
            if not os.path.exists(base_img_path): base_img_path = f"pic{img_num}.png"
            if not os.path.exists(base_img_path): base_img_path = '1.png' if os.path.exists('1.png') else 'cover.png'

            frame_path = draw_static_frame(base_img_path, title_text, phrase)

            try:
                sub_clip = ImageClip(frame_path).with_duration(p_dur)
            except AttributeError:
                sub_clip = ImageClip(frame_path).set_duration(p_dur)

            all_clips.append(sub_clip)

        final_video = concatenate_videoclips(all_clips, method="compose")
        try: final_video = final_video.with_audio(audio_clip)
        except AttributeError: final_video = final_video.set_audio(audio_clip)

        final_video.write_videofile(video_output, fps=24, codec='libx264', audio_codec='aac')
        print(f"✅ 成功生成流暢版廣播劇影片: {video_output}")

        audio_clip.close()
        final_video.close()
        if os.path.exists(audio_file): os.remove(audio_file)

    except Exception as e:
        print(f"⚠️ MP4 壓製失敗: {e}")

if __name__ == "__main__":
    script_file = "video.txt"
    temp_audio = "temp_full_mix.mp3"
    output_video = "genesis_ch1_Pgirl_static.mp4"

    if os.path.exists(script_file):
        success, script_data = process_script_and_audio(script_file, temp_audio)
        if success and os.path.exists(temp_audio):
            generate_multi_image_mp4(temp_audio, output_video, script_data)
