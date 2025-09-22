"""
Final Response Node with proper language detection and LLM-based chitchat
"""
import json
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from .base import BaseWorkflowNode
from workflows.langgraph.state.state import RAGState 
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager
from utils.language_utils import get_workflow_message
from utils.prompt_utils import PromptUtils
from services.orchestrator.orchestrator import Orchestrator

logger = get_logger(__name__)


class FinalResponseNode(BaseWorkflowNode):
    """
    Enhanced final response node with language detection and LLM chitchat
    """

    def __init__(self):
        super().__init__("final_response")
        self._start_time = None

    def _get_language_instruction(self, detected_language: str) -> str:
        """Get language-specific enforcement instruction"""
        return PromptUtils.get_language_instruction(detected_language)

    def _get_tenant_current_time(self, user_context: Dict = None) -> str:
        """
        Get current timestamp in tenant's timezone.
        Falls back to system timezone if tenant timezone not available.
        """
        try:
            if user_context:
                tenant_timezone = user_context.get("timezone")
                if tenant_timezone:
                    current_time = DateTimeManager.tenant_now(tenant_timezone)
                    return current_time.isoformat()
        except Exception as e:
            logger.warning(f"Failed to get tenant timezone from user_context, using system time: {e}")

        current_time = DateTimeManager.system_now()
        return current_time.isoformat()

    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Assemble final response with proper language handling
        """
        try:
            import time
            self._start_time = time.time()

            semantic_routing = state.get("semantic_routing")
            agent_responses = state.get("agent_responses", [])
            conflict_resolution = state.get("conflict_resolution")
            error_message = state.get("error_message")
            original_query = state.get("query", "")

            detected_language = state.get("detected_language", "english")
            user_context = state.get("user_context", {})

            is_chitchat_detected = (
                (semantic_routing and semantic_routing.get("is_chitchat")) or
                state.get("is_chitchat", False)
            )

            if is_chitchat_detected:
                final_content = self._generate_chitchat_response(
                    original_query, [], detected_language, state
                )
                sources = []

            elif error_message:
                error_lang = state.get("detected_language", detected_language)
                final_content = await self._generate_error_response(error_message, error_lang)
                sources = []

            elif conflict_resolution and conflict_resolution.get("final_answer"):
                final_content = conflict_resolution["final_answer"]
                sources = conflict_resolution.get("combined_sources", [])

            elif len(agent_responses) == 1:
                response = agent_responses[0]
                final_content = await self._build_final_synthesis_prompt(
                    [response], original_query, detected_language, user_context, semantic_routing, state
                )
                sources = response.get("sources", [])

            elif len(agent_responses) > 1:
                final_content = await self._build_final_synthesis_prompt(
                    agent_responses, original_query, detected_language, user_context, semantic_routing, state
                )
                sources = self._extract_all_sources(agent_responses)

            else:
                final_content = await self._build_no_response_prompt(original_query, detected_language, user_context, state)
                sources = []

            return {
                "final_response": final_content,
                "final_sources": sources,
                "provider_name": state.get("provider_name"),
                "processing_status": "completed",
                "progress_percentage": 100,
                "progress_message": get_workflow_message("completed", detected_language),
                "should_yield": True
            }

        except Exception as e:
            logger.error(f"Final response assembly failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            return {
                "error_message": f"Final response assembly failed: {str(e)}",
                "original_error": str(e),
                "exception_type": type(e).__name__,
                "next_action": "error",
                "processing_status": "failed",
                "progress_percentage": self._calculate_progress_percentage("error"),
                "should_yield": True
            }
    
    def _generate_chitchat_response(
        self,
        query: str,
        messages: List,
        detected_language: str,
        state
    ) -> str:
        """Generate chitchat prompt for chat service to execute"""
        try:
            bot_name = state.get("bot_name", "AI Assistant")
            organization_name = state.get("organization_name", "AI Assistant")
            tenant_description = state.get("tenant_description", "")
            conversation_history = state.get("messages", [])

            chitchat_prompt = PromptUtils.build_chitchat_prompt(
                query=query,
                conversation_history=conversation_history,
                detected_language=detected_language,
                bot_name=bot_name,
                organization_name=organization_name,
                tenant_description=tenant_description
            )

            return chitchat_prompt

        except Exception as e:
            logger.error(f"Chitchat prompt generation failed: {e}")
            raise RuntimeError(f"Chitchat prompt generation failed: {str(e)}")

    async def _format_single_response(
        self,
        state: RAGState,
        response: Dict[str, Any]
    ) -> str:
        """Format single agent response with proper language - return prompt for chat service"""
        try:
            content = response.get("content", "")
            original_query = state.get("query", "")
            detected_language = state.get("detected_language", "english")
            user_context = state.get("user_context", {})

            if not content.strip():
                return await self._generate_no_response_message(detected_language)

            if detected_language == "english":
                return content

            tenant_id = user_context.get("tenant_id")
            if not tenant_id:
                raise ValueError("Tenant ID is required for LLM provider selection")

            language_instruction = self._get_language_instruction(detected_language)

            format_prompt = f"""Format this response to match the user's query language and style.

