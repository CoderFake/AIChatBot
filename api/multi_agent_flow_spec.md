# Multi-Agent Flow Complete Specification

## Tổng quan kiến trúc

Hệ thống Multi-Agent RAG Flow là một workflow phức hợp sử dụng LangGraph để điều phối và thực thi các tác vụ thông qua nhiều agent chuyên biệt. Workflow này bao gồm các giai đoạn: phân tích query, semantic routing, thực thi agent song song và giải quyết conflict.

## 1. Flow Architecture

### 1.1 Input Structure

```json
{
  "query": "giá trị cốt lõi, muộn có ảnh hưởng đến giá trị nào không",
  "history_chat": [
    {
      "role": "user",
      "content": "...",
      "timestamp": "DYNAMIC_TIMESTAMP_PLACEHOLDER"
    }
  ],
  "user_context": {
    "user_id": "uuid",
    "tenant_id": "uuid",
    "permissions": ["public", "private"],
    "department": "hr"
  },
  "agents": {
    "hr": {
      "desc": "chuyên lĩnh vực chấm công, đi muộn, tiền lương,...",
      "tools": [
        {"name": "rag_tool", "description": "tìm kiếm thông tin, truy xuất"},
        {"name": "summary_tool", "description": "tổng hợp thông tin"},
        {"name": "math_tool", "description": "tính toán thông tin"}
      ]
    },
    "it": {
      "desc": "chuyên lĩnh vực xử lý lỗi, sự cố bảo mật,...",
      "tools": [
        {"name": "rag_tool", "description": "tìm kiếm thông tin, truy xuất"},
        {"name": "log_tool", "description": "tổng hợp thông tin log của công ty"},
        {"name": "math_tool", "description": "tính toán thông tin"}
      ]
    },
    "general": {
      "desc": "tổng quát, xử lý các câu hỏi không thuộc domain cụ thể",
      "tools": [
        {"name": "rag_tool", "description": "tìm kiếm thông tin chung"}
      ]
    }
  }
}
```

### 1.2 Workflow Nodes

#### Node 1: Orchestrator
- **Chức năng**: Phân tích độ phức tạp của query, quyết định workflow path
- **Input**: Raw query, user context, chat history
- **Output**: Routing decision (reflection_router hoặc agent_execution)

#### Node 2: Reflection Semantic Router
- **Chức năng**: Phân tích sâu query, xác định agent và tool cần thiết
- **Input**: Query đã được orchestrator phân loại
- **Output**: Semantic routing structure (như bên dưới)

#### Node 3: Agent Execution
- **Chức năng**: Thực thi song song các agent với tool tương ứng
- **Input**: Semantic routing structure
- **Output**: Kết quả từ từng agent

#### Node 4: Conflict Resolution
- **Chức năng**: Giải quyết xung đột, ưu tiên kết quả
- **Input**: Tất cả kết quả từ agents
- **Output**: Final consolidated result

#### Node 5: Final Response
- **Chức năng**: Format câu trả lời cuối cùng
- **Input**: Resolved result
- **Output**: Structured final response

## 2. Semantic Routing Structure

### 2.1 Phân loại Query

**Không phải chitchat:**
```json
{
  "original_query": "giá trị cốt lõi, muộn có ảnh hưởng đến giá trị nào không",
  "refined_query": "Công ty có bao nhiêu giá trị cốt lõi, và việc đi muộn có ảnh hưởng đến giá trị nào không?",
  "agents": {
    "general": {
      "queries": [
        {"1": "Giá trị cốt lõi của công ty là gì?"}
      ],
      "tools": ["rag_tool"]
    },
    "hr": {
      "queries": [
        {"1": "Đi muộn có những ảnh hưởng gì đến công việc và quy định công ty?"},
        {"2": "Hậu quả hoặc vấn đề khi nhân viên đi muộn"}
      ],
      "tools": ["rag_tool", "summary_tool"]
    }
  },
  "permission": {
    "user_access": ["public", "private"]
  },
  "execution_flow": {
    "planning": {
      "tasks": [
        {
          "1": [
            {
              "agent": "general",
              "tool": "rag_tool",
              "message": "Truy vấn giá trị cốt lõi từ chung",
              "status": "pending"
            },
            {
              "agent": "hr",
              "tool": "rag_tool",
              "message": "Truy vấn nội quy và ảnh hưởng khi đi muộn",
              "status": "pending"
            }
          ],
          "2": [
            {
              "agent": "hr",
              "tool": "rag_tool",
              "message": "Truy vấn hậu quả/vấn đề khi nhân viên đi muộn",
              "status": "pending"
            },
            {
              "agent": "hr",
              "tool": "summary_tool",
              "message": "Tóm tắt ảnh hưởng tổng hợp từ kết quả",
              "status": "pending"
            }
          ],
          "3": [
            {
              "agent": "orchestrator",
              "tool": "summary_tool",
              "message": "Tổng hợp và phản hồi câu hỏi",
              "status": "pending"
            }
          ]
        }
      ],
      "aggregate_status": "pending"
    },
    "conflict_resolution": "So sánh kết quả giữa agents; ưu tiên HR khi liên quan quy định nội bộ"
  }
}
```

