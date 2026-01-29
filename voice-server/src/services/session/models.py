"""Session management models and data structures.

Defines the data structures for session history, conversation turns,
and session state management.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """Session status values."""

    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"
    TIMEOUT = "timeout"


@dataclass
class ConversationTurn:
    """A single turn in a conversation.

    Attributes:
        turn_id: Unique turn identifier.
        timestamp: When the turn occurred.
        role: The role (user, assistant, system).
        content: The text content.
        audio_duration: Optional audio duration in seconds.
        metadata: Additional metadata.
    """

    turn_id: str
    timestamp: float
    role: str  # "user", "assistant", "system"
    content: str
    audio_duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "role": self.role,
            "content": self.content,
            "audio_duration": self.audio_duration,
            "metadata": self.metadata,
        }


@dataclass
class SessionHistory:
    """History of a session's conversation.

    Attributes:
        session_id: Session identifier.
        turns: List of conversation turns.
        created_at: When the session was created.
        updated_at: Last activity timestamp.
        total_turns: Total number of turns.
        total_audio_duration: Total audio duration in seconds.
    """

    session_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    total_turns: int = 0
    total_audio_duration: float = 0.0

    def add_turn(self, turn: ConversationTurn) -> None:
        """Add a conversation turn.

        Args:
            turn: The turn to add.
        """
        self.turns.append(turn)
        self.updated_at = time.time()
        self.total_turns = len(self.turns)
        if turn.audio_duration:
            self.total_audio_duration += turn.audio_duration

    def get_turns(self, role: Optional[str] = None) -> List[ConversationTurn]:
        """Get conversation turns, optionally filtered by role.

        Args:
            role: Optional role filter.

        Returns:
            List of turns.
        """
        if role:
            return [t for t in self.turns if t.role == role]
        return self.turns.copy()

    def get_recent_turns(self, count: int = 10) -> List[ConversationTurn]:
        """Get the most recent conversation turns.

        Args:
            count: Number of recent turns to return.

        Returns:
            List of recent turns.
        """
        return self.turns[-count:] if self.turns else []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "created_datetime": datetime.fromtimestamp(self.created_at).isoformat(),
            "updated_at": self.updated_at,
            "updated_datetime": datetime.fromtimestamp(self.updated_at).isoformat(),
            "total_turns": self.total_turns,
            "total_audio_duration": self.total_audio_duration,
            "turns": [turn.to_dict() for turn in self.turns],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionHistory":
        """Create SessionHistory from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            SessionHistory instance.
        """
        turns = []
        for turn_data in data.get("turns", []):
            turn = ConversationTurn(
                turn_id=turn_data["turn_id"],
                timestamp=turn_data["timestamp"],
                role=turn_data["role"],
                content=turn_data["content"],
                audio_duration=turn_data.get("audio_duration"),
                metadata=turn_data.get("metadata", {}),
            )
            turns.append(turn)

        return cls(
            session_id=data["session_id"],
            turns=turns,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            total_turns=data.get("total_turns", len(turns)),
            total_audio_duration=data.get("total_audio_duration", 0.0),
        )


@dataclass
class SessionState:
    """Current state of an active session.

    Attributes:
        session_id: Unique session identifier.
        status: Current session status.
        created_at: When the session was created.
        last_activity: Last activity timestamp.
        connection_info: WebSocket connection info (if applicable).
        history: Session conversation history.
        metadata: Additional session metadata.
    """

    session_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    connection_info: Optional[Dict[str, Any]] = None
    history: Optional[SessionHistory] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_activity

    @property
    def age(self) -> float:
        """Get session age in seconds."""
        return time.time() - self.created_at

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "created_datetime": datetime.fromtimestamp(self.created_at).isoformat(),
            "last_activity": self.last_activity,
            "last_activity_datetime": datetime.fromtimestamp(self.last_activity).isoformat(),
            "idle_time_seconds": self.idle_time,
            "age_seconds": self.age,
            "connection_info": self.connection_info,
            "metadata": self.metadata,
            "history": self.history.to_dict() if self.history else None,
        }


@dataclass
class SessionStats:
    """Statistics for session tracking.

    Attributes:
        total_sessions: Total number of sessions created.
        active_sessions: Currently active sessions.
        closed_sessions: Total closed sessions.
        timeout_sessions: Total sessions that timed out.
        total_turns: Total conversation turns across all sessions.
        total_audio_duration: Total audio duration in seconds.
    """

    total_sessions: int = 0
    active_sessions: int = 0
    closed_sessions: int = 0
    timeout_sessions: int = 0
    total_turns: int = 0
    total_audio_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_sessions": self.total_sessions,
            "active_sessions": self.active_sessions,
            "closed_sessions": self.closed_sessions,
            "timeout_sessions": self.timeout_sessions,
            "total_turns": self.total_turns,
            "total_audio_duration": self.total_audio_duration,
        }