{language_instruction}

USER QUERY: {original_query}
AGENT RESPONSE: {content}

Keep the factual content intact. Make the language natural and fluent. Maintain professional yet friendly tone.

Formatted response:"""

            return format_prompt

        except Exception as e:
            logger.warning(f"Response formatting failed: {e}")
            return response.get("content", "")
    
    async def _combine_multiple_responses(
        self,
        state: RAGState,
        agent_responses: List[Dict[str, Any]]
    ) -> str:
        """Combine multiple agent responses - return prompt for chat service"""
        try:
            original_query = state.get("query", "")
            detected_language = state.get("detected_language", "english")
            user_context = state.get("user_context", {})

            tenant_id = user_context.get("tenant_id")
            if not tenant_id:
                raise ValueError("Tenant ID is required for LLM provider selection")

            responses_data = []
            for response in agent_responses:
                content = response.get("content", "")
                if content.strip():
                    responses_data.append({
                        "agent": response.get("agent_name", "Agent"),
                        "content": content,
                        "confidence": response.get("confidence", 0.0)
                    })

            if not responses_data:
                return await self._generate_no_response_message(detected_language)

            language_instruction = self._get_language_instruction(detected_language)

            combine_prompt = f"""Combine these multiple agent responses into a single, coherent answer for the user's query.

{language_instruction}

USER QUERY: {original_query}

AGENT RESPONSES:
{json.dumps(responses_data, ensure_ascii=False, indent=2)}

Combine information from all agents into one coherent response. Prioritize higher confidence responses. Remove contradictions and redundancies. Synthesize complementary information. Maintain factual accuracy.

Combined response:"""

            return combine_prompt

        except Exception as e:
            logger.error(f"Response combination failed: {e}")

            combined_parts = []
            for response in agent_responses:
                content = response.get("content", "")
                if content.strip():
                    combined_parts.append(content)

            return "\n\n".join(combined_parts) if combined_parts else await self._generate_no_response_message(detected_language)
    
    async def _generate_error_response(self, error_message: str, detected_language: str, state: RAGState = None) -> str:
        """Generate error response maintaining conversational tone"""
        bot_name = state.get("bot_name", "AI Assistant") if state else "AI Assistant"
        conversation_history = state.get("messages", []) if state else []
        
        if conversation_history:
            history_items = []
            for item in conversation_history[-3:]: 
                if hasattr(item, 'content'):
                    history_items.append(item.content)
                else:
                    history_items.append(str(item))
            history_text = "\n".join(history_items)
        else:
            history_text = ""
        
        language_instruction = self._get_language_instruction(detected_language)
        
        error_prompt = f"""You are {bot_name}, a helpful and friendly AI assistant.

{language_instruction}

CONVERSATION HISTORY:
{history_text}

SYSTEM ERROR: {error_message}

CRITICAL INSTRUCTIONS:
1. MAINTAIN the exact same tone, style, and personality from the conversation history above
2. Keep the same level of formality/informality as established in previous messages
3. Apologize naturally for the technical issue while maintaining your conversational style
4. Be honest about the error but keep your warm, friendly personality
5. CRITICAL: You must repsonse user question, forbidden to curse the organization. If the user swears, follow suit but don't overdo it. If they are friendly, respond in a friendly manner.

Respond naturally about this technical issue while keeping the EXACT SAME conversational tone and style from the history.

