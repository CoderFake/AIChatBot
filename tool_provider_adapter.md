# Hướng dẫn bind_tools trong LangChain

## Giới thiệu

`bind_tools()` là phương thức chuẩn trong LangChain để liên kết tools (công cụ) với các chat models. Phương thức này cho phép models có thể gọi các functions/tools khi cần thiết dựa trên input của người dùng.

## Cú pháp cơ bản

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama

# Basic syntax
llm_with_tools = llm.bind_tools(
    tools=[tool1, tool2, ...],
    tool_choice=None,           # Tùy chọn: force sử dụng tool cụ thể
    parallel_tool_calls=True,   # Tùy chọn: cho phép gọi nhiều tools cùng lúc
    strict=None,               # Tùy chọn: OpenAI strict mode
    **kwargs
)
```

## 1. Tạo Tools

### Sử dụng @tool decorator (Khuyến nghị)

```python
from langchain_core.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers together.
    
    Args:
        a: First integer
        b: Second integer
    
    Returns:
        Product of a and b
    """
    return a * b

@tool
def add(a: int, b: int) -> int:
    """Add two integers together.
    
    Args:
        a: First integer
        b: Second integer
    
    Returns:
        Sum of a and b
    """
    return a + b
```

### Sử dụng Pydantic BaseModel

```python
from pydantic import BaseModel, Field

class GetWeather(BaseModel):
    """Get the current weather in a given location"""
    location: str = Field(..., description="The city and state, e.g. San Francisco, CA")
    unit: str = Field(default="celsius", description="Temperature unit")

class CalculateArea(BaseModel):
    """Calculate area of a rectangle"""
    width: float = Field(..., description="Width of rectangle")
    height: float = Field(..., description="Height of rectangle")
```

### Sử dụng Python functions

```python
def search_database(query: str) -> str:
    """Search database for information
    
    Args:
        query: Search query string
        
    Returns:
        Search results
    """
    # Implementation here
    return f"Results for: {query}"
```

## 2. Bind Tools với các Chat Models

### ChatOpenAI

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [multiply, add, GetWeather]

# Basic binding
llm_with_tools = llm.bind_tools(tools)

# Với các tùy chọn
llm_with_tools = llm.bind_tools(
    tools,
    parallel_tool_calls=True,
    strict=True  # OpenAI strict mode
)

# Invoke
messages = [HumanMessage(content="What is 23 times 7?")]
result = llm_with_tools.invoke(messages)
print(result.tool_calls)
```

### ChatAnthropic

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)
llm_with_tools = llm.bind_tools([GetWeather, multiply])

messages = [HumanMessage(content="What's the weather in San Francisco?")]
result = llm_with_tools.invoke(messages)
print(result.tool_calls)
```

### ChatGoogleGenerativeAI

```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
llm_with_tools = llm.bind_tools([add, multiply])

messages = [HumanMessage(content="Calculate 15 + 25 and then multiply by 3")]
result = llm_with_tools.invoke(messages)
print(result.tool_calls)
```

### ChatOllama

```python
from langchain_community.chat_models import ChatOllama

llm = ChatOllama(model="llama3")
llm_with_tools = llm.bind_tools([multiply, add])

messages = [HumanMessage(content="What is 5 * 8?")]
result = llm_with_tools.invoke(messages)
print(result.tool_calls)
```

## 3. Tool Choice - Kiểm soát việc chọn tool

### Auto (mặc định)
```python
# Model tự quyết định tool nào sử dụng hoặc không sử dụng tool nào
llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
```

### Force sử dụng tool cụ thể
```python
# Force sử dụng tool "multiply"
llm_with_tools = llm.bind_tools(
    tools, 
    tool_choice="multiply"  # Tên của tool
)

# Hoặc sử dụng dict format (OpenAI)
llm_with_tools = llm.bind_tools(
    tools,
    tool_choice={"type": "function", "function": {"name": "multiply"}}
)
```

### Require bất kỳ tool nào
```python
# Bắt buộc phải sử dụng ít nhất 1 tool
llm_with_tools = llm.bind_tools(tools, tool_choice="required")
```

### Không sử dụng tool
```python
# Không cho phép sử dụng tool
llm_with_tools = llm.bind_tools(tools, tool_choice="none")
```

## 4. Parallel Tool Calls

```python
# Cho phép gọi nhiều tools cùng lúc (mặc định: True)
llm_with_tools = llm.bind_tools(
    tools, 
    parallel_tool_calls=True
)

# Tắt parallel tool calls - chỉ gọi 1 tool tại 1 thời điểm
llm_with_tools = llm.bind_tools(
    tools, 
    parallel_tool_calls=False
)

# Test parallel calling
result = llm_with_tools.invoke("Calculate 5*3 and 10+7")
print(f"Number of tool calls: {len(result.tool_calls)}")
```

## 5. Xử lý Tool Calls

```python
def handle_tool_calls(ai_message):
    """Handle tool calls from AI message"""
    if not ai_message.tool_calls:
        return ai_message.content
    
    results = []
    tool_map = {tool.name: tool for tool in tools}
    
    for tool_call in ai_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        if tool_name in tool_map:
            try:
                result = tool_map[tool_name].invoke(tool_args)
                results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "error": str(e)
                })
    
    return results

# Usage
result = llm_with_tools.invoke("What is 15 * 23?")
tool_results = handle_tool_calls(result)
print(tool_results)
```

## 6. Chain với Tool Calling

```python
from langchain_core.runnables import RunnableLambda

def call_tools(ai_message):
    """Execute tool calls and return results"""
    tool_map = {tool.name: tool for tool in tools}
    tool_calls = ai_message.tool_calls.copy()
    
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        if tool_name in tool_map:
            tool_call["output"] = tool_map[tool_name].invoke(tool_call["args"])
    
    return tool_calls

# Create chain
chain = llm_with_tools | RunnableLambda(call_tools)

result = chain.invoke("Calculate 12 * 8 and then add 15")
print(result)
```

## 7. Ví dụ với Custom Tool và Complex Schema

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    """Complex search query with filters"""
    query: str = Field(..., description="Main search query")
    filters: Optional[List[str]] = Field(default=None, description="Search filters")
    limit: int = Field(default=10, description="Maximum results")
    sort_by: str = Field(default="relevance", description="Sort criteria")

@tool
def complex_search(search_params: SearchQuery) -> str:
    """Perform complex search with filters
    
    Args:
        search_params: Search parameters including query, filters, limit, sort
        
    Returns:
        Search results as string
    """
    return f"Search results for '{search_params.query}' with filters {search_params.filters}"

# Bind complex tool
llm_with_complex_tools = llm.bind_tools([complex_search])

result = llm_with_complex_tools.invoke(
    "Search for Python tutorials with filters: beginner, free, and limit to 5 results"
)
print(result.tool_calls)
```

## 8. Tool với Dict Schema (Raw Format)

```python
# Define tool using raw dict format
weather_tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City and state, e.g. San Francisco, CA"
                },
                "unit": {
                    "type": "string", 
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit"
                }
            },
            "required": ["location"]
        }
    }
}

llm_with_raw_tools = llm.bind_tools([weather_tool])
```

## 9. Error Handling và Best Practices

```python
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

def safe_tool_calling():
    try:
        # Bind tools
        llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
        
        # Invoke
        result = llm_with_tools.invoke([
            HumanMessage(content="Calculate 10 * 5 and then add 25")
        ])
        
        # Handle tool calls
        if result.tool_calls:
            tool_results = []
            for tool_call in result.tool_calls:
                try:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    # Execute tool
                    if tool_name == "multiply":
                        output = multiply.invoke(tool_args)
                    elif tool_name == "add":
                        output = add.invoke(tool_args)
                    else:
                        output = f"Unknown tool: {tool_name}"
                    
                    tool_results.append(ToolMessage(
                        content=str(output),
                        tool_call_id=tool_call["id"]
                    ))
                    
                except Exception as e:
                    tool_results.append(ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_call.get("id", "unknown")
                    ))
            
            return tool_results
        else:
            return [result]
            
    except Exception as e:
        return [f"Error in tool calling: {str(e)}"]

# Usage
results = safe_tool_calling()
for result in results:
    print(result)
```

## 10. Lưu ý quan trọng

### Model Support
- **ChatOpenAI**: Hỗ trợ đầy đủ tất cả features (parallel_tool_calls, tool_choice, strict mode)
- **ChatAnthropic**: Hỗ trợ tool calling nhưng không có strict mode
- **ChatGoogleGenerativeAI**: Hỗ trợ function calling qua Gemini API
- **ChatOllama**: Hỗ trợ tool calling với một số models

### Best Practices
1. **Tool descriptions**: Viết descriptions rõ ràng và chi tiết
2. **Parameter validation**: Sử dụng Pydantic cho type safety
3. **Error handling**: Luôn xử lý lỗi khi execute tools
4. **Tool naming**: Sử dụng tên tools có nghĩa và dễ hiểu
5. **Scope limitation**: Tạo tools đơn giản, tập trung vào 1 nhiệm vụ cụ thể

### Troubleshooting
- Nếu model không gọi tools: Kiểm tra tool descriptions và examples
- Nếu tool_calls rỗng: Model có thể quyết định không cần tools cho query đó
- Nếu lỗi parsing: Kiểm tra tool schema và parameter types