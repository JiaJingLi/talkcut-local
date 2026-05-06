from funasr import AutoModel
import os
import sys

# 强制输出到控制台（不缓冲）
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

_model = None


def get_model():
    global _model
    if _model is None:
        print("=" * 60)
        print("[FunASR] 开始加载模型...")
        print("[FunASR] 如果是首次运行，将自动下载模型（约 1.2GB）")
        print("[FunASR] 请耐心等待，不要关闭窗口")
        print("=" * 60)
        
        _model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
        )
        print("[FunASR] 模型加载完成！")
    return _model


def transcribe_with_funasr(audio_path):
    print(f"[FunASR] 开始分析音频: {audio_path}")
    
    model = get_model()
    print("[FunASR] 模型加载完成，开始识别...")
    
    # 尝试多种参数组合，确保获取到句子时间戳
    result = model.generate(
        input=audio_path, 
        batch_size_s=300,
        is_speech_timestamp=True  # 强制生成时间戳
    )
    
    print(f"[FunASR] 识别完成，原始结果: {str(result)[:300]}...")
    
    # 调试：将完整结果保存到文件
    import json
    debug_file = "funasr_debug.json"
    try:
        # 将结果转换为可序列化的格式
        debug_data = []
        for item in result:
            # 将numpy数组等转换为列表
            serialized = {}
            for key, value in item.items():
                if hasattr(value, 'tolist'):  # numpy array
                    serialized[key] = value.tolist()
                elif hasattr(value, '__iter__') and not isinstance(value, (str, list, dict)):
                    serialized[key] = list(value)
                else:
                    serialized[key] = value
            debug_data.append(serialized)
        
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(debug_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"[FunASR] 完整结果已保存到: {debug_file}")
    except Exception as e:
        print(f"[FunASR] 保存调试信息失败: {e}")
        # 如果JSON序列化失败，保存原始字符串
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(str(result))
        print(f"[FunASR] 原始结果已保存到: {debug_file}")

    # 检查返回格式
    if not result or len(result) == 0:
        print("[FunASR] 警告: 识别结果为空")
        return []
    
    first_result = result[0]
    print(f"[FunASR] 结果字段: {list(first_result.keys())}")
    
    # 情况1: 有 sentence_info 字段（FunASR 1.3.1+ 格式）
    if "sentence_info" in first_result and first_result["sentence_info"]:
        print(f"[FunASR] 识别到 {len(first_result['sentence_info'])} 个句子（sentence_info格式）")
        print(f"[FunASR] sentence_info示例: {str(first_result['sentence_info'][0])[:200]}")
        return parse_sentence_info(first_result["sentence_info"], first_result.get("timestamp", []))
    
    # 情况2: 有 timestamp 字段（FunASR 1.3.1+ 单词级时间戳）
    if "timestamp" in first_result and first_result["timestamp"]:
        print(f"[FunASR] 识别到 timestamp 字段，共 {len(first_result['timestamp'])} 个单词时间戳")
        print(f"[FunASR] timestamp示例: {str(first_result['timestamp'][:3])}")
        return parse_timestamp(first_result["text"], first_result["timestamp"])
    
    # 情况3: 有 sentence_timestamp 字段（FunASR 1.3.1+ 格式，无sentence_info时）
    if "sentence_timestamp" in first_result and first_result["sentence_timestamp"]:
        print(f"[FunASR] 识别到 {len(first_result['sentence_timestamp'])} 个时间戳")
        print(f"[FunASR] sentence_timestamp示例: {first_result['sentence_timestamp'][:3]}")
        return parse_sentence_timestamp(first_result["text"], first_result["sentence_timestamp"])
    
    # 情况3: 有 sentences 字段（旧格式，兼容）
    if "sentences" in first_result and first_result["sentences"]:
        print(f"[FunASR] 识别到 {len(first_result['sentences'])} 个句子（sentences旧格式）")
        return parse_sentences(first_result["sentences"])
    
    # 情况4: 只有 text 字段（无时间戳）
    if "text" in first_result:
        print(f"[FunASR] 只有文本，无时间戳。尝试手动分割...")
        text = first_result["text"]
        return split_text_to_segments(text, audio_path)
    
    print("[FunASR] 警告: 未识别到任何句子")
    return []