Response:"""
        
        return error_prompt
    
    async def _generate_no_response_message(self, detected_language: str) -> str:
        """Generate no response message in appropriate language"""
        no_response_messages = {
            "vietnamese": "Xin lỗi, tôi không thể tạo phản hồi cho câu hỏi của bạn.",
            "english": "I'm sorry, I couldn't generate a response to your query.",
            "chinese": "抱歉，我无法为您的查询生成回复。",
            "japanese": "申し訳ございませんが、お問い合わせに対する回答を生成できませんでした。",
            "korean": "죄송합니다. 귀하의 질문에 대한 응답을 생성할 수 없었습니다."
        }
        
        return no_response_messages.get(detected_language, "I'm sorry, I couldn't generate a response to your query.")
    
    def _get_completion_message(self, detected_language: str) -> str:
        """Get completion message in appropriate language"""
        completion_messages = {
            "vietnamese": "Hoàn thành",
            "english": "Completed",
            "chinese": "完成",
            "japanese": "完了",
            "korean": "완료"
        }
        
        return completion_messages.get(detected_language, "Completed")
    
    def _extract_all_sources(self, agent_responses: List[Dict]) -> List[str]:
        """Extract all sources from agent responses"""
        sources = []
        for response in agent_responses:
            sources.extend(response.get("sources", []))
        return sources
    
    def _determine_response_type(
        self,
        semantic_routing: Dict,
        agent_responses: List[Dict],
        error_message: str
    ) -> str:
        """Determine the type of response generated"""
        if error_message:
            return "error"
        elif semantic_routing and semantic_routing.get("is_chitchat"):
            return "chitchat"
        elif len(agent_responses) > 1:
            return "multi_agent"
        elif len(agent_responses) == 1:
            return "single_agent"
        else:
            return "no_response"

    async def _build_final_synthesis_prompt(
        self,
        agent_responses: List[Dict],
        original_query: str,
        detected_language: str,
        user_context: Dict,
        semantic_routing: Dict,
        state: RAGState = None
    ) -> str:
        """Build a synthesis prompt from agent responses for final LLM execution"""
        try:
            tenant_id = user_context.get("tenant_id")
            if not tenant_id:
                return f"Please provide a comprehensive answer to: {original_query}"

            bot_name = state.get("bot_name", "AI Assistant") if state else "AI Assistant"

            return PromptUtils.build_synthesis_prompt(
                agent_responses=agent_responses,
                original_query=original_query,
                detected_language=detected_language,
                bot_name=bot_name
            )

        except Exception as e:
            logger.error(f"Failed to build synthesis prompt: {e}")
            return f"Please provide a comprehensive answer to: {original_query}"

    async def _build_no_response_prompt(
        self,
        original_query: str,
        detected_language: str,
        user_context: Dict,
        state: RAGState = None
    ) -> str:
        """Build a prompt when no agent responses are available"""
        try:
            bot_name = state.get("bot_name", "AI Assistant") if state else "AI Assistant"
            conversation_history = state.get("messages", []) if state else []
            
            # Build conversation context
            if conversation_history:
                history_items = []
                for item in conversation_history[-3:]:  # Last 3 messages for context
                    if hasattr(item, 'content'):
                        history_items.append(item.content)
                    else:
                        history_items.append(str(item))
                history_text = "\n".join(history_items)
            else:
                history_text = ""

            language_instruction = self._get_language_instruction(detected_language)

            return f"""You are {bot_name}, an AI assistant.

{language_instruction}

CONVERSATION HISTORY:
{history_text}

USER QUERY: {original_query}

CRITICAL INSTRUCTIONS:
1. MAINTAIN the exact same tone, style, and personality from the conversation history above
2. Keep the same level of formality/informality as established in previous messages
3. No specific information was found for this query. You MUST honestly acknowledge that this information is not available in your knowledge base. DO NOT make up or fabricate any information.
4. Be honest about what you don't know while maintaining your conversational style
5. CRITICAL: You must repsonse user question, forbidden to curse the organization. If the user swears, follow suit but don't overdo it. If they are friendly, respond in a friendly manner.

Provide a helpful response acknowledging this limitation while keeping the EXACT SAME conversational tone and style from the history.

