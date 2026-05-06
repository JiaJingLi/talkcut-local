import os
import json
import uuid
import yaml
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from engines.analyzer import analyze_talking_head
from engines.renderer import concatenate_segments


app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.route('/')
def index():
    return send_from_directory('templates', 'editor.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    project_id = str(uuid.uuid4())
    project_dir = os.path.join("projects", project_id)
    os.makedirs(project_dir, exist_ok=True)

    video_path = os.path.join(project_dir, secure_filename(video_file.filename))
    video_file.save(video_path)

    try:
        result = analyze_talking_head(video_path, project_id)
        return jsonify(result)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] 分析失败:")
        print(error_detail)
        return jsonify({
            "error": str(e),
            "traceback": error_detail
        }), 500


@app.route('/api/project/<project_id>/json', methods=['GET'])
def get_project_json(project_id):
    json_path = os.path.join("projects", project_id, "project.json")
    if not os.path.exists(json_path):
        return jsonify({"error": "Project not found"}), 404

    with open(json_path, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route('/api/project/<project_id>/stream', methods=['GET'])
def stream_video(project_id):
    video_path = os.path.join("projects", project_id, "source.mp4")
    if not os.path.exists(video_path):
        return jsonify({"error": "Video not found"}), 404

    return send_file(video_path, mimetype='video/mp4')


@app.route('/api/project/<project_id>/render', methods=['POST'])
def render_video(project_id):
    project_dir = os.path.join("projects", project_id)
    source_path = os.path.join(project_dir, "source.mp4")
    output_path = os.path.join(project_dir, "output.mp4")

    if not os.path.exists(source_path):
        return jsonify({"error": "Source video not found"}), 404

    try:
        timeline = request.json.get("timeline", [])
        if not timeline:
            return jsonify({"error": "Empty timeline"}), 400

        success, result = concatenate_segments(source_path, timeline, output_path)

        if success:
            return jsonify({"success": True, "output": "output.mp4"})
        else:
            return jsonify({"error": result}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/project/<project_id>/download', methods=['GET'])
def download_output(project_id):
    output_path = os.path.join("projects", project_id, "output.mp4")
    if not os.path.exists(output_path):
        return jsonify({"error": "Output not found"}), 404

    return send_file(output_path, as_attachment=True, download_name="output.mp4")


# ========== 配置管理 API ==========

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    config = load_config()
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置（阈值、语气词等）"""
    try:
        data = request.get_json()
        config = load_config()

        # 更新语气词库
        if 'filler_words' in data and isinstance(data['filler_words'], list):
            config['filler_words'] = data['filler_words']

        # 更新语气词比例阈值
        if 'filler_ratio_threshold' in data:
            config['filler_ratio_threshold'] = float(data['filler_ratio_threshold'])

        # 更新其他参数
        if 'min_silence_for_cut' in data:
            config['min_silence_for_cut'] = float(data['min_silence_for_cut'])

        if 'slow_speech_speed' in data:
            config['slow_speech_speed'] = float(data['slow_speech_speed'])

        if 'slow_speech_min_duration' in data:
            config['slow_speech_min_duration'] = float(data['slow_speech_min_duration'])

        if 'silence_threshold_factor' in data:
            config['silence_threshold_factor'] = float(data['silence_threshold_factor'])

        # 写回配置文件
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        return jsonify({"success": True, "config": config})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/project/<project_id>/reanalyze', methods=['POST'])
def reanalyze(project_id):
    """用当前最新配置重新分析已有项目"""
    project_dir = os.path.join("projects", project_id)
    source_path = os.path.join(project_dir, "source.mp4")

    if not os.path.exists(source_path):
        return jsonify({"error": "Source video not found"}), 404

    try:
        result = analyze_talking_head(source_path, project_id)
        return jsonify(result)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] 重新分析失败:")
        print(error_detail)
        return jsonify({
            "error": str(e),
            "traceback": error_detail
        }), 500


if __name__ == '__main__':
    config = load_config()
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 5199)
    app.run(host=host, port=port, debug=True)
