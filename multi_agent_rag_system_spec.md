# Multi-Agent RAG System - Functional Specification

> **LƯU Ý**: Tất cả code trong tài liệu này là **PSEUDOCODE** và **EXAMPLE CODE** cho mục đích minh họa. Không sử dụng trực tiếp trong production mà cần implement theo specification này.

## Official Documentation Links

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **BGE-M3**: https://huggingface.co/BAAI/bge-m3
- **Docling**: https://docling-project.github.io/docling/
- **LangChain Docling**: https://python.langchain.com/docs/integrations/document_loaders/docling/
- **LangChain Unstructured**: https://python.langchain.com/docs/integrations/document_loaders/unstructured_file/
- **Milvus**: https://milvus.io/docs
- **Kafka**: https://kafka.apache.org/documentation/

## 1. System Overview

Multi-Agent RAG system uses database-driven configuration for dynamic agent orchestration. RAG is a tool within the system, not an agent itself.

**Core Flow:**
```
Query → Orchestrator ↔ Reflection + Semantic Router → Agent Selection → Permission Check → Tool Selection (including RAG) → Response Assembly
```

**Infrastructure Components:**
- **milvus_public**: Public vector database container for shared knowledge
- **milvus_private**: Private vector database container for department-specific data
- **Document Processing**: Docling primary, LangChain Unstructured fallback
- **Embedding**: BAAI/bge-m3 for multi-modal embeddings

## 2. Database Schema

### Agents Table
```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    description TEXT,
    capabilities JSONB,
    provider_config JSONB,
    status BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Example data:
INSERT INTO agents (name, department, capabilities, provider_config) VALUES
('HR Assistant', 'hr', '{"topics": ["employee", "policy", "benefits"]}', '{"provider": "openai", "model": "gpt-4"}'),
('Finance Analyst', 'finance', '{"topics": ["budget", "expense", "revenue"]}', '{"provider": "anthropic", "model": "claude-3"}');
```

### Tools Table
```sql
CREATE TABLE tools (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'rag', 'calculator', 'api_call', etc
    config JSONB NOT NULL,
    permissions JSONB,
    status BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Example RAG tool configuration:
INSERT INTO tools (name, type, config, permissions) VALUES
('RAG Search', 'rag', 
    '{"milvus_public_uri": "http://milvus_public:19530", "milvus_private_uri": "http://milvus_private:19530", "mmr_lambda": 0.5, "top_k": 10}',
    '{"requires_department_access": true}'
);
```

### Agent-Tools Mapping
```sql
CREATE TABLE agent_tools (
    agent_id UUID REFERENCES agents(id),
    tool_id UUID REFERENCES tools(id),
    priority INTEGER DEFAULT 0,
    is_enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (agent_id, tool_id)
);
```

### Provider Configurations
```sql
CREATE TABLE provider_configs (
    id UUID PRIMARY KEY,
    component_type VARCHAR(50) NOT NULL, -- 'reflection', 'semantic_router', 'llm'  
    provider_name VARCHAR(100) NOT NULL,
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Example configurations:
INSERT INTO provider_configs (component_type, provider_name, config, is_active) VALUES
('reflection', 'openai', '{"model": "gpt-4", "temperature": 0.1}', true),
('semantic_router', 'sentence_transformers', '{"model": "all-MiniLM-L6-v2"}', true);
```

### Collections Access Control
```sql
CREATE TABLE collection_permissions (
    id UUID PRIMARY KEY,
    department VARCHAR(100) NOT NULL,
    collection_name VARCHAR(255) NOT NULL,
    milvus_instance VARCHAR(20) NOT NULL, -- 'public', 'private'
    access_level VARCHAR(20) DEFAULT 'read', -- 'read', 'write', 'admin'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Example permissions:
INSERT INTO collection_permissions (department, collection_name, milvus_instance) VALUES
('hr', 'company_policies', 'public'),
('hr', 'hr_documents', 'private'),
('finance', 'company_policies', 'public'),
('finance', 'financial_reports', 'private');
```

## 3. LangGraph State & Workflow