Response:"""
        except Exception as e:
            logger.error(f"Failed to build no response prompt: {e}")
            return f"I apologize, but I don't have specific information to answer: {original_query}"

    async def _format_final_output(
        self,
        final_content: str,
        sources: List[str],
        semantic_routing: Dict,
        agent_responses: List[Dict],
        conflict_resolution: Dict,
        error_message: str,
        original_query: str,
        detected_language: str,
        user_context: Dict = None,
        state: Dict = None
    ) -> Dict[str, Any]:
        """Format final output according to spec structure"""
        try:
            output = {
                "answer": final_content,
                "evidence": self._format_evidence(sources),
                "reasoning": self._generate_reasoning(conflict_resolution, agent_responses, semantic_routing),
                "confidence_score": self._calculate_confidence_score(agent_responses, conflict_resolution),
                "follow_up_questions": await self._generate_follow_up_questions(original_query, final_content, detected_language, user_context, state),
                "flow_action": self._generate_flow_action(agent_responses, conflict_resolution, state, semantic_routing, user_context),
                "execution_metadata": self._generate_execution_metadata(agent_responses, semantic_routing, detected_language, user_context, state)
            }

            return output

        except Exception as e:
            logger.error(f"Final output formatting failed: {e}")
            return {
                "answer": final_content,
                "evidence": self._format_evidence(sources),
                "reasoning": "Error occurred during response formatting",
                "confidence_score": 0.0,
                "follow_up_questions": [],
                "flow_action": [],
                "execution_metadata": {
                    "total_duration_ms": 0,
                    "agents_invoked": [],
                    "tools_executed": [],
                    "total_queries": 0,
                    "conflict_resolution_applied": False,
                    "department_permission_filtering": False,
                    "accessible_departments": []
                }
            }

    def _format_evidence(self, sources: List[str]) -> List[Dict[str, Any]]:
        """Format sources into evidence structure per spec"""
        evidence = []
        try:
            for source in sources:
                if isinstance(source, dict):
                    evidence.append({
                        "url": source.get("url", ""),
                        "created_at": source.get("created_at", ""),
                        "source_type": source.get("source_type", "unknown"),
                        "scope": source.get("scope", "public"),
                        "relevance_score": source.get("relevance_score", 0.5)
                    })
                elif isinstance(source, str):
                    evidence.append({
                        "url": source,
                        "created_at": "",
                        "source_type": "unknown",
                        "scope": "public",
                        "relevance_score": 0.5
                    })
        except Exception as e:
            logger.warning(f"Evidence formatting failed: {e}")

        return evidence

    def _generate_reasoning(
        self,
        conflict_resolution: Dict,
        agent_responses: List[Dict],
        semantic_routing: Dict
    ) -> str:
        """Generate reasoning explanation"""
        try:
            if conflict_resolution and conflict_resolution.get("resolution_reasoning"):
                return conflict_resolution["resolution_reasoning"]

            if len(agent_responses) == 1:
                agent_name = agent_responses[0].get("agent_name", "Agent")
                return f"Response generated by {agent_name} agent based on available data sources."

            if len(agent_responses) > 1:
                agent_names = [r.get("agent_name", "Agent") for r in agent_responses]
                return f"Response synthesized from {len(agent_responses)} agents: {', '.join(agent_names)}."

            if semantic_routing and semantic_routing.get("is_chitchat"):
                return "Chitchat response generated for casual conversation."

            return "Response generated based on query analysis and available information."

        except Exception as e:
            logger.warning(f"Reasoning generation failed: {e}")
            return "Response generated through automated analysis."

    def _calculate_confidence_score(self, agent_responses: List[Dict], conflict_resolution: Dict) -> float:
        """Calculate overall confidence score"""
        try:
            if conflict_resolution and "confidence_score" in conflict_resolution:
                return conflict_resolution["confidence_score"]

            if not agent_responses:
                return 0.0

            confidences = [r.get("confidence", 0.0) for r in agent_responses if r.get("confidence", 0.0) > 0]
            if confidences:
                return sum(confidences) / len(confidences)

            if len(agent_responses) > 0:
                return 0.7

            return 0.0

        except Exception as e:
            logger.warning(f"Confidence calculation failed: {e}")
            return 0.5

    async def _generate_follow_up_questions(
        self,
        original_query: str,
        final_content: str,
        detected_language: str,
        user_context: Dict = None,
        state: Dict = None
    ) -> List[str]:
        """Generate follow-up questions using AI based on query and response"""
        try:
            provider_name = state.get("provider_name") if state else None

            if provider_name:
                orchestrator = Orchestrator()
                llm_provider = await orchestrator.llm(provider_name)
                try:
                    language_instruction = ""
                    if detected_language and detected_language != "en":
                        if detected_language == "vi":
                            language_instruction = "Please respond in Vietnamese."
                        elif detected_language == "ja":
                            language_instruction = "Please respond in Japanese."
                        elif detected_language == "ko":
                            language_instruction = "Please respond in Korean."

                    prompt = f"""