**Chitchat:**
```json
{
  "refined_query": "",
  "is_chitchat": true,
  "chitchat_response": "Xin chào! Tôi có thể giúp gì cho bạn?"
}
```

## 3. Agent Output Structure

### 3.1 General Agent Output
```json
{
  "agent": "general",
  "queries": [
    {
      "index": 1,
      "query": "Giá trị cốt lõi của công ty là gì?",
      "context": "Trích xuất từ wiki nội bộ và trang giới thiệu công ty.",
      "answer": "Công ty có 4 giá trị cốt lõi: Khách hàng trước tiên, Chính trực, Hợp tác, Kỷ luật.",
      "evidence": [
        {
          "url": "https://intra.company/about/core-values",
          "created_at": "2025-06-10T08:00:00Z",
          "source_type": "rag",
          "scope": "private",
          "relevance_score": 0.95
        }
      ]
    }
  ],
  "tool_trace": [
    {"tool": "rag_tool", "status": "ok", "duration_ms": 97}
  ]
}
```

### 3.2 HR Agent Output
```json
{
  "agent": "hr",
  "queries": [
    {
      "index": 1,
      "query": "Đi muộn có những ảnh hưởng gì đến công việc và quy định công ty?",
      "context": "Trích xuất từ nội quy lao động và chính sách nhân sự",
      "answer": "Đi muộn thường ảnh hưởng đến đánh giá KPI, gây gián đoạn nhóm, và có thể bị cảnh báo nội bộ.",
      "evidence": [
        {
          "url": "https://intra.company/policies/punctuality",
          "created_at": "2025-08-20T03:12:45Z",
          "source_type": "rag",
          "scope": "private",
          "relevance_score": 0.92
        }
      ]
    },
    {
      "index": 2,
      "query": "Hậu quả hoặc vấn đề khi nhân viên đi muộn",
      "context": "Quy định kỷ luật và xử phạt vi phạm",
      "answer": "Có thể bị khiển trách, ảnh hưởng đến xét thưởng, hoặc bị ghi nhận kỷ luật nếu tái phạm.",
      "evidence": [
        {
          "url": "https://intra.company/hr/discipline",
          "created_at": "2025-07-02T10:05:00Z",
          "source_type": "rag",
          "scope": "private",
          "relevance_score": 0.88
        }
      ]
    }
  ],
  "tool_trace": [
    {"tool": "rag_tool", "status": "ok", "duration_ms": 143},
    {"tool": "summary_tool", "status": "ok", "duration_ms": 55}
  ]
}
```

## 4. Conflict Resolution

### 4.1 Resolution Rules

```json
{
  "conflict_resolution_rules": {
    "priority_by_domain": {
      "hr_policies": "hr_agent",
      "it_security": "it_agent", 
      "general_knowledge": "general_agent"
    },
    "priority_by_scope": {
      "private": 0.9,
      "internal": 0.7,
      "public": 0.5
    },
    "priority_by_recency": {
      "within_30_days": 0.9,
      "within_90_days": 0.7,
      "older": 0.5
    },
    "resolution_strategy": "weighted_scoring"
  }
}
```

### 4.2 Conflict Resolution Process
1. **Domain Matching**: Ưu tiên agent chuyên domain
2. **Scope Priority**: Private > Internal > Public
3. **Recency Weight**: Thông tin mới hơn được ưu tiên
4. **Relevance Score**: Điểm relevance cao hơn được ưu tiên
5. **Combined Scoring**: Tổng hợp tất cả factors

