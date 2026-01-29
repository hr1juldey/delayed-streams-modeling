"""Prometheus metrics for the voice server.

Provides metrics collection and formatting for monitoring.
"""

import time
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
)

from config.logging_config import get_logger

logger = get_logger(__name__)

# Create a custom registry for the voice server
_registry = CollectorRegistry()

# Active sessions gauge
active_sessions = Gauge(
    "voice_server_active_sessions",
    "Number of active WebSocket sessions",
    ["service"],  # stt, tts
    registry=_registry,
)

# Request latency histograms
stt_request_latency = Histogram(
    "voice_server_stt_request_latency_ms",
    "STT request latency in milliseconds",
    buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000],
    registry=_registry,
)

tts_request_latency = Histogram(
    "voice_server_tts_request_latency_ms",
    "TTS request latency in milliseconds",
    buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000],
    registry=_registry,
)

# Model status gauge
model_status = Gauge(
    "voice_server_model_status",
    "Model status (1=loaded, 0=not loaded)",
    ["model_type", "model_name"],
    registry=_registry,
)

# Error counter
error_total = Counter(
    "voice_server_errors_total",
    "Total number of errors",
    ["error_type", "service"],
    registry=_registry,
)

# WebSocket connection counter
websocket_connections_total = Counter(
    "voice_server_websocket_connections_total",
    "Total number of WebSocket connections",
    ["service", "status"],  # status: established, closed, error
    registry=_registry,
)

# Audio processing counter
audio_processing_bytes_total = Counter(
    "voice_server_audio_bytes_total",
    "Total audio bytes processed",
    ["direction"],  # input, output
    registry=_registry,
)

# GPU memory gauge (when available)
gpu_memory_bytes = Gauge(
    "voice_server_gpu_memory_bytes",
    "GPU memory usage in bytes",
    ["device"],  # cuda:0, etc.
    registry=_registry,
)

# Session timeouts counter
session_timeouts_total = Counter(
    "voice_server_session_timeouts_total",
    "Total number of session timeouts",
    registry=_registry,
)

# Voice synthesis counter
voice_synthesis_total = Counter(
    "voice_server_voice_synthesis_total",
    "Total number of voice syntheses",
    ["voice_id"],
    registry=_registry,
)


class MetricsCollector:
    """Collects and formats metrics for Prometheus."""

    def __init__(self):
        """Initialize the metrics collector."""
        self._start_time = time.time()

    def update_active_sessions(self, stt_count: int, tts_count: int) -> None:
        """Update active session gauges.

        Args:
            stt_count: Number of active STT sessions.
            tts_count: Number of active TTS sessions.
        """
        active_sessions.labels(service="stt").set(stt_count)
        active_sessions.labels(service="tts").set(tts_count)

    def update_model_status(
        self,
        model_type: str,
        model_name: str,
        loaded: bool,
    ) -> None:
        """Update model status gauge.

        Args:
            model_type: Type of model (stt, tts).
            model_name: Name of the model.
            loaded: Whether the model is loaded.
        """
        model_status.labels(
            model_type=model_type,
            model_name=model_name,
        ).set(1 if loaded else 0)

    def record_stt_latency(self, latency_ms: float) -> None:
        """Record STT request latency.

        Args:
            latency_ms: Latency in milliseconds.
        """
        stt_request_latency.observe(latency_ms)

    def record_tts_latency(self, latency_ms: float) -> None:
        """Record TTS request latency.

        Args:
            latency_ms: Latency in milliseconds.
        """
        tts_request_latency.observe(latency_ms)

    def record_error(self, error_type: str, service: str) -> None:
        """Record an error.

        Args:
            error_type: Type of error.
            service: Service where error occurred (stt, tts).
        """
        error_total.labels(error_type=error_type, service=service).inc()

    def record_websocket_connection(
        self,
        service: str,
        status: str,
    ) -> None:
        """Record a WebSocket connection event.

        Args:
            service: Service (stt, tts).
            status: Connection status (established, closed, error).
        """
        websocket_connections_total.labels(service=service, status=status).inc()

    def record_audio_bytes(self, bytes_count: int, direction: str) -> None:
        """Record processed audio bytes.

        Args:
            bytes_count: Number of bytes.
            direction: Direction (input, output).
        """
        audio_processing_bytes_total.labels(direction=direction).inc(bytes_count)

    def record_session_timeout(self) -> None:
        """Record a session timeout."""
        session_timeouts_total.inc()

    def record_voice_synthesis(self, voice_id: str) -> None:
        """Record a voice synthesis event.

        Args:
            voice_id: Voice identifier.
        """
        voice_synthesis_total.labels(voice_id=voice_id).inc()

    def update_gpu_memory(self, device: str, memory_bytes: int) -> None:
        """Update GPU memory usage.

        Args:
            device: Device identifier (e.g., cuda:0).
            memory_bytes: Memory usage in bytes.
        """
        gpu_memory_bytes.labels(device=device).set(memory_bytes)

    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format.

        Returns:
            Metrics as bytes in Prometheus text format.
        """
        # Add uptime metric
        uptime = time.time() - self._start_time

        # Add custom uptime metric
        from prometheus_client import Gauge

        uptime_gauge = Gauge(
            "voice_server_uptime_seconds",
            "Server uptime in seconds",
            registry=_registry,
        )
        uptime_gauge.set(uptime)

        return generate_latest(_registry)

    def get_metrics_text(self) -> str:
        """Get metrics as text string.

        Returns:
            Metrics in Prometheus text format.
        """
        return self.get_metrics().decode("utf-8")


# Global metrics collector instance
_metrics_collector: MetricsCollector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector.

    Returns:
        MetricsCollector instance.
    """
    return _metrics_collector
