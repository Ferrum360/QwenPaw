# -*- coding: utf-8 -*-
"""Intent Classifier using QwenPaw's built-in embedding model.

利用 QwenPaw 内置的向量模型（llama-server）进行语义匹配。
不需要安装 sentence-transformers，直接调用 http://127.0.0.1:8081/v1/embeddings
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class IntentClassifier:
    """基于 QwenPaw 内置向量模型的意图分类器。

    使用 llama-server (http://127.0.0.1:8081) 的 OpenAI 兼容 API
    获取文本 embedding，计算余弦相似度判断用户意图。

    特性：
    - 自动缓存 embedding（避免重复计算）
    - rapidfuzz 快速预筛 + 语义精筛双层匹配
    - 支持动态注册/注销 skill triggers
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8081/v1",
        model_name: str = "embeddinggemma-300M-Q8_0",
        api_key: str = "",
        cache_dir: str | None = None,
        semantic_threshold: float = 0.65,
        fuzzy_threshold: int = 60,
    ):
        """
        Args:
            base_url: Embedding API 地址
            model_name: 模型名称
            api_key: API Key（留空则不传）
            cache_dir: 缓存目录（默认 ~/.qwenpaw/cache/embeddings）
            semantic_threshold: 语义相似度阈值（0-1）
            fuzzy_threshold: rapidfuzz 模糊匹配阈值（0-100）
        """
        self.base_url = base_url
        self.model_name = model_name
        self.api_key = api_key
        self.semantic_threshold = semantic_threshold
        self.fuzzy_threshold = fuzzy_threshold

        # 注册的技能 triggers
        self.skill_triggers: dict[str, list[str]] = {}

        # 缓存机制
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._cache: dict[str, list[float]] = {}

        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_cache()

    def register_skill(self, skill_name: str, triggers: list[str]) -> None:
        """注册技能的 trigger 描述"""
        self.skill_triggers[skill_name] = triggers
        logger.info(
            "Registered skill '%s' with %d triggers",
            skill_name,
            len(triggers),
        )

    def unregister_skill(self, skill_name: str) -> None:
        """注销技能"""
        if skill_name in self.skill_triggers:
            del self.skill_triggers[skill_name]
            logger.info("Unregistered skill '%s'", skill_name)

    def classify(self, user_input: str) -> tuple[str | None, float]:
        """分类用户输入，返回最匹配的 skill_name 和相似度分数。

        Args:
            user_input: 用户输入的文本

        Returns:
            (skill_name, score):
                - skill_name: 匹配的 skill 名称，无匹配则为 None
                - score: 相似度分数（0-1）
        """
        if not user_input or not self.skill_triggers:
            return None, 0.0

        # 第一层：rapidfuzz 快速预筛
        fuzzy_match = self._fast_fuzzy_match(user_input)
        if fuzzy_match:
            return fuzzy_match, 0.85  # 模糊匹配成功，直接返回

        # 第二层：语义精筛
        return self._semantic_match(user_input)

    def _fast_fuzzy_match(self, user_input: str) -> str | None:
        """第一层：rapidfuzz 快速模糊匹配"""
        try:
            from rapidfuzz import process, fuzz

            all_triggers = []
            for skill_name, triggers in self.skill_triggers.items():
                for trigger in triggers:
                    all_triggers.append((trigger, skill_name))

            best_match = process.extractOne(
                user_input,
                all_triggers,
                scorer=fuzz.token_sort_ratio,
            )

            if best_match and best_match[1] >= self.fuzzy_threshold:
                return best_match[0][1]  # 返回 skill_name

        except ImportError:
            pass  # rapidfuzz 未安装，跳过

        return None

    def _semantic_match(self, user_input: str) -> tuple[str | None, float]:
        """第二层：语义相似度匹配"""
        user_embedding = self._get_embedding(user_input)

        best_skill = None
        best_score = 0.0

        for skill_name, triggers in self.skill_triggers.items():
            for trigger in triggers:
                trigger_embedding = self._get_embedding(trigger)
                score = self._cosine_similarity(user_embedding, trigger_embedding)

                if score > best_score:
                    best_skill = skill_name
                    best_score = score

        if best_score >= self.semantic_threshold:
            return best_skill, best_score

        return None, best_score

    def _get_embedding(self, text: str) -> list[float]:
        """获取文本的 embedding 向量（带缓存）"""
        # 检查内存缓存
        if text in self._cache:
            return self._cache[text]

        # 检查磁盘缓存
        if self._cache_dir:
            cache_file = (
                self._cache_dir / f"{hashlib.md5(text.encode()).hexdigest()}.json"
            )
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text())
                    self._cache[text] = data["embedding"]
                    return data["embedding"]
                except Exception:
                    pass

        # 调用 API
        try:
            response = requests.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": self.model_name,
                    "input": text,
                },
                headers=(
                    {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                ),
                timeout=10,
            )
            response.raise_for_status()

            embedding = response.json()["data"][0]["embedding"]

            # 存入内存缓存
            self._cache[text] = embedding

            # 存入磁盘缓存
            if self._cache_dir:
                cache_file = (
                    self._cache_dir / f"{hashlib.md5(text.encode()).hexdigest()}.json"
                )
                cache_file.write_text(json.dumps({"embedding": embedding}))

            return embedding

        except Exception as exc:
            logger.error("Failed to get embedding for '%s': %s", text[:50], exc)
            raise

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        import numpy as np

        v1, v2 = np.array(vec1), np.array(vec2)
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _load_cache(self) -> None:
        """加载磁盘缓存到内存"""
        if not self._cache_dir:
            return

        try:
            for cache_file in self._cache_dir.glob("*.json"):
                try:
                    data = json.loads(cache_file.read_text())
                    # 简化：只加载最近 1000 条
                    if cache_file.stat().st_mtime > time.time() - 86400 * 7:  # 7天内
                        self._cache[cache_file.stem] = data["embedding"]
                except Exception:
                    pass
        except Exception:
            pass


# 全局单例
_intent_classifier: IntentClassifier | None = None


def get_intent_classifier() -> IntentClassifier:
    """获取全局 intent classifier 单例"""
    global _intent_classifier

    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()

    return _intent_classifier


def reset_intent_classifier() -> None:
    """重置 intent classifier（用于测试或配置变更）"""
    global _intent_classifier
    _intent_classifier = None
