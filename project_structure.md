# Cấu trúc Dự án Hệ thống Agentic RAG

## Tech Stack
- **Database**: PostgreSQL
- **Vector Database**: Milvus  
- **Cache**: Redis
- **Object Storage**: MinIO
- **Embedding Model**: BAAI/bge-M3 (Multilingual)
- **Framework**: FastAPI + LangGraph

```
AIChatBot/
├── README.md
├── docker-compose.yml
│
├── api/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── requirements.txt
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Cấu hình ứng dụng
│   │   ├── database.py            # PostgreSQL connection config
│   │   ├── redis_config.py        # Redis configuration
│   │   ├── minio_config.py        # MinIO configuration
│   │   ├── milvus_config.py       # Milvus configuration
│   │   └── auth_config.py         # Authentication configuration
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py            # JWT, password hashing, authorization
│   │   ├── permissions.py         # Permission management logic
│   │   └── exceptions.py          # Custom exception classes
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py               # API dependencies
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py         # Main API router
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   ├── auth.py       # Authentication endpoints
│   │       │   ├── query.py      # RAG query endpoints
│   │       │   ├── documents.py  # Document management
│   │       │   ├── tools.py      # Tool management endpoints (enable/disable tools)
│   │       │   └── health.py     # Health check endpoints
│   │       └── middleware/
│   │           ├── __init__.py
│   │           ├── auth.py       # Authentication endpoints
│   │           ├── query.py      # RAG query endpoints
│   │           ├── documents.py  # Document management
│   │           └── health.py     # Health check endpoints
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base database model
│   │   │   ├── user.py           # User database model
│   │   │   ├── tenant.py         # Tenant database model
│   │   │   ├── permission.py     # Permission database model
│   │   │   ├── document.py       # Document metadata model
│   │   │   └── audit_log.py      # Audit trail model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py           # User Pydantic schemas
│   │   │   ├── query.py          # Query request/response schemas
│   │   │   ├── document.py       # Document schemas
│   │   │   └── common.py         # Common schemas
│   │   └── vector/
│   │       ├── __init__.py
│   │       ├── milvus_models.py  # Milvus collection schemas
│   │       └── embedding_models.py # BAAI/bge-M3 model definitions
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   └── auth_service.py    # Authentication service
│   │   ├── embedding/
│   │   │   ├── __init__.py
│   │   │   └── embedding_service.py # BAAI/bge-M3 embedding service
│   │   ├── vector/
│   │   │   ├── __init__.py
│   │   │   ├── milvus_service.py    # Milvus operations
│   │   │   └── collection_manager.py # Collection management
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── minio_service.py     # MinIO object storage service
│   │   │   └── file_manager.py      # File upload/download management
│   │   ├── document/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py  # Document CRUD operations
│   │   │   ├── freshness_manager.py # Document freshness management
│   │   │   ├── indexing_service.py  # Document indexing
│   │   │   └── version_control.py   # Document versioning
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── redis_service.py     # Redis cache service
│   │   │   └── cache_manager.py     # Multi-layer cache management
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── tool_manager.py      # Tool enable/disable management
│   │   │   ├── tool_registry.py     # Available tools registry
│   │   │   └── tool_permission.py   # Tool permission validation
│   │   └── notification/
│   │       ├── __init__.py
│   │       ├── notification_service.py # User notifications
│   │       └── webhook_manager.py      # Webhook management
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base/
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py      # Base agent class
│   │   │   └── agent_state.py     # Agent state management
│   │   ├── router/
│   │   │   ├── __init__.py
│   │   │   └── router_agent.py    # Query routing agent
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── hr_agent.py        # HR domain agent
│   │   │   ├── it_agent.py        # IT domain agent
│   │   │   ├── finance_agent.py   # Finance domain agent
│   │   │   └── general_agent.py   # General purpose agent
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── search_tools.py    # Vector search tools
│   │   │   ├── document_tools.py  # Document manipulation tools
│   │   │   └── external_tools.py  # External API tools
│   │   └── synthesis/
│   │       ├── __init__.py
│   │       └── synthesis_agent.py # Response synthesis agent
│   │
│   ├── workflows/
│   │   ├── __init__.py
│   │   └── langgraph/
│   │       ├── __init__.py
│   │       ├── workflow_graph.py   # Main LangGraph workflow
│   │       ├── nodes/
│   │       │   ├── __init__.py
│   │       │   ├── analysis_nodes.py    # Query analysis nodes
│   │       │   ├── retrieval_nodes.py   # Retrieval nodes
│   │       │   └── synthesis_nodes.py   # Response synthesis nodes
│   │       └── state/
│   │           ├── __init__.py
│   │           └── workflow_state.py    # Workflow state schema
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py             # Logging utilities
│       ├── text_processing.py     # Text processing utilities
│       ├── file_utils.py          # File handling utilities
│       ├── datetime_utils.py      # DateTime utilities
│       └── security_utils.py      # Security utilities
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest configuration
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_auth.py          # Authentication tests
│   │   ├── test_permissions.py   # Permission tests
│   │   ├── test_agents.py        # Agent tests
│   │   ├── test_workflows.py     # Workflow tests
│   │   └── test_services.py      # Service tests
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_api.py           # API integration tests
│   │   ├── test_milvus.py        # Milvus integration tests
│   │   └── test_end_to_end.py    # End-to-end tests
│   └── fixtures/
│       ├── __init__.py
│       ├── sample_documents/     # Test documents
│       └── test_data.py         # Test data fixtures
│
├── docs/
│   ├── api/
│   │   ├── openapi.json         # OpenAPI specification
│   │   └── endpoints.md         # API documentation
│   ├── architecture/
│   │   ├── system_design.md     # System architecture
│   │   ├── workflow_design.md   # Workflow documentation
│   │   └── security_model.md    # Security documentation
│   ├── deployment/
│   │   ├── docker_setup.md      # Docker deployment guide
│   │   ├── kubernetes.md        # Kubernetes deployment
│   │   └── production_guide.md  # Production deployment
│   └── user_guide/
│       ├── admin_guide.md       # Admin user guide
│       └── api_usage.md         # API usage guide
│
├── scripts/
│   ├── setup/
│   │   ├── install.sh           # Installation script
│   │   ├── init_system.py       # System initialization
│   │   └── create_collections.py # Milvus collection setup
│   ├── maintenance/
│   │   ├── backup_data.py       # Data backup script
│   │   ├── cleanup_old_docs.py  # Cleanup old documents
│   │   └── optimize_vectors.py  # Vector optimization
│   └── monitoring/
│       ├── health_check.py      # System health check
│       └── performance_monitor.py # Performance monitoring
│
├── deployment/
│   ├── docker/
│   │   ├── Dockerfile           # Application Dockerfile
│   │   ├── Dockerfile.admin     # Admin Dockerfile
│   │   ├── docker-compose.prod.yml # Production compose
│   │   └── services/
│   │       ├── postgres.yml     # PostgreSQL service
│   │       ├── redis.yml        # Redis service
│   │       ├── minio.yml        # MinIO service
│   │       └── milvus.yml       # Milvus service
│   ├── kubernetes/
│   │   ├── namespace.yaml       # Kubernetes namespace
│   │   ├── configmap.yaml       # Configuration maps
│   │   ├── secrets.yaml         # Secrets management
│   │   ├── deployment.yaml      # Application deployment
│   │   ├── service.yaml         # Service definitions
│   │   └── ingress.yaml         # Ingress configuration
│   └── helm/
│       ├── Chart.yaml           # Helm chart
│       ├── values.yaml          # Default values
│       └── templates/           # Helm templates
│
├── data/
│   ├── models/
│   │   └── bge-m3/              # BAAI/bge-M3 model files
│   ├── documents/               # Document storage (local fallback)
│   │   ├── hr/                  # HR documents
│   │   ├── it/                  # IT documents
│   │   ├── finance/             # Finance documents
│   │   └── shared/              # Shared documents
│   ├── embeddings/              # Cached embeddings
│   └── backups/                 # Data backups
│
└── monitoring/
    ├── prometheus/
    │   ├── prometheus.yml       # Prometheus configuration
    │   └── rules/               # Alert rules
    ├── grafana/
    │   ├── dashboards/          # Grafana dashboards
    │   └── provisioning/        # Grafana provisioning
    └── logs/                    # Log files
```

