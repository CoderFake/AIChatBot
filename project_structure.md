# Cấu trúc Dự án Complete Agentic RAG System

## Tech Stack & Architecture
- **Framework**: FastAPI + LangGraph
- **Database**: PostgreSQL
- **Vector Database**: Milvus với per-agent collections
- **Cache**: Redis
- **Object Storage**: MinIO
- **Embedding Model**: BAAI/bge-M3 (Multilingual)
- **Orchestration**: Intelligent LLM-driven task distribution
- **Streaming**: Server-Sent Events (SSE) + WebSocket
- **Multi-language**: Vietnamese, English, Japanese, Korean

```
AIChatBot/
├── README.md
├── docker-compose.yml
├── pyproject.toml
│
├── api/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application với complete lifespan management
│   ├── requirements.txt
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py             # Comprehensive system configuration
│   │   ├── config_manager.py       # Dynamic configuration management
│   │   ├── database.py             # PostgreSQL connection với health checks
│   │   ├── redis_config.py         # Redis configuration và connection pool
│   │   ├── minio_config.py         # MinIO configuration và bucket management
│   │   ├── milvus_config.py        # Milvus configuration với collection schemas
│   │   └── auth_config.py          # Authentication và authorization config
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py             # JWT, password hashing, authorization
│   │   ├── permissions.py          # Permission management với department isolation
│   │   ├── exceptions.py           # Custom exception classes với error handlers
│   │   └── tenant_manager.py       # Multi-tenant management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # API dependencies và injection
│   │   ├── gateway/
│   │   │   ├── __init__.py
│   │   │   └── api_gateway.py      # API gateway với routing logic
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py           # Main API router với all endpoints
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   ├── auth.py         # Authentication endpoints
│   │       │   ├── config.py       # System configuration endpoints
│   │       │   ├── documents.py    # Document management với version control
│   │       │   ├── tools.py        # Tool management endpoints
│   │       │   └── health.py       # Comprehensive health check endpoints
│   │       └── middleware/
│   │           ├── __init__.py
│   │           ├── auth_middleware.py      # Authentication middleware
│   │           ├── logging_middleware.py   # Request/response logging
│   │           └── tenant_middleware.py    # Multi-tenant context
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── document.py            # Document model với metadata
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Base database model với common fields
│   │   │   ├── user.py            # User database model với roles
│   │   │   ├── tenant.py          # Tenant database model
│   │   │   ├── permission.py      # Permission database model với ACL
│   │   │   ├── document.py        # Document metadata model
│   │   │   └── audit_log.py       # Comprehensive audit trail
│   │   ├── schemas/
│   │   │   ├── __init__.py        # Schema exports với proper imports
│   │   │   ├── common.py          # Common schemas và base classes
│   │   │   ├── request/
│   │   │   │   └── document.py    # Document request schemas
│   │   │   └── responses/
│   │   │       ├── __init__.py
│   │   │       ├── document.py    # Document response schemas
│   │   │       ├── health.py      # Health check response models
│   │   │       └── config.py      # Configuration response models
│   │   └── vector/
│   │       ├── __init__.py
│   │       ├── milvus_models.py   # Milvus collection schemas per agent
│   │       └── embedding_models.py # BAAI/bge-M3 model definitions
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── types.py               # Common service types và enums
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py    # Authentication service với JWT
│   │   │   └── permission_service.py # Permission validation service
│   │   ├── embedding/
│   │   │   ├── __init__.py
│   │   │   ├── embedding_service.py # BAAI/bge-M3 embedding service
│   │   │   └── model_manager.py   # Model loading và caching
│   │   ├── vector/
│   │   │   ├── __init__.py
│   │   │   ├── milvus_service.py  # Optimized Milvus operations
│   │   │   └── collection_manager.py # Per-agent collection management
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── minio_service.py   # MinIO object storage service
│   │   │   └── file_manager.py    # File upload/download với versioning
│   │   ├── document/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py # Document CRUD với permission checks
│   │   │   ├── freshness_manager.py # Document freshness tracking
│   │   │   ├── indexing_service.py # Smart document indexing
│   │   │   └── version_control.py  # Document versioning system
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── redis_service.py   # Redis cache service với TTL
│   │   │   └── cache_manager.py   # Multi-layer cache management
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── tool_manager.py    # Tool enable/disable với permissions
│   │   │   ├── tool_registry.py   # Available tools registry
│   │   │   └── tool_permission.py # Tool permission validation
│   │   ├── llm/
│   │   │   └── provider_manager.py # LLM provider management
│   │   ├── notification/
│   │   │   ├── __init__.py
│   │   │   ├── notification_service.py # User notifications
│   │   │   └── webhook_manager.py      # Webhook management
│   │   ├── dataclasses/
│   │   │   ├── llm.py             # LLM dataclasses và configurations
│   │   │   ├── milvus.py          # Milvus dataclasses
│   │   │   ├── multi_agent_workflow.py # Workflow dataclasses
│   │   │   ├── orchestrator.py    # Orchestrator dataclasses
│   │   │   └── tools.py           # Tool dataclasses
│   │   └── orchestrator/
│   │       └── orchestrator_service.py # Intelligent orchestration service
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base/
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py      # Base agent class với common functionality
│   │   │   └── agent_state.py     # Agent state management
│   │   ├── router/
│   │   │   ├── __init__.py
│   │   │   └── router_agent.py    # Intelligent query routing agent
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── hr_agent.py        # HR domain specialist agent
│   │   │   ├── it_agent.py        # IT domain specialist agent
│   │   │   ├── finance_agent.py   # Finance domain specialist agent
│   │   │   └── general_agent.py   # General purpose agent
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── search_tools.py    # Advanced vector search tools
│   │   │   ├── document_tools.py  # Document manipulation tools
│   │   │   └── external_tools.py  # External API integration tools
│   │   └── synthesis/
│   │       ├── __init__.py
│   │       └── synthesis_agent.py # Response synthesis và aggregation
│   │
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── langgraph/
│   │   │   ├── __init__.py
│   │   │   ├── multi_agent_workflow.py # Complete multi-agent workflow
│   │   │   ├── workflow_graph.py       # Main LangGraph workflow definition
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_node.py        # Base node implementation
│   │   │   │   ├── core_nodes.py       # Core workflow nodes
│   │   │   │   ├── permission_nodes.py # Permission check nodes
│   │   │   │   └── retrieval_nodes.py  # Document retrieval nodes
│   │   │   ├── edges/
│   │   │   │   ├── __init__.py
│   │   │   │   └── condition_edges.py  # Conditional edge logic
│   │   │   └── state/
│   │   │       ├── __init__.py
│   │   │       └── unified_state.py    # Unified workflow state schema
│   │   └── monitoring/
│   │       ├── __init__.py
│   │       └── unified_monitor.py      # Workflow monitoring và metrics
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py              # Structured logging với correlation IDs
│       ├── text_processing.py      # Advanced text processing utilities
│       ├── file_utils.py           # File handling với security checks
│       ├── datetime_utils.py       # DateTime utilities với timezone support
│       └── security_utils.py       # Security utilities và validation
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest configuration với fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_auth.py           # Authentication tests
│   │   ├── test_permissions.py    # Permission system tests
│   │   ├── test_agents.py         # Agent functionality tests
│   │   ├── test_workflows.py      # Workflow logic tests
│   │   └── test_services.py       # Service layer tests
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_api.py            # API integration tests
│   │   ├── test_milvus.py         # Milvus integration tests
│   │   └── test_end_to_end.py     # Complete workflow tests
│   └── fixtures/
│       ├── __init__.py
│       ├── sample_documents/      # Test documents cho all domains
│       └── test_data.py          # Test data fixtures
│
├── docs/
│   ├── api/
│   │   ├── openapi.json          # Auto-generated OpenAPI specification
│   │   └── endpoints.md          # API endpoint documentation
│   ├── architecture/
│   │   ├── system_design.md      # Complete system architecture
│   │   ├── workflow_design.md    # LangGraph workflow documentation
│   │   └── security_model.md     # Security và permission model
│   ├── deployment/
│   │   ├── docker_setup.md       # Docker deployment guide
│   │   ├── kubernetes.md         # Kubernetes deployment
│   │   └── production_guide.md   # Production deployment guide
│   └── user_guide/
│       ├── admin_guide.md        # Admin user guide
│       └── api_usage.md          # API usage examples
│
├── scripts/
│   ├── setup/
│   │   ├── install.sh            # Complete installation script
│   │   ├── init_system.py        # System initialization với checks
│   │   └── create_collections.py # Milvus collection setup per agent
│   ├── maintenance/
│   │   ├── backup_data.py        # Comprehensive data backup
│   │   ├── cleanup_old_docs.py   # Document cleanup với retention
│   │   └── optimize_vectors.py   # Vector index optimization
│   └── monitoring/
│       ├── health_check.py       # System health monitoring
│       └── performance_monitor.py # Performance metrics collection
│
├── deployment/
│   ├── docker/
│   │   ├── Dockerfile            # Multi-stage application build
│   │   ├── Dockerfile.admin      # Admin interface build
│   │   ├── docker-compose.prod.yml # Production compose với scaling
│   │   └── services/
│   │       ├── postgres.yml      # PostgreSQL service với persistence
│   │       ├── redis.yml         # Redis service với clustering
│   │       ├── minio.yml         # MinIO service với replication
│   │       └── milvus.yml        # Milvus service với optimization
│   ├── kubernetes/
│   │   ├── namespace.yaml        # Kubernetes namespace isolation
│   │   ├── configmap.yaml        # Configuration management
│   │   ├── secrets.yaml          # Secrets management với encryption
│   │   ├── deployment.yaml       # Application deployment với HPA
│   │   ├── service.yaml          # Service definitions với load balancing
│   │   └── ingress.yaml          # Ingress với SSL termination
│   └── helm/
│       ├── Chart.yaml            # Helm chart definition
│       ├── values.yaml           # Default values với environment configs
│       └── templates/            # Kubernetes templates
│
├── data/
│   ├── models/
│   │   └── bge-m3/               # BAAI/bge-M3 model files và cache
│   ├── documents/                # Document storage structure
│   │   ├── hr/                   # HR documents với access control
│   │   ├── it/                   # IT documents với version tracking
│   │   ├── finance/              # Finance documents với encryption
│   │   └── shared/               # Shared documents với permissions
│   ├── embeddings/               # Cached embeddings với TTL
│   └── backups/                  # System backups với rotation
│
└── monitoring/
    ├── prometheus/
    │   ├── prometheus.yml        # Prometheus configuration với scraping
    │   └── rules/                # Alert rules cho system monitoring
    ├── grafana/
    │   ├── dashboards/           # Pre-built dashboards cho all metrics
    │   └── provisioning/         # Grafana auto-provisioning
    └── logs/                     # Structured log files với rotation
```

