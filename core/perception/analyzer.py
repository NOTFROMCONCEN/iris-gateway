"""Iris AI Gateway - 感知分析器

分析用户消息的情绪、意图、关键词等。
"""

import logging
import re
from typing import List, Optional

from models.schemas import Message, PerceptionResult, EmotionType, IntentType

logger = logging.getLogger(__name__)


class PerceptionAnalyzer:
    """感知分析器 - 基于规则引擎的轻量级分析"""

    # 情绪关键词映射
    EMOTION_KEYWORDS = {
        EmotionType.HAPPY: ["开心", "高兴", "愉快", "棒", "优秀", "感谢", "喜欢", "love", "great", "happy", "thanks"],
        EmotionType.SAD: ["难过", "伤心", "失望", "遗憾", "糟糕", "bad", "sad", "sorry", "unfortunate"],
        EmotionType.ANGRY: ["生气", "愤怒", "恼火", "烦", "讨厌", "angry", "annoyed", "frustrated", "mad"],
        EmotionType.SURPRISED: ["惊讶", "震惊", "意外", "居然", "surprised", "shocked", "amazed"],
        EmotionType.FEARFUL: ["害怕", "担心", "焦虑", "恐惧", "scared", "worried", "anxious", "afraid"],
        EmotionType.CURIOUS: ["好奇", "想知道", "为什么", "怎么", "how", "why", "what", "curious", "wonder"],
        EmotionType.EMPATHETIC: ["理解", "支持", "陪伴", "心疼", "care", "understand", "support", "empathy"],
    }

    # 意图关键词映射
    INTENT_KEYWORDS = {
        IntentType.QUESTION: ["?", "吗", "什么", "为什么", "怎么", "如何", "who", "what", "when", "where", "why", "how"],
        IntentType.COMMAND: ["请", "帮我", "给我", "执行", "运行", "请帮我", "please", "help me", "run", "execute"],
        IntentType.CREATIVE: ["写", "创作", "设计", "创意", "画", "write", "create", "design", "compose", "draft"],
        IntentType.ANALYSIS: ["分析", "比较", "评估", "总结", "评价", "analyze", "compare", "evaluate", "assess", "summarize"],
        IntentType.EMOTIONAL_SUPPORT: ["难过", "难受", "心情不好", "安慰", "support", "feel bad", "depressed", "lonely"],
        IntentType.CODE: ["代码", "程序", "函数", "bug", "错误", "code", "program", "function", "script", "debug"],
    }

    # 紧急度关键词
    URGENCY_KEYWORDS = [
        "紧急", "急", "尽快", "马上", "立刻", "urgent", "asap", "immediately",
        " hurry", " rush", " deadline", "critical",
    ]

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    async def analyze(self, messages: List[Message]) -> Optional[PerceptionResult]:
        """分析消息列表，返回感知结果"""
        if not self.enabled:
            return None

        try:
            # 只分析用户消息
            user_messages = [m.content for m in messages if m.role.value == "user"]
            if not user_messages:
                return None

            text = " ".join(user_messages)

            # 情绪分析
            emotion, emotion_conf = self._analyze_emotion(text)

            # 意图分析
            intent, intent_conf = self._analyze_intent(text)

            # 关键词提取
            keywords = self._extract_keywords(text)

            # 紧急度
            urgency = self._analyze_urgency(text)

            # 情感极性 (-1 到 1)
            sentiment = self._analyze_sentiment(text)

            return PerceptionResult(
                emotion=emotion,
                emotion_confidence=emotion_conf,
                intent=intent,
                intent_confidence=intent_conf,
                keywords=keywords[:10],  # 最多 10 个关键词
                urgency=urgency,
                sentiment=sentiment,
            )
        except Exception as e:
            logger.warning(f"Perception analysis failed: {e}")
            return None

    def _analyze_emotion(self, text: str) -> tuple:
        """分析情绪"""
        text_lower = text.lower()
        scores = {}
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[emotion] = score

        if scores:
            best_emotion = max(scores, key=scores.get)
            confidence = min(1.0, scores[best_emotion] * 0.3)
            return best_emotion, confidence
        return EmotionType.NEUTRAL, 0.0

    def _analyze_intent(self, text: str) -> tuple:
        """分析意图"""
        text_lower = text.lower()
        scores = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[intent] = score

        if scores:
            best_intent = max(scores, key=scores.get)
            confidence = min(1.0, scores[best_intent] * 0.3)
            return best_intent, confidence
        return IntentType.CONVERSATION, 0.0

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单规则：提取 2-10 个字符的词组
        words = re.findall(r'[\u4e00-\u9fa5]{2,8}|[a-zA-Z]{3,}', text.lower())
        # 去重并过滤常见词
        stop_words = {"the", "and", "this", "that", "with", "for", "you", "are", "can"}
        keywords = []
        seen = set()
        for w in words:
            if w not in stop_words and w not in seen and len(w) > 1:
                keywords.append(w)
                seen.add(w)
        return keywords

    def _analyze_urgency(self, text: str) -> float:
        """分析紧急度 (0-1)"""
        text_lower = text.lower()
        count = sum(1 for kw in self.URGENCY_KEYWORDS if kw in text_lower)
        return min(1.0, count * 0.3)

    def _analyze_sentiment(self, text: str) -> float:
        """分析情感极性 (-1 到 1)"""
        text_lower = text.lower()
        positive = sum(1 for kw in self.EMOTION_KEYWORDS[EmotionType.HAPPY] if kw in text_lower)
        negative = sum(1 for kw in self.EMOTION_KEYWORDS[EmotionType.SAD] if kw in text_lower)
        negative += sum(1 for kw in self.EMOTION_KEYWORDS[EmotionType.ANGRY] if kw in text_lower)

        total = positive + negative
        if total == 0:
            return 0.0
        return (positive - negative) / total
