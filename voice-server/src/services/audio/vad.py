"""Voice Activity Detection (VAD) for audio stream processing.

Provides server-side VAD capabilities using semantic VAD from the STT model
or energy-based VAD for simple scenarios.
"""

import asyncio
import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from config.logging_config import get_logger

logger = get_logger(__name__)


class VADMode(str, Enum):
    """VAD operation modes."""

    ENERGY = "energy"  # Energy-based VAD
    SEMANTIC = "semantic"  # Semantic VAD from STT model
    HYBRID = "hybrid"  # Combined energy + semantic VAD
    CLIENT = "client"  # Client-side VAD (server does nothing)


@dataclass
class VADResult:
    """Result from VAD processing.

    Attributes:
        is_speech: Whether the segment contains speech.
        probability: Confidence probability (0.0-1.0).
        energy: Audio energy level.
        timestamp: Timestamp of the detection.
    """

    is_speech: bool
    probability: float
    energy: float
    timestamp: float


@dataclass
class SpeechSegment:
    """A detected speech segment.

    Attributes:
        start_sample: Start sample index.
        end_sample: End sample index (exclusive).
        start_time: Start time in seconds.
        end_time: End time in seconds.
        confidence: Average confidence score.
    """

    start_sample: int
    end_sample: int
    start_time: float
    end_time: float
    confidence: float