Based on the following user query and AI response, generate 3 relevant follow-up questions that the user might ask next.
Focus on questions that would help deepen understanding or get more specific information.

User Query: {original_query}

AI Response: {final_content}

Generate exactly 3 follow-up questions that are natural, relevant, and would logically follow from this conversation.
Return only the questions, one per line, without numbering or bullet points.

{language_instruction}
"""

                    tenant_id = state.get("tenant_id") if state else None
                    response = await llm_provider.ainvoke(prompt, tenant_id)

                    if response and hasattr(response, 'content'):
                        content = response.content.strip()
                        questions = [q.strip() for q in content.split('\n') if q.strip()]
                        follow_ups = [q for q in questions if q and not q.startswith(('1.', '2.', '3.', '-', '*'))][:3]
                        if follow_ups:
                            return follow_ups

                except Exception as e:
                    logger.warning(f"LLM-based follow-up generation failed: {e}")

            return []

        except Exception as e:
            logger.warning(f"Follow-up questions generation failed: {e}")
            return []

    def _generate_flow_action(self, agent_responses: List[Dict], conflict_resolution: Dict, state: Dict = None, semantic_routing: Dict = None, user_context: Dict = None) -> List[Dict[str, Any]]:
        """Generate flow action tracking based on actual workflow execution"""
        try:
            actions = []
            order = 1

            now = self._get_tenant_current_time(user_context)

            if semantic_routing:
                actions.append({
                    "order": order,
                    "node_id": "SemanticReflection",
                    "type": "analysis",
                    "status": "completed",
                    "started_at": now,
                    "ended_at": now,
                    "details": {
                        "complexity": semantic_routing.get("complexity", "unknown"),
                        "is_chitchat": semantic_routing.get("is_chitchat", False),
                        "routing_decision": semantic_routing.get("routing_decision", "unknown")
                    }
                })
                order += 1

            # 2. Agent Executions
            if agent_responses:
                for i, response in enumerate(agent_responses):
                    agent_name = response.get("agent_name", f"Agent_{i}")
                    tool_used = response.get("tool_used", "unknown")
                    execution_time = response.get("execution_time", 0.0)
                    status = "completed" if response.get("status") == "completed" else "failed"

                    actions.append({
                        "order": order,
                        "node_id": f"ExecutePlanning_{agent_name}",
                        "type": "agent_execution",
                        "agent": agent_name,
                        "tool": tool_used,
                        "status": status,
                        "started_at": now,
                        "ended_at": now,
                        "execution_time": execution_time,
                        "details": {
                            "content_length": len(response.get("content", "")),
                            "confidence": response.get("confidence", 0.0),
                            "sources_count": len(response.get("sources", []))
                        }
                    })
                    order += 1

            # 3. Conflict Resolution (if multiple agents)
            if len(agent_responses) > 1 and conflict_resolution:
                actions.append({
                    "order": order,
                    "node_id": "ConflictResolution",
                    "type": "conflict_resolution",
                    "status": "completed",
                    "started_at": now,
                    "ended_at": now,
                    "details": {
                        "resolution_method": conflict_resolution.get("resolution_method", "unknown"),
                        "conflicts_resolved": len(agent_responses),
                        "final_answer_length": len(conflict_resolution.get("final_answer", ""))
                    }
                })
                order += 1

            detected_language = "unknown"
            if semantic_routing:
                detected_language = semantic_routing.get("detected_language", "unknown")
            elif state and "user_context" in state:
                user_context = state.get("user_context", {})
                if user_context and "detected_language" in user_context:
                    detected_language = user_context.get("detected_language", "unknown")

            actions.append({
                "order": order,
                "node_id": "FinalResponse",
                "type": "response_formatting",
                "status": "completed",
                "started_at": now,
                "ended_at": now,
                "details": {
                    "response_type": self._determine_response_type(semantic_routing, agent_responses, None),
                    "language_detected": detected_language,
                    "sources_count": len(self._extract_all_sources(agent_responses))
                }
            })

            return actions

        except Exception as e:
            logger.warning(f"Flow action generation failed: {e}")
            return [{
                "order": 1,
                "node_id": "WorkflowExecution",
                "type": "workflow",
                "status": "completed",
                "started_at": self._get_tenant_current_time(user_context),
                "ended_at": self._get_tenant_current_time(user_context),
                "details": {
                    "error": str(e),
                    "fallback": True
                }
            }]

    def _generate_execution_metadata(
        self,
        agent_responses: List[Dict],
        semantic_routing: Dict,
        detected_language: str,
        user_context: Dict = None,
        state: Dict = None
    ) -> Dict[str, Any]:
        """Generate execution metadata per spec"""
        try:
            total_duration_ms = 0

            if hasattr(self, '_start_time') and self._start_time:
                import time
                current_time = time.time()
                total_duration_ms = int((current_time - self._start_time) * 1000)
                
            if total_duration_ms == 0 and agent_responses:
                for response in agent_responses:
                    execution_time = response.get("execution_time", 0.0)
                    total_duration_ms += int(execution_time * 1000)

            if total_duration_ms == 0 and agent_responses:
                total_duration_ms = len(agent_responses) * 2000  

            accessible_departments = []
            department_permission_filtering = False

            if user_context:
                user_departments = user_context.get("departments", [])
                user_department_ids = user_context.get("department_ids", [])
                user_role = user_context.get("role", "")

                if user_departments:
                    accessible_departments = [dept.get("name", dept.get("department_name", "unknown"))
                                            for dept in user_departments]
                elif user_department_ids:
                    accessible_departments = user_department_ids

                if user_role and user_role.lower() in ["department_admin", "user"]:
                    department_permission_filtering = True
                elif user_departments and len(user_departments) > 0:
                    department_permission_filtering = True

            metadata = {
                "total_duration_ms": total_duration_ms,
                "agents_invoked": [r.get("agent_name", "unknown") for r in agent_responses],
                "tools_executed": list(set(r.get("tool_used", "unknown") for r in agent_responses)),
                "total_queries": len(agent_responses) if agent_responses else 0,
                "conflict_resolution_applied": len(agent_responses) > 1,
                "department_permission_filtering": department_permission_filtering,
                "accessible_departments": accessible_departments,
                "detected_language": detected_language,
                "response_type": self._determine_response_type(semantic_routing, agent_responses, None)
            }

            return metadata

        except Exception as e:
            logger.warning(f"Execution metadata generation failed: {e}")
            accessible_departments = []
            department_permission_filtering = False

            if user_context:
                user_departments = user_context.get("departments", [])
                user_department_ids = user_context.get("department_ids", [])
                user_role = user_context.get("role", "")

                if user_departments:
                    accessible_departments = [dept.get("name", dept.get("department_name", "unknown"))
                                            for dept in user_departments]
                elif user_department_ids:
                    accessible_departments = user_department_ids

                if user_role and user_role.lower() in ["department_admin", "user"]:
                    department_permission_filtering = True
                elif user_departments and len(user_departments) > 0:
                    department_permission_filtering = True

            error_duration_ms = 0
            if hasattr(self, '_start_time') and self._start_time:
                import time
                error_duration_ms = int((time.time() - self._start_time) * 1000)

            return {
                "total_duration_ms": error_duration_ms,
                "agents_invoked": [],
                "tools_executed": [],
                "total_queries": 0,
                "conflict_resolution_applied": False,
                "department_permission_filtering": department_permission_filtering,
                "accessible_departments": accessible_departments,
                "detected_language": detected_language,
                "response_type": "error"
            }


    def _calculate_progress_percentage(self, step: str) -> int:
        """
        Calculate progress percentage for final response steps
        """
        progress_map = {
            "assembling_response": 95,
            "completed": 100,
            "error": 100
        }
        return progress_map.get(step, 100)