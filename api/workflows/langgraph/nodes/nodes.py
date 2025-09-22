"""
Updated main nodes file integrating all enhanced components
"""
import json
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from .base import BaseWorkflowNode
from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger
from utils.language_utils import get_workflow_message
from services.orchestrator.orchestrator import Orchestrator

logger = get_logger(__name__)


class OrchestratorNode(BaseWorkflowNode):
    """
    Initial orchestrator node that decides workflow path
    Always routes to semantic_reflection for proper planning
    """
    
    def __init__(self):
        super().__init__("orchestrator")
    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Analyze query and route to semantic reflection
        """
        try:
            query = state["query"]
            messages = state.get("messages", [])

            logger.info(f"Orchestrator processing query: {query[:50]}...")

            return {
                "next_action": "semantic_reflection",
                "processing_status": "processing",
                "progress_percentage": 5,
                "progress_message": "Starting query analysis",
                "should_yield": True,
                "execution_metadata": {
                    "orchestrator_decision": "semantic_reflection",
                    "query_length": len(query),
                    "message_count": len(messages)
                }
            }
            
        except Exception as e:
            logger.error(f"Orchestrator failed: {e}")
            return {
                "error_message": f"Orchestrator failed: {str(e)}",
                "next_action": "error",
                "processing_status": "failed",
                "should_yield": True
            }

    async def _load_agent_providers(self, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Load agent providers for all agents in the structure
        """
        try:
            from services.agents.agent_service import AgentService
            from config.database import execute_db_operation

            tenant_id = user_context.get("tenant_id")
            if not tenant_id:
                logger.warning("No tenant_id in user_context, cannot load agent providers")
                return {}

            async def load_providers_operation(db):
                agent_service = AgentService(db)
                agents_structure = await agent_service.get_agents_structure_for_user(user_context)

                agent_providers = {}
                for agent_name, agent_info in agents_structure.items():
                    agent_id = agent_info.get("agent_id")
                    if agent_id:
                        try:
                            provider = await agent_service._get_agent_llm_provider(agent_id, tenant_id)
                            if provider:
                                agent_providers[agent_id] = getattr(provider, 'name', f'provider_{agent_id}')
                                logger.debug(f"Loaded provider name for agent {agent_name} ({agent_id})")
                        except Exception as e:
                            logger.warning(f"Failed to load provider for agent {agent_name}: {e}")

                return agent_providers

            agent_providers = await execute_db_operation(load_providers_operation)
            logger.info(f"Loaded {len(agent_providers)} agent providers")
            return agent_providers

        except Exception as e:
            logger.error(f"Failed to load agent providers: {e}")
            return {}


