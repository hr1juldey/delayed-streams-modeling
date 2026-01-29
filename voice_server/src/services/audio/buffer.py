"""Audio buffer with backpressure handling for streaming.

Provides bounded buffer management for audio streaming with
configurable size limits and backpressure signals.
"""

import asyncio
import time
import numpy as np
from typing import Optional, Deque
from collections import deque

from voice_server.config.logging_config import get_logger
from voice_server.src.core.exceptions import AudioProcessingException

logger = get_logger(__name__)


class AudioBuffer:
    """Thread-safe audio buffer with backpressure handling.

    Features:
    - Bounded size to prevent memory exhaustion
    - Backpressure signaling when buffer is full
    - Async put/get operations
    - Drop-old strategy when buffer overflows
    - Statistics tracking
    """

    def __init__(
        self,
        max_size_ms: float = 5000.0,
        sample_rate: int = 24000,
        backpressure_threshold: float = 0.8,
        drop_strategy: str = "oldest",
    ):
        """Initialize the audio buffer.

        Args:
            max_size_ms: Maximum buffer size in milliseconds.
            sample_rate: Sample rate in Hz.
            backpressure_threshold: Fraction of max size to trigger backpressure (0.0-1.0).
            drop_strategy: Strategy when buffer is full ("oldest", "newest", "block").
        """
        self.max_size_ms = max_size_ms
        self.sample_rate = sample_rate
        self.max_size_samples = int((max_size_ms / 1000.0) * sample_rate)
        self.backpressure_threshold = backpressure_threshold
        self.drop_strategy = drop_strategy

        # Use deque for efficient append/popleft
        self._buffer: Deque[np.ndarray] = deque()
        self._current_size_samples = 0
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._not_full = asyncio.Condition(self._lock)

        # Statistics
        self._total_added = 0
        self._total_removed = 0
        self._total_dropped = 0
        self._backpressure_triggered = 0
        self._peak_size_samples = 0

    async def put(self, audio: np.ndarray, timeout: Optional[float] = None) -> bool:
        """Add audio to the buffer.

        Args:
            audio: Audio array to add.
            timeout: Max time to wait for buffer space (None = no wait).

        Returns:
            True if audio was added, False if dropped or timed out.

        Raises:
            AudioProcessingException: If timeout expires and drop_strategy is "block".
        """
        async with self._not_full:
            audio_samples = len(audio)

            # Check if we need backpressure
            await self._wait_for_space(audio_samples, timeout)

            async with self._lock:
                # Check if still fits (might have changed while waiting)
                if self._would_overflow(audio_samples):
                    return await self._handle_overflow(audio, timeout)

                # Add to buffer
                self._buffer.append(audio)
                self._current_size_samples += audio_samples
                self._total_added += 1

                # Update peak size
                if self._current_size_samples > self._peak_size_samples:
                    self._peak_size_samples = self._current_size_samples

                # Signal that buffer is not empty
                self._not_empty.notify(1)

                # Check if we should signal backpressure
                if self._is_above_threshold():
                    self._backpressure_triggered += 1

                return True

    async def get(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Get audio chunk from the buffer.

        Args:
            timeout: Max time to wait for data (None = wait forever).

        Returns:
            Audio array, or None if timeout expires.

        Raises:
            AudioProcessingException: If timeout expires.
        """
        async with self._not_empty:
            # Wait for data
            if not self._buffer:
                try:
                    await asyncio.wait_for(self._not_empty.wait(), timeout)
                except asyncio.TimeoutError:
                    return None

            async with self._lock:
                if not self._buffer:
                    return None

                # Get oldest chunk
                audio = self._buffer.popleft()
                self._current_size_samples -= len(audio)
                self._total_removed += 1

                # Signal that there's space available
                self._not_full.notify(1)

                return audio

    async def get_all(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Get all audio from buffer as single array.

        Args:
            timeout: Max time to wait for data.

        Returns:
            Concatenated audio array, or None if empty.
        """
        async with self._not_empty:
            # Wait for at least some data
            if not self._buffer:
                try:
                    await asyncio.wait_for(self._not_empty.wait(), timeout)
                except asyncio.TimeoutError:
                    return None

            async with self._lock:
                if not self._buffer:
                    return None

                # Get all chunks
                chunks = list(self._buffer)
                self._buffer.clear()
                self._current_size_samples = 0
                self._total_removed += len(chunks)

                # Signal space available
                self._not_full.notify(len(chunks))

                # Concatenate
                if len(chunks) == 1:
                    return chunks[0]
                return np.concatenate(chunks)

    def clear(self) -> None:
        """Clear all audio from the buffer."""
        # Need to run in async context if called from sync code
        # For now, just mark as empty - proper clear needs async
        self._buffer.clear()
        self._current_size_samples = 0

    @property
    def size_samples(self) -> int:
        """Current buffer size in samples."""
        return self._current_size_samples

    @property
    def size_ms(self) -> float:
        """Current buffer size in milliseconds."""
        return (self._current_size_samples / self.sample_rate) * 1000.0

    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return self._current_size_samples == 0

    @property
    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return self._current_size_samples >= self.max_size_samples

    @property
    def backpressure_active(self) -> bool:
        """Check if backpressure is active."""
        return self._is_above_threshold()

    @property
    def utilization(self) -> float:
        """Buffer utilization as fraction (0.0-1.0)."""
        return self._current_size_samples / self.max_size_samples

    def get_stats(self) -> dict:
        """Get buffer statistics.

        Returns:
            Dictionary with buffer metrics.
        """
        return {
            "size_ms": self.size_ms,
            "max_size_ms": self.max_size_ms,
            "utilization": self.utilization,
            "backpressure_active": self.backpressure_active,
            "total_added": self._total_added,
            "total_removed": self._total_removed,
            "total_dropped": self._total_dropped,
            "backpressure_triggered": self._backpressure_triggered,
            "peak_size_ms": (self._peak_size_samples / self.sample_rate) * 1000.0,
        }

    async def _wait_for_space(self, needed_samples: int, timeout: Optional[float]) -> None:
        """Wait for buffer space if needed.

        Args:
            needed_samples: Number of samples needed.
            timeout: Max time to wait.

        Raises:
            AudioProcessingException: If timeout expires.
        """
        if self._would_overflow(needed_samples) and self.drop_strategy == "block":
            start_time = time.time()

            while self._would_overflow(needed_samples):
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise AudioProcessingException(
                            f"Buffer full, timeout after {timeout}s"
                        )
                    remaining = timeout - elapsed
                    await self._not_full.wait(remaining)
                else:
                    await self._not_full.wait()

    def _would_overflow(self, additional_samples: int) -> bool:
        """Check if adding samples would overflow buffer.

        Args:
            additional_samples: Number of samples to add.

        Returns:
            True if would overflow, False otherwise.
        """
        return (self._current_size_samples + additional_samples) > self.max_size_samples

    def _is_above_threshold(self) -> bool:
        """Check if buffer is above backpressure threshold.

        Returns:
            True if above threshold, False otherwise.
        """
        return self.utilization > self.backpressure_threshold

    async def _handle_overflow(self, audio: np.ndarray, timeout: Optional[float]) -> bool:
        """Handle buffer overflow based on drop strategy.

        Args:
            audio: Audio to add.
            timeout: Timeout for blocking strategy.

        Returns:
            True if audio was added, False otherwise.

        Raises:
            AudioProcessingException: If blocking and timeout expires.
        """
        if self.drop_strategy == "oldest":
            # Drop oldest chunks until we have space
            needed = len(audio)
            while self._would_overflow(needed) and self._buffer:
                removed = self._buffer.popleft()
                self._current_size_samples -= len(removed)
                self._total_dropped += 1

            # Add new audio
            self._buffer.append(audio)
            self._current_size_samples += len(audio)
            self._total_added += 1
            return True

        elif self.drop_strategy == "newest":
            # Drop the new audio
            self._total_dropped += 1
            logger.warning(f"Dropping audio chunk ({len(audio)} samples)")
            return False

        elif self.drop_strategy == "block":
            # Should have waited in _wait_for_space
            raise AudioProcessingException("Buffer full and drop strategy is 'block'")

        else:
            raise ValueError(f"Unknown drop strategy: {self.drop_strategy}")


class AudioChunkQueue:
    """Async queue for audio chunks with backpressure.

    Simpler alternative to AudioBuffer for chunk-based processing.
    """

    def __init__(self, max_size: int = 100):
        """Initialize the chunk queue.

        Args:
            max_size: Maximum number of chunks in queue.
        """
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=max_size)
        self._total_added = 0
        self._total_removed = 0
        self._total_dropped = 0

    async def put(self, chunk: np.ndarray, block: bool = True) -> bool:
        """Add a chunk to the queue.

        Args:
            chunk: Audio chunk to add.
            block: Whether to block if queue is full.

        Returns:
            True if added, False if dropped (when block=False).
        """
        try:
            if block:
                await self._queue.put(chunk)
                self._total_added += 1
                return True
            else:
                self._queue.put_nowait(chunk)
                self._total_added += 1
                return True
        except asyncio.QueueFull:
            self._total_dropped += 1
            return False

    async def get(self) -> np.ndarray:
        """Get a chunk from the queue.

        Returns:
            Audio chunk.

        Raises:
            asyncio.QueueEmpty: If queue is empty (should use task with done callback).
        """
        chunk = await self._queue.get()
        self._total_removed += 1
        return chunk

    def task_done(self) -> None:
        """Mark a queue item as done."""
        self._queue.task_done()

    async def join(self) -> None:
        """Wait for all items to be processed."""
        await self._queue.join()

    @property
    def size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    @property
    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    def get_stats(self) -> dict:
        """Get queue statistics.

        Returns:
            Dictionary with queue metrics.
        """
        return {
            "size": self.size,
            "max_size": self._queue.maxsize,
            "total_added": self._total_added,
            "total_removed": self._total_removed,
            "total_dropped": self._total_dropped,
        }