### State Definition
```python
# PSEUDOCODE - Example implementation
from typing_extensions import TypedDict
from typing import List, Dict, Optional
from langgraph.graph import add_messages

class SystemState(TypedDict):
    query: str
    chat_history: List[Dict]
    clarified_query: Optional[str]
    selected_agent: Optional[Dict]
    available_tools: List[Dict]
    tool_results: Dict[str, any]
    final_response: Optional[str]
    permissions: Dict[str, bool]
```

### Node Implementation
```python
# PSEUDOCODE - Implementation example
from langgraph.graph import StateGraph, START, END

def orchestrator_node(state: SystemState) -> SystemState:
    """Route to reflection or direct processing based on query complexity"""
    if needs_clarification(state["query"], state["chat_history"]):
        return {"next_action": "reflection"}
    return {"next_action": "agent_selection"}

def reflection_semantic_router_node(state: SystemState) -> SystemState:
    """Database-driven reflection and routing"""
    reflection_config = get_provider_config("reflection")
    router_config = get_provider_config("semantic_router")
    
    clarified_query = apply_reflection(
        state["query"], 
        state["chat_history"], 
        reflection_config
    )
    
    return {"clarified_query": clarified_query}

def agent_selection_node(state: SystemState) -> SystemState:
    """Select agent from database based on semantic matching"""
    query = state.get("clarified_query", state["query"])
    selected_agent = select_agent_from_db(query)
    
    # Get department permissions
    permissions = get_department_permissions(selected_agent["department"])
    
    return {
        "selected_agent": selected_agent,
        "permissions": permissions
    }

def tool_selection_node(state: SystemState) -> SystemState:
    """Get available tools for selected agent from database"""
    agent_id = state["selected_agent"]["id"]
    available_tools = get_agent_tools_from_db(agent_id, state["permissions"])
    return {"available_tools": available_tools}

def tool_execution_node(state: SystemState) -> SystemState:
    """Execute tools including RAG if needed"""
    results = {}
    
    for tool in state["available_tools"]:
        if should_execute_tool(tool, state):
            results[tool["name"]] = execute_tool(tool, state)
    
    return {"tool_results": results}

def response_assembly_node(state: SystemState) -> SystemState:
    """Assemble final response using agent's provider configuration"""
    agent_config = state["selected_agent"]["provider_config"]
    
    final_response = generate_response_with_provider(
        query=state.get("clarified_query", state["query"]),
        tool_results=state["tool_results"],
        provider_config=agent_config
    )
    
    return {"final_response": final_response}
```

### Graph Construction
```python
# PSEUDOCODE - LangGraph workflow setup
workflow = StateGraph(SystemState)

workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("reflection_router", reflection_semantic_router_node)  
workflow.add_node("agent_selection", agent_selection_node)
workflow.add_node("tool_selection", tool_selection_node)
workflow.add_node("tool_execution", tool_execution_node)
workflow.add_node("response_assembly", response_assembly_node)

workflow.add_edge(START, "orchestrator")
workflow.add_conditional_edges("orchestrator", route_based_on_action)
workflow.add_edge("reflection_router", "agent_selection")
workflow.add_edge("agent_selection", "tool_selection")
workflow.add_edge("tool_selection", "tool_execution")
workflow.add_edge("tool_execution", "response_assembly")
workflow.add_edge("response_assembly", END)

app = workflow.compile()
```

## 4. Document Processing Pipeline