## Tính năng chính của Complete Agentic RAG System

### 🧠 Intelligent Orchestration
- **LLM-driven Decision Making**: Không hardcode routing logic
- **Dynamic Task Distribution**: Phân phối tasks dựa trên context
- **Smart Agent Selection**: Chọn agents phù hợp cho từng query
- **Conflict Resolution**: Giải quyết xung đột giữa agent responses
- **Performance Optimization**: Auto-tuning dựa trên metrics

### 🔍 Optimized Vector Search
- **Per-Agent Collections**: Mỗi agent có collection riêng trong Milvus
- **Hybrid Search**: Kết hợp BM25 + Vector search cho độ chính xác cao
- **Smart Chunking**: Chunking tự động based on file size và content type
- **Auto-Reindexing**: Reindex tự động khi detect document changes
- **Permission-Aware Search**: Vector search tích hợp permission checks

### 🌊 Real-time Streaming
- **Server-Sent Events (SSE)**: Real-time response streaming
- **WebSocket Support**: Bi-directional communication cho interactive queries
- **Progress Tracking**: Real-time progress updates cho long-running tasks
- **Batch Processing**: Efficient handling của multiple concurrent requests
- **Error Recovery**: Graceful error handling và recovery mechanisms

### 🌍 Multi-language Support
- **BAAI/bge-M3**: Advanced multilingual embedding model
- **Cross-lingual Retrieval**: Query trong một ngôn ngữ, retrieve documents ở ngôn ngữ khác
- **Language Detection**: Tự động detect ngôn ngữ của query và documents
- **Localized Responses**: Response formatting theo ngôn ngữ preference
- **Supported Languages**: Vietnamese (primary), English, Japanese, Korean

