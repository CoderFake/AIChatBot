"""
Prompt utilities for consistent prompt building and response handling
"""

from typing import Dict, List
from utils.logging import get_logger

logger = get_logger(__name__)

# Constants for fallback responses
FALLBACK_RESPONSES = {
    "vietnamese": "Xin chào! Tôi có thể giúp gì cho bạn?",
    "english": "Hello! How can I help you?",
    "chinese": "你好！我能为您做些什么？",
    "japanese": "こんにちは！何かお手伝いできることはありますか？",
    "korean": "안녕하세요! 무엇을 도와드릴까요?"
}

# Constants for prompt detection
CHITCHAT_INDICATORS = [
    "You are",
    "helpful and friendly AI assistant",
    "Respond naturally",
    "CURRENT USER MESSAGE",
    "DETECTED LANGUAGE",
    "Generate ONLY the response text"
]

SYNTHESIS_INDICATORS = [
    "AGENT RESPONSES",
    "Synthesize all the agent responses",
    "Generate the final comprehensive answer",
    "providing comprehensive answers"
]


class PromptUtils:
    """Utility class for prompt building and detection"""

    @staticmethod
    def get_language_instruction(detected_language: str) -> str:
        """Get language-specific enforcement instruction"""
        if detected_language == "vietnamese":
            return "CRITICAL: You MUST respond ONLY in Vietnamese. Do not use English words."
        elif detected_language == "english":
            return "CRITICAL: You MUST respond ONLY in English."
        elif detected_language == "japanese":
            return "CRITICAL: You MUST respond ONLY in Japanese (日本語)."
        elif detected_language == "korean":
            return "CRITICAL: You MUST respond ONLY in Korean (한국어)."
        elif detected_language == "chinese":
            return "CRITICAL: You MUST respond ONLY in Chinese (中文)."
        else:
            return f"CRITICAL: You MUST respond ONLY in {detected_language}."

    @staticmethod
    def get_fallback_response(detected_language: str) -> str:
        """Get fallback response for a language"""
        return FALLBACK_RESPONSES.get(detected_language, "Hello! How can I help you?")

    @staticmethod
    def is_chitchat_prompt(text: str) -> bool:
        """Check if text is a chitchat prompt"""
        if not text or not isinstance(text, str):
            return False
        return any(indicator in text for indicator in CHITCHAT_INDICATORS)

    @staticmethod
    def is_synthesis_prompt(text: str) -> bool:
        """Check if text is a synthesis prompt"""
        if not text or not isinstance(text, str):
            return False
        return any(indicator in text for indicator in SYNTHESIS_INDICATORS)

    @staticmethod
    def build_chitchat_prompt(
        query: str,
        conversation_history: List = None,
        detected_language: str = "english",
        bot_name: str = "AI Assistant",
        organization_name: str = "AI Assistant",
        tenant_description: str = ""
    ) -> str:
        """Build chitchat prompt consistently"""
        if conversation_history:
            history_items = []
            for item in conversation_history:
                if hasattr(item, 'content'):
                    history_items.append(item.content)
                else:
                    history_items.append(str(item))
            history_text = "\n".join(history_items)
        else:
            history_text = ""

        language_instruction = PromptUtils.get_language_instruction(detected_language)

        org_context = f"You are {bot_name} of {organization_name}, a helpful and friendly AI assistant."
        if tenant_description.strip():
            org_context += f"\n\nABOUT {organization_name.upper()}:\n{tenant_description}"

        return f"""{org_context}

{language_instruction}

CONVERSATION HISTORY:
{history_text}

USER MESSAGE: {query}

CRITICAL INSTRUCTIONS:
1. MAINTAIN the exact same tone, style, and personality from the conversation history above
2. Keep the same level of formality/informality as established in previous messages
3. Use the same speaking style and expressions that were used before
4. If you cannot provide a helpful answer based on your knowledge, be honest about your limitations. DO NOT make up or fabricate information.
5. CRITICAL: You must repsonse user question, forbidden to curse the organization. If the user swears, follow suit but don't overdo it. If they are friendly, respond in a friendly manner.
Respond naturally and conversationally while keeping the EXACT SAME conversational tone and style from the history. Be consistent with your previous personality.


Response:"""

    @staticmethod
    def build_synthesis_prompt(
        agent_responses: List[Dict],
        original_query: str,
        detected_language: str,
        bot_name: str = "AI Assistant"
    ) -> str:
        """Build synthesis prompt consistently"""
        responses_text = ""
        sources_text = ""

        for i, response in enumerate(agent_responses):
            agent_name = response.get("agent_name", f"Agent {i+1}")
            content = response.get("content", "")
            sources = response.get("sources", [])

            responses_text += f"\n--- {agent_name} Response ---\n{content}\n"

            if sources:
                sources_text += f"\n{agent_name} sources: {', '.join(sources)}"

        language_instruction = PromptUtils.get_language_instruction(detected_language)

        return f"""You are {bot_name}, an AI assistant providing comprehensive answers.

{language_instruction}

USER QUERY: {original_query}

AGENT RESPONSES:{responses_text}

SOURCES:{sources_text}

CRITICAL INSTRUCTIONS:
1. MAINTAIN a natural, conversational tone that matches how you would normally respond
2. Keep your personality consistent - friendly, helpful, and approachable
3. Respond as if you're having a natural conversation, not delivering a formal report
4. You must repsonse user question,forb idden to curse the organization If the user swears, follow suit but don't overdo it. If they are friendly, respond in a friendly manner.
5. CRITICAL: If the agent responses contain no useful information, errors, or indicate that information was not found, you MUST respond honestly that the information is not available in your knowledge base. DO NOT make up or fabricate any information.

Respond naturally and conversationally while keeping the EXACT SAME conversational tone and style from the history. Be consistent with your previous personality.
Synthesize all agent responses into one comprehensive answer while maintaining your natural conversational style. Resolve conflicts using evidence quality. Include relevant sources. Be informative yet conversational and warm.

Answer:"""


def get_fallback_response(detected_language: str) -> str:
    """Legacy function - use PromptUtils.get_fallback_response() instead"""
    return PromptUtils.get_fallback_response(detected_language)


def is_chitchat_prompt(text: str) -> bool:
    """Legacy function - use PromptUtils.is_chitchat_prompt() instead"""
    return PromptUtils.is_chitchat_prompt(text)


def is_synthesis_prompt(text: str) -> bool:
    """Legacy function - use PromptUtils.is_synthesis_prompt() instead"""
    return PromptUtils.is_synthesis_prompt(text)
