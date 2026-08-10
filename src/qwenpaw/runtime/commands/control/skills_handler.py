# -*- coding: utf-8 -*-
"""Handler for /skills command.

Lists enabled skills for the current channel, separated into core (eager) 
and lazy (on-demand) categories. Supports dynamic skill loading (Phase 1).
"""

from __future__ import annotations

from pathlib import Path

import frontmatter as fm

from ....agents.skill_system import (
    detect_lazy_skill_trigger,
    get_workspace_skills_dir,
    load_skill_content,
    reconcile_workspace_manifest,
    resolve_core_and_lazy_skills,
)
from ....agents.utils.file_handling import (
    read_text_file_with_encoding_fallback,
)
from ....exceptions import SkillsError

from .base import BaseControlCommandHandler, ControlContext


class SkillsCommandHandler(BaseControlCommandHandler):
    """Handler for /skills command.

    Usage:
        /skills          # List all enabled skills (core + lazy)
        /load <skill>    # Manually load a lazy skill's full content
    """

    command_name = "/skills"
    description = (
        "List chat-available skills and expose explicit skill commands"
    )

    @staticmethod
    def _truncate_description(
        text: str,
        limit: int = 32,
    ) -> str:
        """Return a single-line shortened description for compact lists."""
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3].rstrip()}..."

    async def handle(self, context: ControlContext) -> str:
        workspace = context.workspace
        workspace_dir: Path | None = getattr(
            workspace,
            "workspace_dir",
            None,
        )
        if workspace_dir is None:
            return "**Error**: Workspace not initialized."

        channel_id = context.channel.channel
        
        # Check if this is a /load <skill> command
        input_text = (context.input or "").strip()
        if input_text.startswith("/load ") or input_text.startswith("/["):
            skill_name = input_text.replace("/load ", "").replace("/[", "").replace("]", "").strip()
            return await self._handle_load_skill(context, workspace_dir, skill_name)
        
        # Normal /skills listing
        return await self._handle_list_skills(context, workspace_dir, channel_id)

    async def _handle_list_skills(
        self,
        context: ControlContext,
        workspace_dir: Path,
        channel_id: str,
    ) -> str:
        """List all enabled skills, separated into core and lazy categories."""
        manifest = reconcile_workspace_manifest(workspace_dir)
        skills_dir = get_workspace_skills_dir(workspace_dir)

        # Use new core/lazy separation
        core_skills, lazy_skills_meta = resolve_core_and_lazy_skills(
            workspace_dir, channel_id
        )
        
        lines = []
        
        # Core skills section
        lines.append("**🔥 Core Skills (Always Loaded)**")
        lines.append("-" * 40)
        
        if core_skills:
            for skill_name in sorted(core_skills):
                skill_dir = skills_dir / skill_name
                if not skill_dir.exists():
                    continue
                
                description = ""
                try:
                    post = fm.loads(
                        read_text_file_with_encoding_fallback(skill_dir / "SKILL.md")
                    )
                    description = post.get("description", "") or ""
                except Exception:
                    description = entry.get("metadata", {}).get("description", "")
                
                lines.append(f"✅ `{skill_name}` — {self._truncate_description(description, 50)}")
        else:
            lines.append("*No core skills enabled.*")
        
        lines.append("")
        
        # Lazy skills section
        lines.append("**⏳ Lazy Skills (On-Demand Loading)**")
        lines.append("-" * 40)
        
        if lazy_skills_meta:
            for skill_name, meta in sorted(lazy_skills_meta.items()):
                triggers = meta.get("triggers", [])
                trigger_str = ", ".join(triggers[:3])
                if len(triggers) > 3:
                    trigger_str += f" (+{len(triggers)-3} more)"
                
                lines.append(
                    f"⏳ `{skill_name}` — triggers: `{trigger_str}`"
                )
        else:
            lines.append("*No lazy skills configured.*")
        
        lines.append("")
        lines.append("---")
        lines.append(
            "*Use `/load <skill_name>` to manually load a lazy skill.*\n"
            "*Or just use the skill naturally — triggers auto-detect.*"
        )
        
        return "\n".join(lines)

    async def _handle_load_skill(
        self,
        context: ControlContext,
        workspace_dir: Path,
        skill_name: str,
    ) -> str:
        """Manually load a lazy skill's full content."""
        if not skill_name:
            return "❌ Usage: `/load <skill_name>` or `/[skill_name]`"
        
        try:
            content = load_skill_content(workspace_dir, skill_name)
            
            # Check if this is actually a lazy skill
            manifest = reconcile_workspace_manifest(workspace_dir)
            entry = manifest.get("skills", {}).get(skill_name, {})
            dynamic_config = entry.get("dynamic") or {}
            mode = dynamic_config.get("mode", "eager")
            
            if mode != "lazy":
                return (
                    f"ℹ️ Skill `{skill_name}` is already a core skill (eager loading).\n\n"
                    f"**Content preview:**\n```\n{content[:500]}...\n```"
                )
            
            return (
                f"✅ Loaded lazy skill: **`{skill_name}`**\n\n"
                f"**Full instructions injected into context.**\n"
                f"*Content size: {len(content)} bytes*"
            )
        
        except SkillsError as exc:
            return f"❌ Failed to load skill `{skill_name}`: {exc.message}"
        except Exception as exc:
            return f"❌ Unexpected error loading `{skill_name}`: {exc}"


class AutoLoadSkillHandler(BaseControlCommandHandler):
    """Auto-detect and load lazy skills based on trigger keywords.
    
    This handler runs automatically before each agent turn to detect
    if user input matches any lazy skill's trigger keywords.
    
    Phase 1: Keyword matching only
    Phase 2A: Enhanced with semantic similarity (IntentClassifier)
    """
    
    command_name = "/autoload"
    description = "Auto-detect lazy skill triggers"
    
    @staticmethod
    async def check_and_load(
        workspace_dir: Path,
        channel_id: str,
        user_input: str,
        use_semantic: bool = False,
    ) -> tuple[bool, str | None]:
        """Check if user input matches any lazy skill trigger.
        
        Args:
            workspace_dir: Workspace directory path
            channel_id: Current channel ID
            user_input: User's message text
            use_semantic: If True, use IntentClassifier for semantic matching
        
        Returns:
            tuple[matched, skill_name]: 
                - matched: True if a trigger was detected
                - skill_name: Name of the matched skill (or None)
        """
        _, lazy_skills_meta = resolve_core_and_lazy_skills(
            workspace_dir, channel_id
        )
        
        # Use enhanced detection with optional semantic matching
        matched_skill = detect_lazy_skill_trigger(
            user_input,
            lazy_skills_meta,
            use_semantic=use_semantic,
        )
        
        if matched_skill:
            try:
                content = load_skill_content(workspace_dir, matched_skill)
                lazy_skills_meta[matched_skill]["_loaded_content"] = content
                return True, matched_skill
            except Exception as exc:
                logger.error("Failed to load skill '%s': %s", matched_skill, exc)
                return False, None
        
        return False, None
