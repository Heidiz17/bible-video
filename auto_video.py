import os
import re
import asyncio
import sys
import time
import urllib.request
import edge_tts
from pydub import AudioSegment

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

async def generate_tts(text, output_mp3):
    clean_text = re.sub(r'\[.*?\]', '', text).strip()
    if not clean_text:
        return False

    for attempt in range(8):
        try:
            communicate = edge_tts.Communicate(clean_text, VOICE, rate='-20%')
            await communicate.save(output_mp3)
            if os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 1000:
                print(f"✅ [P女 廣東話] 語音合成成功！")
                return True
        except Exception as e:
            print(f"⚠️ 語音生成重試第 {attempt+1} 次...")
            await asyncio.sleep(3)
    return False

def mix_chapter_audio(text_file, output_audio_filename):
    """處理廣東話配音 + 大自然音效 + 背景音樂混音"""
    with open(text_file, 'r', encoding='utf-8') as f:
        raw_content = f.read()

    current_bgm_type = 'calm'
    pattern_sfx = r'(\[雷雨\]|\[雷聲\]|\[雨聲雷鳴\]|\[風雨雷電\]|\[下雨\]|\[雨聲\]|\[海洋\]|\[海浪\]|\[海浪風鈴\]|\[柴火\]|\[溫暖\]|\[森林\]|\[天地\]|\[森林鳥鳴\]|\[風鈴\]|\[海鳥\]|\[溪流\]|\[流水\]|\[戰爭\]|\[交戰\]|\[洞穴\]|\[水滴\])'
    parts_sfx = re.split(pattern_sfx, raw_content)
    
    combined_voice_sfx = []
    for part in parts_sfx:
        if not part.strip(): continue
        
        bgm_match = re.search(r'\[BGM\s*:\s*(happy|calm|sad)\]', part, re.IGNORECASE)
        if bgm_match:
            current_bgm_type = bgm_match.group(1).lower()
            clean_part = re.sub(r'\[BGM\s*:\s*(happy|calm|sad)\]', '', part, re.IGNORECASE).strip()
            if clean_part:
                sub_parts_sfx = re.split(pattern_sfx, clean_part)
                for sub_part in sub_parts_sfx:
                    if not sub_part.strip(): continue
                    if sub_part in TAG_AUDIO_MAP:
                        combined_voice_sfx.append((sub_part, None, current_bgm_type))
                    else:
                        combined_voice_sfx.append((None, sub_part.strip(), current_bgm_type))
        elif part in TAG_AUDIO_MAP:
            combined_voice_sfx.append((part, None, current_bgm_type))
        elif not re.match(r'\[TITLE\s*:', part, re.IGNORECASE) and not re.match(r'\[IMG\s*:', part, re.IGNORECASE):
            combined_voice_sfx.append((None, part.strip(), current_bgm_type))

    if not combined_voice_sfx:
        combined_voice_sfx = [(None, raw_content.strip(), 'calm')]

    combined_voice = AudioSegment.silent(duration=0)
    combined_sfx = AudioSegment.silent(duration=0)
    combined_bgm = AudioSegment.silent(duration=0)

    created_temp_files = []
    print(f"🔊 正在處理廣東話配音、大自然音效與背景音樂...")

    for idx, (tag_sfx, text_tts, tag_bgm_type) in enumerate(combined_voice_sfx):
        seg_dur = 0
        if text_tts:
            temp_file = f"temp_tts_{idx}.mp3"
            created_temp_files.append(temp_file)
            success = asyncio.run(generate_tts(text_tts, temp_file))
            if success and os.path.exists(temp_file):
                raw_voice = AudioSegment.from_file(temp_file)
                combined_voice += raw_voice + AudioSegment.silent(duration=1500)
                seg_dur = len(raw_voice) + 1500
        
        seg_sfx = AudioSegment.silent(duration=seg_dur)
        if tag_sfx and tag_sfx in TAG_AUDIO_MAP:
            sfx_filename = TAG_AUDIO_MAP[tag_sfx]
            if os.path.exists(sfx_filename):
                snd = AudioSegment.from_file(sfx_filename)
                snd_looped = (snd * (int(seg_dur / len(snd)) + 1))[:seg_dur] - 22
                seg_sfx = snd_looped.fade_in(500).fade_out(1000)
        combined_sfx += seg_sfx
        
        bgm_music_track = AudioSegment.silent(duration=seg_dur)
        music_filename = MUSIC_MAP.get(tag_bgm_type, 'music_calm.mp3')
        if music_filename and os.path.exists(music_filename):
            bgm_music = AudioSegment.from_file(music_filename)
            bgm_music = bgm_music.apply_gain(-22.0 - bgm_music.dBFS)
            music_looped = (bgm_music * (int(seg_dur / len(bgm_music)) + 1))[:seg_dur]
            bgm_music_track = music_looped.fade_out(1500)
        combined_bgm += bgm_music_track

    for t_file in created_temp_files:
        if os.path.exists(t_file):
            os.remove(t_file)

    if len(combined_voice) == 0:
        print(f"❌ 語音生成失敗，請檢查網路連線。")
        return False

    final_mix = combined_bgm.overlay(combined_sfx).overlay(combined_voice, position=1000)
    final_mix.export(output_audio_filename, format="mp3")
    print(f"🎉 聲音總合成完成: {output_audio_filename}")
    return True

def generate_multi_image_mp4(audio_file, video_output, text_file="video.txt"):
    """智能自動辨識 1.png 到 7.png 或 pic1.png 做動畫"""
    try:
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        audio_clip = AudioFileClip(audio_file)
        total_duration = audio_clip.duration

        with open(text_file, 'r', encoding='utf-8') as f:
            content = f.read()

        img_tags = re.findall(r'\[IMG\s*:\s*(.*?)\]', content, re.IGNORECASE)
        num_images = len(img_tags) if img_tags else 7
        dur_per_img = total_duration / num_images

        clips = []
        print(f"🎬 正在壓製多圖慢推動畫 MP4 (共 {num_images} 張相片)...")
        for idx in range(1, num_images + 1):
            # 優先搜尋 1.png，找不到再找 pic1.png
            img_path = f"{idx}.png"
            if not os.path.exists(img_path):
                img_path = f"pic{idx}.png"
            if not os.path.exists(img_path):
                img_path = '1.png' if os.path.exists('1.png') else 'cover.png'

            print(f"📸 第 {idx} 幕使用相片: {img_path}")
            img_clip = ImageClip(img_path).set_duration(dur_per_img)
            img_clip = img_clip.resize(lambda t: 1 + 0.05 * (t / dur_per_img))

            if idx > 1:
                img_clip = img_clip.crossfadein(1.0)

            clips.append(img_clip)

        final_video = concatenate_videoclips(clips, method="compose")
        final_video = final_video.set_audio(audio_clip)

        final_video.write_videofile(video_output, fps=24, codec='libx264', audio_codec='aac')
        print(f"✅ 成功生成廣東話動畫影片: {video_output}")

        audio_clip.close()
        final_video.close()
        if os.path.exists(audio_file):
            os.remove(audio_file)

    except Exception as e:
        print(f"⚠️ MP4 影片壓製失敗: {e}")

if __name__ == "__main__":
    script_file = "video.txt"
    temp_audio = "temp_full_mix.mp3"
    output_video = "genesis_ch1_Pgirl.mp4"

    if os.path.exists(script_file):
        success = mix_chapter_audio(script_file, temp_audio)
        if success and os.path.exists(temp_audio):
            generate_multi_image_mp4(temp_audio, output_video, script_file)
