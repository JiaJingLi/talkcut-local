import os
import librosa
import numpy as np
import yaml


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def analyze_audio_features(audio_path, segments):
    config = load_config()
    threshold_factor = config.get("silence_threshold_factor", 0.3)

    y, sr = librosa.load(audio_path, sr=16000)
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=512)[0]

    silence_threshold = threshold_factor * np.mean(rms)
    is_silent = rms < silence_threshold

    hop_time = 512 / sr

    for i, segment in enumerate(segments):
        seg_start = segment["start"]
        seg_end = segment["end"]

        if i == 0:
            segment["silence_before"] = 0.0
        else:
            prev_end = segments[i - 1]["end"]
            gap_start = prev_end
            gap_end = seg_start
            gap_duration = gap_end - gap_start

            if gap_duration > 0:
                start_frame = int(gap_start / hop_time)
                end_frame = int(gap_end / hop_time)
                gap_frames = is_silent[start_frame:end_frame] if end_frame > start_frame else np.array([])
                silence_ratio = np.mean(gap_frames) if len(gap_frames) > 0 else 0
                segment["silence_before"] = gap_duration * silence_ratio
            else:
                segment["silence_before"] = 0.0

        duration = seg_end - seg_start
        text_len = len(segment["text"])
        if duration > 0:
            segment["avg_speed"] = text_len / duration
        else:
            segment["avg_speed"] = 0.0

    return segments
