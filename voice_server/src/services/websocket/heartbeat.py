"""Heartbeat monitoring for WebSocket connections.

Provides ping/pong mechanism and connection health tracking.
"""

import asyncio
import time
from typing import Optional, Set, Dict
from dataclasses import dataclass

from voice_server.config.logging_config import get_logger
from voice_server.config.settings import ServerSettings
from voice_server.src.services.websocket.connection import ConnectionManager, ConnectionInfo
from voice_server.src.services.websocket.protocol import Message, MessageType

logger = get_logger(__name__)


@dataclass
class HeartbeatStats:
    """Statistics for heartbeat monitoring.

    Attributes:
        last_ping_sent: Timestamp of last ping sent.
        last_pong_received: Timestamp of last pong received.
        ping_count: Total number of pings sent.
        pong_count: Total number of pongs received.
        missed_pings: Number of pings without response.
        round_trip_times: List of recent round-trip times in seconds.
    """

    last_ping_sent: float = 0.0
    last_pong_received: float = 0.0
    ping_count: int = 0
    pong_count: int = 0
    missed_pings: int = 0
    round_trip_times: list = None

    def __post_init__(self):
        if self.round_trip_times is None:
            self.round_trip_times = []

    @property
    def average_rtt(self) -> Optional[float]:
        """Calculate average round-trip time."""
        if not self.round_trip_times:
            return None
        return sum(self.round_trip_times) / len(self.round_trip_times)

    def add_rtt(self, rtt: float) -> None:
        """Add a round-trip time measurement.

        Keeps only the last 10 measurements.
        """
        self.round_trip_times.append(rtt)
        if len(self.round_trip_times) > 10:
            self.round_trip_times.pop(0)

    @property
    def is_stale(self, timeout_seconds: float = 60.0) -> bool:
        """Check if connection is stale (no recent pong).

        Args:
            timeout_seconds: Seconds without pong to consider stale.

        Returns:
            True if stale, False otherwise.
        """
        if self.last_pong_received == 0.0:
            # Never received a pong
            return self.missed_pings >= 3

        idle_time = time.time() - self.last_pong_received
        return idle_time > timeout_seconds