### Primary: Docling + LangChain Docling Integration
```python
# PSEUDOCODE - Document processing with Docling
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.chunking import HybridChunker
from langchain_community.document_loaders import DoclingLoader
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

class DocumentProcessor:
    def __init__(self):
        # Primary: Docling with advanced PDF processing
        pipeline_options = PdfPipelineOptions(
            do_table_structure=True,
            do_ocr=True,
            do_picture=True
        )
        
        self.docling_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        # LangChain Docling loader for integration
        self.langchain_docling_loader = DoclingLoader
        
        # Hybrid chunker with BGE-M3 tokenizer
        tokenizer = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained("BAAI/bge-m3"),
            max_tokens=512
        )
        self.chunker = HybridChunker(tokenizer=tokenizer)
        
        # Fallback: LangChain Unstructured
        self.fallback_loader = None
    
    def process_document(self, source: str, department: str) -> List[Dict]:
        """
        Process document with Docling primary, Unstructured fallback
        """
        try:
            # Primary: Docling processing
            result = self.docling_converter.convert(source)
            chunks = list(self.chunker.chunk(dl_doc=result.document))
            
            processed_chunks = []
            for chunk in chunks:
                processed_chunks.append({
                    "text": chunk.text,
                    "metadata": {
                        "source": source,
                        "department": department,
                        "page_number": chunk.meta.get("page_no"),
                        "processing_method": "docling"
                    }
                })
            
            return processed_chunks
            
        except Exception as e:
            # Fallback: LangChain Unstructured
            return self.fallback_processing(source, department)
    
    def fallback_processing(self, source: str, department: str) -> List[Dict]:
        """
        Fallback to LangChain Unstructured when Docling fails
        """
        from langchain_community.document_loaders import UnstructuredFileLoader
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        try:
            loader = UnstructuredFileLoader(source)
            documents = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            
            chunks = text_splitter.split_documents(documents)
            
            processed_chunks = []
            for chunk in chunks:
                processed_chunks.append({
                    "text": chunk.page_content,
                    "metadata": {
                        "source": source,
                        "department": department,
                        "processing_method": "unstructured_fallback"
                    }
                })
            
            return processed_chunks
            
        except Exception as fallback_error:
            raise Exception(f"Both Docling and Unstructured processing failed: {str(fallback_error)}")
```

### BGE-M3 Embedding Service
```python
# PSEUDOCODE - BGE-M3 embedding implementation
from FlagEmbedding import BGEM3FlagModel

class EmbeddingService:
    def __init__(self):
        # BGE-M3: Multi-functionality, Multi-linguality, Multi-granularity
        self.model = BGEM3FlagModel(
            'BAAI/bge-m3',
            use_fp16=True,  # GPU optimization
            device='cuda' if torch.cuda.is_available() else 'cpu'
        )
    
    def encode_documents(self, documents: List[str]) -> Dict:
        """
        Encode documents with dense, sparse, and multi-vector embeddings
        """
        return self.model.encode(
            documents,
            return_dense=True,      # For semantic similarity
            return_sparse=True,     # For lexical matching (BM25-like)
            return_colbert_vecs=True,  # For multi-vector retrieval
            batch_size=12,
            max_length=8192  # Support long documents
        )
    
    def encode_queries(self, queries: List[str]) -> Dict:
        """Encode queries for search"""
        return self.model.encode(
            queries,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False  # Queries don't need multi-vector
        )
```

## 5. Dual Milvus Container Setup

### Milvus Public Container
```python
# PSEUDOCODE - Public Milvus configuration
class MilvusPublicService:
    def __init__(self):
        self.client = MilvusClient("http://milvus_public:19530")
        self.embedding_function = BGEM3EmbeddingFunction(
            model_name='BAAI/bge-m3',
            device='cpu',
            use_fp16=False
        )
    
    def create_public_collections(self):
        """Create collections for shared knowledge"""
        collections = [
            "company_policies",
            "general_knowledge", 
            "public_documentation"
        ]
        
        for collection_name in collections:
            self.create_collection_with_bge_m3_schema(collection_name)
    
    def create_collection_with_bge_m3_schema(self, collection_name: str):
        """Create collection optimized for BGE-M3"""
        schema = self.client.create_schema(
            auto_id=True, 
            enable_dynamic_field=True
        )
        
        # BGE-M3 specific fields
        schema.add_field("pk", DataType.INT64, is_primary=True)
        schema.add_field(
            "dense_vector", 
            DataType.FLOAT_VECTOR, 
            dim=1024  # BGE-M3 dense dimension
        )
        schema.add_field(
            "sparse_vector", 
            DataType.SPARSE_FLOAT_VECTOR
        )
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("department", DataType.VARCHAR, max_length=100)
        schema.add_field("document_source", DataType.VARCHAR, max_length=500)
        
        # Indexes for hybrid search
        index_params = self.client.prepare_index_params()
        index_params.add_index("dense_vector", "HNSW", "IP")
        index_params.add_index("sparse_vector", "SPARSE_INVERTED_INDEX", "IP")
        
        self.client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params
        )
```

