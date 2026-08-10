# -*- coding: utf-8 -*-
"""Check the loading status of all skills.

Phase 2B: Agent self-management — view which skills are loaded/unloaded.
Phase 2C: Auto-unload stale skills on check (idle timeout + threshold).
"""

from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolChunk
from agentscope.message import ToolResultState

from ...constant import WORKING_DIR
from ...runtime.tool_registry import tool_descriptor
from ..skill_system.skill_tools import (
    check_skill_status_tool,
    auto_unload_stale_skills,
    get_context_usage,
    should_auto_unload,
)


@tool_descriptor(
    async_execution=False,
    tool_type="internal",
    policy_name="CheckSkillStatus",
    ui_description="View loading status of all core and lazy skills (auto-unloads stale)",
    ui_icon="📋",
)
def check_skill_status() -> ToolChunk:
    """Check the loading status of all skills.

    Use this when the agent wants to know which skills are currently
    loaded in context and which are still lazy (unloaded).
    
    Phase 2C: Automatically unloads stale skills before checking status.

    Returns:
        ToolChunk with a formatted list of core and lazy skills.
    """
    workspace_dir = WORKING_DIR / "workspaces" / "default"
    
    # Phase 2C: Auto-unload stale skills
    try:
        unload_result = auto_unload_stale_skills(workspace_dir, max_idle_seconds=300)
        if unload_result.unloaded_skills:
            print(f"[Auto-unload] Freed ~{unload_result.freed_tokens} tokens")
    except Exception as exc:
        print(f"[Auto-unload] Warning: {exc}")
    
    result = check_skill_status_tool(workspace_dir)
    
    # Get context usage info
    try:
        usage = get_context_usage()
    except Exception:
        usage = None
    
    # Build formatted output
    lines = ["# Skill Loading Status\n"]
    
    # Context usage summary (Phase 2C)
    if usage and usage.total_bytes > 0:
        lines.append(f"**Context Usage:** {usage.total_bytes:,} bytes (~{usage.total_tokens_estimated:,} tokens)")
        lines.append("")
    
    # Core skills
    lines.append(f"## Core Skills ({len(result.core_skills)})")
    for skill_name in result.core_skills[:10]:
        lines.append(f"- ✅ `{skill_name}`")
    if len(result.core_skills) > 10:
        lines.append(f"... and {len(result.core_skills) - 10} more")
    lines.append("")
    
    # Lazy skills
    lines.append(f"## Lazy Skills ({len(result.lazy_skills)})")
    for skill_info in result.lazy_skills:
        status_icon = "✅" if skill_info.loaded else "⏳"
        size_str = f" ({skill_info.content_size:,} bytes)" if skill_info.loaded else ""
        triggers_str = f" | Triggers: {', '.join(skill_info.triggers)}" if skill_info.triggers else ""
        lines.append(f"- {status_icon} `{skill_info.name}`{size_str}{triggers_str}")
    lines.append("")
    
    # Auto-unload note (Phase 2C)
    lines.append("---")
    lines.append("*Auto-unload: Idle >5 min or context >80%*")
    
    text = "\n".join(lines)
    
    return ToolChunk(
        is_last=True,
        state=ToolResultState.SUCCESS,
        content=[TextBlock(type="text", text=text)],
    )
