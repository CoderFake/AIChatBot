# AIChatBot - Multi-Agent RAG System

> 🚀 **Enterprise Multi-Tenant Agentic RAG System** with LangGraph Workflow, Vector Search and Real-time Chat

AIChatBot is an advanced multi-agent RAG (Retrieval-Augmented Generation) system designed for enterprise environments with multi-tenant capabilities, parallel processing, and multiple AI model integrations.

## 🌟 Key Features

### 🤖 Multi-Agent Architecture
- **Orchestrator Agent**: Coordinates and analyzes query complexity
- **Semantic Router**: Deep analysis and intelligent routing
- **Specialized Agents**: HR, IT, General,.. with specialized tools
- **Conflict Resolution**: Resolves conflicts and prioritizes results

### 🔄 LangGraph Workflow
- **Parallel Execution**: Concurrent agent execution
- **Reflection & Routing**: Semantic routing with feedback capabilities
- **Stream Processing**: Real-time progress tracking
- **Error Handling**: Comprehensive error handling and fallback

### 🏢 Multi-Tenant Support
- **Tenant Isolation**: Complete data isolation
- **Permission System**: Granular permissions (public/private/internal)
- **Department-based Access**: Department-level access control
- **Dynamic Configuration**: Flexible tenant-specific configuration

### 🔍 Advanced RAG
- **Dual Vector Stores**: Public/Private Milvus instances
- **BGE-M3 Embeddings**: Multilingual semantic understanding
- **MMR Search**: Maximum Marginal Relevance
- **Document Processing**: Docling + LangChain fallback

### 🎯 LLM Integration
- **Multi-Provider**: Gemini, Anthropic, Mistral, Ollama
- **Model Switching**: Dynamic model selection
- **Streaming Response**: Real-time response generation
- **Caching**: Redis-based intelligent caching

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Next.js UI    │    │   FastAPI       │    │   PostgreSQL    │
│   (Frontend)    │◄──►│   (Backend)     │◄──►│   (Database)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │           LangGraph Workflow            │
        │  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
        │  │Orchestr.│  │Semantic │  │ Agents  │ │
        │  │         │  │ Router  │  │ (HR/IT) │ │
        │  └─────────┘  └─────────┘  └─────────┘ │
        └─────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     ▼                     │
   ┌─────────┐         ┌─────────────┐         ┌─────────┐
   │ Milvus  │         │    Redis    │         │  MinIO  │
   │(Vector) │         │  (Cache)    │         │(Storage)│
   └─────────┘         └─────────────┘         └─────────┘
```

### Core Components

1. **API Layer**: FastAPI với async/await, OpenAPI docs
2. **Workflow Engine**: LangGraph cho multi-agent orchestration
3. **Vector Storage**: Dual Milvus instances (public/private)
4. **Caching**: Redis cho performance optimization
5. **Storage**: MinIO for document management
6. **Monitoring**: Prometheus + Grafana + Loki stack

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- 8GB+ RAM khuyến nghị

### 1. Clone Repository
```bash
git clone https://github.com/CoderFake/AIChatBot.git
cd AIChatBot
```

### 2. Environment Setup
```bash
# Tạo file .env từ template
cp env.example .env

# Chỉnh sửa các biến môi trường cần thiết (REQUIRED)
nano .env

# Tối thiểu cần thiết:
# - SECRET_KEY và JWT_SECRET_KEY
# - Database credentials
# - Ít nhất một LLM API key (Gemini/Anthropic/Mistral)
```

### 3. Start Services
```bash
# Khởi động tất cả services
docker-compose up -d

# Hoặc chỉ khởi động backend
docker-compose up -d postgres redis milvus_public milvus_private minio kafka api

# Kiểm tra trạng thái
docker-compose ps
```

### 4. Initialize Database
```bash
# Chạy migrations
docker-compose exec api python init_db.py
```

### 5. Access Applications
- **API Documentation**: http://localhost:15000/docs
- **Frontend**: http://localhost:3001
- **Grafana**: http://localhost:3000 (admin/admin)
- **MinIO Console**: http://localhost:9001

## ⚙️ Configuration

### Required Environment Variables

```bash
# Security (REQUIRED)
SECRET_KEY=your-super-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Database
POSTGRES_DB=ai_chatbot
POSTGRES_USER=ai_user
POSTGRES_PASSWORD=secure_password

# LLM API Keys (Choose one or more)
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
MISTRAL_API_KEY=your_mistral_api_key

