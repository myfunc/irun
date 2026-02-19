"""
Re-export of GameSession protocol for net consumers.

The protocol lives in ivan.games.game_session to avoid circular imports
between net.server and games.session_adapter.
"""

from ivan.games.game_session import GameSession

__all__ = ["GameSession"]