class HeartbeatMonitor:
    """Monitors and manages heartbeat for WebSocket connections.

    Features:
    - Periodic ping transmission
    - Pong response tracking
    - Round-trip time measurement
    - Stale connection detection
    - Automatic cleanup of dead connections
    """

    PING_INTERVAL_SECONDS = 30.0
    PING_TIMEOUT_SECONDS = 60.0
    MAX_MISSED_PINGS = 3

    def __init__(
        self,
        connection_manager: ConnectionManager,
        settings: ServerSettings | None = None,
    ):
        """Initialize the heartbeat monitor.

        Args:
            connection_manager: Connection manager to monitor.
            settings: Optional server settings.
        """
        self.connection_manager = connection_manager
        self.settings = settings or ServerSettings()
        self._heartbeat_stats: Dict[str, HeartbeatStats] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

        # Use settings to override defaults
        self.ping_interval = self.settings.heartbeat_interval_seconds
        self.ping_timeout = self.ping_interval * 2
        self.max_missed_pings = self.MAX_MISSED_PINGS

    async def start(self) -> None:
        """Start the heartbeat monitor background task."""
        if self._running:
            logger.warning("Heartbeat monitor already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Heartbeat monitor started")

    async def stop(self) -> None:
        """Stop the heartbeat monitor."""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Heartbeat monitor stopped")

    def register_session(self, session_id: str) -> None:
        """Register a new session for heartbeat monitoring.

        Args:
            session_id: Session identifier.
        """
        if session_id not in self._heartbeat_stats:
            self._heartbeat_stats[session_id] = HeartbeatStats()
            logger.debug(f"Registered session for heartbeat: {session_id}")

    def unregister_session(self, session_id: str) -> None:
        """Unregister a session from heartbeat monitoring.

        Args:
            session_id: Session identifier.
        """
        if session_id in self._heartbeat_stats:
            stats = self._heartbeat_stats.pop(session_id)
            logger.debug(
                f"Unregistered session from heartbeat: {session_id}, "
                f"pings={stats.ping_count}, pongs={stats.pong_count}"
            )

    def record_pong(self, session_id: str, ping_timestamp: float) -> None:
        """Record a pong response from a session.

        Args:
            session_id: Session identifier.
            ping_timestamp: Timestamp from the original ping.
        """
        stats = self._heartbeat_stats.get(session_id)
        if not stats:
            logger.debug(f"Pong from unregistered session: {session_id}")
            return

        stats.pong_count += 1
        stats.last_pong_received = time.time()
        stats.missed_pings = 0

        # Calculate round-trip time
        rtt = stats.last_pong_received - ping_timestamp
        stats.add_rtt(rtt)

        logger.debug(f"Received pong from {session_id}, RTT={rtt*1000:.1f}ms")

    async def send_ping(self, session_id: str, protocol) -> bool:
        """Send a ping message to a session.

        Args:
            session_id: Session identifier.
            protocol: Message protocol instance.

        Returns:
            True if ping was sent successfully, False otherwise.
        """
        stats = self._heartbeat_stats.get(session_id)
        if not stats:
            return False

        try:
            ping_timestamp = time.time()
            stats.last_ping_sent = ping_timestamp
            stats.ping_count += 1

            # Create ping message
            from voice_server.src.services.websocket.protocol import Message

            ping_message = Message(
                type=MessageType.HEARTBEAT,
                data={"ping": ping_timestamp},
                session_id=session_id,
            )

            # Send via connection manager
            return await self.connection_manager.send_message(session_id, ping_message)

        except Exception as e:
            logger.error(f"Error sending ping to {session_id}: {e}")
            return False

    async def _monitor_loop(self) -> None:
        """Background task to monitor connections and send pings."""
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)

                # Get all active sessions
                active_sessions = self.connection_manager.get_active_sessions()

                for session_id in active_sessions:
                    await self._check_and_ping_session(session_id)

            except asyncio.CancelledError:
                logger.info("Heartbeat monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat monitor loop: {e}")

    async def _check_and_ping_session(self, session_id: str) -> None:
        """Check a session and send ping if needed.

        Args:
            session_id: Session identifier.
        """
        stats = self._heartbeat_stats.get(session_id)

        # Create stats if not exists (session connected after monitor started)
        if not stats:
            self.register_session(session_id)
            stats = self._heartbeat_stats.get(session_id)

        # Check for stale connection
        if stats.is_stale(timeout_seconds=self.ping_timeout):
            logger.warning(
                f"Stale connection detected: {session_id}, "
                f"missed_pings={stats.missed_pings}"
            )
            await self.connection_manager.disconnect(session_id)
            self.unregister_session(session_id)
            return

        # Send ping
        conn_info = self.connection_manager.get_connection(session_id)
        if conn_info:
            success = await self.send_ping(session_id, conn_info.protocol)
            if not success:
                stats.missed_pings += 1
            else:
                # Reset missed pings on successful send
                stats.missed_pings = 0

    def get_stats(self, session_id: str) -> Optional[HeartbeatStats]:
        """Get heartbeat statistics for a session.

        Args:
            session_id: Session identifier.

        Returns:
            HeartbeatStats if session exists, None otherwise.
        """
        return self._heartbeat_stats.get(session_id)

    def get_all_stats(self) -> Dict[str, HeartbeatStats]:
        """Get heartbeat statistics for all sessions.

        Returns:
            Dictionary mapping session IDs to their stats.
        """
        return self._heartbeat_stats.copy()

    def get_health_summary(self) -> dict:
        """Get a summary of connection health.

        Returns:
            Dictionary with health metrics.
        """
        total_sessions = len(self._heartbeat_stats)
        healthy_sessions = sum(
            1
            for stats in self._heartbeat_stats.values()
            if not stats.is_stale(timeout_seconds=self.ping_timeout)
        )

        # Calculate average RTT across all sessions
        rtts = [
            stats.average_rtt
            for stats in self._heartbeat_stats.values()
            if stats.average_rtt is not None
        ]
        avg_rtt = sum(rtts) / len(rtts) if rtts else None

        return {
            "total_sessions": total_sessions,
            "healthy_sessions": healthy_sessions,
            "unhealthy_sessions": total_sessions - healthy_sessions,
            "average_rtt_ms": avg_rtt * 1000 if avg_rtt else None,
            "ping_interval_seconds": self.ping_interval,
            "ping_timeout_seconds": self.ping_timeout,
        }


# Global heartbeat monitor instance
_heartbeat_monitor: Optional[HeartbeatMonitor] = None


def get_heartbeat_monitor() -> HeartbeatMonitor:
    """Get the global heartbeat monitor instance.

    Returns:
        The HeartbeatMonitor instance.

    Raises:
        RuntimeError: If heartbeat monitor has not been initialized.
    """
    global _heartbeat_monitor
    if _heartbeat_monitor is None:
        raise RuntimeError("Heartbeat monitor not initialized")
    return _heartbeat_monitor


def set_heartbeat_monitor(monitor: HeartbeatMonitor) -> None:
    """Set the global heartbeat monitor instance.

    Args:
        monitor: The HeartbeatMonitor instance to set.
    """
    global _heartbeat_monitor
    _heartbeat_monitor = monitor