# Email (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
```

### Advanced Configuration

<details>
<summary>🔧 Vector Database Settings</summary>

```bash
# Milvus Configuration
MILVUS_COLLECTION_PREFIX=rag
MILVUS_VECTOR_DIM=1024
MILVUS_INDEX_TYPE=HNSW
MILVUS_METRIC_TYPE=COSINE

# BGE-M3 Embedding
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BATCH_SIZE=12
BGE_M3_MAX_LENGTH=8192
```
</details>

<details>
<summary>🎯 Workflow Settings</summary>

```bash
# LangGraph Workflow
WORKFLOW_MAX_ITERATIONS=10
WORKFLOW_TIMEOUT_SECONDS=300
WORKFLOW_ENABLE_REFLECTION=true
WORKFLOW_ENABLE_SEMANTIC_ROUTING=true

# Orchestrator
ORCHESTRATOR_STRATEGY=llm_orchestrator
ORCHESTRATOR_MAX_AGENTS_PER_QUERY=3
ORCHESTRATOR_CONFIDENCE_THRESHOLD=0.7
```
</details>

## 📚 API Usage

### Authentication
```python
import requests

# Login
response = requests.post("http://localhost:15000/api/v1/auth/login", 
    json={"username": "admin", "password": "password"})
token = response.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}
```

### Chat API
```python
# Send chat message
chat_response = requests.post(
    "http://localhost:15000/api/v1/chat/message",
    headers=headers,
    json={
        "message": "How many core values does the company have?",
        "tenant_id": "your-tenant-id"
    }
)

# Stream response
for line in chat_response.iter_lines():
    if line:
        print(json.loads(line))
```

### Document Upload
```python
# Upload document
files = {"file": open("document.pdf", "rb")}
upload_response = requests.post(
    "http://localhost:15000/api/v1/documents/upload",
    headers=headers,
    files=files,
    data={"scope": "private", "department": "hr"}
)
```

## 🔄 Multi-Agent Flow Example

```json
{
  "query": "Core values and impact of tardiness",
  "workflow_result": {
    "orchestrator_decision": "multi_agent_required",
    "agents_selected": ["general", "hr"],
    "execution_plan": {
      "step_1": "general_agent → rag_tool (core values)",
      "step_2": "hr_agent → rag_tool (tardiness policy)", 
      "step_3": "conflict_resolution → merge_results"
    },
    "final_answer": "The company has 4 core values. Tardiness directly affects the Discipline and Responsibility values...",
    "confidence_score": 0.89,
    "execution_time_ms": 1250
  }
}
```

## 🔍 Monitoring & Observability

### Health Checks
```bash
# API Health
curl http://localhost:15000/api/v1/health/live

# Component Status
curl http://localhost:15000/api/v1/health/ready
```

### Metrics
- **Prometheus**: http://localhost:9090
- **Grafana Dashboards**: http://localhost:3000
- **Application Logs**: `docker-compose logs -f api`

### Performance Monitoring
- Request/Response times
- Agent execution metrics  
- Vector search performance
- Cache hit rates
- Error rates by component

## 🚀 Production Deployment

### Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.prod.yml aichatbot
```


### Environment Considerations
- **CPU**: 4+ cores recommended
- **RAM**: 16GB+ for production
- **Storage**: SSD for vector database
- **Network**: Load balancer for high availability

## 🛠️ Development

### Backend Development
```bash
# Setup Python environment
cd api
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt

# Run development server
python main.py
```

### Frontend Development  
```bash
cd frontend
npm install
npm run dev
```

### Testing
```bash
# Backend tests
cd api
pytest

# Frontend tests
cd frontend  
npm test
```

## 📖 Documentation

- **API Documentation**: `/docs` endpoint when running server
- **Architecture**: [`docs/architecture/`](docs/architecture/)
- **User Guide**: [`docs/user_guide/`](docs/user_guide/)
- **Deployment**: [`docs/deployment/`](docs/deployment/)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Create a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 🙋‍♂️ Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/AIChatBot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/AIChatBot/discussions)
- **Email**: support@yourcompany.com

## 🚀 Roadmap

- [ ] **Q1 2025**: GraphRAG integration
- [ ] **Q2 2025**: Multi-modal support (image/audio)
- [ ] **Q3 2025**: Advanced analytics dashboard
- [ ] **Q4 2025**: Mobile app support

---

**Made with ❤️ by AIChatBot**
