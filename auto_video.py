import os
import re
import asyncio
import sys
import time
import urllib.request
import edge_tts
from pydub import AudioSegment
from PIL import Image, ImageDraw, ImageFont

# 廣東話配音：預設 P女 (曉曼)
VOICE = 'zh-HK-HiuMaanNeural'

# 大自然環境音效對應表
TAG_AUDIO_MAP = {
    '[雷雨]': 'thunder.mp3',
    '[雷聲]': 'thunder.mp3',
    '[雨聲雷鳴]': 'thunder.mp3',
    '[風雨雷電]': 'thunder.mp3',
    '[下雨]': 'rain.mp3',
    '[雨聲]': 'rain.mp3',
    '[海洋]': 'wave.mp3',
    '[海浪]': 'wave.mp3',
    '[海浪風鈴]': 'wave.mp3',
    '[柴火]': 'fire.mp3',
    '[溫暖]': 'fire.mp3',
    '[森林]': 'forest.mp3',
    '[天地]': 'forest.mp3',
    '[森林鳥鳴]': 'forest.mp3',
    '[風鈴]': 'windbell.mp3',
    '[海鳥]': 'windbell.mp3',
    '[溪流]': 'stream.mp3',
    '[流水]': 'stream.mp3',
    '[戰爭]': 'war.mp3',
    '[交戰]': 'war.mp3',
    '[洞穴]': 'cave.mp3',
    '[水滴]': 'cave.mp3'
}

# 背景音樂 BGM 對應表
MUSIC_MAP = {
    'happy': 'music_happy.mp3',
    'sad': 'music_sad.mp3',
    'calm': 'music_calm.mp3'
}

def download_chinese_font():
    """自動下載標準高清中文字型"""
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

