import os
import subprocess
import json
import uuid
import shutil
import numpy as np
import librosa
from .transcription import transcribe_with_funasr
from .audio_features import analyze_audio_features
from .issue_detector import detect_speech_issues
from .auto_cutter import generate_auto_cuts


def extract_audio(video_path, out_audio_path):
    os.makedirs(os.path.dirname(out_audio_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        out_audio_path
    ]

    print(f"[FFmpeg] 提取音频: {video_path} -> {out_audio_path}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print(f"[FFmpeg] 错误: {result.stderr.decode()}")
        return False

    if not os.path.exists(out_audio_path):
        print(f"[FFmpeg] 警告: 输出文件不存在")
        return False

    file_size = os.path.getsize(out_audio_path)
    print(f"[FFmpeg] 音频提取成功，文件大小: {file_size} 字节")
    return True


def get_video_duration(video_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        return float(result.stdout.decode().strip())
    except:
        return 0.0


def generate_waveform_data(audio_path, num_samples=2000):
    """
    生成波形数据用于前端绘制
    :param audio_path: 音频文件路径
    :param num_samples: 返回的采样点数（越少前端绘制越快）
    :return: 归一化到 0~1 的幅度数组
    """
    try:
        print(f"[Waveform] 生成波形数据: {audio_path}")
        y, sr = librosa.load(audio_path, sr=16000, mono=True)

        # 计算 RMS 能量作为波形幅度
        rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=512)[0]

        # 下采样到 num_samples 个点
        if len(rms) > num_samples:
            indices = np.linspace(0, len(rms) - 1, num_samples).astype(int)
            rms = rms[indices]

        # 归一化到 0~1
        max_val = np.max(rms)
        if max_val > 0:
            rms = rms / max_val

        # 转换为列表（方便 JSON 序列化）
        waveform = rms.tolist()
        print(f"[Waveform] 波形数据生成完成，{len(waveform)} 个采样点")
        return waveform

    except Exception as e:
        print(f"[Waveform] 生成波形数据失败: {e}")
        return []


def analyze_talking_head(video_path, project_id=None):
    if project_id is None:
        project_id = str(uuid.uuid4())

    project_dir = os.path.join("projects", project_id)
    os.makedirs(project_dir, exist_ok=True)

    dest_video = os.path.join(project_dir, "source.mp4")
    if os.path.abspath(video_path) != os.path.abspath(dest_video):
        shutil.copy2(video_path, dest_video)

    audio_path = os.path.join(project_dir, "audio.wav")
    extract_audio(dest_video, audio_path)

    print(f"[Analyzer] 开始识别...")
    segments = transcribe_with_funasr(audio_path)
    print(f"[Analyzer] 识别完成，得到 {len(segments) if segments else 0} 个段落")

    if not segments:
        print("[Analyzer] 错误: 识别结果为空")
        raise ValueError("语音识别失败，未返回任何段落")

    # 验证segments
    for i, seg in enumerate(segments):
        if "start" not in seg:
            print(f"[Analyzer] 错误: segments[{i}] 缺少 'start' 字段")
            print(f"[Analyzer] 内容: {seg}")
            raise ValueError(f"识别结果格式错误：段落 {i} 缺少 start 字段")
        if "end" not in seg:
            print(f"[Analyzer] 错误: segments[{i}] 缺少 'end' 字段")
            print(f"[Analyzer] 内容: {seg}")
            raise ValueError(f"识别结果格式错误：段落 {i} 缺少 end 字段")

    analyze_audio_features(audio_path, segments)

    issues = detect_speech_issues(segments)

    auto_cuts = generate_auto_cuts(segments, issues)

    duration = get_video_duration(dest_video)

    # 生成波形数据
    waveform = generate_waveform_data(audio_path)

    project_data = {
        "project_id": project_id,
        "source_video": "source.mp4",
        "duration": duration,
        "segments": segments,
        "auto_cuts": auto_cuts,
        "issues": issues,
        "waveform": waveform,
        "metadata": {
            "total_segments": len(segments),
            "total_cuts": len(auto_cuts),
            "total_issues": len(issues)
        }
    }

    json_path = os.path.join(project_dir, "project.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, ensure_ascii=False, indent=2)

    return project_data
