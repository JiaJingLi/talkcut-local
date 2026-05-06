import os
import re
import yaml


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_speech_issues(segments):
    config = load_config()
    filler_ratio_threshold = config.get("filler_ratio_threshold", 0.15)
    slow_speech_speed = config.get("slow_speech_speed", 2.0)
    slow_speech_min_duration = config.get("slow_speech_min_duration", 1.5)
    filler_words = config.get("filler_words", [])

    issues = []

    for segment in segments:
        text = segment["text"]
        duration = segment["end"] - segment["start"]

        total_chars = len(text)
        if total_chars == 0:
            continue

        filler_count = 0
        for fw in filler_words:
            filler_count += text.count(fw)

        filler_ratio = filler_count / total_chars
        if filler_ratio > filler_ratio_threshold:
            issues.append({
                "time": segment["start"],
                "end": segment["end"],
                "type": "filler_overuse",
                "text": text,
                "detail": f"语气词占比 {filler_ratio:.2%} 超过阈值"
            })

        repetition_pattern = config.get("repetition_pattern", r"(.{2,})\1{2,}")
        if re.search(repetition_pattern, text):
            issues.append({
                "time": segment["start"],
                "end": segment["end"],
                "type": "repetition",
                "text": text,
                "detail": "检测到连续重复词"
            })

        if segment["avg_speed"] < slow_speech_speed and duration > slow_speech_min_duration:
            issues.append({
                "time": segment["start"],
                "end": segment["end"],
                "type": "slow_speech",
                "text": text,
                "detail": f"语速 {segment['avg_speed']:.1f} 字/秒 低于阈值"
            })

    return issues