## 5. Final Output Structure

```json
{
  "answer": "Công ty có 4 giá trị cốt lõi. Việc đi muộn ảnh hưởng trực tiếp đến giá trị Kỷ luật và Trách nhiệm, đồng thời có thể tác động đến đánh giá KPI và khen thưởng.",
  "evidence": [
    {
      "url": "https://intra.company/about/core-values",
      "created_at": "2025-06-10T08:00:00Z",
      "source_type": "rag",
      "scope": "private",
      "relevance_score": 0.95
    },
    {
      "url": "https://intra.company/policies/punctuality",
      "created_at": "2025-08-20T03:12:45Z",
      "source_type": "rag",
      "scope": "private",
      "relevance_score": 0.92
    }
  ],
  "reasoning": "Ưu tiên kết quả từ HR (nguồn private, cập nhật mới hơn) khi nội dung liên quan quy định nội bộ.",
  "confidence_score": 0.89,
  "follow_up_questions": [
    "Cụ thể có mấy giá trị cốt lõi?",
    "Giá trị nào quan trọng nhất trong đánh giá hiệu suất?",
    "Nội quy đi muộn định nghĩa thế nào (số phút, số lần)?"
  ],
  "flow_action": [
    {
      "order": 1,
      "node_id": "Router",
      "type": "router",
      "agent": null,
      "tool": null,
      "status": "done",
      "started_at": "2025-09-09T09:00:00Z",
      "ended_at": "2025-09-09T09:00:01Z",
      "metadata": {"decision": "reflection_needed"}
    },
    {
      "order": 2,
      "node_id": "PermissionCheck", 
      "type": "permission",
      "agent": null,
      "tool": null,
      "status": "done",
      "started_at": "2025-09-09T09:00:01Z",
      "ended_at": "2025-09-09T09:00:01Z",
      "details": {"scope": ["public", "private"]}
    },
    {
      "order": 3,
      "node_id": "general#rag",
      "type": "agent_tool",
      "agent": "general",
      "tool": "rag_tool",
      "query_index": 1,
      "status": "done",
      "duration_ms": 97,
      "input_hash": "5b4ae6...",
      "output_hash": "f1c202..."
    },
    {
      "order": 4,
      "node_id": "hr#rag:1",
      "type": "agent_tool", 
      "agent": "hr",
      "tool": "rag_tool",
      "query_index": 1,
      "status": "done",
      "duration_ms": 143
    },
    {
      "order": 5,
      "node_id": "hr#rag:2",
      "type": "agent_tool",
      "agent": "hr", 
      "tool": "rag_tool",
      "query_index": 2,
      "status": "done",
      "duration_ms": 156
    },
    {
      "order": 6,
      "node_id": "hr#summary",
      "type": "agent_tool",
      "agent": "hr",
      "tool": "summary_tool", 
      "status": "done",
      "duration_ms": 55,
      "depends_on": ["hr#rag:1", "hr#rag:2"]
    },
    {
      "order": 7,
      "node_id": "ConflictResolver",
      "type": "resolver",
      "status": "done", 
      "policy": "prefer_hr_if_internal",
      "duration_ms": 21,
      "resolved_conflicts": 2
    },
    {
      "order": 8,
      "node_id": "AnswerFormatter",
      "type": "formatter",
      "status": "done",
      "duration_ms": 10
    }
  ],
  "execution_metadata": {
    "total_duration_ms": 520,
    "agents_invoked": ["general", "hr"],
    "tools_executed": ["rag_tool", "summary_tool"],
    "total_queries": 3,
    "conflict_resolution_applied": true,
    "department_permission_filtering": true,
    "accessible_departments": ["hr", "it", "general"]
  }
}
```

## 6. Error Handling

### 6.1 Error Response Structure

