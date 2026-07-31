from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # TTS
    cosyvoice_api_key: str = ""

    # 阿里云
    aliyun_access_key: str = ""
    aliyun_secret: str = ""
    bailian_endpoint: str = "https://dashscope.aliyuncs.com/api/v1/services/video/smart-strip"

    # AutoDL GPU (Wav2Lip)
    wav2lip_url: str = "http://127.0.0.1:8000"

    # 淘宝开放平台
    taobao_app_key: str = ""
    taobao_app_secret: str = ""

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # 文件存储
    video_dir: str = "./data/videos"

    # Mock 开关 (测试用)
    mock_external_api: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
