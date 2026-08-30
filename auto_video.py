import os
import re
import asyncio
import urllib.request
import edge_tts
from pydub import AudioSegment
from PIL import Image, ImageDraw, ImageFont

VOICE = 'zh-HK-HiuMaanNeural'
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
        font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChineseHK/NotoSansCJKhk-Bold.otf"
        try:
            urllib.request.urlretrieve(font_url, font_path)
        except Exception:
            pass
    return font_path if os.path.exists(font_path) else None

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
    if not os.path.exists(text_file):
        return False, []
        
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()

    script_data = []
    current_bgm = 'calm'
    raw_sections = re.split(r'(\[IMG\s*:\s*.*?\])', content)
    img_idx = 0
    combined_voice = AudioSegment.silent(duration=0)
    created_temp_files = []
    scene_info = [] # 記錄每個景嘅時長

    current_scene_dur = 0
    current_sfx_list = []

    for section in raw_sections:
        if not section.strip(): continue
        img_match = re.search(r'\[IMG\s*:\s*(.*?)\]', section, re.IGNORECASE)
        if img_match:
            if img_idx > 0:
                scene_info.append({'img_idx': img_idx, 'duration': current_scene_dur / 1000.0})
                current_scene_dur = 0
            img_idx += 1
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
                    current_scene_dur += dur_ms
                    script_data.append({'phrase': p})

    if current_scene_dur > 0:
        scene_info.append({'img_idx': max(img_idx, 1), 'duration': current_scene_dur / 1000.0})

    for tf in created_temp_files:
        if os.path.exists(tf): os.remove(tf)

    total_duration = len(combined_voice)
    if total_duration == 0: return False, [], []

    bgm_filename = MUSIC_MAP.get(current_bgm, 'music_calm.mp3')
    if os.path.exists(bgm_filename):
        raw_bgm = AudioSegment.from_file(bgm_filename)
        raw_bgm = raw_bgm.apply_gain(-26.0 - raw_bgm.dBFS)
        combined_bgm = (raw_bgm * (int(total_duration / len(raw_bgm)) + 2))[:total_duration]
        combined_bgm = combined_bgm.fade_out(1500)
    else:
        combined_bgm = AudioSegment.silent(duration=total_duration)

    final_mix = combined_bgm.overlay(combined_voice, position=1000)
    final_mix.export(output_audio_filename, format="mp3")
    return True, scene_info, script_data

def generate_genesis_chapter1(audio_file, video_output, scene_info):
    try:
        from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips, ImageClip
    except ImportError:
        from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips, ImageClip

    audio_clip = AudioFileClip(audio_file)
    scene_clips = []

    print("🎬 正在順序組合創世記第一章嘅 7 個場景影片...")

    for scene in scene_info:
        idx = scene['img_idx']
        target_dur = scene['duration'] # 呢個場景配音需要的秒數
        
        v_path = f"{idx}.mp4" # 對應 1.mp4, 2.mp4 ... 7.mp4
        if os.path.exists(v_path):
            try:
                v_clip = VideoFileClip(v_path)
                orig_dur = v_clip.duration
                # 循環或放慢嚟填滿呢個場景嘅配音長度
                loop_times = int(target_dur / orig_dur) + 1
                extended_clip = concatenate_videoclips([v_clip] * loop_times).subclip(0, target_dur)
                scene_clips.append(extended_clip)
                continue
            except Exception:
                pass
        
        # 萬一冇對應嘅 mp4，用對應嘅靜態圖頂上
        img_path = f"{idx}.png"
        if not os.path.exists(img_path): img_path = "1.png"
        scene_clips.append(ImageClip(img_path).with_duration(target_dur))

    final_video = concatenate_videoclips(scene_clips, method="compose")
    try:
        final_video = final_video.set_audio(audio_clip)
    except AttributeError:
        final_video = final_video.with_audio(audio_clip)

    final_video.write_videofile(video_output, fps=24, codec='libx264', audio_codec='aac')
    print(f"✅ 創世記第一章完整壓製成功: {video_output}")

    audio_clip.close()
    final_video.close()
    if os.path.exists(audio_file): os.remove(audio_file)

if __name__ == "__main__":
    script_file = "video.txt"
    temp_audio = "temp_genesis_ch1.mp3"
    output_mp4 = "genesis_chapter_1_full.mp4"

    success, scene_info, script_data = process_script_and_audio(script_file, temp_audio)
    if success and os.path.exists(temp_audio):
        generate_genesis_chapter1(temp_audio, output_mp4, scene_info)