def validate_segments(segments):
    """验证segments是否有效，每个segment必须有start和end字段"""
    if not segments:
        print("[FunASR] 警告: segments 为空")
        return False
    
    for i, seg in enumerate(segments):
        if "start" not in seg:
            print(f"[FunASR] 错误: segments[{i}] 缺少 'start' 字段")
            print(f"[FunASR] 内容: {seg}")
            return False
        if "end" not in seg:
            print(f"[FunASR] 错误: segments[{i}] 缺少 'end' 字段")
            print(f"[FunASR] 内容: {seg}")
            return False
    
    print(f"[FunASR] segments 验证通过，共 {len(segments)} 个段落")
    return True


def parse_sentence_info(sentence_info, word_timestamps):
    """解析 FunASR 1.3.1+ 的 sentence_info 字段"""
    if not sentence_info:
        return []
    
    print(f"[FunASR] 解析 sentence_info，共 {len(sentence_info)} 条")
    
    # 检查第一个元素的格式
    first = sentence_info[0]
    print(f"[FunASR] sentence_info[0] 类型: {type(first)}, 内容: {str(first)[:200]}")
    
    segments = []
    
    # 格式1: sentence_info 是字典列表，每个字典包含 text/start/end
    if isinstance(first, dict):
        # 检查时间戳单位
        start_val = first.get("start", 0)
        time_divisor = 1 if start_val <= 1000 else 1000
        if time_divisor == 1000:
            print("[FunASR] 检测到时间戳单位为毫秒，将除以1000")
        
        for i, sent in enumerate(sentence_info):
            segments.append({
                "id": i + 1,
                "start": sent.get("start", 0) / time_divisor,
                "end": sent.get("end", 0) / time_divisor,
                "text": sent.get("text", ""),
                "words": [],  # FunASR 1.3.1 可能不支持单词级时间戳
                "avg_speed": 0.0,
                "silence_before": 0.0
            })
    
    # 格式2: sentence_info 是字符串列表（只有句子文本）
    elif isinstance(first, str):
        print("[FunASR] sentence_info 是文本列表，尝试匹配 sentence_timestamp...")
        # 这种情况需要有 sentence_timestamp 字段
        # 但是这个函数被调用时，sentence_timestamp 可能不在参数中
        # 所以这里我们只能返回空，让调用者使用其他解析方法
        print("[FunASR] 警告: sentence_info 是文本列表，但缺少时间戳信息")
        return []
    
    print(f"[FunASR] sentence_info 解析完成，共 {len(segments)} 个段落")
    return segments