### 🔐 Advanced Permission System
- **Department-level Isolation**: Strict separation giữa các phòng ban
- **Document-level Access Control**: Fine-grained permissions cho từng document
- **Tool Permissions**: Control access to external tools per user/role
- **Audit Trail**: Comprehensive logging của all access và actions
- **Multi-tenant Support**: Complete tenant isolation với shared infrastructure

### 🎯 Smart Agent Architecture
- **Router Agent**: Intelligent query routing với context awareness
- **Domain Specialists**: HR, IT, Finance agents với specialized knowledge
- **Tool Integration**: Dynamic tool loading based on permissions và context
- **Response Synthesis**: Intelligent aggregation của multiple agent responses
- **Learning Capabilities**: Agents improve over time based on feedback

## API Endpoints Structure

### Health Check Endpoints (`/api/v1/health`)
- `GET /` - Basic health check với service info
- `GET /detailed` - Comprehensive health check với all components
- `GET /status` - Detailed system status cho monitoring
- `GET /ready` - Kubernetes readiness probe
- `GET /live` - Kubernetes liveness probe

### Document Management (`/api/v1/documents`)
- Complete CRUD operations với version control
- Bulk upload và processing
- Permission-aware document access
- Metadata management và search
- Document freshness tracking

### Configuration (`/api/v1/config`)
- System configuration management
- Tool enable/disable controls
- Agent configuration updates
- Permission matrix management

