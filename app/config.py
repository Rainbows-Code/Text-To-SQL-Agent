"""
配置管理模块：从 .env 文件与环境变量加载配置
支持 pydantic-settings / pydantic 及原生 dotenv 回退
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

def load_env_file(env_path: Path):
    """简单解析 .env 文件"""
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key not in os.environ:
                        os.environ[key] = val

load_env_file(BASE_DIR / ".env")

# 国内 HuggingFace 镜像默认配置
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        LLM_BASE_URL: str = "https://api.siliconflow.cn/v1"
        LLM_API_KEY: str = "your_free_api_key_here"
        LLM_MODEL: str = "deepseek-ai/DeepSeek-V3"

        DB_PATH: str = "data/database.sqlite"

        EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-zh-v1.5"
        RAG_TOP_K: int = 3

        MAX_REPAIR_TURNS: int = 3

        model_config = SettingsConfigDict(
            env_file=str(BASE_DIR / ".env"),
            env_file_encoding="utf-8",
            extra="ignore"
        )

        @property
        def abs_db_path(self) -> Path:
            p = Path(self.DB_PATH)
            if p.is_absolute():
                return p
            return BASE_DIR / p

    settings = Settings()

except ImportError:
    # 环境尚未安装 pydantic-settings 时的轻量级 fallback
    class Settings:
        def __init__(self):
            self.LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
            self.LLM_API_KEY = os.getenv("LLM_API_KEY", "your_free_api_key_here")
            self.LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")
            self.DB_PATH = os.getenv("DB_PATH", "data/database.sqlite")
            self.EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5")
            self.RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
            self.MAX_REPAIR_TURNS = int(os.getenv("MAX_REPAIR_TURNS", "3"))

        @property
        def abs_db_path(self) -> Path:
            p = Path(self.DB_PATH)
            if p.is_absolute():
                return p
            return BASE_DIR / p

    settings = Settings()
