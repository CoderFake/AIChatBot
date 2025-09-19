"""
Language Detection and Localization Utilities
Provides centralized language detection and message localization
"""
from typing import Dict, Any, Optional
import re

try:
    from langdetect import detect as langdetect_detect
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger(__name__)


class LanguageDetector:
    """
    Centralized language detection with multiple fallback strategies
    """

    def __init__(self):
        # Regex patterns for fallback detection
        self._patterns = {
            'chinese': re.compile(r'[\u4e00-\u9fff]'),
            'japanese': re.compile(r'[\u3040-\u309f\u30a0-\u30ff]'),
            'korean': re.compile(r'[\uac00-\ud7af]'),
            'vietnamese': re.compile(r'[àáảãạầấẩẫậằắẳẵặèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵđ]', re.IGNORECASE)
        }

    def detect(self, text: str) -> str:
        """
        Detect language using multiple strategies

        Args:
            text: Input text to detect language

        Returns:
            Detected language code (vietnamese, english, chinese, japanese, korean)
        """
        if not text or not text.strip():
            return "english"

        try:
            # Strategy 1: Use langdetect if available
            if LANGDETECT_AVAILABLE:
                try:
                    detected = langdetect_detect(text.strip())
                    from models.database.types import LANGUAGE_MAPPING
                    mapped_lang = LANGUAGE_MAPPING.get(detected, detected)

                    from models.database.types import SUPPORTED_LANGUAGES
                    if mapped_lang in SUPPORTED_LANGUAGES:
                        return mapped_lang
                    else:
                        logger.debug(f"Detected unsupported language '{mapped_lang}', defaulting to english")
                        return "english"

                except Exception as e:
                    logger.debug(f"Langdetect failed: {e}, using fallback")

            # Strategy 2: Regex pattern matching
            detected_lang = self._detect_by_patterns(text)
            if detected_lang != "english": 
                return detected_lang

            # Strategy 3: Character-based heuristics
            detected_lang = self._detect_by_heuristics(text)

            from models.database.types import SUPPORTED_LANGUAGES
            if detected_lang in SUPPORTED_LANGUAGES:
                return detected_lang
            else:
                logger.debug(f"Final detection '{detected_lang}' not supported, defaulting to english")
                return "english"

        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return "english"

    def _detect_by_patterns(self, text: str) -> str:
        """
        Detect language using regex patterns
        """
        for lang, pattern in self._patterns.items():
            if pattern.search(text):
                from models.database.types import SUPPORTED_LANGUAGES
                if lang in SUPPORTED_LANGUAGES:
                    return lang
        return "english"

    def _detect_by_heuristics(self, text: str) -> str:
        """
        Detect language using character-based heuristics
        """
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        japanese_chars = sum(1 for char in text if '\u3040' <= char <= '\u309f' or '\u30a0' <= char <= '\u30ff')
        korean_chars = sum(1 for char in text if '\uac00' <= char <= '\ud7af')
        vietnamese_chars = sum(1 for char in text if char.lower() in 'àáảãạầấẩẫậằắẳẵặèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵđ')

        total_chars = len(text)
        if total_chars == 0:
            return "english"

        # Calculate percentages
        scores = {
            'chinese': chinese_chars / total_chars,
            'japanese': japanese_chars / total_chars,
            'korean': korean_chars / total_chars,
            'vietnamese': vietnamese_chars / total_chars
        }

        max_lang = max(scores, key=scores.get)
        if scores[max_lang] > 0.1:  
            from models.database.types import SUPPORTED_LANGUAGES
            if max_lang in SUPPORTED_LANGUAGES:
                return max_lang

        return "english"


class MessageLocalizer:
    """
    Centralized message localization
    """

    def __init__(self):
        self._message_cache: Dict[str, Dict[str, str]] = {}

    def get_message(self, key: str, language: str, **kwargs) -> str:
        """
        Get localized message

        Args:
            key: Message key
            language: Language code
            **kwargs: Format arguments

        Returns:
            Localized message
        """
        try:
            from models.database.types import LOCALIZED_MESSAGES
            messages = LOCALIZED_MESSAGES.get(key, {})

            # Get message template, fallback to english, then to key
            template = messages.get(language, messages.get("english", key))

            # Format with provided arguments
            if kwargs:
                try:
                    return template.format(**kwargs)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to format message {key}: {e}")
                    return template

            return template

        except Exception as e:
            logger.error(f"Message localization failed for key '{key}': {e}")
            return key

    def get_workflow_message(self, key: str, language: str, **kwargs) -> str:
        """
        Get workflow-specific localized message
        """
        try:
            from models.database.types import WORKFLOW_MESSAGES
            return self.get_message(key, language, **kwargs)
        except Exception:
            return self.get_message(key, language, **kwargs)


# Global instances
language_detector = LanguageDetector()
message_localizer = MessageLocalizer()


def detect_language(text: str) -> str:
    """
    Convenience function for language detection
    """
    return language_detector.detect(text)


def get_localized_message(key: str, language: str, **kwargs) -> str:
    """
    Convenience function for message localization
    """
    return message_localizer.get_message(key, language, **kwargs)


def get_workflow_message(key: str, language: str, **kwargs) -> str:
    """
    Convenience function for workflow messages
    """
    return message_localizer.get_workflow_message(key, language, **kwargs)
