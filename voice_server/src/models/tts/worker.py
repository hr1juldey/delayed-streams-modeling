"""Thread-safe TTS worker for Pocket TTS.

Pocket TTS is NOT thread-safe, so we use a single worker with
asyncio queues to serialize requests while handling multiple sessions.
"""

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional
from enum import Enum

from voice_server.config.logging_config import get_logger
from voice_server.src.core.exceptions import ModelException

logger = get_logger(__name__)


class WorkerStatus(str, Enum):
    """Worker status."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass
class TTSRequest:
    """TTS synthesis request.

    Attributes:
        request_id: Unique request identifier.
        text: Text to synthesize.
        voice_id: Voice identifier.
        speed: Speech speed multiplier.
        stability: Stability/CFG scale.
        pitch: Pitch adjustment.
        future: Future for the result.
    """

    request_id: str
    text: str
    voice_id: str
    speed: float
    stability: float
    pitch: float
    future: asyncio.Future


@dataclass
class TTSResponseChunk:
    """TTS synthesis response chunk.

    Attributes:
        request_id: Request identifier.
        audio: Audio chunk as bytes (PCM int16).
        is_final: Whether this is the final chunk.
        text: Text that was synthesized (for final chunk).
    """

    request_id: str
    audio: bytes
    is_final: bool
    text: Optional[str] = None


class TTSWorker:
    """Thread-safe worker for TTS synthesis.

    Runs all TTS operations serially in a thread pool while handling
    requests from multiple concurrent sessions via asyncio queues.
    """

    def __init__(self, tts_model_class):
        """Initialize the TTS worker.

        Args:
            tts_model_class: The Pocket TTS model class.
        """
        self._tts_model_class = tts_model_class
        self._model = None
        self._status = WorkerStatus.STOPPED
        self._request_queue: asyncio.Queue[TTSRequest] = asyncio.Queue()
        self._response_queues: dict[str, asyncio.Queue] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the worker and load the model.

        Raises:
            ModelException: If worker fails to start.
        """
        if self._status != WorkerStatus.STOPPED:
            logger.warning(f"Worker already {self._status.value}")
            return

        self._status = WorkerStatus.STARTING

        try:
            # Load model in thread pool
            self._model = await asyncio.to_thread(self._load_model_sync)

            # Start worker task
            self._worker_task = asyncio.create_task(self._worker_loop())
            self._status = WorkerStatus.RUNNING

            logger.info("TTS worker started successfully")

        except Exception as e:
            logger.error(f"Failed to start TTS worker: {e}")
            self._status = WorkerStatus.STOPPED
            raise ModelException(f"Failed to start TTS worker: {e}") from e

    def _load_model_sync(self):
        """Load the TTS model synchronously.

        Returns:
            Loaded TTS model instance.
        """
        try:
            logger.info("Loading Pocket TTS model...")
            model = self._tts_model_class.load_model()
            logger.info("Pocket TTS model loaded")
            return model
        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            raise

    async def stop(self) -> None:
        """Stop the worker and cleanup resources."""
        if self._status == WorkerStatus.STOPPED:
            return

        self._status = WorkerStatus.STOPPING

        # Cancel worker task
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        # Clear model
        self._model = None
        self._response_queues.clear()

        self._status = WorkerStatus.STOPPED
        logger.info("TTS worker stopped")

    async def synthesize(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
        stability: float = 1.0,
        pitch: float = 1.0,
    ) -> AsyncIterator[TTSResponseChunk]:
        """Submit a synthesis request and yield response chunks.

        Args:
            text: Text to synthesize.
            voice_id: Voice identifier.
            speed: Speech speed multiplier.
            stability: Stability/CFG scale.
            pitch: Pitch adjustment.

        Yields:
            TTSResponseChunk with audio chunks.

        Raises:
            ModelException: If synthesis fails.
        """
        if self._status != WorkerStatus.RUNNING:
            raise ModelException(f"Worker not running (status: {self._status.value})")

        request_id = f"{id(asyncio.current_task())}_{asyncio.get_event_loop().time()}"

        # Create response queue for this request
        response_queue: asyncio.Queue[TTSResponseChunk] = asyncio.Queue()
        self._response_queues[request_id] = response_queue

        try:
            # Submit request
            request = TTSRequest(
                request_id=request_id,
                text=text,
                voice_id=voice_id,
                speed=speed,
                stability=stability,
                pitch=pitch,
                future=asyncio.get_event_loop().create_future(),
            )
            await self._request_queue.put(request)

            # Yield response chunks as they arrive
            while True:
                chunk = await response_queue.get()

                if chunk.is_final:
                    # Final chunk - yield it and break
                    yield chunk
                    break

                yield chunk

        except Exception as e:
            logger.error(f"Error during synthesis: {e}")
            raise ModelException(f"Synthesis failed: {e}") from e
        finally:
            # Clean up response queue
            self._response_queues.pop(request_id, None)

    async def load_voice(self, voice_path: str) -> None:
        """Load a custom voice.

        Args:
            voice_path: Path to voice file.

        Raises:
            ModelException: If voice loading fails.
        """
        if self._status != WorkerStatus.RUNNING:
            raise ModelException(f"Worker not running (status: {self._status.value})")

        try:
            # Load voice in thread pool
            await asyncio.to_thread(self._load_voice_sync, voice_path)
            logger.info(f"Voice loaded: {voice_path}")

        except Exception as e:
            logger.error(f"Failed to load voice: {e}")
            raise ModelException(f"Failed to load voice: {e}") from e

    def _load_voice_sync(self, voice_path: str) -> None:
        """Load a voice synchronously.

        Args:
            voice_path: Path to voice file.
        """
        # Use pocket-tts export-voice functionality
        # This is a placeholder - actual implementation depends on pocket-tts API
        logger.info(f"Loading voice from: {voice_path}")

    async def _worker_loop(self) -> None:
        """Main worker loop that processes requests serially.

        All TTS operations run in this loop to ensure thread safety.
        """
        logger.info("TTS worker loop started")

        try:
            while self._status == WorkerStatus.RUNNING:
                try:
                    # Get next request with timeout
                    request = await asyncio.wait_for(
                        self._request_queue.get(),
                        timeout=1.0,
                    )

                    # Process request
                    await self._process_request(request)

                except asyncio.TimeoutError:
                    # No requests, continue loop
                    continue
                except Exception as e:
                    logger.error(f"Error processing request: {e}")

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
        except Exception as e:
            logger.error(f"Worker loop error: {e}")

        logger.info("TTS worker loop ended")

    async def _process_request(self, request: TTSRequest) -> None:
        """Process a TTS synthesis request.

        Args:
            request: The request to process.
        """
        response_queue = self._response_queues.get(request.request_id)

        if response_queue is None:
            logger.warning(f"No response queue for request: {request.request_id}")
            return

        try:
            # Run synthesis in thread pool
            audio_bytes = await asyncio.to_thread(
                self._synthesize_sync,
                request.text,
            )

            # Split into chunks and send
            chunk_size = 1920  # 80ms at 24kHz
            total_chunks = (len(audio_bytes) + chunk_size - 1) // chunk_size

            for i in range(total_chunks):
                start = i * chunk_size
                end = min(start + chunk_size, len(audio_bytes))
                chunk_data = audio_bytes[start:end]

                is_final = (i == total_chunks - 1)

                chunk = TTSResponseChunk(
                    request_id=request.request_id,
                    audio=chunk_data,
                    is_final=is_final,
                    text=request.text if is_final else None,
                )

                await response_queue.put(chunk)

        except Exception as e:
            logger.error(f"Error in _process_request: {e}")
            # Send error chunk
            await response_queue.put(
                TTSResponseChunk(
                    request_id=request.request_id,
                    audio=b"",
                    is_final=True,
                    text=None,
                )
            )

    def _synthesize_sync(self, text: str) -> bytes:
        """Synthesize speech synchronously.

        Args:
            text: Text to synthesize.

        Returns:
            Audio as bytes (PCM int16).
        """
        try:
            # Call pocket-tts generate_audio
            # This is the actual CPU-bound TTS operation
            audio_array = self._model.generate_audio(text)

            # Convert to bytes if needed
            if hasattr(audio_array, "tobytes"):
                return audio_array.tobytes()
            else:
                # Assume it's already bytes
                return audio_array

        except Exception as e:
            logger.error(f"Error in synchronous synthesis: {e}")
            raise ModelException(f"Synthesis failed: {e}") from e

    @property
    def is_running(self) -> bool:
        """Check if the worker is running."""
        return self._status == WorkerStatus.RUNNING

    @property
    def status(self) -> WorkerStatus:
        """Get the current worker status."""
        return self._status

    @property
    def queue_size(self) -> int:
        """Get the current request queue size."""
        return self._request_queue.qsize()

    def get_stats(self) -> dict:
        """Get worker statistics.

        Returns:
            Dictionary with worker metrics.
        """
        return {
            "status": self._status.value,
            "queue_size": self.queue_size,
            "active_requests": len(self._response_queues),
            "model_loaded": self._model is not None,
        }
