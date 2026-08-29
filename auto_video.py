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

def draw_static_frame(img_path, title_text, subtitle_phrase):
    """生成穩定高清靜態畫面，絕不閃爍縮放"""
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
            communicate = edge_tts.Communicate(clean_text, VOICE, rate='-20%')
            await communicate.save(output_mp3)
            if os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 1000:
                return True
        except Exception:
            await asyncio.sleep(3)
    return False

def process_script_and_audio(text_file, output_audio_filename):
    """精準分析聲音時間，音效與 BGM 皆由頭連貫播到尾"""
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()

    script_data = []
    current_bgm = 'calm'
    first_sfx_tag = None
    
    raw_sections = re.split(r'(\[IMG\s*:\s*.*?\])', content)
    img_idx = 0
    combined_voice = AudioSegment.silent(duration=0)
    
    print("🔊 正在精準分析曉曼語音，並設定音效長播連貫...")
    created_temp_files = []

    for section in raw_sections:
        if not section.strip(): continue
        
        img_match = re.search(r'\[IMG\s*:\s*(.*?)\]', section, re.IGNORECASE)
        if img_match:
            img_idx += 1
            continue
            
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        for line in lines:
            bgm_m = re.search(r'\[BGM\s*:\s*(happy|calm|sad)\]', line, re.IGNORECASE)
            if bgm_m:
                current_bgm = bgm_m.group(1).lower()
                line = re.sub(r'\[BGM\s*:\s*(happy|calm|sad)\]', '', line, re.IGNORECASE).strip()
            
            if not line: continue
            
            # 抓取第一個出現的大自然音效標籤，作全程連貫播放
            if line in TAG_AUDIO_MAP:
                if not first_sfx_tag:
                    first_sfx_tag = line
                continue
                
            if re.match(r'\[TITLE\s*:', line, re.IGNORECASE): continue

            phrases = [p.strip() for p in re.split(r'(?<=……)\s*', line) if p.strip()]
            for p in phrases:
                temp_f = f"temp_phrase_{len(script_data)}.mp3"
                created_temp_files.append(temp_f)
                success = asyncio.run(generate_tts(p, temp_f))
                
                if success and os.path.exists(temp_f):
                    raw_audio = AudioSegment.from_file(temp_f)
                    dur_ms = len(raw_audio) + 1000
                    combined_voice += raw_audio + AudioSegment.silent(duration=1000)
                    script_data.append({
                        'img_idx': max(img_idx, 1),
                        'phrase': p,
                        'duration': dur_ms / 1000.0
                    })

    for tf in created_temp_files:
        if os.path.exists(tf): os.remove(tf)

    total_duration = len(combined_voice)
    if total_duration == 0: return False, []

    # 1. BGM 連續長播
    bgm_filename = MUSIC_MAP.get(current_bgm, 'music_calm.mp3')
    if os.path.exists(bgm_filename):
        raw_bgm = AudioSegment.from_file(bgm_filename)
        raw_bgm = raw_bgm.apply_gain(-22.0 - raw_bgm.dBFS)
        combined_bgm = (raw_bgm * (int(total_duration / len(raw_bgm)) + 2))[:total_duration]
    else:
        combined_bgm = AudioSegment.silent(duration=total_duration)

    # 2. SFX 大自然音效全程連續長播（絕不每句中斷！）
    if first_sfx_tag and first_sfx_tag in TAG_AUDIO_MAP and os.path.exists(TAG_AUDIO_MAP[first_sfx_tag]):
        snd = AudioSegment.from_file(TAG_AUDIO_MAP[first_sfx_tag]) - 20
        combined_sfx = (snd * (int(total_duration / len(snd)) + 2))[:total_duration]
    else:
        combined_sfx = AudioSegment.silent(duration=total_duration)

    final_mix = combined_bgm.overlay(combined_sfx).overlay(combined_voice, position=1000)
    final_mix.export(output_audio_filename, format="mp3")
    print(f"🎉 聲音完全連貫合成完成: {output_audio_filename}")
    return True, script_data

def generate_multi_image_mp4(audio_file, video_output, script_data):
    """壓製乾淨純靜態畫面 + 1:1 同步字幕影片"""
    try:
        try:
            from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
        except ImportError:
            from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        audio_clip = AudioFileClip(audio_file)
        title_text = "創世記 第一章"
        all_clips = []
        
        print("🎬 正在壓製【純靜態乾淨畫面 + 完全連貫音效】影片...")

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
        print(f"✅ 成功生成完美乾淨版廣播劇影片: {video_output}")

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
        success, script_data = process_script_and_audio(script_file, temp_audio)
        if success and os.path.exists(temp_audio):
            generate_multi_image_mp4(temp_audio, output_video, script_data)