```json
{
  "error": true,
  "error_code": "AGENT_EXECUTION_FAILED",
  "error_message": "HR agent failed to execute rag_tool",
  "partial_results": {
    "general": {
      "status": "success",
      "answer": "Partial answer from general agent"
    },
    "hr": {
      "status": "failed",
      "error": "Tool timeout"
    }
  },
  "fallback_answer": "Dựa trên thông tin có sẵn, công ty có 4 giá trị cốt lõi. Tuy nhiên, không thể truy xuất thông tin chi tiết về ảnh hưởng của việc đi muộn.",
  "flow_action": [
    {
      "order": 1,
      "node_id": "ErrorHandler",
      "type": "error_handler",
      "status": "handled",
      "error_details": {
        "failed_agent": "hr",
        "failed_tool": "rag_tool", 
        "error_type": "timeout"
      }
    }
  ]
}
```

## 7. Performance Metrics

### 7.1 Tracking Metrics

```json
{
  "performance_metrics": {
    "query_processing_time_ms": 520,
    "agent_execution_times": {
      "general": 97,
      "hr": 354
    },
    "tool_usage_stats": {
      "rag_tool": {"calls": 3, "avg_time_ms": 132},
      "summary_tool": {"calls": 1, "avg_time_ms": 55}
    },
    "conflict_resolution_time_ms": 21,
    "cache_hit_ratio": 0.33,
    "content_quality_metrics": {
      "hr_agent": {
        "completeness": "comprehensive",
        "recency": "within_30_days",
        "domain_match": "perfect"
      },
      "general_agent": {
        "completeness": "partial_with_context", 
        "recency": "within_90_days",
        "domain_match": "general"
      }
    }
  }
}
```

## 8. Configuration & Settings

### 8.1 Workflow Configuration

```json
{
  "workflow_config": {
    "max_concurrent_agents": 5,
    "timeout_per_agent_ms": 30000,
    "max_retries": 3,
    "enable_caching": true,
    "cache_ttl_seconds": 3600,
    "conflict_resolution_threshold": 0.1,
    "min_relevance_score": 0.7,
    "enable_follow_up_questions": true,
    "max_follow_up_questions": 5
  }
}
```

### 8.2 Agent Configuration

```json
{
  "agent_configs": {
    "default_timeout_ms": 30000,
    "max_queries_per_agent": 10,
    "enable_parallel_execution": true,
    "tool_selection_strategy": "relevance_based",
    "output_format": "structured_json"
  }
}
```

## 9. Examples

### 9.1 Detailed Execution Plan Example

**Input Query:** "Tính toán chi phí nghỉ phép và so sánh với chính sách công ty"

**Generated Execution Plan:**
```json
{
  "original_query": "Tính toán chi phí nghỉ phép và so sánh với chính sách công ty",
  "refined_query": "Tính toán chi phí nghỉ phép và so sánh với chính sách công ty",
  "agents": {
    "hr": {
      "queries": [
        {"1": "Tìm chính sách nghỉ phép của công ty"},
        {"2": "Tính toán chi phí nghỉ phép dựa trên lương cơ bản"}
      ],
      "tools": ["rag_tool", "math_tool"],
      "sequential_tools": ["rag_tool", "summary_tool", "math_tool"]
    }
  },
  "execution_flow": {
    "planning": {
      "tasks": [
        {
          "1": [
            {
              "agent": "hr",
              "tool": "rag_tool",
              "purpose": "Tìm kiếm và thu thập thông tin về chính sách nghỉ phép từ cơ sở dữ liệu công ty",
              "message": "Tìm kiếm chính sách nghỉ phép, quyền lợi và quy định liên quan",
              "status": "pending"
            }
          ]
        },
        {
          "2": [
            {
              "agent": "hr",
              "tool": "summary_tool",
              "purpose": "Phân tích và tóm tắt các chính sách đã tìm được để hiểu rõ quyền lợi",
              "message": "Tóm tắt các chính sách nghỉ phép quan trọng và quyền lợi liên quan",
              "status": "pending"
            }
          ]
        },
        {
          "3": [
            {
              "agent": "hr",
              "tool": "math_tool",
              "purpose": "Tính toán chi phí nghỉ phép dựa trên lương và số ngày nghỉ",
              "message": "Tính toán chi phí nghỉ phép dựa trên lương cơ bản và số ngày nghỉ",
              "status": "pending"
            }
          ]
        }
      ],
      "aggregate_status": "pending"
    },
    "conflict_resolution": "Chọn kết quả có độ tin cậy cao nhất và thông tin đầy đủ nhất"
  }
}
```

### 9.2 Stream Output Example