class ErrorHandlerNode(BaseWorkflowNode):
    """
    Handle errors and provide fallback responses with language detection
    """
    
    def __init__(self):
        super().__init__("error_handler")
    
    async def execute(self, state: RAGState, config: RunnableConfig, db = None) -> Dict[str, Any]:
        """
        Handle workflow errors and provide appropriate response
        """
        try:
            error_message = state.get("error_message")
            if not error_message:
                original_error = state.get("original_error", "")
                exception_type = state.get("exception_type", "")
                if original_error and exception_type:
                    error_message = f"{exception_type}: {original_error}"
                elif original_error:
                    error_message = str(original_error)
                elif exception_type:
                    error_message = f"Error of type: {exception_type}"
                else:
                    error_message = "Unknown error occurred during workflow execution"

            agent_responses = state.get("agent_responses", [])
            detected_language = state.get("detected_language", "english")
            
            if agent_responses:
                user_context = state.get("user_context", {})
                partial_content = await self._create_partial_response(
                    agent_responses, error_message, detected_language, user_context, db
                )
                state["error_message"] = partial_content
                state["error_response_language"] = detected_language
                return {
                    "processing_status": "completed_with_errors",
                    "progress_percentage": 100,
                    "progress_message": get_workflow_message('error_completion', detected_language),
                    "should_yield": False,  
                    "execution_metadata": {
                        "error_handled": True,
                        "partial_results_available": True,
                        "detected_language": detected_language
                    }
                }
            
            fallback_response = self._create_friendly_error_message(detected_language, error_message)

            # Update state with error response for final_response node
            state["error_message"] = fallback_response
            state["error_response_language"] = detected_language
            return {
                "processing_status": "failed",
                "progress_percentage": 100,
                "progress_message": get_workflow_message('error_completion', detected_language),
                "should_yield": False,  # Let final_response node handle yielding
                "execution_metadata": {
                    "error_handled": True,
                    "partial_results_available": False,
                    "original_error": error_message,
                    "detected_language": detected_language
                }
            }
            
        except Exception as e:
            logger.error(f"Error handler itself failed: {e}")
            detected_language = state.get("detected_language", "english") if state else "english"
            friendly_message = self._create_friendly_error_message(detected_language, str(e))

            # Update state with error response for final_response node
            if state:
                state["error_message"] = friendly_message
                state["error_response_language"] = detected_language
            return {
                "processing_status": "failed",
                "progress_percentage": 100,
                "should_yield": False,
                "execution_metadata": {
                    "error_handler_failed": True
                }
            }
    
    def _create_friendly_error_message(self, detected_language: str, technical_error: str) -> str:
        """Create user-friendly error message based on language"""
        
        # Define friendly error messages by language
        friendly_messages = {
            "vietnamese": {
                "base": "Xin lỗi, tôi đang gặp một chút khó khăn kỹ thuật và không thể xử lý yêu cầu của bạn lúc này.",
                "suggestions": [
                    "Vui lòng thử lại sau vài phút.",
                    "Bạn có thể thử diễn đạt câu hỏi theo cách khác.",
                    "Nếu vấn đề vẫn tiếp tục, vui lòng liên hệ bộ phận hỗ trợ."
                ]
            },
            "english": {
                "base": "I'm sorry, I'm experiencing some technical difficulties and cannot process your request at the moment.",
                "suggestions": [
                    "Please try again in a few minutes.",
                    "You might try rephrasing your question.",
                    "If the problem persists, please contact support."
                ]
            },
            "japanese": {
                "base": "申し訳ございませんが、技術的な問題が発生しており、現在お客様のリクエストを処理できません。",
                "suggestions": [
                    "数分後に再度お試しください。",
                    "質問を別の方法で表現してみてください。",
                    "問題が続く場合は、サポートにお問い合わせください。"
                ]
            },
            "korean": {
                "base": "죄송합니다. 기술적인 문제가 발생하여 현재 요청을 처리할 수 없습니다.",
                "suggestions": [
                    "몇 분 후에 다시 시도해 주세요.",
                    "질문을 다르게 표현해 보세요.",
                    "문제가 지속되면 지원팀에 문의해 주세요."
                ]
            },
            "chinese": {
                "base": "抱歉，我遇到了一些技术问题，目前无法处理您的请求。",
                "suggestions": [
                    "请几分钟后再试。",
                    "您可以尝试换个方式表达您的问题。",
                    "如果问题持续存在，请联系支持团队。"
                ]
            }
        }
        
        lang_data = friendly_messages.get(detected_language, friendly_messages["english"])
        
        message_parts = [lang_data["base"]]
        message_parts.extend(lang_data["suggestions"])
        
        friendly_message = "\n\n".join(message_parts)
        
        logger.error(f"Technical error details: {technical_error}")
        
        return friendly_message
    
    async def _create_partial_response(
        self,
        agent_responses: List[Dict],
        error_message: str,
        detected_language: str,
        user_context: Dict[str, Any],
        db = None
    ) -> str:
        """Create response from partial agent results with LLM formatting"""
        try:
            successful_responses = [resp for resp in agent_responses 
                                  if resp.get("status") == "completed"]
            
            if not successful_responses:
                return get_workflow_message('no_results', detected_language)

            responses_content = []
            for resp in successful_responses:
                content = resp.get("content", "")
                if content.strip():
                    responses_content.append({
                        "agent": resp.get("agent_name", "Agent"),
                        "content": content
                    })

            if not responses_content:
                return get_workflow_message('no_results', detected_language)

            try:
                provider_name = user_context.get("provider_name")
                if provider_name:
                    orchestrator = Orchestrator()
                    provider = await orchestrator.llm(provider_name)
                    partial_prompt = f"""
Create a helpful response from these partial results, acknowledging that some information may be incomplete due to system issues.

LANGUAGE: {detected_language}
ERROR CONTEXT: {error_message}
PARTIAL RESULTS:
{json.dumps(responses_content, ensure_ascii=False, indent=2)}

INSTRUCTIONS:
- Combine the available information into a coherent response
- Acknowledge that results may be incomplete
- Respond in {detected_language}
- Be helpful with what information is available
- Mention that some agents experienced issues

Provide ONLY the formatted response.
"""
                    tenant_id = user_context.get("tenant_id")
                    formatted = await provider.ainvoke(partial_prompt, tenant_id)
                    return formatted.content.strip()
                    
            except Exception as e:
                logger.warning(f"Could not use LLM for partial response formatting: {e}")
            
        except Exception as e:
            logger.error(f"Partial response creation failed: {e}")
            
            content_parts = []
            for resp in agent_responses:
                content = resp.get("content", "")
                if content and content.strip():
                    content_parts.append(content)
            
            combined_content = "\n\n".join(content_parts)
            
            incomplete_messages = {
                "vietnamese": f"{combined_content}\n\nLưu ý: Kết quả có thể không đầy đủ do một số agent gặp sự cố.",
                "english": f"{combined_content}\n\nNote: Results may be incomplete due to some agents experiencing issues.",
                "chinese": f"{combined_content}\n\n注意：由于某些代理遇到问题，结果可能不完整。",
                "japanese": f"{combined_content}\n\n注意：一部のエージェントで問題が発生したため、結果が不完全な場合があります。",
                "korean": f"{combined_content}\n\n참고: 일부 에이전트에 문제가 발생하여 결과가 불완전할 수 있습니다."
            }
            
            return incomplete_messages.get(detected_language, 
                f"{combined_content}\n\nNote: Results may be incomplete due to some agents experiencing issues.")