### Milvus Private Container
```python
# PSEUDOCODE - Private Milvus configuration
class MilvusPrivateService:
    def __init__(self):
        self.client = MilvusClient("http://milvus_private:19530")
        self.embedding_function = BGEM3EmbeddingFunction(
            model_name='BAAI/bge-m3',
            device='cpu',
            use_fp16=False
        )
    
    def create_department_collections(self, departments: List[str]):
        """Create private collections for each department"""
        for department in departments:
            collection_name = f"{department}_private_docs"
            self.create_collection_with_bge_m3_schema(collection_name)
            
            # Set department-specific access controls
            self.set_collection_permissions(collection_name, department)
    
    def set_collection_permissions(self, collection_name: str, department: str):
        """Set RBAC permissions for collection"""
        # Implementation depends on Milvus RBAC setup
        pass
```

## 6. RAG Tool Implementation

### RAG Tool with MMR Search
```python
# PSEUDOCODE - RAG as a tool in the system
class RAGTool:
    def __init__(self, tool_config: Dict):
        self.config = tool_config
        self.public_milvus = MilvusClient(tool_config["milvus_public_uri"])
        self.private_milvus = MilvusClient(tool_config["milvus_private_uri"])
        self.embedding_service = EmbeddingService()
    
    def execute(self, query: str, agent_info: Dict, permissions: Dict) -> Dict:
        """Execute RAG search based on permissions"""
        
        # Determine accessible collections
        accessible_collections = self.get_accessible_collections(
            agent_info["department"], 
            permissions
        )
        
        if not accessible_collections:
            return {"type": "rag_results", "data": [], "error": "No accessible collections"}
        
        # Perform MMR search across accessible collections
        results = self.mmr_search_across_collections(query, accessible_collections)
        
        return {
            "type": "rag_results",
            "data": results,
            "metadata": {
                "collections_searched": [col["name"] for col in accessible_collections],
                "results_count": len(results),
                "search_method": "mmr"
            }
        }
    
    def get_accessible_collections(self, department: str, permissions: Dict) -> List[Dict]:
        """Get collections based on department permissions"""
        collections = []
        
        # Query database for accessible collections
        accessible = database.query("""
            SELECT collection_name, milvus_instance, access_level
            FROM collection_permissions
            WHERE department = %s OR milvus_instance = 'public'
        """, [department])
        
        for row in accessible:
            collections.append({
                "name": row["collection_name"],
                "instance": "public" if row["milvus_instance"] == "public" else "private",
                "client": self.public_milvus if row["milvus_instance"] == "public" else self.private_milvus
            })
        
        return collections
    
    def mmr_search_across_collections(self, query: str, collections: List[Dict]) -> List[Dict]:
        """
        MMR search implementation across multiple collections
        Reference: https://docs.llamaindex.ai/en/stable/examples/vector_stores/SimpleIndexDemoMMR/
        """
        query_embeddings = self.embedding_service.encode_queries([query])
        query_dense = query_embeddings["dense"][0]
        
        # Collect candidates from all accessible collections
        all_candidates = []
        
        for collection_info in collections:
            client = collection_info["client"]
            collection_name = collection_info["name"]
            
            try:
                search_results = client.search(
                    collection_name=collection_name,
                    data=[query_dense.tolist()],
                    limit=20,  # Get more candidates for MMR
                    output_fields=["text", "department", "document_source"]
                )
                
                for hit in search_results[0]:
                    all_candidates.append({
                        "id": hit["id"],
                        "text": hit["entity"]["text"],
                        "department": hit["entity"]["department"],
                        "source": hit["entity"]["document_source"],
                        "relevance_score": hit["distance"],
                        "collection": collection_name,
                        "instance": collection_info["instance"],
                        "dense_vector": self.get_document_vector(client, collection_name, hit["id"])
                    })
            
            except Exception as e:
                print(f"Error searching collection {collection_name}: {e}")
                continue
        
        # Apply MMR algorithm
        return self.apply_mmr_algorithm(
            query_dense, 
            all_candidates, 
            lambda_param=self.config.get("mmr_lambda", 0.5),
            k=self.config.get("top_k", 10)
        )
    
    def apply_mmr_algorithm(self, query_vector: np.ndarray, candidates: List[Dict], lambda_param: float, k: int) -> List[Dict]:
        """
        Maximal Marginal Relevance implementation
        Formula: MMR = arg max[λ × Sim₁(dᵢ, q) - (1-λ) × max Sim₂(dᵢ, dⱼ)]
        """
        if len(candidates) <= k:
            return candidates
        
        selected = []
        remaining = candidates.copy()
        
        # Select first document (most relevant)
        first_doc = max(remaining, key=lambda x: x["relevance_score"])
        selected.append(first_doc)
        remaining.remove(first_doc)
        
        # Iteratively select remaining documents
        while len(selected) < k and remaining:
            mmr_scores = []
            
            for candidate in remaining:
                # Relevance score (similarity to query)
                relevance = cosine_similarity(
                    [query_vector],
                    [candidate["dense_vector"]]
                )[0][0]
                
                # Diversity score (max similarity to selected documents)
                max_similarity = 0
                for selected_doc in selected:
                    similarity = cosine_similarity(
                        [candidate["dense_vector"]],
                        [selected_doc["dense_vector"]]
                    )[0][0]
                    max_similarity = max(max_similarity, similarity)
                
                # MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                mmr_scores.append((candidate, mmr_score))
            
            # Select document with highest MMR score
            best_candidate, best_score = max(mmr_scores, key=lambda x: x[1])
            selected.append(best_candidate)
            remaining.remove(best_candidate)
        
        return selected
```

