import os
import yaml


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_auto_cuts(segments, issues=None):
    config = load_config()
    min_silence = config.get("min_silence_for_cut", 1.5)

    auto_cuts = []

    for i in range(1, len(segments)):
        current = segments[i]
        previous = segments[i - 1]

        if current["silence_before"] >= min_silence:
            auto_cuts.append({
                "start": previous["end"],
                "end": current["start"],
                "duration": current["start"] - previous["end"],
                "reason": "silence"
            })

    if issues:
        for issue in issues:
            if issue["type"] == "filler_overuse":
                has_overlap = False
                for cut in auto_cuts:
                    # issue使用"time"字段，cut使用"start"字段
                    if not (issue["end"] <= cut["start"] or issue["time"] >= cut["end"]):
                        has_overlap = True
                        break

                if not has_overlap:
                    auto_cuts.append({
                        "start": issue["time"],
                        "end": issue["end"],
                        "duration": issue["end"] - issue["time"],
                        "reason": "filler"
                    })

    auto_cuts.sort(key=lambda x: x["start"])

    merged = []
    for cut in auto_cuts:
        if merged and cut["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], cut["end"])
            merged[-1]["duration"] = merged[-1]["end"] - merged[-1]["start"]
        else:
            merged.append(cut.copy())

    return merged
