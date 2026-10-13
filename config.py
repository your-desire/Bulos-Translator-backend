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
    translation_timeout_seconds: int = Field(default=300)

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

    # MongoDB Atlas — audio file storage (GridFS)
    mongodb_uri:       str = Field(default="")
    mongodb_audio_db:  str = Field(default="bulos_audio")

    # STT (Speech-to-Text) Settings
    # Model path: either a Whisper model size ("tiny", "small") or
    # an absolute path to a fine-tuned CTranslate2 model directory
    stt_enabled: bool = Field(default=True)
    stt_model_path: str = Field(default="large-v3")
    stt_device: str = Field(default="cpu")
    stt_compute_type: str = Field(default="int8")

    # LSTM Translation Settings — Step 5 of the Bulos pipeline
    # Requires models/lstm/<direction>/model.keras + src/tgt_tokenizer.json
    # Run Bulos_LSTM_Training_Ready.ipynb to generate the model files.
    lstm_enabled:    bool = Field(default=False)
    lstm_models_dir: str  = Field(default="models/lstm")

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
