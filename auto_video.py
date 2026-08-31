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

def draw_dynamic_video_frame(video_frame_img, title_text, subtitle_phrase):
    try:
        font_file = download_chinese_font()
        img = video_frame_img.convert("RGBA")
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

        return img
    except Exception:
        return video_frame_img

async def generate_tts(text, output_mp3):
    clean_text = re.sub(r'\[.*?\]', '', text).strip()
    if not clean_text: return False
    for _ in range(8):
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
    raw_sections = re.split(r'(\[IMG\s*:\s*.*?\])', content)
    img_idx = 0
    combined_voice = AudioSegment.silent(duration=0)
    created_temp_files = []
    scene_sfx_info = []

    for section in raw_sections:
        if not section.strip(): continue
        if re.search(r'\[IMG\s*:\s*(.*?)\]', section, re.IGNORECASE):
            img_idx += 1
            continue
            
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        current_sfx_list = []
        scene_phrases = []

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
                        'duration': dur_ms / 1000.0
                    })
                    scene_phrases.append(dur_ms)

        if scene_phrases:
            scene_sfx_info.append({'sfx_list': current_sfx_list, 'total_dur_ms': sum(scene_phrases)})

    for tf in created_temp_files:
        if os.path.exists(tf): os.remove(tf)

    total_duration = len(combined_voice)
    if total_duration == 0: return False, []

    bgm_filename = MUSIC_MAP.get(current_bgm, 'music_calm.mp3')
    combined_bgm = AudioSegment.silent(duration=total_duration)
    if os.path.exists(bgm_filename):
        raw_bgm = AudioSegment.from_file(bgm_filename)
        raw_bgm = raw_bgm.apply_gain(-22.0 - raw_bgm.dBFS)
        combined_bgm = (raw_bgm * (int(total_duration / len(raw_bgm)) + 2))[:total_duration].fade_out(1500)

    combined_sfx = AudioSegment.silent(duration=0)
    for sc in scene_sfx_info:
        dur_ms = sc['total_dur_ms']
        scene_sfx_mix = AudioSegment.silent(duration=dur_ms)
        for tag in sc['sfx_list']:
            sfx_file = TAG_AUDIO_MAP.get(tag)
            if sfx_file and os.path.exists(sfx_file):
                snd = AudioSegment.from_file(sfx_file) - 20
                scene_sfx_mix = scene_sfx_mix.overlay((snd * (int(dur_ms / len(snd)) + 3))[:dur_ms])
        combined_sfx += scene_sfx_mix

    final_mix = combined_bgm.overlay(combined_sfx[:total_duration].fade_out(1500)).overlay(combined_voice, position=1000)
    final_mix.export(output_audio_filename, format="mp3")
    return True, script_data
