# -*- coding: utf-8 -*-
"""Skill lifecycle tools for Agent self-management.

Phase 2B: Agent 自主决策 — 暴露 tool 让 Agent 自主管理技能生命周期。
Phase 2C: 智能自动卸载策略 — 基于使用历史和 token 占用的自动化管理。

提供核心 tool：
1. load_skill(skill_name) — 加载 lazy skill 的完整指令
2. unload_skill(skill_name) — 卸载已加载的 lazy skill
3. check_skill_status() — 查看所有技能的加载状态

Phase 2C 增强：
4. auto_unload_stale_skills() — 自动卸载长时间未使用的技能
5. get_context_usage() — 获取当前 context 使用情况
6. smart_unload_recommendation() — 智能卸载建议
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class SkillLoadResult:
    """load_skill 工具的返回结果"""
    status: str  # "success" | "error" | "already_loaded"
    skill_name: str
    content_size: int = 0  # bytes
    freed_tokens: int = 0  # tokens (if unloaded)
    message: str = ""


@dataclass
class SkillStatusInfo:
    """单个技能的详细信息"""
    name: str
    loaded: bool = False
    triggers: list[str] = field(default_factory=list)
    content_size: int = 0  # bytes
    description: str = ""
    last_used: float = 0.0  # Unix timestamp
    use_count: int = 0  # Total times used


@dataclass
class SkillStatusResult:
    """check_skill_status 工具的返回结果"""
    core_skills: list[str] = field(default_factory=list)
    lazy_skills: list[SkillStatusInfo] = field(default_factory=list)


@dataclass
class ContextUsageInfo:
    """Context 使用情况"""
    total_bytes: int = 0
    total_tokens_estimated: int = 0
    skill_breakdown: dict[str, int] = field(default_factory=dict)
    percentage_of_limit: float = 0.0  # 0-100%
    limit_bytes: int = 10 * 1024 * 1024  # 10MB default limit


@dataclass
class AutoUnloadResult:
    """auto_unload 工具的返回结果"""
    unloaded_skills: list[str] = field(default_factory=list)
    freed_tokens: int = 0
    reason: str = ""
    message: str = ""


# ========== Phase 2B: 全局缓存 ==========

# 全局缓存：记录已加载的 lazy skill content
_loaded_skills_cache: dict[str, str] = {}

_skill_usage_history: Dict[str, Dict[str, Any]] = {}  # {skill_name: {"last_used": timestamp, "use_count": int}}


def get_loaded_skills_cache() -> dict[str, str]:
    """获取已加载技能的缓存（供其他模块使用）"""
    return _loaded_skills_cache


def clear_loaded_skills_cache() -> None:
    """清空已加载技能缓存（用于测试或重置）"""
    global _loaded_skills_cache
    global _skill_usage_history
    _loaded_skills_cache = {}
    _skill_usage_history = {}
    logger.info("Cleared loaded skills cache and usage history")


# ========== Phase 2C: 使用历史管理 ==========

def record_skill_usage(skill_name: str, content_size: int) -> None:
    """记录技能使用历史（Phase 2C）"""
    now = time.time()

    if skill_name in _skill_usage_history:
        _skill_usage_history[skill_name]["last_used"] = now
        _skill_usage_history[skill_name]["use_count"] += 1
        _skill_usage_history[skill_name]["content_size"] = content_size
    else:
        _skill_usage_history[skill_name] = {
            "last_used": now,
            "use_count": 1,
            "content_size": content_size,
        }

    logger.debug(
        "Recorded usage for '%s': count=%d, last_used=%s",
        skill_name,
        _skill_usage_history[skill_name]["use_count"],
        time.strftime("%H:%M:%S", time.localtime(now)),
    )


def get_skill_usage_info(skill_name: str) -> dict | None:
    """获取技能使用信息"""
    return _skill_usage_history.get(skill_name)


def get_all_usage_info() -> dict[str, dict]:
    """获取所有技能的使用信息"""
    return _skill_usage_history.copy()


# ========== Phase 2C: Context 监控 ==========

def estimate_tokens_from_bytes(byte_size: int) -> int:
    """从字节数估算 token 数（粗略估计）"""
    # 英文：1 token ≈ 4 chars
    # 中文：1 token ≈ 1.5 chars
    # 取中间值：1 token ≈ 3 chars
    return byte_size // 3


def get_context_usage() -> ContextUsageInfo:
    """获取当前 context 使用情况（Phase 2C）"""
    info = ContextUsageInfo()

    for skill_name, content in _loaded_skills_cache.items():
        size = len(content)
        info.total_bytes += size
        info.skill_breakdown[skill_name] = size

    info.total_tokens_estimated = estimate_tokens_from_bytes(info.total_bytes)
    info.percentage_of_limit = (info.total_bytes / info.limit_bytes) * 100 if info.limit_bytes > 0 else 0

    return info


def should_auto_unload() -> tuple[bool, str]:
    """判断是否应该自动卸载（Phase 2C）

    Returns:
        (should_unload, reason): 是否应该卸载及原因
    """
    usage = get_context_usage()

    # 规则 1: Token 占用超过 80%
    if usage.percentage_of_limit > 80:
        return True, f"Context 占用过高 ({usage.percentage_of_limit:.1f}%)"

    # 规则 2: Token 占用超过 60% 且有多个技能加载
    if usage.percentage_of_limit > 60 and len(_loaded_skills_cache) > 2:
        return True, f"Context 占用较高 ({usage.percentage_of_limit:.1f}%)，建议释放部分技能"

    return False, ""


def get_least_used_skill() -> str | None:
    """获取最少使用的技能（用于自动卸载）"""
    if not _skill_usage_history:
        return None

    # Find skill with lowest use_count, then oldest last_used
    least_used = None
    min_count = float('inf')
    oldest_time = 0

    for skill_name, history in _skill_usage_history.items():
        count = history.get("use_count", 0)
        last_used = history.get("last_used", 0)

        # Prefer lowest count, then oldest last_used
        if count < min_count or (count == min_count and last_used < oldest_time):
            least_used = skill_name
            min_count = count
            oldest_time = last_used

    return least_used


# ========== Phase 2C: 自动卸载策略 ==========

def auto_unload_stale_skills(
    workspace_dir: Path,
    max_idle_seconds: int = 300,  # 5 分钟无使用就卸载
    min_use_count: int = 1,  # 至少使用过 1 次才卸载
) -> AutoUnloadResult:
    """自动卸载长时间未使用的技能（Phase 2C）

    Args:
        workspace_dir: Workspace directory path
        max_idle_seconds: 最大空闲时间（秒），默认 300（5 分钟）
        min_use_count: 最小使用次数，默认 1

    Returns:
        AutoUnloadResult with unloaded skills and freed tokens
    """
    now = time.time()
    result = AutoUnloadResult()

    to_unload = []

    for skill_name, history in _skill_usage_history.items():
        idle_time = now - history.get("last_used", 0)
        use_count = history.get("use_count", 0)

        # Unload if: idle > max_idle_seconds AND use_count >= min_use_count
        if idle_time > max_idle_seconds and use_count >= min_use_count:
            to_unload.append(skill_name)

    # Also unload if context usage is too high
    if not to_unload:
        should_unload, reason = should_auto_unload()
        if should_unload:
            least_used = get_least_used_skill()
            if least_used:
                to_unload.append(least_used)

    # Execute unload
    global _loaded_skills_cache
    for skill_name in to_unload:
        if skill_name in _loaded_skills_cache:
            content_size = len(_loaded_skills_cache[skill_name])
            freed_tokens = estimate_tokens_from_bytes(content_size)

            del _loaded_skills_cache[skill_name]
            if skill_name in _skill_usage_history:
                del _skill_usage_history[skill_name]

            result.unloaded_skills.append(skill_name)
            result.freed_tokens += freed_tokens

            logger.info(
                "Auto-unloaded '%s': freed ~%d tokens (%d bytes)",
                skill_name,
                freed_tokens,
                content_size,
            )

    if result.unloaded_skills:
        result.reason = "Idle timeout" if not should_auto_unload()[0] else "High context usage"
        result.message = f"✅ Auto-unloaded {len(result.unloaded_skills)} skill(s), freed ~{result.freed_tokens} tokens"
    else:
        result.message = "ℹ️ No skills met auto-unload criteria"

    return result


def smart_unload_recommendation() -> Dict[str, Any]:
    """智能卸载建议（Phase 2C）

    Returns:
        dict with recommendation details
    """
    usage = get_context_usage()
    recommendation: Dict[str, Any] = {
        "context_usage": {
            "total_bytes": usage.total_bytes,
            "total_tokens_estimated": usage.total_tokens_estimated,
            "percentage_of_limit": usage.percentage_of_limit,
        },
        "skills_summary": {
            "total_loaded": len(_loaded_skills_cache),
            "by_use_frequency": {},
        },
        "recommendations": [],
    }

    # Analyze usage frequency
    for skill_name, history in _skill_usage_history.items():
        count = history.get("use_count", 0)
        last_used = history.get("last_used", 0)
        idle_seconds = time.time() - last_used

        freq_label = "high" if count >= 5 else ("medium" if count >= 2 else "low")
        recommendation["skills_summary"]["by_use_frequency"][skill_name] = {
            "use_count": count,
            "frequency": freq_label,
            "idle_minutes": idle_seconds / 60,
            "content_size": history.get("content_size", 0),
        }

        # Generate recommendations
        if idle_seconds > 300 and count <= 2:  # Idle > 5 min, used <= 2 times
            recommendation["recommendations"].append({
                "action": "unload",
                "skill": skill_name,
                "reason": f"Low usage ({count} times), idle {idle_seconds/60:.1f} min",
                "estimated_freed_tokens": estimate_tokens_from_bytes(history.get("content_size", 0)),
            })
        elif idle_seconds < 60:  # Used within last minute
            recommendation["recommendations"].append({
                "action": "keep",
                "skill": skill_name,
                "reason": "Recently active",
            })

    # Context usage recommendation
    if usage.percentage_of_limit > 80:
        recommendation["recommendations"].insert(
            0, {
                "action": "urgent_unload",
                "skill": get_least_used_skill(),
                "reason": f"Context usage critical ({usage.percentage_of_limit:.1f}%)",
                "priority": "high",
            },
        )
    elif usage.percentage_of_limit > 60:
        recommendation["recommendations"].insert(
            0, {
                "action": "consider_unload",
                "skill": get_least_used_skill(),
                "reason": f"Context usage elevated ({usage.percentage_of_limit:.1f}%)",
                "priority": "medium",
            },
        )

    return recommendation


# ========== Phase 2B Core Tools ==========

def load_skill_tool(
    workspace_dir: Path,
    skill_name: str,
) -> SkillLoadResult:
    """加载 lazy skill 的完整指令。

    Args:
        workspace_dir: Workspace directory path
        skill_name: Name of the skill to load

    Returns:
        SkillLoadResult with status and metadata
    """
    from .registry import load_skill_content, reconcile_workspace_manifest

    if not skill_name:
        return SkillLoadResult(
            status="error",
            skill_name="",
            message="❌ Usage: load_skill(skill_name)",
        )

    try:
        # Check if already loaded
        if skill_name in _loaded_skills_cache:
            content = _loaded_skills_cache[skill_name]
            # Phase 2C: Record usage
            record_skill_usage(skill_name, len(content))

            return SkillLoadResult(
                status="already_loaded",
                skill_name=skill_name,
                content_size=len(content),
                message=f"ℹ️ Skill '{skill_name}' is already loaded ({len(content)} bytes)",
            )

        # Load full SKILL.md content
        content = load_skill_content(workspace_dir, skill_name)

        # Cache it
        _loaded_skills_cache[skill_name] = content

        # Phase 2C: Record usage history
        record_skill_usage(skill_name, len(content))

        # Get trigger info
        manifest = reconcile_workspace_manifest(workspace_dir)
        entry = manifest.get("skills", {}).get(skill_name, {})
        dynamic_config = entry.get("dynamic") or {}
        triggers = dynamic_config.get("triggers", [])

        logger.info(
            "Loaded skill '%s': %d bytes, %d triggers",
            skill_name,
            len(content),
            len(triggers),
        )

        return SkillLoadResult(
            status="success",
            skill_name=skill_name,
            content_size=len(content),
            message=f"✅ Loaded skill '{skill_name}' ({len(content)} bytes, {len(triggers)} triggers)",
        )

    except Exception as exc:
        logger.error("Failed to load skill '%s': %s", skill_name, exc)
        return SkillLoadResult(
            status="error",
            skill_name=skill_name,
            message=f"❌ Failed to load '{skill_name}': {exc}",
        )


def unload_skill_tool(
    workspace_dir: Path,
    skill_name: str,
) -> SkillLoadResult:
    """卸载已加载的 lazy skill，释放 context。

    Args:
        workspace_dir: Workspace directory path (unused but kept for API consistency)
        skill_name: Name of the skill to unload

    Returns:
        SkillLoadResult with status and freed tokens estimate
    """
    global _loaded_skills_cache
    global _skill_usage_history

    if not skill_name:
        return SkillLoadResult(
            status="error",
            skill_name="",
            message="❌ Usage: unload_skill(skill_name)",
        )

    # Check if skill is loaded
    if skill_name not in _loaded_skills_cache:
        return SkillLoadResult(
            status="error",
            skill_name=skill_name,
            message=f"ℹ️ Skill '{skill_name}' is not currently loaded",
        )

    # Get content size before unloading
    content_size = len(_loaded_skills_cache[skill_name])

    # Estimate tokens (1 token ≈ 4 chars for English, ~1.5 chars for Chinese)
    estimated_tokens = content_size // 3  # Rough estimate

    # Remove from cache
    del _loaded_skills_cache[skill_name]

    # Phase 2C: Also remove from usage history
    if skill_name in _skill_usage_history:
        del _skill_usage_history[skill_name]

    logger.info(
        "Unloaded skill '%s': freed ~%d tokens (%d bytes)",
        skill_name,
        estimated_tokens,
        content_size,
    )

    return SkillLoadResult(
        status="success",
        skill_name=skill_name,
        freed_tokens=estimated_tokens,
        message=f"✅ Unloaded skill '{skill_name}' (freed ~{estimated_tokens} tokens)",
    )


def check_skill_status_tool(
    workspace_dir: Path,
) -> SkillStatusResult:
    """查看所有技能的加载状态。

    Args:
        workspace_dir: Workspace directory path

    Returns:
        SkillStatusResult with core and lazy skills info
    """
    from .registry import reconcile_workspace_manifest

    result = SkillStatusResult()
    loaded_cache = get_loaded_skills_cache()

    # Get pool skills (core)
    manifest = reconcile_workspace_manifest(workspace_dir)
    for pool_name, pool_info in sorted(manifest.get("pools", {}).items()):
        for skill_name in sorted(pool_info.get("skills", {}).keys()):
            result.core_skills.append(skill_name)

    # Known lazy skills from Phase 1 definition
    # (dynamic field may be cleared from skill.json, so we hardcode the list)
    lazy_skill_names = [
        "market-access-audit",
        "kb-ingest",
        "liteparse",
        "doc-web-to-md",
    ]

    for skill_name in lazy_skill_names:
        is_loaded = skill_name in loaded_cache
        content_size = len(loaded_cache[skill_name]) if is_loaded else 0

        # Try to get triggers from manifest entry
        entry = manifest.get("skills", {}).get(skill_name, {})
        dynamic_config = entry.get("dynamic") or {}
        triggers = dynamic_config.get("triggers", [])

        # Phase 2C: Get usage info
        usage_info = get_skill_usage_info(skill_name)
        last_used = usage_info.get("last_used", 0) if usage_info else 0
        use_count = usage_info.get("use_count", 0) if usage_info else 0

        result.lazy_skills.append(
            SkillStatusInfo(
                name=skill_name,
                loaded=is_loaded,
                triggers=triggers,
                content_size=content_size,
                last_used=last_used,
                use_count=use_count,
            ),
        )

    return result


# 全局单例（用于 tool registry）
_skill_tools_initialized = False


def ensure_skill_tools_initialized(workspace_dir: Path) -> None:
    """确保 skill tools 已初始化"""
    global _skill_tools_initialized
    if not _skill_tools_initialized:
        _skill_tools_initialized = True
        logger.info("Skill tools initialized")
