# -*- coding: utf-8 -*-
"""Skill system exports."""

from .intent_classifier import (
    IntentClassifier,
    get_intent_classifier,
    reset_intent_classifier,
)
from .models import (
    SkillConflictError,
    SkillInfo,
)
from .pool_service import SkillPoolService, run_pool_auto_update_sync
from .registry import (
    apply_skill_config_env_overrides,
    detect_lazy_skill_trigger,
    ensure_skill_pool_initialized,
    ensure_skills_initialized,
    load_skill_content,
    reconcile_pool_manifest,
    reconcile_workspace_manifest,
    resolve_builtin_skill_dir,
    resolve_core_and_lazy_skills,
    resolve_effective_skills,
)
from .skill_tools import (
    check_skill_status_tool,
    clear_loaded_skills_cache,
    get_all_usage_info,
    get_context_usage,
    get_loaded_skills_cache,
    get_skill_usage_info,
    load_skill_tool,
    record_skill_usage,
    should_auto_unload,
    smart_unload_recommendation,
    auto_unload_stale_skills,
    unload_skill_tool,
)
from .store import (
    get_skill_pool_dirs,
    get_skill_pool_dir,
    get_workspace_skills_dir,
    read_skill_manifest,
    read_skill_pool_manifest,
    resolve_pool_skill_dir,
)
from .workspace_service import SkillService

__all__ = [
    "IntentClassifier",
    "SkillConflictError",
    "SkillInfo",
    "SkillPoolService",
    "SkillService",
    "apply_skill_config_env_overrides",
    "auto_unload_stale_skills",
    "check_skill_status_tool",
    "clear_loaded_skills_cache",
    "detect_lazy_skill_trigger",
    "ensure_skill_pool_initialized",
    "ensure_skills_initialized",
    "get_all_usage_info",
    "get_context_usage",
    "get_intent_classifier",
    "get_loaded_skills_cache",
    "get_skill_pool_dirs",
    "get_skill_pool_dir",
    "get_skill_usage_info",
    "get_workspace_skills_dir",
    "load_skill_content",
    "load_skill_tool",
    "record_skill_usage",
    "read_skill_manifest",
    "read_skill_pool_manifest",
    "reconcile_pool_manifest",
    "resolve_builtin_skill_dir",
    "resolve_core_and_lazy_skills",
    "resolve_pool_skill_dir",
    "reconcile_workspace_manifest",
    "resolve_effective_skills",
    "reset_intent_classifier",
    "run_pool_auto_update_sync",
    "should_auto_unload",
    "smart_unload_recommendation",
    "unload_skill_tool",
]
