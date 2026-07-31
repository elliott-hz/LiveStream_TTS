"""播单计算：根据编排配置生成播放列表"""

import random
from dataclasses import dataclass


@dataclass
class PlaylistItem:
    segment_id: str
    clip_path: str
    weight: int
    pause_after: int       # 播放后停顿秒数
    pause_content: str     # freeze / card / custom


def generate(items: list[dict], play_mode: str = "sequential") -> list[PlaylistItem]:
    """
    根据编排的 clips 生成播放列表。

    items: [{"segment_id": "xxx", "clip_path": "/path/to/clip.mp4",
             "weight": 2, "pause_after": 3, "pause_content": "freeze"}, ...]
    play_mode: "sequential" | "random"
    """
    playlist = []
    for item in items:
        for _ in range(item["weight"]):
            playlist.append(PlaylistItem(
                segment_id=item["segment_id"],
                clip_path=item["clip_path"],
                weight=item["weight"],
                pause_after=item.get("pause_after", 0),
                pause_content=item.get("pause_content", "freeze"),
            ))

    if play_mode == "random":
        random.shuffle(playlist)

    return playlist


def to_concat_file(playlist: list[PlaylistItem], output_path: str):
    """生成 FFmpeg concat demuxer 需要的播放列表文件"""
    with open(output_path, "w") as f:
        for item in playlist:
            f.write(f"file '{item.clip_path}'\n")
