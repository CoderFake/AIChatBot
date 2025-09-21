# Ép kiểu JSON đầu ra cho Chat Models LangChain 0.2+

## Các phương pháp chính

### 1. Sử dụng `with_structured_output()` (Khuyến nghị)

Đây là phương pháp tốt nhất cho các model hỗ trợ native structured output như OpenAI, Anthropic, Google.

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List

class ResponseSchema(BaseModel):
    """Schema for structured response"""
    answer: str = Field(description="Main answer to the question")
    confidence: float = Field(description="Confidence score from 0 to 1")
    sources: List[str] = Field(description="List of information sources")

# ChatOpenAI with structured output
openai_llm = ChatOpenAI(model="gpt-4o", temperature=0)
openai_structured = openai_llm.with_structured_output(ResponseSchema)

# ChatAnthropic with structured output
anthropic_llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0)
anthropic_structured = anthropic_llm.with_structured_output(ResponseSchema)

# ChatGoogleGenerativeAI with structured output
google_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
google_structured = google_llm.with_structured_output(ResponseSchema)

# Tạo messages
messages = [
    SystemMessage(content="You are a helpful assistant that provides structured responses."),
    HumanMessage(content="What is the capital of Vietnam?")
]

# Invoke với structured output
result = openai_structured.invoke(messages)
print(result)  # Trả về ResponseSchema object
```

### 2. Sử dụng JSON Mode với OpenAI

```python
from langchain_openai import ChatOpenAI

# JSON mode cho OpenAI
json_llm = ChatOpenAI(model="gpt-4o")
json_structured = json_llm.bind(response_format={"type": "json_object"})

messages = [
    SystemMessage(content="You are a helpful assistant. Always respond with valid JSON."),
    HumanMessage(content='Return a JSON object with key "random_ints" and a value of 5 random integers.')
]

result = json_structured.invoke(messages)
print(result.content)  # JSON string
```

### 3. Sử dụng `JsonOutputParser`

```python
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

class Joke(BaseModel):
    """Schema for joke response"""
    setup: str = Field(description="Question to set up a joke")
    punchline: str = Field(description="Answer to resolve the joke")

# Setup parser
parser = JsonOutputParser(pydantic_object=Joke)

# Tạo prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer the user query.\n{format_instructions}"),
    ("human", "{query}")
])

# Chain với parser
chain = prompt | openai_llm | parser

# Invoke
result = chain.invoke({
    "query": "Tell me a joke about cats",
    "format_instructions": parser.get_format_instructions()
})
print(result)  # Dict object
```

### 4. ChatOllama với JSON format

```python
from langchain_community.chat_models import ChatOllama

# ChatOllama với JSON format
ollama_llm = ChatOllama(model="llama3", format="json")

messages = [
    SystemMessage(content="Respond only in JSON format."),
    HumanMessage(content='Return weather data with keys: location, temperature, condition')
]

result = ollama_llm.invoke(messages)
print(result.content)  # JSON string
```

## Ví dụ chi tiết với TypedDict

```python
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage

class WeatherResponse(TypedDict):
    """Weather response schema"""
    location: str
    temperature: int
    condition: str
    humidity: int

# Sử dụng với ChatOpenAI
weather_llm = ChatOpenAI(model="gpt-4o").with_structured_output(WeatherResponse)

messages = [
    SystemMessage(content="You are a weather assistant. Provide weather information in the specified format."),
    HumanMessage(content="What's the weather like in Hanoi today?")
]

weather_data = weather_llm.invoke(messages)
print(weather_data)  # Dict với keys: location, temperature, condition, humidity
```

## Xử lý lỗi và validation

```python
from langchain_core.output_parsers import OutputParserException
import json

def safe_json_invoke(llm, messages, parser=None):
    """Safely invoke LLM with JSON parsing"""
    try:
        if parser:
            result = llm.invoke(messages)
            return parser.parse(result.content)
        else:
            result = llm.invoke(messages)
            return json.loads(result.content)
    except (OutputParserException, json.JSONDecodeError) as e:
        print(f"JSON parsing error: {e}")
        return None
    except Exception as e:
        print(f"General error: {e}")
        return None

# Sử dụng
parser = JsonOutputParser(pydantic_object=Joke)
result = safe_json_invoke(openai_llm, messages, parser)
```

## Streaming với JSON Output

```python
from langchain_core.output_parsers import JsonOutputParser

# Chỉ hoạt động với dict schema (TypedDict hoặc JSON Schema)
parser = JsonOutputParser()

chain = prompt | openai_llm | parser

# Stream partial JSON objects
for chunk in chain.stream({"query": "Tell me about AI"}):
    print(chunk)  # Các chunk JSON partial
```

## Lưu ý quan trọng

1. **Model Support**: 
   - `with_structured_output()` hoạt động tốt nhất với OpenAI, Anthropic, Google
   - ChatOllama cần sử dụng `format="json"` parameter
   - Một số model có thể cần prompt engineering để tạo JSON hợp lệ

2. **Error Handling**:
   - Luôn xử lý lỗi JSON parsing
   - Sử dụng try-catch cho OutputParserException

3. **Performance**:
   - `with_structured_output()` nhanh hơn JsonOutputParser
   - JSON mode của OpenAI đáng tin cậy hơn prompting

4. **Validation**:
   - Pydantic models cung cấp type safety và validation
   - TypedDict nhẹ hơn nhưng ít validation hơn