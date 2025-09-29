import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging
from models import ChatSession, SessionSummary, Message
from llm_service import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, storage_path: str = None, llm_service: LLMService = None):
        self.storage_path = Path(storage_path or os.getenv('SESSION_STORAGE_PATH', './sessions'))
        self.storage_path.mkdir(exist_ok=True)
        self.llm_service = llm_service or LLMService()

        # Storage files
        self.sessions_file = self.storage_path / 'sessions.json'
        self.summaries_file = self.storage_path / 'summaries.json'

        logger.info(f"SessionManager initialized with storage path: {self.storage_path}")

    def create_session(self, memory_enabled: bool = True) -> ChatSession:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())[:8]  # Short UUID for readability
        previous_summaries = []

        # Load previous summaries if memory is enabled
        if memory_enabled:
            previous_summaries = self._load_all_summaries()

        session = ChatSession(
            session_id=session_id,
            messages=[],
            start_time=datetime.now(),
            is_active=True,
            memory_enabled=memory_enabled,
            previous_summaries=previous_summaries
        )

        logger.info(f"Created new session {session_id} with memory_enabled={memory_enabled}")
        return session

    def save_session(self, session: ChatSession) -> None:
        """Save session to storage"""
        try:
            sessions = self._load_sessions()
            sessions[session.session_id] = session.to_dict()

            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)

            logger.info(f"Session {session.session_id} saved successfully")

        except Exception as e:
            logger.error(f"Error saving session {session.session_id}: {str(e)}")
            raise

    def load_session(self, session_id: str) -> Optional[ChatSession]:
        """Load a session from storage"""
        try:
            sessions = self._load_sessions()
            if session_id in sessions:
                session_data = sessions[session_id]
                session = ChatSession.from_dict(session_data)
                logger.info(f"Session {session_id} loaded successfully")
                return session
            else:
                logger.warning(f"Session {session_id} not found")
                return None

        except Exception as e:
            logger.error(f"Error loading session {session_id}: {str(e)}")
            return None

    def close_session(self, session: ChatSession) -> Optional[SessionSummary]:
        """Close a session and generate summary"""
        try:
            # Mark session as inactive
            session.is_active = False

            # Generate summary
            summary_text = self.llm_service.generate_session_summary_sync(session)

            # Create summary object
            session_summary = SessionSummary(
                session_id=session.session_id,
                summary=summary_text,
                message_count=len(session.messages),
                start_time=session.start_time,
                end_time=datetime.now()
            )

            # Save summary to storage (always, regardless of memory setting)
            self._save_summary(session_summary)

            # Save updated session
            self.save_session(session)

            logger.info(f"Session {session.session_id} closed and summarized")
            return session_summary

        except Exception as e:
            logger.error(f"Error closing session {session.session_id}: {str(e)}")
            return None

    def get_session_history(self) -> List[str]:
        """Get list of all session IDs"""
        try:
            sessions = self._load_sessions()
            return list(sessions.keys())
        except Exception:
            return []

    def get_active_sessions(self) -> List[ChatSession]:
        """Get all currently active sessions"""
        try:
            sessions = self._load_sessions()
            active_sessions = []

            for session_data in sessions.values():
                if session_data.get('is_active', False):
                    active_sessions.append(ChatSession.from_dict(session_data))

            return active_sessions

        except Exception as e:
            logger.error(f"Error getting active sessions: {str(e)}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from storage"""
        try:
            sessions = self._load_sessions()
            if session_id in sessions:
                del sessions[session_id]

                with open(self.sessions_file, 'w') as f:
                    json.dump(sessions, f, indent=2)

                logger.info(f"Session {session_id} deleted")
                return True
            else:
                logger.warning(f"Session {session_id} not found for deletion")
                return False

        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {str(e)}")
            return False

    def get_session_summaries(self) -> List[SessionSummary]:
        """Get all session summaries"""
        return self._load_all_summaries()

    def _load_sessions(self) -> Dict[str, Any]:
        """Load all sessions from storage"""
        try:
            if self.sessions_file.exists():
                with open(self.sessions_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}")
            return {}

    def _save_summary(self, summary: SessionSummary) -> None:
        """Save a session summary"""
        try:
            summaries = self._load_summaries()
            summaries[summary.session_id] = summary.to_dict()

            with open(self.summaries_file, 'w') as f:
                json.dump(summaries, f, indent=2)

            logger.info(f"Summary for session {summary.session_id} saved")

        except Exception as e:
            logger.error(f"Error saving summary: {str(e)}")
            raise

    def _load_summaries(self) -> Dict[str, Any]:
        """Load all summaries from storage"""
        try:
            if self.summaries_file.exists():
                with open(self.summaries_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading summaries: {str(e)}")
            return {}

    def _load_all_summaries(self) -> List[SessionSummary]:
        """Load all session summaries"""
        try:
            summaries_data = self._load_summaries()
            summaries = []

            for summary_data in summaries_data.values():
                summaries.append(SessionSummary.from_dict(summary_data))

            # Sort by end_time (most recent first)
            summaries.sort(key=lambda x: x.end_time, reverse=True)
            return summaries

        except Exception as e:
            logger.error(f"Error loading all summaries: {str(e)}")
            return []

    def cleanup_old_sessions(self, keep_count: int = 50) -> None:
        """Clean up old sessions, keeping only the most recent ones"""
        try:
            sessions = self._load_sessions()
            summaries = self._load_summaries()

            if len(sessions) <= keep_count:
                return

            # Sort sessions by start time
            session_items = list(sessions.items())
            session_items.sort(key=lambda x: x[1].get('start_time', ''), reverse=True)

            # Keep only the most recent sessions
            sessions_to_keep = dict(session_items[:keep_count])

            # Save updated sessions
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions_to_keep, f, indent=2)

            # Remove summaries for deleted sessions
            sessions_to_delete = set(sessions.keys()) - set(sessions_to_keep.keys())
            for session_id in sessions_to_delete:
                summaries.pop(session_id, None)

            with open(self.summaries_file, 'w') as f:
                json.dump(summaries, f, indent=2)

            logger.info(f"Cleaned up {len(sessions_to_delete)} old sessions")

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about stored sessions"""
        try:
            sessions = self._load_sessions()
            summaries = self._load_summaries()

            active_count = sum(1 for s in sessions.values() if s.get('is_active', False))
            total_messages = sum(len(s.get('messages', [])) for s in sessions.values())

            return {
                'total_sessions': len(sessions),
                'active_sessions': active_count,
                'total_summaries': len(summaries),
                'total_messages': total_messages,
                'storage_path': str(self.storage_path)
            }

        except Exception as e:
            logger.error(f"Error getting storage stats: {str(e)}")
            return {}