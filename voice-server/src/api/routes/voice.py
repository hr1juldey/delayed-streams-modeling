"""Voice management HTTP endpoints.

Provides endpoints for uploading, listing, switching, and deleting custom voices.
"""

import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, status

from config.logging_config import get_logger
from config.settings import ServerSettings
from src.core.exceptions import VoiceException
from src.core.security import verify_api_key

logger = get_logger(__name__)

router = APIRouter(dependencies=[])


@router.post("/api/v1/voice/upload")
async def upload_voice(
    file: UploadFile = File(...),
    voice_id: Optional[str] = None,
    description: Optional[str] = None,
):
    """Upload a custom voice file.

    Args:
        file: Audio file (WAV, MP3) for voice cloning.
        voice_id: Optional voice ID (auto-generated if not provided).
        description: Optional voice description.

    Returns:
        Voice information.

    Raises:
        HTTPException: If upload fails.
    """
    # Check if TTS model is initialized
    from src.models.tts.model_manager import _tts_model_manager

    if _tts_model_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS model not initialized",
        )

    settings = ServerSettings()
    voices_path = Path(settings.voices_path)
    voices_path.mkdir(parents=True, exist_ok=True)

    # Generate voice ID if not provided
    if not voice_id:
        voice_id = str(uuid.uuid4())

    # Validate file extension
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in [".wav", ".mp3", ".flac", ".ogg"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {file_ext}. Use WAV, MP3, FLAC, or OGG.",
        )

    try:
        # Save uploaded file temporarily
        temp_path = voices_path / f"{voice_id}{file_ext}"

        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"Voice file uploaded: {voice_id}, size={len(content)} bytes")

        # For now, we'll just store the file path
        # In production, you would use pocket-tts export-voice functionality
        voice_info = {
            "voice_id": voice_id,
            "filename": file.filename,
            "description": description or f"Custom voice: {voice_id}",
            "path": str(temp_path),
            "size_bytes": len(content),
            "status": "uploaded",
        }

        return voice_info

    except Exception as e:
        logger.error(f"Failed to upload voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload voice: {str(e)}",
        )


@router.get("/api/v1/voice/list")
async def list_voices():
    """List all available voices.

    Returns:
        List of voice information.
    """
    from src.models.tts.model_manager import _tts_model_manager

    if _tts_model_manager is None:
        return {
            "voices": [
                {
                    "voice_id": "default",
                    "name": "Default Voice",
                    "description": "Built-in default voice",
                    "language": "en",
                }
            ]
        }

    try:
        voices = await _tts_model_manager.list_voices()
        return {"voices": voices}

    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list voices: {str(e)}",
        )


@router.post("/api/v1/voice/switch")
async def switch_voice(voice_id: str):
    """Switch the active voice for TTS synthesis.

    Args:
        voice_id: Voice ID to switch to.

    Returns:
        Success message.
    """
    from src.models.tts.model_manager import _tts_model_manager

    if _tts_model_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS model not initialized",
        )

    try:
        await _tts_model_manager.switch_voice(voice_id)
        logger.info(f"Switched to voice: {voice_id}")

        return {
            "status": "success",
            "voice_id": voice_id,
            "message": f"Switched to voice: {voice_id}",
        }

    except Exception as e:
        logger.error(f"Failed to switch voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to switch voice: {str(e)}",
        )


@router.get("/api/v1/voice/{voice_id}")
async def get_voice(voice_id: str):
    """Get information about a specific voice.

    Args:
        voice_id: Voice identifier.

    Returns:
        Voice information.
    """
    from src.models.tts.model_manager import _tts_model_manager

    if _tts_model_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS model not initialized",
        )

    try:
        voices = await _tts_model_manager.list_voices()

        # Find the requested voice
        for voice in voices:
            if voice.get("voice_id") == voice_id:
                return voice

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice not found: {voice_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get voice: {str(e)}",
        )


@router.delete("/api/v1/voice/{voice_id}")
async def delete_voice(voice_id: str):
    """Delete a custom voice.

    Args:
        voice_id: Voice identifier to delete.

    Returns:
        Success message.
    """
    if voice_id == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default voice",
        )

    settings = ServerSettings()
    voices_path = Path(settings.voices_path)

    # Find and delete the voice file
    voice_found = False

    if voices_path.exists():
        for voice_file in voices_path.glob(f"{voice_id}.*"):
            voice_file.unlink()
            voice_found = True
            logger.info(f"Deleted voice file: {voice_file}")

    if voice_found:
        return {
            "status": "success",
            "voice_id": voice_id,
            "message": f"Voice deleted: {voice_id}",
        }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Voice not found: {voice_id}",
    )


@router.post("/api/v1/voice/parameters")
async def set_voice_parameters(
    speed: Optional[float] = None,
    stability: Optional[float] = None,
    pitch: Optional[float] = None,
):
    """Set voice synthesis parameters.

    Args:
        speed: Speech speed multiplier (0.5 to 2.0).
        stability: Stability/CFG scale (0.0 to 1.0).
        pitch: Pitch adjustment (0.5 to 2.0).

    Returns:
        Current parameters.
    """
    from src.models.tts.model_manager import _tts_model_manager

    if _tts_model_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS model not initialized",
        )

    try:
        _tts_model_manager.set_voice_parameters(
            speed=speed,
            stability=stability,
            pitch=pitch,
        )

        # Return current parameters
        return {
            "speed": _tts_model_manager._model.config.speed if _tts_model_manager._model else 1.0,
            "stability": _tts_model_manager._model.config.stability if _tts_model_manager._model else 1.0,
            "pitch": _tts_model_manager._model.config.pitch if _tts_model_manager._model else 1.0,
        }

    except Exception as e:
        logger.error(f"Failed to set voice parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set parameters: {str(e)}",
        )
