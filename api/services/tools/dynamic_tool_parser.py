"""
Dynamic Tool Parameter Parser
Implements best practices for scalable tool parameter parsing
"""
import json
import re
from typing import Dict, Any
from langchain_core.tools import BaseTool
from utils.logging import get_logger

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
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """
        Parse natural language query to tool-specific parameters using tool's schema

        Args:
            tool_name: Name of the tool
            query: Natural language query
            agent_provider_name: Name of LLM provider for parsing
            tenant_id: Tenant identifier for API access

        Returns:
            Dict of parsed parameters

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

        prompt = self._build_parsing_prompt(tool_name, tool_instance, query, schema_info)

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
                result = json.loads(json_match.group())
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
        schema_info: Dict[str, Any]
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
            f"Required parameters: {schema_info['required_params']}",
            f"Optional parameters: {schema_info['optional_params']}",
            "",
            "Parameter details:"
        ]
        
        for param, detail in schema_info['param_details'].items():
            prompt_parts.append(f"- {param}: {detail}")
        
        prompt_parts.extend([
            "",
            self._get_dynamic_tool_instructions(tool_name, tool_instance),
            "",
            "Return ONLY a JSON object with the extracted parameters.",
            "Use appropriate default values for missing optional parameters.",
            "Example format: {\"param1\": \"value1\", \"param2\": \"value2\"}"
        ])
        
        return "\n".join(prompt_parts)
    
    def _get_dynamic_tool_instructions(self, tool_name: str, tool_instance: BaseTool) -> str:
        """Get dynamic instructions based on tool attributes and category"""
        instructions = []
        
        # Check if tool has specific parsing hints
        if hasattr(tool_instance, 'parsing_hints'):
            instructions.append(f"Parsing hints: {tool_instance.parsing_hints}")
        
        # Add category-specific instructions
        category = getattr(tool_instance, 'category', 'general')
        
        category_instructions = {
            'datetime': [
                "For time queries ('mấy giờ', 'what time', 'bây giờ'): use 'current_time' operation",
                "For date queries ('ngày nào', 'today', 'hôm nay'): use 'current_date' operation", 
                "For general time questions: use 'current_datetime' operation",
                "Default timezone: 'Asia/Ho_Chi_Minh'",
                "Default format: '%H:%M:%S %d/%m/%Y'",
                "",
                "RELATIVE TIME EXPRESSIONS (Vietnamese/English):",
                "- 'ngày mai', 'mai', 'tomorrow' → operation: 'add_time', amount: 1, unit: 'days'",
                "- 'ngày kia', 'kia' (day after tomorrow) → operation: 'add_time', amount: 2, unit: 'days'",
                "- 'hôm qua', 'qua', 'yesterday' → operation: 'subtract_time', amount: 1, unit: 'days'",
                "- 'hôm kia' (day before yesterday) → operation: 'subtract_time', amount: 2, unit: 'days'",
                "- 'tuần sau', 'tuần tới', 'next week' → operation: 'add_time', amount: 1, unit: 'weeks'",
                "- 'tuần trước', 'tuần rồi', 'last week' → operation: 'subtract_time', amount: 1, unit: 'weeks'",
                "- 'tháng sau', 'tháng tới', 'next month' → operation: 'add_time', amount: 1, unit: 'months'",
                "- 'tháng trước', 'tháng rồi', 'last month' → operation: 'subtract_time', amount: 1, unit: 'months'",
                "- 'năm sau', 'năm tới', 'next year' → operation: 'add_time', amount: 1, unit: 'years'",
                "- 'năm trước', 'năm ngoái', 'last year' → operation: 'subtract_time', amount: 1, unit: 'years'",
                "",
                "For relative time expressions, do NOT set datetime_string (let tool use current time automatically).",
                "Context awareness: 'ngày kia thì sao' means 'what about the day after tomorrow' - use add_time with amount=2."
            ],
            'calculation': [
                "Extract mathematical expressions from natural language",
                "Convert word numbers to digits if needed",
                "Handle Vietnamese math terms (cộng=+, trừ=-, nhân=*, chia=/)",
                "Preserve mathematical operators and parentheses"
            ],
            'search': [
                "Extract main search terms and keywords",
                "Identify any filters or constraints mentioned",
                "Consider context and intent of the search"
            ],
            'weather': [
                "Extract location names (cities, countries, regions)",
                "Identify specific weather information requested",
                "Default units: 'metric'",
                "Default forecast_days: 1"
            ],
            'web_search': [
                "Extract search query terms",
                "Identify any specific domains or sites mentioned",
                "Consider search intent and scope"
            ],
            'summary': [
                "Identify the content or text to be summarized",
                "Determine summary length or format requested",
                "Consider any specific focus areas mentioned"
            ]
        }
        
        if category in category_instructions:
            instructions.extend(category_instructions[category])
        else:
            instructions.append("Extract relevant parameters based on the tool's purpose and user intent")
        
        # Add tool-specific instructions if available
        if hasattr(tool_instance, 'get_parsing_instructions'):
            custom_instructions = tool_instance.get_parsing_instructions()
            if custom_instructions:
                instructions.append(f"Tool-specific instructions: {custom_instructions}")
        
        return "Instructions:\n" + "\n".join(f"- {inst}" for inst in instructions)
    
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
    
    def should_parse_parameters(self, tool_name: str) -> bool:
        """
        Determine if a tool needs parameter parsing
        Tools with complex schemas need parsing, simple query-only tools don't
        """
        tool_instance = self.tool_instances.get(tool_name)
        if not tool_instance:
            return False
        
        schema_info = self._extract_tool_schema(tool_instance)
        
        if (schema_info['required_params'] == ['query'] and 
            len(schema_info['optional_params']) == 0):
            return False
        
        if (len(schema_info['required_params']) > 1 or 
            len(schema_info['optional_params']) > 0):
            return True
        
        return False