def generate_mp4_with_subtitles(audio_file, video_output, script_data):
    try:
        from moviepy.editor import AudioFileClip, ImageSequenceClip, VideoFileClip
    except ImportError:
        from moviepy import AudioFileClip, ImageSequenceClip, VideoFileClip

    audio_clip = AudioFileClip(audio_file)
    title_text = "創世記 第一章"
    all_frame_paths = []
    
    print("🚀 正在啟動 終極橡筋慢速拉長技術：場景無縫映射...")

    frame_counter = 0
    fps = 24
    TARGET_W, TARGET_H = 1280, 720  # 統一標準尺寸

    # 1. 預先計算每一個場景（img_idx）總共包含多少秒的語音
    scene_durations = {}
    for item in script_data:
        img_num = item['img_idx']
        scene_durations[img_num] = scene_durations.get(img_num, 0.0) + item['duration']

    # 2. 記錄每一個場景已經推進了多少秒
    scene_elapsed = {}

    # 3. 預先載入所有用到的 MP4 影片物件並獲取其總長度
    video_clips = {}
    unique_img_indices = set(item['img_idx'] for item in script_data)
    for img_num in unique_img_indices:
        v_path = f"{img_num}.mp4"
        if not os.path.exists(v_path):
            v_path = "1.mp4"
        
        if os.path.exists(v_path):
            try:
                v_clip = VideoFileClip(v_path)
                video_clips[img_num] = {
                    'clip': v_clip,
                    'duration': v_clip.duration if v_clip.duration > 0 else 5.0
                }
            except Exception:
                pass

    # 4. 逐句對白精準渲染畫面
    for item in script_data:
        img_num = item['img_idx']
        phrase = item['phrase']
        p_dur = item['duration']
        target_frames = int(p_dur * fps)

        scene_total_dur = scene_durations.get(img_num, 1.0)
        
        if img_num not in scene_elapsed:
            scene_elapsed[img_num] = 0.0

        v_info = video_clips.get(img_num)
        v_clip = v_info['clip'] if v_info else None
        orig_dur = v_info['duration'] if v_info else 5.0

        for i in range(target_frames):
            # 當前句子在整個大場景中的絕對時間進度
            current_phrase_local_t = scene_elapsed[img_num] + (i / fps)
            
            if v_clip:
                # 🌟 核心橡筋公式：將大場景的進度完美對應到原片的 0 到 orig_dur 之間，平滑慢速播完！
                progress_ratio = current_phrase_local_t / scene_total_dur
                progress_ratio = max(0.0, min(1.0, progress_ratio))
                vid_t = progress_ratio * orig_dur
                vid_t = min(vid_t, orig_dur - 0.001)

                try:
                    frame_arr = v_clip.get_frame(vid_t)
                    pil_img = Image.fromarray(frame_arr).convert("RGB")
                except Exception:
                    pil_img = Image.new("RGB", (TARGET_W, TARGET_H), (20, 20, 20))
            else:
                pil_img = Image.new("RGB", (TARGET_W, TARGET_H), (20, 20, 20))

            # 統一尺寸防護網
            if pil_img.size != (TARGET_W, TARGET_H):
                try:
                    pil_img = pil_img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
                except AttributeError:
                    try:
                        pil_img = pil_img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
                    except AttributeError:
                        pil_img = pil_img.resize((TARGET_W, TARGET_H))

            # 疊加招牌與即時字幕
            draw_img = draw_dynamic_video_frame(pil_img, title_text, phrase)
            
            frame_path = f"frame_cache_{frame_counter:05d}.png"
            draw_img.save(frame_path, "PNG")
            all_frame_paths.append(frame_path)
            frame_counter += 1

        # 更新該場景已消耗的時間
        scene_elapsed[img_num] += p_dur

    # 關閉所有影片物件以釋放資源
    for v_info in video_clips.values():
        try:
            v_info['clip'].close()
        except Exception:
            pass

    if all_frame_paths:
        print("🔗 正在將橡筋拉長後的平滑畫格與完美語音合成 MP4 大片...")
        clip = ImageSequenceClip(all_frame_paths, fps=fps)
        
        try:
            clip = clip.with_audio(audio_clip)
        except AttributeError:
            clip = clip.set_audio(audio_clip)

        clip.write_videofile(video_output, fps=fps, codec='libx264', audio_codec='aac')
        
        audio_clip.close()
        clip.close()
        if os.path.exists(audio_file): os.remove(audio_file)

        # 清理暫存畫格
        print("🧹 正在清理暫存畫格快取...")
        for fp in all_frame_paths:
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass

        print(f"🎉 橡筋拉長技術大功告成！完美不跳格的影片已生成: {video_output}")

if __name__ == "__main__":
    script_file = "video.txt"
    temp_audio = "temp_full_mix.mp3"
    output_video = "genesis_ch1_Pgirl_dynamic.mp4"

    if os.path.exists(script_file):
        success, script_data = process_script_and_audio(script_file, temp_audio)
        if success and os.path.exists(temp_audio):
            generate_mp4_with_subtitles(temp_audio, output_video, script_data)
    else:
        print("⚠️ 找不到 video.txt 檔案！")
