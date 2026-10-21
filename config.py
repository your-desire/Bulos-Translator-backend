"""Configuration management using Pydantic BaseSettings"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration settings"""

    # Application Settings
    app_name: str = Field(default="Bulos Translator API")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)

    # Server Settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Admin API Key (for dictionary/alphabet reload)
    admin_api_key: str = Field(default="change-this-to-secure-random-uuid")

    # Logging Settings
    log_level: str = Field(default="INFO")
    log_file_path: str = Field(default="./logs/app.log")
    log_max_bytes: int = Field(default=10 * 1024 * 1024)
    log_backup_count: int = Field(default=5)

    # Performance Settings
    max_concurrent_requests: int = Field(default=100)
    translation_timeout_seconds: int = Field(default=30)

    # CORS Settings
    cors_origins: list = Field(default=["*"])
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: list = Field(default=["GET", "POST", "PUT", "DELETE"])
    cors_allow_headers: list = Field(default=["*"])

    # Supported Languages
    supported_languages: list = Field(default=["bul", "en", "tl"])

    # Fuzzy Matching Settings
    fuzzy_match_enabled: bool = Field(default=True)
    fuzzy_match_threshold: float = Field(default=0.80)
    fuzzy_match_min_length: int = Field(default=3)

    # MongoDB Settings
    mongodb_url: str = Field(default="")
    mongodb_database: str = Field(default="bulos_translator")
    mongodb_max_pool_size: int = Field(default=50)
    mongodb_min_pool_size: int = Field(default=10)

    # STT (Speech-to-Text) Settings
    # Model path: either a Whisper model size ("tiny", "small") or
    # an absolute path to a fine-tuned CTranslate2 model directory
    stt_enabled: bool = Field(default=True)
    stt_model_path: str = Field(default="tiny")
    stt_device: str = Field(default="cpu")
    stt_compute_type: str = Field(default="int8")

    # Filipino Pivot Translation (Day 5 - DISABLED by default)
    # Uses Filipino as intermediate language when direct translation fails
    # Architecture: Attempt direct first → If unusable, try source→tl→target
    # Quality gates ensure only verified/approved translations accepted
    filipino_pivot_enabled: bool = Field(default=False)
    filipino_pivot_timeout_seconds: int = Field(default=45)  # Max time for pivot attempt
    filipino_pivot_require_phrase_match: bool = Field(default=True)  # Strict: only accept phrase_match for Bulos stage

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_ignore_empty = True
        extra = "ignore"


try:
    settings = Settings()
except Exception:
    import os
    os.environ.setdefault('ADMIN_API_KEY', 'change-this-to-secure-random-uuid')
    settings = Settings()