## 7. Tool Registry & Execution
```python
# PSEUDOCODE - Dynamic tool loading and execution
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.load_tools_from_database()
    
    def load_tools_from_database(self):
        """Load all enabled tools from database"""
        tools_data = database.query("""
            SELECT id, name, type, config, permissions
            FROM tools 
            WHERE status = true
        """)
        
        for tool_data in tools_data:
            tool_class = self.get_tool_class(tool_data["type"])
            self.tools[tool_data["id"]] = {
                "instance": tool_class(tool_data["config"]),
                "permissions": tool_data["permissions"],
                "name": tool_data["name"]
            }
    
    def get_tool_class(self, tool_type: str):
        """Factory pattern for tool instantiation"""
        tool_map = {
            "rag": RAGTool,
            "calculator": CalculatorTool,
            "api_call": APICallTool,
            "database_query": DatabaseQueryTool,
            "web_search": WebSearchTool
        }
        return tool_map.get(tool_type, GenericTool)
    
    def execute_tool(self, tool_id: str, query: str, context: Dict) -> Dict:
        """Execute specific tool with context"""
        if tool_id not in self.tools:
            return {"error": f"Tool {tool_id} not found"}
        
        tool_info = self.tools[tool_id]
        
        # Check tool permissions
        if not self.check_tool_permissions(tool_info["permissions"], context):
            return {"error": "Insufficient permissions for tool"}
        
        try:
            return tool_info["instance"].execute(query, context.get("agent_info"), context.get("permissions"))
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
```

