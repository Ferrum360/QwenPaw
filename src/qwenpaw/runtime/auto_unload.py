# -*- coding: utf-8 -*-
"""Auto-unload hook — automatically unload stale skills after N turns.

Phase 2C: Add more triggers for auto-unload.
This hook runs in POST_RESPONSE phase and checks every 5 turns.
"""

import logging
from pathlib import Path

from .hooks import HookBase, HookContext, HookResult, HookAction
from .phases import Phase

logger = logging.getLogger(__name__)


class AutoUnloadHook(HookBase):
    """Automatically unload stale skills every N turns.

    Runs in POST_RESPONSE phase to check and unload idle skills.
    Configurable turn interval (default: 5 turns).
    """

    phase = Phase.POST_RESPONSE
    name = "auto_unload"
    priority = 200  # Run after other hooks

    def __init__(self, turn_interval: int = 5):
        """Initialize the auto-unload hook.

        Args:
            turn_interval: Number of turns between auto-unload checks.
                          Default is 5 turns. Set to 0 to disable.
        """
        self.turn_interval = turn_interval

    async def run(self, ctx: HookContext) -> HookResult:
        """Run the auto-unload check.

        Args:
            ctx: Hook context with session state

        Returns:
            HookResult indicating whether to continue or short-circuit
        """
        if self.turn_interval <= 0:
            return HookResult()

        try:
            # Increment turn count
            self._increment_turn_count(ctx)

            # Get current turn count
            turn_count = self._get_turn_count(ctx)

            # Check if we should auto-unload
            if turn_count > 0 and turn_count % self.turn_interval == 0:
                logger.info(
                    "Auto-unload hook triggered at turn %d (interval=%d)",
                    turn_count,
                    self.turn_interval,
                )

                # Trigger auto-unload
                await self._trigger_auto_unload(ctx)

        except Exception as exc:
            logger.warning("Auto-unload hook failed: %s", exc, exc_info=True)

        return HookResult()

    def _increment_turn_count(self, ctx: HookContext) -> None:
        """Increment the turn counter in mode_state.

        Args:
            ctx: Hook context
        """
        # Ensure mode_state exists
        if not hasattr(ctx, 'mode_state') or ctx.mode_state is None:
            ctx.mode_state = {}

        # Increment turn count
        current = ctx.mode_state.get('turn_count', 0)
        ctx.mode_state['turn_count'] = current + 1

        logger.debug(f"Turn count incremented to {current + 1}")

    def _get_turn_count(self, ctx: HookContext) -> int:
        """Get the current turn count from session state.

        Args:
            ctx: Hook context

        Returns:
            Current turn count (0 if not available)
        """
        # Try to get from mode_state first
        mode_state = getattr(ctx, 'mode_state', None)
        if mode_state:
            return mode_state.get('turn_count', 0)

        # Fallback: try to get from request metadata
        request = getattr(ctx, 'request', None)
        if request:
            metadata = getattr(request, 'metadata', {})
            turn_count = metadata.get('turn_count', 0)
            if turn_count:
                return turn_count

        # Last resort: estimate from input_msgs length
        input_msgs = getattr(ctx, 'input_msgs', [])
        if input_msgs:
            # Count user messages (rough estimate)
            user_msg_count = sum(
                1 for msg in input_msgs
                if hasattr(msg, 'role') and msg.role == 'user'
            )
            if user_msg_count:
                return user_msg_count

        return 0

    async def _trigger_auto_unload(self, ctx: HookContext) -> None:
        """Trigger the auto-unload process.

        Args:
            ctx: Hook context with workspace_dir
        """
        from ...agents.skill_system.skill_tools import (
            auto_unload_stale_skills,
            get_context_usage,
        )

        workspace_dir = ctx.workspace_dir
        if not workspace_dir:
            logger.debug("No workspace_dir available for auto-unload")
            return

        # Get context usage before auto-unload
        try:
            usage = get_context_usage()
            if usage.total_bytes == 0:
                logger.debug("No skills loaded, skipping auto-unload")
                return
        except Exception as exc:
            logger.debug("Failed to get context usage: %s", exc)
            return

        # Trigger auto-unload
        try:
            result = auto_unload_stale_skills(workspace_dir, max_idle_seconds=300)

            if result.unloaded_skills:
                logger.info(
                    "Auto-unload hook: freed ~%d tokens by unloading %d skill(s)",
                    result.freed_tokens,
                    len(result.unloaded_skills),
                )

                # Log which skills were unloaded
                for skill_name in result.unloaded_skills:
                    logger.info(f"  Unloaded: {skill_name}")

        except Exception as exc:
            logger.warning("Auto-unload failed: %s", exc, exc_info=True)


# Singleton instance for registration
auto_unload_hook = AutoUnloadHook(turn_interval=5)