### Authentication (`/api/v1/auth`)
- JWT-based authentication
- Role và permission management
- Multi-tenant user management
- Session handling

## Infrastructure Services Detail

### PostgreSQL
- **User & Permission Management**: Complete RBAC implementation
- **Document Metadata**: Versioning, ownership, access logs
- **Audit Trail**: Comprehensive action logging với correlation IDs
- **Multi-tenant Schema**: Isolated data per tenant với shared services
- **Connection Pooling**: Optimized connections với health monitoring

### Milvus Vector Database
- **Per-Agent Collections**: Isolated vector storage cho từng agent domain
- **BAAI/bge-M3 Embeddings**: 1024-dimensional multilingual vectors
- **Hybrid Search**: Combined BM25 + vector similarity search
- **Permission Integration**: Vector search với access control filters
- **Auto-Optimization**: Index tuning based on usage patterns

### Redis Cache
- **Multi-layer Caching**: Agent memory, query results, session data
- **TTL Management**: Smart expiration based on data type và usage
- **Distributed Sessions**: Session storage cho multi-instance deployment
- **Rate Limiting**: API rate limiting với user-based quotas
- **Real-time Metrics**: Performance metrics tracking và alerting

### MinIO Object Storage
- **Document Versioning**: Complete version history với rollback capability
- **Multi-tenant Buckets**: Isolated storage per tenant với ACL
- **Backup Integration**: Automated backups với retention policies
- **Large File Handling**: Efficient storage cho large documents và models
- **Security**: Encryption at rest và in transit

## Development & Deployment

### Docker & Kubernetes
- **Multi-stage Builds**: Optimized container images
- **Horizontal Pod Autoscaling**: Auto-scaling based on metrics
- **Service Mesh**: Istio integration cho advanced networking
- **Persistent Storage**: StatefulSets cho databases với backup automation
- **Rolling Updates**: Zero-downtime deployments với health checks

### Monitoring & Observability
- **Prometheus Metrics**: Custom metrics cho all components
- **Grafana Dashboards**: Pre-built dashboards cho system monitoring
- **Distributed Tracing**: Request tracing through entire workflow
- **Structured Logging**: JSON logs với correlation IDs
- **Alert Management**: Proactive alerting cho system issues

### Security
- **Zero Trust Architecture**: All communications authenticated và encrypted
- **Secret Management**: Kubernetes secrets với external secret stores
- **Network Policies**: Micro-segmentation cho enhanced security
- **Vulnerability Scanning**: Automated security scans cho containers
- **Compliance**: GDPR và data protection compliance built-in