## Các Module Chính

### 1. Core Framework
- **FastAPI**: API layer với automatic documentation
- **LangGraph**: Workflow orchestration engine
- **PostgreSQL**: Relational database cho metadata và user management
- **Milvus**: Vector database với multi-collection support
- **Redis**: Multi-layer caching system
- **MinIO**: Object storage cho documents và files
- **BAAI/bge-M3**: Multilingual embedding model

### 2. Security & Permissions
- **JWT Authentication**: Token-based authentication
- **RBAC**: Role-based access control
- **Department-level isolation**: Strict data separation
- **Audit trail**: Comprehensive logging

### 3. Document Management
- **Real-time monitoring**: File system watchers, webhooks
- **Version control**: Document versioning với retention policies
- **Freshness SLA**: Tiered update guarantees
- **Multi-source ingestion**: SharePoint, Git, Slack, etc.
- **Object storage**: MinIO cho document files với versioning
- **Multilingual support**: BAAI/bge-M3 cho Vietnamese và English

### 4. AI Agents & Workflow
- **Router Agent**: Query routing với permission awareness
- **Domain Agents**: Specialized agents cho từng phòng ban
- **Tool Agents**: Dynamic tool loading theo permissions
- **Synthesis Agent**: Response aggregation với content filtering

## Infrastructure Services

### PostgreSQL
- **User Management**: Authentication, authorization, permissions
- **Metadata Storage**: Document metadata, audit logs, tool configurations
- **Multi-tenant Support**: Tenant isolation với database schemas

### Redis  
- **Cache**: Agent memory và frequent queries
- **Session Management**: User sessions và workflow state
- **Rate Limiting**: API rate limiting và usage tracking

### MinIO
- **Document Storage**: Original files với versioning support
- **Backup Storage**: System backups và document archives
- **Model Storage**: Embedding model files và custom models
- **Multi-tenant Buckets**: Isolated storage per tenant

### Milvus
- **Vector Collections**: Department-specific collections với ACL
- **Embedding Storage**: BAAI/bge-M3 vectors (1024 dimensions)
- **Similarity Search**: Semantic search với permission filtering
- **Index Optimization**: HNSW/IVF indexes cho performance

### BAAI/bge-M3 Features
- **Multilingual**: Vietnamese, English, Japanese, Korea support
- **Dense Retrieval**: High-quality semantic embeddings
- **Cross-lingual**: Query trong một ngôn ngữ, retrieve documents ở ngôn ngữ khác
- **Instruction Following**: Better understanding của complex queries
- **1024 Dimensions**: Optimal balance giữa quality và performance