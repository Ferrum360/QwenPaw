# -*- coding: utf-8 -*-
"""Unload a loaded lazy skill to free context.

Phase 2B: Agent self-management — unload lazy skill when no longer needed.
"""

from agentscope.message import TextBlock
from agentscope.tool import ToolChunk
from agentscope.message import ToolResultState

from ...constant import WORKING_DIR
from ...runtime.tool_registry import tool_descriptor
from ..skill_system.skill_tools import unload_skill_tool


@tool_descriptor(
    async_execution=False,
    tool_type="internal",
    policy_name="UnloadSkill",
    ui_description="Unload a loaded lazy skill to free context tokens",
    ui_icon="📤",
)
def unload_skill(
    skill_name: str,
) -> ToolChunk:
    """Unload a loaded lazy skill to free context tokens.

    Use this when the agent has finished using a skill and wants to
    reduce context size. This removes the skill's SKILL.md content
    from the active context.

    Args:
        skill_name: Name of the skill to unload (e.g., 'market-access-audit').

    Returns:
        ToolChunk with unload status and estimated tokens freed.
    """
    workspace_dir = WORKING_DIR / "workspaces" / "default"

    result = unload_skill_tool(workspace_dir, skill_name)

    if result.status == "success":
        return ToolChunk(
            is_last=True,
            state=ToolResultState.SUCCESS,
            content=[TextBlock(type="text", text=result.message)],
        )
    else:
        return ToolChunk(
            is_last=True,
            state=ToolResultState.ERROR,
            content=[TextBlock(type="text", text=result.message)],
        )
