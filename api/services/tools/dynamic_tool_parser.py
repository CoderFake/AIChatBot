"""
Dynamic Tool Parameter Parser
Implements best practices for scalable tool parameter parsing
"""
import json
import re
from typing import Dict, Any, Optional
from langchain_core.tools import BaseTool
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager

logger = get_logger(__name__)


class DynamicToolParser:
    """
    Dynamic tool parameter parser that uses tool's own schema
    Follows DRY principle and scales with any new tools
    """
    
    def __init__(self, tool_instances: Dict[str, BaseTool]):
        self.tool_instances = tool_instances
        
    async def parse_tool_parameters(
        self,
        tool_name: str,
        query: str,
        agent_provider_name: str = None,
        tenant_id: str = None,
        user_context: Optional[Dict[str, Any]] = None,
        original_params: Optional[Dict[str, Any]] = None,
        retry_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Parse natural language query to tool-specific parameters using tool's schema

        Args:
            tool_name: Name of the tool
            query: Natural language query
            agent_provider_name: Name of LLM provider for parsing
            tenant_id: Tenant identifier for API access
            user_context: User context for additional parameters
            original_params: Original parameters to preserve (e.g., user_id, department)

        Returns:
            Dict of parsed parameters merged with original context

        Raises:
            ValueError: If parsing fails or tool not found
        """
        if not agent_provider_name:
            raise ValueError(f"Agent provider name is required for parsing {tool_name} tool parameters")

        from services.orchestrator.orchestrator import Orchestrator
        orchestrator = Orchestrator()
        agent_provider = await orchestrator.llm(agent_provider_name)

        tool_instance = self.tool_instances.get(tool_name)
        if not tool_instance:
            raise ValueError(f"Tool {tool_name} not found in registry")

        schema_info = self._extract_tool_schema(tool_instance)

        tenant_timezone = None
        tenant_current_datetime = None

        if user_context:
            tenant_timezone = user_context.get("timezone")
            tenant_current_datetime = user_context.get("tenant_current_datetime")

        if tenant_timezone is None and tenant_id:
            try:
                tenant_timezone = await DateTimeManager.get_tenant_timezone(tenant_id)
            except Exception:
                tenant_timezone = None

        if tenant_timezone is None:
            tenant_timezone = getattr(DateTimeManager.system_tz, "key", str(DateTimeManager.system_tz))

        if tenant_current_datetime is None:
            try:
                tenant_current_datetime = DateTimeManager.tenant_now(tenant_timezone).isoformat()
            except Exception:
                tenant_current_datetime = DateTimeManager.system_now().isoformat()

        prompt = self._build_parsing_prompt(
            tool_name,
            tool_instance,
            query,
            schema_info,
            tenant_timezone,
            tenant_current_datetime,
            retry_context,
        )

        try:
            response = await agent_provider.ainvoke(prompt, tenant_id)
            
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                parsed_result = json.loads(json_match.group())
                
                # Merge with original parameters to preserve context
                if original_params:
                    # Start with original params and update with parsed params
                    result = original_params.copy()
                    result.update(parsed_result)
                    logger.debug(f"Merged parsed params with original: {list(parsed_result.keys())} + {list(original_params.keys())}")
                else:
                    result = parsed_result
                
                # Enhanced validation for retry scenarios
                if retry_context:
                    self._validate_retry_parameters(tool_name, result, schema_info, retry_context)
                else:
                    self._validate_tool_params(tool_name, result, schema_info)
                
                return result
            else:
                raise ValueError("No JSON found in LLM response")
                
        except Exception as e:
            logger.error(f"Failed to parse {tool_name} query with LLM: {e}")
            raise ValueError(f"Failed to parse {tool_name} tool parameters from query: '{query}'. Error: {str(e)}")
    
    def _extract_tool_schema(self, tool_instance: BaseTool) -> Dict[str, Any]:
        """Extract schema information from tool's args_schema (Pydantic model)"""
        try:
            if not hasattr(tool_instance, 'args_schema') or not tool_instance.args_schema:
                return {
                    "required_params": ["query"],
                    "optional_params": [],
                    "param_details": {"query": "User query string"}
                }
            
            schema = tool_instance.args_schema.model_json_schema()
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            required_params = required
            optional_params = [name for name in properties.keys() if name not in required]
            
            param_details = {}
            for name, prop in properties.items():
                description = prop.get('description', 'No description')
                param_type = prop.get('type', 'string')
                default = prop.get('default', None)
                enum_values = prop.get('enum', None)
                
                detail = f"{description} (type: {param_type}"
                if enum_values:
                    detail += f", options: {enum_values}"
                if default is not None:
                    detail += f", default: {default}"
                detail += ")"
                
                param_details[name] = detail
            
            return {
                "required_params": required_params,
                "optional_params": optional_params,
                "param_details": param_details,
                "full_schema": schema
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract schema for tool {tool_instance.name}: {e}")
            return {
                "required_params": ["query"],
                "optional_params": [],
                "param_details": {"query": "User query string"}
            }
    
    def _build_parsing_prompt(
        self,
        tool_name: str,
        tool_instance: BaseTool,
        query: str,
        schema_info: Dict[str, Any],
        tenant_timezone: str,
        tenant_current_datetime: str,
        retry_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build dynamic parsing prompt based on tool schema"""
        
        prompt_parts = [
            f"Analyze this user query and extract the appropriate parameters for the {tool_name} tool.",
            "",
            f"User query: \"{query}\"",
            "",
            f"Tool: {tool_name}",
            f"Description: {tool_instance.description}",
            "",
        ]
        
        # Add retry context if this is a retry attempt
        if retry_context:
            prompt_parts.extend([
                "RETRY ATTEMPT - Previous execution failed:",
                f"Previous Error: {retry_context.get('error_message', 'Unknown error')}",
                f"Failed Parameters: {retry_context.get('failed_params', {})}",
                "",
                "CRITICAL INSTRUCTIONS FOR RETRY:",
                "1. Learn from the previous error and adjust parameter extraction",
                "2. Ensure ALL required parameters are properly extracted",
                "3. Validate parameter types and formats based on the error",
                "4. If the error mentioned missing parameters, focus on extracting them",
                "5. If the error mentioned invalid values, correct the format/type",
                "",
            ])
        
        schema_info = self._extract_tool_schema(tool_instance)
        
        if (len(schema_info['required_params']) <= 1 and 
            schema_info['required_params'] == ['query'] and 
            len(schema_info['optional_params']) == 0):
            prompt_parts.extend([
                "Extract the main query or search terms from the user input.",
                "Focus on the core intent and relevant keywords."
            ])
        else:
            prompt_parts.extend([
                f"Required parameters: {schema_info['required_params']}",
                f"Optional parameters: {schema_info['optional_params']}",
                "",
                "Parameter details:"
            ])
            
            for param, detail in schema_info['param_details'].items():
                prompt_parts.append(f"- {param}: {detail}")
        
        prompt_parts.append("")
        prompt_parts.append(self._get_dynamic_tool_instructions(tool_name, tool_instance))

        if tool_name == "datetime":
            prompt_parts.extend([
                "",
                "Tenant context:",
                f"- Tenant timezone: {tenant_timezone}",
                f"- Current tenant datetime: {tenant_current_datetime}",
                "- Always interpret date/time queries using the tenant's local timezone instead of UTC.",
            ])

        prompt_parts.extend([
            "",
            "CRITICAL: Return ONLY a JSON object with the exact parameters required by the tool.",
            "Ensure parameter names match the tool schema exactly.",
            "Use appropriate data types for each parameter.",
            "Example format: {\"param1\": \"value1\", \"param2\": \"value2\"}"
        ])
        
        # Add retry-specific validation if this is a retry
        if retry_context:
            prompt_parts.extend([
                "",
                "RETRY VALIDATION:",
                "- Double-check all required parameters are included",
                "- Verify parameter types match schema requirements",
                "- Ensure parameter values are in correct format",
                "- Learn from the previous error to avoid repeating the same mistake"
            ])
        
        return "\n".join(prompt_parts)
    
    def _get_dynamic_tool_instructions(self, tool_name: str, tool_instance: BaseTool) -> str:
        """Get dynamic instructions based on tool attributes and category"""
        instructions = []
        
        # Get category-specific instructions dynamically
        category = getattr(tool_instance, 'category', 'general')
        
        # Add dynamic instructions based on tool attributes
        if hasattr(tool_instance, 'parsing_hints'):
            instructions.append(f"Parsing hints: {tool_instance.parsing_hints}")
        
        if hasattr(tool_instance, 'get_parsing_instructions'):
            custom_instructions = tool_instance.get_parsing_instructions()
            if custom_instructions:
                instructions.extend(custom_instructions if isinstance(custom_instructions, list) else [custom_instructions])
        
        # Fallback to generic instructions if no custom instructions
        if not instructions or len(instructions) == 0:
            instructions.append(f"Analyze the user query and extract parameters suitable for {category} category operations")
            instructions.append("Focus on the tool's defined schema and parameter requirements")
            instructions.append("Extract only the information that matches the tool's expected input format")
        
        return "Instructions:\n" + "\n".join(f"- {inst}" for inst in instructions)
    
    def _validate_retry_parameters(
        self,
        tool_name: str,
        params: Dict[str, Any],
        schema_info: Dict[str, Any],
        retry_context: Dict[str, Any]
    ):
        """Enhanced validation for retry scenarios with error context"""
        try:
            # First, do standard validation
            self._validate_tool_params(tool_name, params, schema_info)
            
            # Additional retry-specific checks
            previous_error = retry_context.get('error_message', '')
            failed_params = retry_context.get('failed_params', {})
            
            # Check if previously missing parameters are now present
            if 'missing' in previous_error.lower() or 'required' in previous_error.lower():
                required_params = schema_info.get('required_params', [])
                still_missing = [param for param in required_params if param not in params]
                if still_missing:
                    raise ValueError(
                        f"Retry failed: Still missing required parameters for {tool_name}: {still_missing}. "
                        f"Previous error: {previous_error}"
                    )
            
            # Check if parameter types are corrected based on previous error
            if 'type' in previous_error.lower() or 'format' in previous_error.lower():
                full_schema = schema_info.get('full_schema', {})
                properties = full_schema.get('properties', {})
                
                for param_name, param_value in params.items():
                    if param_name in properties and param_name in failed_params:
                        expected_type = properties[param_name].get('type')
                        if expected_type == 'array' and not isinstance(param_value, list):
                            raise ValueError(
                                f"Retry validation failed: Parameter '{param_name}' should be a list, got {type(param_value)}. "
                                f"Previous error: {previous_error}"
                            )
                        elif expected_type == 'string' and not isinstance(param_value, str):
                            raise ValueError(
                                f"Retry validation failed: Parameter '{param_name}' should be a string, got {type(param_value)}. "
                                f"Previous error: {previous_error}"
                            )
            
            logger.info(f"Retry validation passed for {tool_name} - parameters corrected from previous error")
            
        except Exception as e:
            logger.error(f"Retry parameter validation failed for {tool_name}: {e}")
            raise
    
    def _validate_tool_params(
        self, 
        tool_name: str, 
        params: Dict[str, Any], 
        schema_info: Dict[str, Any]
    ):
        """Validate parsed parameters against tool schema"""
        required_params = schema_info.get('required_params', [])
        
        # Check required parameters
        missing_params = [param for param in required_params if param not in params]
        if missing_params:
            raise ValueError(f"Missing required parameters for {tool_name}: {missing_params}")
        
        # Validate parameter types if schema available
        full_schema = schema_info.get('full_schema', {})
        properties = full_schema.get('properties', {})
        
        for param_name, param_value in params.items():
            if param_name in properties:
                expected_type = properties[param_name].get('type')
                enum_values = properties[param_name].get('enum')
                
                # Validate enum values
                if enum_values and param_value not in enum_values:
                    logger.warning(f"Parameter {param_name} value '{param_value}' not in expected options: {enum_values}")
        
        logger.debug(f"Tool {tool_name} parameters validated successfully")