def parse_timestamp(text, timestamps):
    """解析 FunASR 1.3.1+ 的 timestamp 字段（单词级时间戳）"""
    if not timestamps or not text:
        return []
    
    print(f"[FunASR] 解析 timestamp（单词级时间戳），共 {len(timestamps)} 个")
    print(f"[FunASR] timestamp 示例: {str(timestamps[:3])}")
    
    # 检查时间戳格式
    first_ts = timestamps[0] if timestamps else None
    print(f"[FunASR] 第一个时间戳类型: {type(first_ts)}, 内容: {first_ts}")
    
    # 检查时间戳单位（毫秒还是秒）
    start_val = first_ts[0] if isinstance(first_ts, (list, tuple)) else first_ts
    time_divisor = 1 if start_val <= 1000 else 1000
    if time_divisor == 1000:
        print("[FunASR] 检测到时间戳单位为毫秒，将除以1000")
    
    # 将文本按标点符号分割成句子
    import re
    # 匹配中文标点：。！？；
    # 使用正则表达式保留标点符号
    sentence_endings = re.finditer(r'[。！？；]', text)
    positions = [m.start() for m in sentence_endings]
    
    if not positions:
        # 没有标点符号，整个文本作为一个句子
        sentences = [text]
        print(f"[FunASR] 文本无标点，作为单个句子处理")
    else:
        # 按标点符号分割
        sentences = []
        start_idx = 0
        for pos in positions:
            # 包括标点符号
            sentence = text[start_idx:pos+1].strip()
            if sentence:
                sentences.append(sentence)
            start_idx = pos + 1
        # 处理最后一段（如果有）
        if start_idx < len(text):
            last = text[start_idx:].strip()
            if last:
                sentences.append(last)
        print(f"[FunASR] 文本分割为 {len(sentences)} 个句子")
    
    # 将单词时间戳分配到句子中
    # timestamp 格式可能是 [start, end, word] 或 [start, end]
    word_timestamps = []
    for ts in timestamps:
        if isinstance(ts, (list, tuple)) and len(ts) >= 2:
            start = ts[0] / time_divisor
            end = ts[1] / time_divisor
            word = ts[2] if len(ts) >= 3 else ""
            word_timestamps.append({"start": start, "end": end, "word": word})
    
    print(f"[FunASR] 转换后得到 {len(word_timestamps)} 个单词时间戳")
    
    # 如果没有单词时间戳，返回空
    if not word_timestamps:
        print("[FunASR] 警告: 无法解析时间戳")
        return []
    
    # 简单分配：按字数比例分配时间戳
    # 更精确的方法需要对齐文本，但这里先做简单实现
    total_words = sum(len(s) for s in sentences)
    segments = []
    ts_idx = 0
    
    for i, sent in enumerate(sentences):
        # 分配时间戳
        sent_start = word_timestamps[ts_idx]["start"] if ts_idx < len(word_timestamps) else 0
        # 估算这个句子应该占多少个单词时间戳
        word_ratio = len(sent) / total_words if total_words > 0 else 1 / len(sentences)
        ts_count = max(1, int(len(word_timestamps) * word_ratio))
        
        if ts_idx + ts_count < len(word_timestamps):
            sent_end = word_timestamps[ts_idx + ts_count - 1]["end"]
        else:
            sent_end = word_timestamps[-1]["end"]
        
        ts_idx += ts_count
        
        segments.append({
            "id": i + 1,
            "start": sent_start,
            "end": sent_end,
            "text": sent,
            "words": [],
            "avg_speed": len(sent) / (sent_end - sent_start) if sent_end > sent_start else 0,
            "silence_before": 0.0
        })
    
    print(f"[FunASR] timestamp 解析完成，共 {len(segments)} 个段落")
    return segments


def parse_sentence_timestamp(text, timestamps):
    """解析 FunASR 1.3.1+ 的 sentence_timestamp 字段（仅有时间戳，无句子文本）"""
    if not timestamps or not text:
        return []
    
    print(f"[FunASR] 解析 sentence_timestamp，共 {len(timestamps)} 个时间戳")
    print(f"[FunASR] 文本: {text[:100]}...")
    
    # 检查时间戳单位
    first_start = timestamps[0][0] if timestamps and len(timestamps[0]) > 0 else 0
    time_divisor = 1 if first_start <= 1000 else 1000
    if time_divisor == 1000:
        print("[FunASR] 检测到时间戳单位为毫秒，将除以1000")
    
    # 将文本按标点符号分割成句子
    import re
    # 匹配中文标点：。！？；
    parts = re.split(r'([。！？；])', text)
    
    # 重新组合（保留标点）
    sentences = []
    current = ""
    for part in parts:
        if part in "。！？；":
            current += part
            if current.strip():
                sentences.append(current.strip())
                current = ""
        else:
            current += part
    
    if current.strip():
        sentences.append(current.strip())
    
    if not sentences:
        sentences = [text]
    
    print(f"[FunASR] 文本分割为 {len(sentences)} 个句子，时间戳有 {len(timestamps)} 个")
    
    # 匹配句子和时间戳
    segments = []
    for i, sent in enumerate(sentences):
        if i < len(timestamps):
            start_time = timestamps[i][0] / time_divisor
            end_time = timestamps[i][1] / time_divisor
        else:
            # 如果时间戳不够，使用最后一个时间戳的结束时间
            start_time = timestamps[-1][1] / time_divisor if timestamps else 0
            end_time = start_time + 3.0  # 假设每个句子3秒
        
        segments.append({
            "id": i + 1,
            "start": start_time,
            "end": end_time,
            "text": sent,
            "words": [],
            "avg_speed": len(sent) / (end_time - start_time) if end_time > start_time else 0,
            "silence_before": 0.0
        })
    
    print(f"[FunASR] sentence_timestamp 解析完成，共 {len(segments)} 个段落")
    return segments


