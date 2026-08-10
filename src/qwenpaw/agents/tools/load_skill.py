# -*- coding: utf-8 -*-
"""Load a lazy skill's full instruction set.

Phase 2B: Agent self-management — load lazy skill on demand.
"""

from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolChunk
from agentscope.message import ToolResultState

from ...constant import WORKING_DIR
from ...runtime.tool_registry import tool_descriptor
from ..skill_system.skill_tools import load_skill_tool


@tool_descriptor(
    async_execution=False,
    tool_type="internal",
    policy_name="LoadSkill",
    ui_description="Load a lazy skill's full SKILL.md content into context",
    ui_icon="📥",
)
def load_skill(
    skill_name: str,
) -> ToolChunk:
    """Load a lazy skill's full instruction set into the agent's context.

    Use this when the agent needs to use a skill that hasn't been loaded yet.
    Lazy skills are only injected with their name+description at startup;
    this tool loads the complete SKILL.md content on demand.

    Args:
        skill_name: Name of the skill to load (e.g., 'market-access-audit').

    Returns:
        ToolChunk with load status and metadata.
    """
    # Get workspace dir from environment or default
    workspace_dir = WORKING_DIR / "workspaces" / "default"
    
    result = load_skill_tool(workspace_dir, skill_name)
    
    if result.status == "success":
        return ToolChunk(
            is_last=True,
            state=ToolResultState.SUCCESS,
            content=[TextBlock(type="text", text=result.message)],
        )
    elif result.status == "already_loaded":
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
