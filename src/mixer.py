"""
M10 — Audio Mixer
POC: 暂不实现。仅做单音轨 passthrough。后续支持多音轨混音。
"""


class AudioMixer:
    """
    音频混音器。
    POC: 单音轨直接透传。
    """

    def mix(self, pcm_data: bytes) -> bytes:
        """
        混音入口。
        POC: 直接透传。
        """
        return pcm_data
