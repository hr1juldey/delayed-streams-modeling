"""Configuration settings for the voice server using Pydantic Settings."""

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioSettings(BaseModel):
    """Audio processing configuration."""

    chunk_size: int = 1920  # 80ms at 24kHz
    input_sample_rate: int = 24000
    output_sample_rate: int = 24000
    input_format: Literal["float32", "int16"] = "float32"


class STTSettings(BaseModel):
    """Speech-to-Text model configuration."""

    model_name: Literal["1b-en_fr", "2.6b-en"] = "1b-en_fr"
    device: str = "cuda"
    preload_model: bool = True
    warmup_on_startup: bool = False  # Disabled due to potential CUDA issues
    vad_mode: Literal["client", "server"] = "client"
    streaming_mode: Literal["partial", "final", "both"] = "both"
    confidence_threshold: float = 0.5
    target_latency_ms: int = 200
    custom_vocabulary: list[str] = Field(default_factory=list)


class TTSSettings(BaseModel):
    """Text-to-Speech model configuration."""

    default_voice: str = "default"
    device: str = "cpu"  # Pocket TTS is CPU-only
    preload_model: bool = True
    enable_normalization: bool = True
    speed: float = 1.0
    stability: float = 1.0  # CFG coefficient
    pitch: float = 1.0


class SessionSettings(BaseModel):
    """Session management configuration."""

    timeout_minutes: int = 30
    storage_backend: Literal["sqlite", "memory"] = "sqlite"
    recovery_enabled: bool = True
    history_required: bool = True
    max_history_length: int = 1000


class ServerSettings(BaseSettings):
    """Main server configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_prefix="VOICE_SERVER",
        case_sensitive=False,
    )

    api_version: str = "v1"
    host: str = "0.0.0.0"
    port: int = 16000  # 16000 range for voice services
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    api_keys: list[str] = Field(default_factory=list)
    require_auth: bool = False
    max_concurrent_sessions: int = 10
    websocket_compression: bool = True
    heartbeat_interval_seconds: int = 30
    voices_path: str = "./data/voices"
    db_path: str = "./data/db"

    # Sub-settings
    audio: AudioSettings = Field(default_factory=AudioSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