def parse_sentences(sentences):
    """解析句子时间戳（旧格式）"""
    if not sentences:
        return []
    
    first_sent = sentences[0]
    print(f"[FunASR] 第一个句子原始数据: start={first_sent.get('start')}, end={first_sent.get('end')}")
    
    # 检查时间戳单位（毫秒还是秒）
    start_val = first_sent.get("start", 0)
    time_divisor = 1
    if start_val > 1000:
        time_divisor = 1000
        print("[FunASR] 检测到时间戳单位为毫秒，将除以1000")
    else:
        print("[FunASR] 检测到时间戳单位为秒")

    segments = []
    for sent in sentences:
        words = []
        if "words" in sent:
            words = [
                {
                    "word": w["text"],
                    "start": w["start"] / time_divisor,
                    "end": w["end"] / time_divisor
                }
                for w in sent["words"]
            ]

        segments.append({
            "id": len(segments) + 1,
            "start": sent["start"] / time_divisor,
            "end": sent["end"] / time_divisor,
            "text": sent["text"],
            "words": words,
            "avg_speed": 0.0,
            "silence_before": 0.0
        })

    print(f"[FunASR] 转换完成，共 {len(segments)} 个段落")
    return segments


def split_text_to_segments(text, audio_path):
    """当没有时间戳时，根据标点分割文本并估算时间戳"""
    print(f"[FunASR] 手动分割文本: {text[:100]}...")
    
    # 获取音频时长
    import subprocess
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        duration = float(result.stdout.decode().strip())
    except:
        duration = 60.0  # 默认1分钟
    
    print(f"[FunASR] 音频时长: {duration}秒")
    
    # 按标点符号分割文本
    import re
    # 匹配中文标点：。！？；
    parts = re.split(r'([。！？；])', text)
    
    # 重新组合（保留标点）
    sentences = []
    current = ""
    for part in parts:
        if part in "。！？；":
            current += part
            if current.strip():
                sentences.append(current.strip())
                current = ""
        else:
            current += part
    
    if current.strip():
        sentences.append(current.strip())
    
    if not sentences:
        sentences = [text]
    
    print(f"[FunASR] 分割为 {len(sentences)} 个句子")
    
    # 估算每个句子的时长（按字数比例）
    total_chars = sum(len(s) for s in sentences)
    segments = []
    current_time = 0.0
    
    for i, sent in enumerate(sentences):
        # 按字数比例分配时间
        char_ratio = len(sent) / total_chars if total_chars > 0 else 1 / len(sentences)
        sent_duration = duration * char_ratio
        
        segments.append({
            "id": i + 1,
            "start": current_time,
            "end": current_time + sent_duration,
            "text": sent,
            "words": [],
            "avg_speed": len(sent) / sent_duration if sent_duration > 0 else 0,
            "silence_before": 0.0
        })
        
        current_time += sent_duration
    
    print(f"[FunASR] 手动分割完成，共 {len(segments)} 个段落")
    return segments
