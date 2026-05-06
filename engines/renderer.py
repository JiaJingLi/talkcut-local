import os
import subprocess
import tempfile
import shutil


def extract_segment(source_path, output_dir, start, end, index):
    segment_path = os.path.join(output_dir, f"segment_{index}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", source_path,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        segment_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return segment_path


def concatenate_segments(source_path, timeline, output_path):
    with tempfile.TemporaryDirectory() as temp_dir:
        segment_files = []
        for i, (start, end) in enumerate(timeline):
            if end > start:
                seg = extract_segment(source_path, temp_dir, start, end, i)
                segment_files.append(seg)

        if not segment_files:
            return False, "No valid segments to concatenate"

        list_file = os.path.join(temp_dir, "segments.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path
        ]

        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"FFmpeg error: {result.stderr.decode()}"

        return True, output_path