## 8. Message Queue for Document Processing
```python
# PSEUDOCODE - Kafka integration for async document processing
from kafka import KafkaProducer, KafkaConsumer
import json

class DocumentProcessingQueue:
    def __init__(self, bootstrap_servers: List[str]):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
            batch_size=16384,
            linger_ms=10
        )
    
    def queue_document_for_processing(self, document_info: Dict):
        """Queue document for background embedding and indexing"""
        message = {
            "document_path": document_info["path"],
            "department": document_info["department"],
            "collection_target": document_info.get("collection", "auto"),
            "processing_priority": document_info.get("priority", "normal"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.producer.send('document_processing', message)
    
    def consume_and_process_documents(self):
        """Consumer worker for document processing"""
        consumer = KafkaConsumer(
            'document_processing',
            bootstrap_servers=self.bootstrap_servers,
            group_id='document_processors',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=True
        )
        
        document_processor = DocumentProcessor()
        embedding_service = EmbeddingService()
        
        for message in consumer:
            doc_info = message.value
            
            try:
                # Process document with Docling/Unstructured
                chunks = document_processor.process_document(
                    doc_info["document_path"],
                    doc_info["department"]
                )
                
                # Generate embeddings
                embeddings = embedding_service.encode_documents(
                    [chunk["text"] for chunk in chunks]
                )
                
                # Store in appropriate Milvus instance
                self.store_embeddings(chunks, embeddings, doc_info)
                
            except Exception as e:
                print(f"Document processing failed: {e}")
```

## 9. Environment Configuration
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/multi_agent_rag

# Milvus Instances  
MILVUS_PUBLIC_URI=http://milvus_public:19530
MILVUS_PRIVATE_URI=http://milvus_private:19530

# Caching
REDIS_URL=redis://localhost:6379
CACHE_TTL=3600

# Message Queue
KAFKA_BROKERS=kafka:9092

# BGE-M3 Configuration
BGE_M3_MODEL=BAAI/bge-m3
BGE_M3_USE_FP16=true
BGE_M3_DEVICE=cuda
BGE_M3_BATCH_SIZE=12
BGE_M3_MAX_LENGTH=8192

# MMR Configuration  
MMR_LAMBDA_DEFAULT=0.5
MMR_TOP_K_DEFAULT=10

# Document Processing
DOCLING_ENABLE_OCR=true
DOCLING_ENABLE_TABLE_STRUCTURE=true
LANGCHAIN_FALLBACK_ENABLED=true
```

## 10. Docker Compose Setup
```yaml
version: '3.8'
services:
  # Dual Milvus setup
  milvus_public:
    image: milvusdb/milvus:v2.6.0
    container_name: milvus_public
    ports:
      - "19530:19530"
    environment:
      - ETCD_ENDPOINTS=etcd:2379
      - MINIO_ADDRESS=minio:9000
    volumes:
      - milvus_public_data:/var/lib/milvus
    
  milvus_private:
    image: milvusdb/milvus:v2.6.0  
    container_name: milvus_private
    ports:
      - "19531:19530"
    environment:
      - ETCD_ENDPOINTS=etcd:2379
      - MINIO_ADDRESS=minio:9000
    volumes:
      - milvus_private_data:/var/lib/milvus
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  kafka:
    image: confluentinc/cp-kafka:latest
    ports:
      - "9092:9092"
    environment:
      - KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092
      - KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
  
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=multi_agent_rag
      - POSTGRES_USER=user  
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  milvus_public_data:
  milvus_private_data:
  redis_data:
  postgres_data:
```

## 11. Key Features Summary

- **Database-Driven Architecture**: All configurations, agents, tools, and permissions managed via database
- **Dual Milvus Setup**: Separate public/private vector databases for data isolation
- **RAG as Tool**: RAG functionality implemented as one tool among many, not as a standalone agent
- **Document Processing Pipeline**: Docling primary with LangChain Unstructured fallback
- **BGE-M3 Multi-Modal Embeddings**: Dense, sparse, and multi-vector embeddings for hybrid search
- **MMR Algorithm**: Maximal Marginal Relevance for diverse and relevant results
- **Permission-Based Access**: Fine-grained access control via database configuration
- **Async Processing**: Kafka-based queue for background document processing
- **Provider Flexibility**: Database-configurable LLM providers per agent
- **Caching Layer**: Redis for high-performance configuration and result caching

> **Implementation Note**: This functional specification provides the architecture and database design. All code examples are pseudocode for illustration purposes and require proper implementation following the referenced documentation.