```json
[
  // 1. Plan Ready
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "plan_ready",
      "progress_percentage": 75,
      "progress_message": "Execution plan is ready",
      "plan_summary": {
        "total_tasks": 3,
        "tasks": [
          {
            "step_number": 1,
            "agent": "hr",
            "tool": "rag_tool",
            "purpose": "Tìm kiếm và thu thập thông tin về chính sách nghỉ phép từ cơ sở dữ liệu công ty",
            "message": "Tìm kiếm chính sách nghỉ phép, quyền lợi và quy định liên quan"
          },
          {
            "step_number": 2,
            "agent": "hr",
            "tool": "summary_tool",
            "purpose": "Phân tích và tóm tắt các chính sách đã tìm được để hiểu rõ quyền lợi",
            "message": "Tóm tắt các chính sách nghỉ phép quan trọng và quyền lợi liên quan"
          },
          {
            "step_number": 3,
            "agent": "hr",
            "tool": "math_tool",
            "purpose": "Tính toán chi phí nghỉ phép dựa trên lương và số ngày nghỉ",
            "message": "Tính toán chi phí nghỉ phép dựa trên lương cơ bản và số ngày nghỉ"
          }
        ]
      }
    }
  },

  // 2. Executing Task 1
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "executing_task",
      "progress_percentage": 75,
      "progress_message": "Task 1/3: Tìm kiếm và thu thập thông tin về chính sách nghỉ phép từ cơ sở dữ liệu công ty",
      "current_task": {
        "agent": "hr",
        "tool": "rag_tool",
        "purpose": "Tìm kiếm và thu thập thông tin về chính sách nghỉ phép từ cơ sở dữ liệu công ty"
      }
    }
  },

  // 3. Task 1 Completed
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "task_completed",
      "progress_percentage": 81.7,
      "progress_message": "Completed 1/3: Tìm kiếm và thu thập thông tin về chính sách nghỉ phép từ cơ sở dữ liệu công ty",
      "completed_task": {
        "agent": "hr",
        "tool": "rag_tool",
        "purpose": "Tìm kiếm và thu thập thông tin về chính sách nghỉ phép từ cơ sở dữ liệu công ty",
        "status": "completed"
      }
    }
  },

  // 4. Executing Task 2
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "executing_task",
      "progress_percentage": 81.7,
      "progress_message": "Task 2/3: Phân tích và tóm tắt các chính sách đã tìm được để hiểu rõ quyền lợi",
      "current_task": {
        "agent": "hr",
        "tool": "summary_tool",
        "purpose": "Phân tích và tóm tắt các chính sách đã tìm được để hiểu rõ quyền lợi"
      }
    }
  },

  // 5. Task 2 Completed
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "task_completed",
      "progress_percentage": 88.3,
      "progress_message": "Completed 2/3: Phân tích và tóm tắt các chính sách đã tìm được để hiểu rõ quyền lợi",
      "completed_task": {
        "agent": "hr",
        "tool": "summary_tool",
        "purpose": "Phân tích và tóm tắt các chính sách đã tìm được để hiểu rõ quyền lợi",
        "status": "completed"
      }
    }
  },

  // 6. Executing Task 3
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "executing_task",
      "progress_percentage": 88.3,
      "progress_message": "Task 3/3: Tính toán chi phí nghỉ phép dựa trên lương và số ngày nghỉ",
      "current_task": {
        "agent": "hr",
        "tool": "math_tool",
        "purpose": "Tính toán chi phí nghỉ phép dựa trên lương và số ngày nghỉ"
      }
    }
  },

  // 7. Task 3 Completed
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "task_completed",
      "progress_percentage": 95,
      "progress_message": "Completed 3/3: Tính toán chi phí nghỉ phép dựa trên lương và số ngày nghỉ",
      "completed_task": {
        "agent": "hr",
        "tool": "math_tool",
        "purpose": "Tính toán chi phí nghỉ phép dựa trên lương và số ngày nghỉ",
        "status": "completed"
      }
    }
  },

  // 8. Final Decision
  {
    "node": "execute_planning",
    "output": {
      "processing_status": "ready_for_resolution",
      "progress_percentage": 95,
      "progress_message": "All tasks completed, proceeding to final response",
      "agent_responses": [...]
    }
  }
]
```