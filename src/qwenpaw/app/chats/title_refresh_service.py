# -*- coding: utf-8 -*-
"""Chat title refresh service.

Responsible for generating a new title from recent messages and
persisting it via the chat manager's compare-and-set mechanism.
This is a pure chat-layer concern — no knowledge of memory backends.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...agents.model_factory import _ModelAndFormatter
    from agentscope.message import Msg

logger = logging.getLogger(__name__)


class ChatTitleRefreshService:
    """Generate chat titles and persist them via compare-and-set.

    Public API::

        async def refresh(
            session_id: str,
            recent_messages: list[Msg],
        ) -> None

    All failures are logged and swallowed so title refresh never breaks
    the request path.
    """

    def __init__(
        self,
        chat_manager: Any,
        agent_id: str,
    ) -> None:
        self._chat_manager = chat_manager
        self._agent_id = agent_id

    async def refresh(
        self,
        *,
        session_id: str,
        recent_messages: list[Any],
    ) -> None:
        """Re-generate a chat title from the recent conversation slice.

        Called after each auto-memory flush (see ``ChatTitleRefreshMiddleware``).
        The chat is located by runtime session id, the recent messages are fed
        to the LLM for a fresh title, and the name is updated compare-and-set
        so a user-chosen name is never clobbered.
        """
        if not recent_messages:
            return

        from ...config.config import load_agent_config
        from ...exceptions import AppBaseException

        try:
            cfg = load_agent_config(self._agent_id).running
        except (ValueError, AppBaseException) as exc:
            logger.info("Auto title refresh skipped: config unavailable (%s)", exc)
            return

        title_cfg = cfg.auto_title_config
        if not title_cfg.enabled or not title_cfg.refresh_on_auto_memory:
            logger.info(
                "Auto title refresh skipped: refresh_on_auto_memory disabled "
                "(enabled=%s refresh=%s)",
                title_cfg.enabled,
                title_cfg.refresh_on_auto_memory,
            )
            return

        chat = await self._chat_manager.find_chat_by_session_id(session_id)
        if chat is None:
            logger.info(
                "Auto title refresh skipped: no chat for session %s",
                session_id,
            )
            return

        chat_id = chat.id

        transcript = _messages_to_text(recent_messages)
        if not transcript:
            await self._record(chat_id, ok=False, reason="empty transcript")
            return

        try:
            from ...agents.model_factory import create_model_and_formatter
            from ...utils.model_response import consume_model_response
            from ..title_generator import REFRESH_TITLE_PROMPT, _clean_title
            from agentscope.message import Msg, TextBlock

            try:
                model, _ = create_model_and_formatter(
                    agent_id=self._agent_id,
                )
            except (ValueError, AppBaseException) as exc:
                logger.info(
                    "Auto title refresh skipped: no model available for chat %s (%s)",
                    chat_id,
                    exc,
                )
                await self._record(chat_id, ok=False, reason=f"no model: {exc}")
                return

            messages = [
                Msg(
                    name="system",
                    role="system",
                    content=[TextBlock(type="text", text=REFRESH_TITLE_PROMPT)],
                ),
                Msg(
                    name="user",
                    role="user",
                    content=[TextBlock(type="text", text=transcript)],
                ),
            ]

            raw_title = await asyncio.wait_for(
                consume_model_response(model, messages),
                timeout=title_cfg.timeout_seconds,
            )
        except Exception:
            logger.exception(
                "Auto title refresh LLM failed for chat %s",
                chat_id,
            )
            await self._record(chat_id, ok=False, reason="LLM failed")
            return

        title = _clean_title(raw_title)
        if not title:
            logger.info(
                "Auto title refresh produced empty output for chat %s",
                chat_id,
            )
            await self._record(chat_id, ok=False, reason="empty LLM output")
            return

        # Compare-and-set: expected name is the last title we set (or the
        # current name for chats created before this feature shipped). If the
        # user renamed the chat manually, the name no longer matches and the
        # update is skipped.
        expected_name = chat.meta.get("auto_title_last") or chat.name
        updated = await self._chat_manager.set_auto_title(
            chat.id,
            title,
            expected_name=expected_name,
        )
        if updated is None:
            logger.info(
                "Auto title refresh skipped: chat %s renamed manually",
                chat.id,
            )
            await self._record(chat_id, ok=False, reason="renamed manually")
            return
        logger.info(
            "Auto-refreshed chat %s title to %r (session %s)",
            chat.id,
            title,
            session_id,
        )
        await self._record(chat_id, ok=True, reason="ok", title=title)

    async def _record(
        self,
        chat_id: str,
        *,
        ok: bool,
        reason: str = "",
        title: str = "",
    ) -> None:
        try:
            await self._chat_manager.record_auto_title_refresh(
                chat_id,
                ok=ok,
                reason=reason,
                title=title,
            )
        except Exception:
            logger.exception(
                "Auto title refresh state record failed for chat %s",
                chat_id,
            )


def _messages_to_text(messages: list[Any]) -> str:
    """Convert a list of message objects into a plain-text transcript."""
    parts: list[str] = []
    for msg in messages:
        role = getattr(msg, "role", "")
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            # AgentScope 2.0 Msg — extract text blocks
            for block in content:
                text = getattr(block, "text", "") or ""
                if text:
                    parts.append(f"[{role}] {text}")
        elif content:
            parts.append(f"[{role}] {content}")
    return "\n".join(parts)