class EnergyVAD:
    """Energy-based Voice Activity Detection.

    Uses audio energy levels to detect speech segments.
    Simple but effective for clear speech with low background noise.
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        frame_duration_ms: int = 30,
        speech_threshold_db: float = -40.0,
        silence_threshold_ms: int = 300,
        min_speech_duration_ms: int = 100,
    ):
        """Initialize the energy-based VAD.

        Args:
            sample_rate: Audio sample rate in Hz.
            frame_duration_ms: Frame duration for energy calculation.
            speech_threshold_db: Energy threshold for speech detection (dB).
            silence_threshold_ms: Minimum silence to mark speech end.
            min_speech_duration_ms: Minimum duration for valid speech segment.
        """
        self.sample_rate = sample_rate
        self.frame_size = int((frame_duration_ms / 1000.0) * sample_rate)
        self.speech_threshold_db = speech_threshold_db
        self.silence_threshold_samples = int((silence_threshold_ms / 1000.0) * sample_rate)
        self.min_speech_samples = int((min_speech_duration_ms / 1000.0) * sample_rate)

        # State tracking
        self._in_speech = False
        self._speech_start_sample = 0
        self._silence_start_sample = 0
        self._current_segment_frames: List[float] = []

    def process_frame(self, audio: np.ndarray, sample_index: int = 0) -> VADResult:
        """Process a single audio frame for VAD.

        Args:
            audio: Audio frame (float32, -1.0 to 1.0).
            sample_index: Sample index of the frame start.

        Returns:
            VADResult for this frame.
        """
        # Calculate energy
        energy = self._calculate_energy(audio)
        energy_db = self._energy_to_db(energy)

        # Determine if speech based on threshold
        is_speech = energy_db > self.speech_threshold_db

        # Smooth probability
        probability = self._smooth_probability(is_speech)

        return VADResult(
            is_speech=is_speech,
            probability=probability,
            energy=energy_db,
            timestamp=sample_index / self.sample_rate,
        )

    def process_stream(
        self,
        audio: np.ndarray,
    ) -> Tuple[List[SpeechSegment], List[VADResult]]:
        """Process a complete audio stream to find speech segments.

        Args:
            audio: Complete audio array.

        Returns:
            Tuple of (detected segments, frame results).
        """
        segments = []
        results = []

        # Reset state
        self.reset()

        # Process frames
        for i in range(0, len(audio), self.frame_size):
            frame = audio[i:i + self.frame_size]
            if len(frame) < self.frame_size:
                break

            result = self.process_frame(frame, i)
            results.append(result)

            # Update state
            if result.is_speech and not self._in_speech:
                # Start of speech
                self._in_speech = True
                self._speech_start_sample = i
                self._current_segment_frames = [result.probability]
            elif result.is_speech and self._in_speech:
                # Continue speech
                self._current_segment_frames.append(result.probability)
            elif not result.is_speech and self._in_speech:
                # Potential end of speech
                self._silence_start_sample = i

                # Check if silence threshold met
                silence_duration = i - self._silence_start_sample
                if silence_duration >= self.silence_threshold_samples:
                    # End of speech segment
                    speech_duration = i - self._speech_start_sample
                    if speech_duration >= self.min_speech_samples:
                        # Valid segment
                        avg_confidence = np.mean(self._current_segment_frames)
                        segment = SpeechSegment(
                            start_sample=self._speech_start_sample,
                            end_sample=i,
                            start_time=self._speech_start_sample / self.sample_rate,
                            end_time=i / self.sample_rate,
                            confidence=avg_confidence,
                        )
                        segments.append(segment)

                    # Reset
                    self._in_speech = False
                    self._current_segment_frames = []

        # Handle final segment if still in speech
        if self._in_speech:
            speech_duration = len(audio) - self._speech_start_sample
            if speech_duration >= self.min_speech_samples:
                avg_confidence = np.mean(self._current_segment_frames)
                segment = SpeechSegment(
                    start_sample=self._speech_start_sample,
                    end_sample=len(audio),
                    start_time=self._speech_start_sample / self.sample_rate,
                    end_time=len(audio) / self.sample_rate,
                    confidence=avg_confidence,
                )
                segments.append(segment)

        return segments, results

    def _calculate_energy(self, audio: np.ndarray) -> float:
        """Calculate RMS energy of audio frame.

        Args:
            audio: Audio frame.

        Returns:
            RMS energy.
        """
        return np.sqrt(np.mean(audio ** 2))

    def _energy_to_db(self, energy: float) -> float:
        """Convert energy to dB.

        Args:
            energy: RMS energy.

        Returns:
            Energy in dB (can be negative).
        """
        if energy < 1e-10:
            return -100.0
        return 20 * np.log10(energy)

    def _smooth_probability(self, is_speech: bool) -> float:
        """Smooth the speech probability.

        Args:
            is_speech: Raw speech detection result.

        Returns:
            Smoothed probability.
        """
        # Simple smoothing - could be enhanced with hysteresis
        return 0.9 if is_speech else 0.1

    def reset(self) -> None:
        """Reset VAD state."""
        self._in_speech = False
        self._speech_start_sample = 0
        self._silence_start_sample = 0
        self._current_segment_frames = []


class SemanticVAD:
    """Semantic VAD using STT model's VAD heads.

    Wraps the semantic VAD from the Kyutai STT model.
    """

    def __init__(self, stt_model=None):
        """Initialize the semantic VAD.

        Args:
            stt_model: Optional STT model with VAD capability.
        """
        self.stt_model = stt_model

    async def process_frame(
        self,
        audio: np.ndarray,
    ) -> VADResult:
        """Process audio frame using semantic VAD.

        Args:
            audio: Audio frame to analyze.

        Returns:
            VADResult from semantic analysis.
        """
        if self.stt_model is None:
            # Fallback to energy-based VAD
            logger.warning("STT model not available, using energy-based VAD fallback")
            energy_vad = EnergyVAD()
            return energy_vad.process_frame(audio)

        # Use STT model's VAD
        # This would call the model's step_with_extra_heads method
        # and extract the VAD decision
        try:
            # TODO: Integrate with actual STT model VAD
            # For now, return placeholder
            return VADResult(
                is_speech=False,
                probability=0.0,
                energy=-100.0,
                timestamp=0.0,
            )
        except Exception as e:
            logger.error(f"Error in semantic VAD: {e}")
            # Fallback
            energy_vad = EnergyVAD()
            return energy_vad.process_frame(audio)


class VADProcessor:
    """Main VAD processor that delegates to appropriate VAD implementation.

    Supports energy-based, semantic, and hybrid VAD modes.
    """

    def __init__(
        self,
        mode: VADMode = VADMode.ENERGY,
        sample_rate: int = 24000,
        stt_model=None,
        speech_threshold_db: float = -40.0,
        silence_threshold_ms: int = 300,
    ):
        """Initialize the VAD processor.

        Args:
            mode: VAD mode to use.
            sample_rate: Audio sample rate.
            stt_model: Optional STT model for semantic VAD.
            speech_threshold_db: Energy threshold for speech.
            silence_threshold_ms: Silence duration for speech end.
        """
        self.mode = mode
        self.sample_rate = sample_rate

        # Initialize VAD implementations
        self._energy_vad = EnergyVAD(
            sample_rate=sample_rate,
            speech_threshold_db=speech_threshold_db,
            silence_threshold_ms=silence_threshold_ms,
        )
        self._semantic_vad = SemanticVAD(stt_model) if stt_model else None

    async def process_audio(
        self,
        audio: np.ndarray,
    ) -> VADResult:
        """Process audio for voice activity.

        Args:
            audio: Audio frame to analyze.

        Returns:
            VADResult indicating speech presence.
        """
        if self.mode == VADMode.CLIENT:
            # Client-side VAD - always return true
            return VADResult(
                is_speech=True,
                probability=1.0,
                energy=0.0,
                timestamp=0.0,
            )

        elif self.mode == VADMode.ENERGY:
            # Run energy VAD in thread pool to avoid blocking
            return await asyncio.to_thread(self._energy_vad.process_frame, audio)

        elif self.mode == VADMode.SEMANTIC:
            if self._semantic_vad:
                return await self._semantic_vad.process_frame(audio)
            else:
                # Fallback to energy VAD
                return await asyncio.to_thread(self._energy_vad.process_frame, audio)

        elif self.mode == VADMode.HYBRID:
            # Combine energy and semantic VAD
            energy_result = await asyncio.to_thread(self._energy_vad.process_frame, audio)
            if self._semantic_vad:
                semantic_result = await self._semantic_vad.process_frame(audio)
                # Combine results (AND logic)
                return VADResult(
                    is_speech=energy_result.is_speech and semantic_result.is_speech,
                    probability=(energy_result.probability + semantic_result.probability) / 2,
                    energy=energy_result.energy,
                    timestamp=energy_result.timestamp,
                )
            return energy_result

        else:
            logger.warning(f"Unknown VAD mode: {self.mode}, using energy VAD")
            return await asyncio.to_thread(self._energy_vad.process_frame, audio)

    def reset(self) -> None:
        """Reset VAD state."""
        self._energy_vad.reset()

    @staticmethod
    def get_default_thresholds() -> dict:
        """Get default threshold values for different noise levels.

        Returns:
            Dictionary of threshold configurations.
        """
        return {
            "quiet": {
                "speech_threshold_db": -50.0,
                "silence_threshold_ms": 500,
            },
            "normal": {
                "speech_threshold_db": -40.0,
                "silence_threshold_ms": 300,
            },
            "noisy": {
                "speech_threshold_db": -30.0,
                "silence_threshold_ms": 200,
            },
        }