def add_small_watermark(img_path):
    """喺圖片左上角加上細細個嘅「招牌」水印"""
    try:
        font_file = download_chinese_font()
        img = Image.open(img_path).convert("RGBA")
        width, height = img.size

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        
        box_w = int(width * 0.28)
        box_h = int(height * 0.06)
        margin = int(height * 0.02)
        
        draw_overlay.rounded_rectangle(
            [(margin, margin), (margin + box_w, margin + box_h)],
            radius=10,
            fill=(0, 0, 0, 150)
        )
        
        img = Image.alpha_composite(img, overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        font_size = int(height * 0.03)
        font = ImageFont.truetype(font_file, font_size) if font_file else ImageFont.load_default()
        
        brand_text = "★ 廣東話聖經劇場 ★"
        text_x = margin + (box_w / 2)
        text_y = margin + (box_h / 2)
        
        draw.text((text_x, text_y), brand_text, font=font, fill=(255, 215, 0), anchor="mm")

        out_watermarked = f"wm_{img_path}"
        img.save(out_watermarked)
        return out_watermarked
    except Exception as e:
        print(f"⚠️ 水印繪製失敗 ({img_path}): {e}")
        return img_path

async def generate_tts(text, output_mp3):
    clean_text = re.sub(r'\[.*?\]', '', text).strip()
    if not clean_text:
        return False

    for attempt in range(8):
        try:
            communicate = edge_tts.Communicate(clean_text, VOICE, rate='-20%')
            await communicate.save(output_mp3)
            if os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 1000:
                print(f"✅ [廣東話 TTS] 語音合成成功！")
                return True
        except Exception as e:
            print(f"⚠️ 語音生成重試第 {attempt+1} 次...")
            await asyncio.sleep(3)
    return False

def mix_chapter_audio(text_file, output_audio_filename):
    """【音樂最高權重不中斷版】：BGM 由頭播到尾，大自然音效持續，換圖完全不影響音訊"""
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
                if clean_part in TAG_AUDIO_MAP:
                    current_sfx_tag = clean_part
                else:
                    parsed_segments.append((current_sfx_tag, clean_part, current_bgm_type))
        elif part in TAG_AUDIO_MAP:
            current_sfx_tag = part
        elif not re.match(r'\[TITLE\s*:', part, re.IGNORECASE) and not re.match(r'\[IMG\s*:', part, re.IGNORECASE):
            parsed_segments.append((current_sfx_tag, part.strip(), current_bgm_type))

    if not parsed_segments:
        parsed_segments = [(None, raw_content.strip(), 'calm')]

    combined_voice = AudioSegment.silent(duration=0)
    created_temp_files = []
    segment_durations = []

    print(f"🔊 正在合成廣東話配音...")

    for idx, (sfx_tag, text_tts, bgm_type) in enumerate(parsed_segments):
        seg_dur = 0
        if text_tts:
            temp_file = f"temp_tts_{idx}.mp3"
            created_temp_files.append(temp_file)
            success = asyncio.run(generate_tts(text_tts, temp_file))
            if success and os.path.exists(temp_file):
                raw_voice = AudioSegment.from_file(temp_file)
                combined_voice += raw_voice + AudioSegment.silent(duration=1500)
                seg_dur = len(raw_voice) + 1500

        segment_durations.append((seg_dur, sfx_tag, bgm_type))

    for t_file in created_temp_files:
        if os.path.exists(t_file):
            os.remove(t_file)

    total_duration = len(combined_voice)
    if total_duration == 0:
        print(f"❌ 語音生成失敗。")
        return False

    # 1. 建立一條【完全連續不間斷】的 BGM 背景音樂大音軌
    print(f"🎵 正在構建不間斷長播背景音樂音軌 (總長度: {total_duration / 1000:.1f} 秒)...")
    
    # 預設首選音樂
    first_bgm_type = segment_durations[0][2] if segment_durations else 'calm'
    bgm_filename = MUSIC_MAP.get(first_bgm_type, 'music_calm.mp3')
    
    if os.path.exists(bgm_filename):
        raw_bgm = AudioSegment.from_file(bgm_filename)
        raw_bgm = raw_bgm.apply_gain(-22.0 - raw_bgm.dBFS)
        # 循環複製整首音樂直到涵蓋總長度，確保 100% 不斷音
        loop_count = int(total_duration / len(raw_bgm)) + 2
        combined_bgm = (raw_bgm * loop_count)[:total_duration]
    else:
        combined_bgm = AudioSegment.silent(duration=total_duration)

    # 2. 建立大自然音效音軌 (SFX)
    combined_sfx = AudioSegment.silent(duration=0)
    for dur, sfx_tag, bgm_type in segment_durations:
        if dur > 0 and sfx_tag and sfx_tag in TAG_AUDIO_MAP:
            sfx_filename = TAG_AUDIO_MAP[sfx_tag]
            if os.path.exists(sfx_filename):
                snd = AudioSegment.from_file(sfx_filename)
                snd_looped = (snd * (int(dur / len(snd)) + 2))[:dur] - 20
                combined_sfx += snd_looped
            else:
                combined_sfx += AudioSegment.silent(duration=dur)
        else:
            combined_sfx += AudioSegment.silent(duration=dur)

    # 3. 三軌融合：BGM (最高權重不間斷) + SFX + 廣東話語音
    final_mix = combined_bgm.overlay(combined_sfx).overlay(combined_voice, position=1000)
    final_mix.export(output_audio_filename, format="mp3")
    print(f"🎉 聲音總合成完成（BGM 完全連續長播無中斷）: {output_audio_filename}")
    return True

def generate_multi_image_mp4(audio_file, video_output, text_file="video.txt"):
    """多圖慢推 + 1秒Crossfade淡入淡出 + 左上角細細個招牌水印"""
    try:
        try:
            from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
        except ImportError:
            from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        audio_clip = AudioFileClip(audio_file)
        total_duration = audio_clip.duration

        with open(text_file, 'r', encoding='utf-8') as f:
            content = f.read()

        img_tags = re.findall(r'\[IMG\s*:\s*(.*?)\]', content, re.IGNORECASE)
        num_images = len(img_tags) if img_tags else 7
        dur_per_img = total_duration / num_images

        clips = []
        print(f"🎬 正在壓製 7 張動態幻燈片影片 (總長 {total_duration:.1f} 秒)...")
        
        for idx in range(1, num_images + 1):
            base_img = f"{idx}.png"
            if not os.path.exists(base_img):
                base_img = f"pic{idx}.png"
            if not os.path.exists(base_img):
                base_img = '1.png' if os.path.exists('1.png') else 'cover.png'

            # 加上左上角細招牌水印
            watermarked_img = add_small_watermark(base_img)

            try:
                img_clip = ImageClip(watermarked_img).with_duration(dur_per_img)
                img_clip = img_clip.resized(lambda t: 1 + 0.05 * (t / dur_per_img))
            except AttributeError:
                img_clip = ImageClip(watermarked_img).set_duration(dur_per_img)
                img_clip = img_clip.resize(lambda t: 1 + 0.05 * (t / dur_per_img))

            # 淡入淡出轉場
            if idx > 1:
                try:
                    img_clip = img_clip.crossfadein(1.0)
                except Exception:
                    pass

            clips.append(img_clip)

        final_video = concatenate_videoclips(clips, method="compose")

        try:
            final_video = final_video.with_audio(audio_clip)
        except AttributeError:
            final_video = final_video.set_audio(audio_clip)

        final_video.write_videofile(video_output, fps=24, codec='libx264', audio_codec='aac')
        print(f"✅ 成功生成廣東話劇場影片: {video_output}")

        audio_clip.close()
        final_video.close()
        if os.path.exists(audio_file):
            os.remove(audio_file)

    except Exception as e:
        print(f"⚠️ MP4 影片壓製失敗: {e}")

if __name__ == "__main__":
    script_file = "video.txt"
    temp_audio = "temp_full_mix.mp3"
    output_video = "genesis_ch13_Pgirl.mp4"

    if os.path.exists(script_file):
        success = mix_chapter_audio(script_file, temp_audio)
        if success and os.path.exists(temp_audio):
            generate_multi_image_mp4(temp_audio, output_video, script_file)
