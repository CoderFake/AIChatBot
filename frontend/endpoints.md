# API Endpoints Documentation

## Overview
This document lists all available API endpoints in the AI ChatBot system, organized by functionality. Each endpoint includes method, path, request/response schemas, and authentication requirements.

## Base URL
```
/api/v1/
```

---

## 🔐 Authentication Endpoints (`auth.py`)

### 1. POST `/auth/login`
**User Login**

**Authentication:** None (public endpoint)

**Request:**
```json
{
  "username": "string",
  "password": "string",
  "tenant_id": "string (optional)"
}
```

**Response:**
```json
{
  "user_id": "string",
  "username": "string",
  "email": "string",
  "full_name": "string (optional)",
  "role": "string",
  "tenant_id": "string (optional)",
  "department_id": "string (optional)",
  "is_verified": "boolean",
  "last_login": "string (optional)",
  "first_login": "boolean",
  "access_token": "string",
  "refresh_token": "string"
}
```

### 2. POST `/auth/refresh-token`
**Refresh Access Token**

**Authentication:** None

**Request:**
```json
{
  "refresh_token": "string"
}
```

**Response:**
```json
{
  "access_token": "string",
  "expires_in": "number"
}
```

### 3. POST `/auth/logout`
**User Logout**

**Authentication:** Bearer token required

**Request:** None

**Response:**
```json
{
  "success": true,
  "detail": "Logged out successfully"
}
```

### 4. POST `/auth/maintainer/invite`
**Maintainer Invites Tenant Admins**

**Authentication:** MAINTAINER role required

**Request:**
```json
{
  "tenant_id": "string",
  "emails": ["string"]
}
```

**Response:**
```json
{
  "links": ["string"]
}
```

### 5. POST `/auth/validate-invite-token`
**Validate Invite Token**

**Authentication:** None

**Request:**
```json
{
  "token": "string"
}
```

**Response:**
```json
{
  "email": "string",
  "username": "string",
  "role": "string",
  "tenant_name": "string",
  "token_type": "string"
}
```

### 6. POST `/auth/accept-invite`
**Accept Invite**

**Authentication:** None

**Request:**
```json
{
  "token": "string",
  "new_password": "string"
}
```

**Response:**
```json
{
  "success": true,
  "detail": "Invite accepted"
}
```

### 7. POST `/auth/forgot-password`
**Request Password Reset**

**Authentication:** None

**Request:**
```json
{
  "username_or_email": "string",
  "tenant_id": "string (optional)"
}
```

**Response:**
```json
{
  "success": true,
  "detail": "If account exists, an email has been sent"
}
```

### 8. POST `/auth/reset-password`
**Reset Password**

**Authentication:** None

**Request:**
```json
{
  "token": "string",
  "new_password": "string"
}
```

**Response:**
```json
{
  "success": true,
  "detail": "Password has been reset"
}
```

### 9. POST `/auth/change-password`
**Change Password**

**Authentication:** Bearer token required

**Request:**
```json
{
  "current_password": "string",
  "new_password": "string",
  "confirm_password": "string"
}
```

**Response:**
```json
{
  "success": true,
  "detail": "Password changed successfully"
}
```

### 10. GET `/auth/me`
**Get Current User Profile**

**Authentication:** Bearer token required

**Request:** None

**Response:**
```json
{
  "user_id": "string",
  "username": "string",
  "email": "string",
  "full_name": "string (optional)",
  "role": "string",
  "tenant_id": "string (optional)",
  "department_id": "string (optional)",
  "is_verified": "boolean",
  "last_login": "string (optional)",
  "created_at": "string (optional)",
  "force_password_change": "boolean (optional)"
}
```

---

## 🏢 Tenant Management Endpoints (`tenants.py`)

### 1. POST `/tenants`
**Create New Tenant**

**Authentication:** MAINTAINER role required

**Request:**
```json
{
  "tenant_name": "string",
  "timezone": "string",
  "locale": "string (optional)",
  "sub_domain": "string (optional)",
  "description": "string (optional)",
  "allowed_providers": ["string"] (optional),
  "allowed_tools": ["string"] (optional)
}
```

**Response:**
```json
{
  "tenant_id": "string",
  "tenant_name": "string",
  "admin_user_id": "string",
  "admin_username": "string",
  "admin_email": "string",
  "setup_status": "string"
}
```

### 2. GET `/tenants`
**List Tenants**

**Authentication:** MAINTAINER role required

**Query Parameters:**
- `page`: integer (default: 1)
- `limit`: integer (default: 20)
- `is_active`: boolean (optional)

**Response:**
```json
{
  "tenants": [
    {
      "id": "string",
      "tenant_name": "string",
      "timezone": "string",
      "locale": "string",
      "sub_domain": "string (optional)",
      "is_active": "boolean",
      "description": "string (optional)",
      "created_at": "string",
      "updated_at": "string (optional)"
    }
  ],
  "total": "integer",
  "page": "integer",
  "limit": "integer",
  "has_more": "boolean"
}
```

### 3. GET `/tenants/{tenant_id}/public-info`
**Get Public Tenant Info**

**Authentication:** None (public endpoint)

**Response:**
```json
{
  "id": "string",
  "tenant_name": "string",
  "locale": "string",
  "is_active": "boolean",
  "description": "string (optional)",
  "sub_domain": "string (optional)",
  "logo_url": "string (optional)",
  "primary_color": "string (optional)"
}
```

### 4. GET `/tenants/{tenant_id}`
**Get Tenant Detail**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "id": "string",
  "tenant_id": "string",
  "tenant_name": "string",
  "timezone": "string",
  "locale": "string",
  "sub_domain": "string (optional)",
  "is_active": "boolean",
  "description": "string (optional)",
  "created_at": "string",
  "updated_at": "string (optional)",
  "status": "string (optional)",
  "admin_count": "integer (optional)",
  "user_count": "integer (optional)",
  "is_deleted": "boolean (optional)",
  "deleted_at": "string (optional)",
  "version": "string (optional)",
  "settings": "object (optional)"
}
```

### 5. PUT `/tenants/{tenant_id}`
**Update Tenant**

**Authentication:** ADMIN role required (own tenant) or MAINTAINER

**Request:**
```json
{
  "tenant_name": "string (optional)",
  "timezone": "string (optional)",
  "locale": "string (optional)",
  "sub_domain": "string (optional)",
  "description": "string (optional)",
  "is_active": "boolean (optional)"
}
```

**Response:**
```json
{
  "success": true
}
```

### 6. DELETE `/tenants/{tenant_id}`
**Soft Delete Tenant**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "success": true
}
```

### 7. POST `/tenants/configure-provider`
**Configure Provider for Tenant**

**Authentication:** ADMIN role required (own tenant) or MAINTAINER

**Request:**
- `tenant_id`: string (path)
- `provider_name`: string (body)
- `model_name`: string (body)
- `api_keys`: list[string] (body)
- `provider_model_config`: dict (optional body)

### 8. POST `/tenants/setup-workflow-agent`
**Setup Workflow Agent**

**Authentication:** ADMIN role required (own tenant) or MAINTAINER

**Request:**
- `tenant_id`: string (path)
- `provider_name`: string (body)
- `model_name`: string (body)
- `provider_model_config`: dict (optional body)

### 9. POST `/tenants/enable-tools`
**Enable Tools for Tenant**

**Authentication:** ADMIN role required (own tenant) or MAINTAINER

**Request:**
- `tenant_id`: string (path)

### 10. POST `/tenants/departments/{department_id}/enable-tools`
**Enable Tools for Department**

**Authentication:** ADMIN or DEPT_ADMIN role required

**Request:**
- `department_id`: string (path)

### 11. POST `/tenants/complete-setup`
**Complete Tenant Setup**

**Authentication:** ADMIN role required (own tenant) or MAINTAINER

**Request:**
- `tenant_id`: string (body)
- `provider_name`: string (body)
- `model_name`: string (body)
- `api_keys`: list[string] (body)
- `provider_model_config`: dict (optional body)

**Response:**
```json
{
  "success": true,
  "tenant_id": "string",
  "setup_completed": true,
  "provider_config": "object",
  "workflow_agent": "object",
  "enabled_tools": "object",
  "orchestrator_ready": true
}
```

### 12. POST `/tenants/invite-department-admins`
**Invite Department Admins**

**Authentication:** ADMIN role required

**Request:**
- `department_id`: string (body)
- `emails`: list[string] (body)

**Response:**
```json
{
  "success": true,
  "message": "string",
  "invite_links": ["string"]
}
```

### 13. POST `/tenants/invite-department-managers`
**Invite Department Managers**

**Authentication:** At least DEPT_ADMIN role required

**Request:**
- `department_id`: string (body)
- `emails`: list[string] (body)

**Response:**
```json
{
  "success": true,
  "message": "string",
  "invite_links": ["string"]
}
```

### 14. POST `/tenants/invite-users`
**Invite Users**

**Authentication:** At least DEPT_MANAGER role required

**Request:**
- `department_id`: string (body)
- `emails`: list[string] (body)

**Response:**
```json
{
  "success": true,
  "message": "string",
  "invite_links": ["string"]
}
```

---

## 🏥 Health Check Endpoints (`health.py`)

### 1. GET `/health`
**Basic Health Check**

**Authentication:** None

**Response:**
```json
{
  "status": "healthy",
  "service": "string",
  "version": "string",
  "environment": "string",
  "framework": "FastAPI",
  "timestamp": "number"
}
```

### 2. GET `/health/ready`
**Readiness Check**

**Authentication:** None

**Response:**
```json
{
  "status": "ready",
  "timestamp": "number"
}
```

### 3. GET `/health/live`
**Liveness Check**

**Authentication:** None

**Response:**
```json
{
  "status": "alive",
  "timestamp": "number"
}
```

---

## 👑 Tenant Admin Endpoints (`tenant_admin.py`)

### 1. GET `/tenant-admin/workflow-agent`
**Get Workflow Agent Config**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "id": "string",
  "tenant_id": "string",
  "provider_name": "string",
  "model_name": "string",
  "model_configuration": "object",
  "max_iterations": "integer",
  "timeout_seconds": "integer",
  "confidence_threshold": "number",
  "is_active": "boolean"
}
```

### 2. POST `/tenant-admin/workflow-agent`
**Create or Update Workflow Agent**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "provider_name": "string",
  "model_name": "string",
  "model_configuration": "object (optional)",
  "max_iterations": "integer (optional)",
  "timeout_seconds": "integer (optional)",
  "confidence_threshold": "number (optional)"
}
```

**Response:** Same as GET response

### 3. GET `/tenant-admin/settings`
**Get Tenant Settings**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "tenant_name": "string",
  "description": "string (optional)",
  "timezone": "string",
  "locale": "string",
  "chatbot_name": "string (optional)",
  "logo_url": "string (optional)"
}
```

### 4. PUT `/tenant-admin/settings`
**Update Tenant Settings**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "tenant_name": "string (optional)",
  "description": "string (optional)",
  "timezone": "string (optional)",
  "locale": "string (optional)",
  "chatbot_name": "string (optional)",
  "logo_url": "string (optional)"
}
```

**Response:** Same as GET response

### 5. GET `/tenant-admin/departments`
**List Departments**

**Authentication:** At least ADMIN role required

**Response:**
```json
[
  {
    "id": "string",
    "department_name": "string",
    "description": "string (optional)",
    "is_active": "boolean",
    "agent_count": "integer",
    "user_count": "integer"
  }
]
```

### 6. POST `/tenant-admin/departments`
**Create Department with Agent**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "department_name": "string",
  "description": "string (optional)"
}
```

**Response:** Department object

### 7. GET `/tenant-admin/departments/{department_id}`
**Get Department**

**Authentication:** At least ADMIN role required

**Response:** Department object

### 8. PUT `/tenant-admin/departments/{department_id}`
**Update Department**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "department_name": "string",
  "description": "string (optional)"
}
```

**Response:** Updated department object

### 9. DELETE `/tenant-admin/departments/{department_id}`
**Delete Department**

**Authentication:** ADMIN role required

**Response:**
```json
{
  "success": true,
  "message": "Department deleted successfully"
}
```

### 10. GET `/tenant-admin/agents`
**List Agents**

**Authentication:** At least ADMIN role required

**Query Parameters:**
- `department_id`: string (optional)

**Response:**
```json
[
  {
    "id": "string",
    "agent_name": "string",
    "description": "string",
    "department_id": "string",
    "department_name": "string",
    "provider_id": "string (optional)",
    "model_id": "string (optional)",
    "is_enabled": "boolean",
    "is_system": "boolean"
  }
]
```

### 11. POST `/tenant-admin/agents`
**Create Agent**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "agent_name": "string",
  "description": "string",
  "department_id": "string",
  "provider_id": "string (optional)",
  "model_id": "string (optional)"
}
```

**Response:** Agent object

### 12. GET `/tenant-admin/agents/{agent_id}`
**Get Agent**

**Authentication:** At least ADMIN role required

**Response:** Agent object

### 13. PUT `/tenant-admin/agents/{agent_id}`
**Update Agent**

**Authentication:** At least ADMIN role required

**Request:** Same as create

**Response:** Updated agent object

### 14. DELETE `/tenant-admin/agents/{agent_id}`
**Delete Agent**

**Authentication:** ADMIN role required

**Response:**
```json
{
  "success": true,
  "message": "Agent deleted successfully"
}
```

### 15. GET `/tenant-admin/tools`
**List Tenant Tools**

**Authentication:** At least ADMIN role required

**Response:**
```json
[
  {
    "id": "string",
    "tool_name": "string",
    "description": "string (optional)",
    "category": "string",
    "is_enabled": "boolean",
    "is_system": "boolean",
    "access_level": "string"
  }
]
```

### 16. POST `/tenant-admin/tools/{tool_id}/enable`
**Enable Tool for Tenant**

**Authentication:** At least ADMIN role required

**Query Parameters:**
- `is_enabled`: boolean (default: true)

**Response:**
```json
{
  "success": true,
  "message": "Tool enabled/disabled successfully"
}
```

### 17. POST `/tenant-admin/departments/{department_id}/tools/{tool_id}/enable`
**Enable Tool for Department**

**Authentication:** At least ADMIN role required

**Query Parameters:**
- `is_enabled`: boolean (default: true)
- `access_level_override`: string (optional)

**Response:**
```json
{
  "success": true,
  "message": "Tool enabled/disabled for department successfully"
}
```

---

## 👥 User Management Endpoints (`users.py`)

### 1. GET `/users`
**List Users**

**Authentication:** At least ADMIN role required

**Query Parameters:**
- `tenant_id`: string (optional, auto-filtered for non-maintainers)
- `department_id`: string (optional)
- `is_active`: boolean (optional)
- `page`: integer (default: 1)
- `limit`: integer (default: 20)
- `search`: string (optional, search by username/email/full name)

**Response:**
```json
{
  "users": [
    {
      "id": "string",
      "username": "string",
      "email": "string",
      "full_name": "string (optional)",
      "role": "string",
      "tenant_id": "string (optional)",
      "department_id": "string (optional)",
      "is_active": "boolean",
      "is_verified": "boolean",
      "last_login": "string (optional)",
      "created_at": "string (optional)"
    }
  ],
  "total": "integer",
  "page": "integer",
  "limit": "integer",
  "has_more": "boolean"
}
```

### 2. GET `/users/{user_id}`
**Get User Details**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "full_name": "string (optional)",
  "role": "string",
  "tenant_id": "string (optional)",
  "department_id": "string (optional)",
  "is_active": "boolean",
  "is_verified": "boolean",
  "last_login": "string (optional)",
  "created_at": "string (optional)"
}
```

---

## 👤 Department Management Endpoints (`departments.py`)

### 1. GET `/departments`
**List Departments**

**Authentication:** At least ADMIN role required

**Query Parameters:**
- `tenant_id`: string (optional)
- `department_name`: string (optional)

**Response:**
```json
{
  "departments": [
    {
      "id": "string",
      "name": "string",
      "tenant_id": "string",
      "created_at": "string",
      "updated_at": "string",
      "agent_count": "integer",
      "user_count": "integer"
    }
  ],
  "total": "integer"
}
```

### 2. GET `/departments/{department_id}`
**Get Department Details**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "department": {
    "id": "string",
    "name": "string",
    "tenant_id": "string",
    "created_at": "string",
    "updated_at": "string",
    "agents": ["object"],
    "users": ["object"]
  }
}
```

### 3. PUT `/departments/{department_id}`
**Update Department**

**Authentication:** At least ADMIN role required

**Request:**
- `department_name`: string (body)

**Response:**
```json
{
  "success": true,
  "message": "string"
}
```

### 4. DELETE `/departments/{department_id}`
**Delete Department**

**Authentication:** At least ADMIN role required

**Query Parameters:**
- `cascade`: boolean (default: true)

**Response:**
```json
{
  "success": true,
  "message": "string"
}
```

### 5. POST `/departments/agents`
**Create Agent for Department**

**Authentication:** At least ADMIN role required

**Request:**
- `department_id`: string (body)
- `agent_name`: string (body)
- `description`: string (body)
- `provider_id`: string (optional body)
- `model_id`: string (optional body)

**Response:**
```json
{
  "agent": {
    "id": "string",
    "name": "string",
    "description": "string",
    "department_id": "string",
    "is_enabled": "boolean"
  }
}
```

### 6. GET `/departments/{department_id}/agents`
**List Agents in Department**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "agents": ["object"],
  "total": "integer",
  "department_id": "string"
}
```

---

## 🤖 Agent Management Endpoints (`agents.py`)

### 1. GET `/agents`
**List All Agents**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "agents": ["object"],
  "total": "integer"
}
```

### 2. GET `/agents/{agent_id}`
**Get Agent Details**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "id": "string",
  "agent_name": "string",
  "provider_id": "string",
  "model_name": "string",
  "description": "string (optional)",
  "config": "object (optional)",
  "is_active": "boolean",
  "tenant_id": "string (optional)",
  "created_at": "string",
  "updated_at": "string"
}
```

### 3. PUT `/agents/{agent_id}`
**Update Agent**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "agent_name": "string (optional)",
  "provider_id": "string (optional)",
  "model_name": "string (optional)",
  "description": "string (optional)",
  "config": "object (optional)"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Agent updated successfully"
}
```

### 4. DELETE `/agents/{agent_id}`
**Delete Agent**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "success": true,
  "message": "Agent deleted successfully with cascade"
}
```

### 5. POST `/agents/{agent_id}/tenants/{tenant_id}`
**Assign Agent to Tenant**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "success": true,
  "message": "Agent assigned to tenant successfully"
}
```

### 6. DELETE `/agents/{agent_id}/tenants/{tenant_id}`
**Remove Agent from Tenant**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "success": true,
  "message": "Agent removed from tenant successfully"
}
```

### 7. GET `/agents/tenants/{tenant_id}`
**List Agents for Tenant**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "agents": ["object"],
  "total": "integer"
}
```

---

## 💬 Chat Endpoints (`chat.py`)

### 1. POST `/chat/create-session`
**Create Chat Session**

**Authentication:** Bearer token required

**Request:**
- `title`: string (optional body)

**Response:**
```json
{
  "session_id": "string",
  "title": "string",
  "created_at": "string",
  "is_anonymous": "boolean"
}
```

### 2. GET `/chat/sessions`
**Get Chat Sessions**

**Authentication:** Bearer token required

**Query Parameters:**
- `skip`: integer (default: 0)
- `limit`: integer (default: 20)

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "string",
      "title": "string",
      "created_at": "string",
      "updated_at": "string",
      "message_count": "integer",
      "is_active": "boolean"
    }
  ],
  "total": "integer"
}
```

### 3. GET `/chat/sessions/{session_id}/messages`
**Get Session Messages**

**Authentication:** Bearer token required

**Query Parameters:**
- `skip`: integer (default: 0)
- `limit`: integer (default: 50)

**Response:**
```json
{
  "messages": [
    {
      "id": "string",
      "session_id": "string",
      "role": "string",
      "content": "string",
      "created_at": "string"
    }
  ],
  "total": "integer",
  "session_id": "string"
}
```

### 4. POST `/chat/query`
**Chat Query with Streaming**

**Authentication:** Bearer token required

**Request:**
```json
{
  "query": "string",
  "session_id": "string (optional)",
  "access_scope": "object (optional)"
}
```

**Response:** Server-Sent Events (SSE) stream with JSON objects:
```json
{
  "type": "start|progress|planning|execution|resolution|final_result|error|complete",
  "message": "string",
  "progress": "number",
  "status": "string",
  "node": "string (optional)",
  "planning_data": "object (optional)",
  "execution_data": "object (optional)",
  "resolution_data": "object (optional)",
  "final_data": "object (optional)",
  "error_data": "object (optional)"
}
```

### 5. GET `/chat/health`
**Chat Health Check**

**Authentication:** None

**Response:**
```json
{
  "status": "healthy|unhealthy",
  "workflow_initialized": "boolean",
  "service": "chat",
  "error": "string (optional)"
}
```

---

## 📄 Document Management Endpoints (`documents.py`)

### 1. POST `/documents/upload`
**Upload Document**

**Authentication:** Bearer token required

**Request (Form Data):**
- `file`: File (required)
- `collection_name`: string (required)
- `access_level`: "public" or "private" (required)
- `folder_id`: string (optional)
- `user_context`: auto-injected

**Response:**
```json
{
  "success": true,
  "document_id": "string",
  "file_name": "string",
  "bucket": "string",
  "storage_key": "string",
  "chunks": "integer",
  "collection": "string",
  "access_level": "string"
}
```

### 2. GET `/documents/collections`
**Get Department Collections**

**Authentication:** Bearer token required

**Query Parameters:**
- `department_name`: string (required)

**Response:**
```json
{
  "department": "string",
  "public_access": "object",
  "private_access": "object",
  "accessible_collections": ["string"],
  "public_collections": ["string"],
  "private_collections": ["string"]
}
```

### 3. POST `/documents/folders`
**Create Folder**

**Authentication:** Bearer token required

**Request (Form Data):**
- `folder_name`: string (required)
- `parent_folder_id`: string (optional)

**Response:**
```json
{
  "success": true,
  "folder": "object"
}
```

### 4. GET `/documents/tree`
**Get Folder Tree**

**Authentication:** Bearer token required

**Query Parameters:**
- `folder_id`: string (optional)
- `access_level`: "public" or "private" or null (optional)

**Response:** Folder tree structure

### 5. GET `/documents/tree/public`
**Get Public Folder Tree**

**Authentication:** Bearer token required

**Query Parameters:**
- `folder_id`: string (optional)

**Response:** Public folder tree structure

### 6. GET `/documents/tree/private`
**Get Private Folder Tree**

**Authentication:** Bearer token required

**Query Parameters:**
- `folder_id`: string (optional)

**Response:** Private folder tree structure

---

## 🔧 Provider Management Endpoints (`providers.py`)

### 1. GET `/providers`
**List Providers by Role**

**Authentication:** At least DEPT_ADMIN role required

**Query Parameters:**
- `tenant_id`: string (optional)
- `department_id`: string (optional)

**Response:**
```json
{
  "providers": ["object"],
  "context": "object"
}
```

### 2. GET `/providers/available`
**Get Available Providers**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "providers": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "type": "string",
      "is_enabled": "boolean"
    }
  ]
}
```

### 3. POST `/providers/{provider_id}/tenants/{tenant_id}`
**Configure Provider for Tenant**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "is_enabled": "boolean",
  "api_keys": "object (optional)",
  "provider_config": "object (optional)"
}
```

**Response:**
```json
{
  "status": "success",
  "provider_id": "string",
  "tenant_id": "string"
}
```

### 4. GET `/providers/tenants/{tenant_id}`
**List Tenant Providers**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "providers": ["object"],
  "context": "object"
}
```

### 5. GET `/providers/{provider_id}/models`
**Get Provider Models**

**Authentication:** At least DEPT_ADMIN role required

**Response:**
```json
{
  "models": ["object"],
  "provider_id": "string"
}
```

### 6. PUT `/providers/maintainer/{provider_id}`
**Update Provider (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Request:** Provider update data

**Response:**
```json
{
  "status": "updated",
  "provider_id": "string"
}
```

### 7. POST `/providers/maintainer/{provider_id}/tenants/{tenant_id}/enable`
**Enable Provider for Tenant (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Request:**
```json
{
  "is_enabled": "boolean",
  "api_keys": "object (optional)",
  "provider_config": "object (optional)"
}
```

**Response:**
```json
{
  "status": "success",
  "provider_id": "string",
  "tenant_id": "string"
}
```

### 8. DELETE `/providers/maintainer/{provider_id}/tenants/{tenant_id}`
**Remove Provider from Tenant (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "status": "removed",
  "provider_id": "string",
  "tenant_id": "string"
}
```

---

## 🛠️ Tool Management Endpoints (`tools.py`)

### 1. GET `/tools/available`
**List Tools by Role**

**Authentication:** At least DEPT_ADMIN role required

**Query Parameters:**
- `tenant_id`: string (optional)
- `department_id`: string (optional)

**Response:**
```json
{
  "tools": ["object"],
  "context": "object"
}
```

### 2. POST `/tools/{tool_id}/tenants/{tenant_id}`
**Configure Tool for Tenant**

**Authentication:** At least ADMIN role required

**Request:**
```json
{
  "is_enabled": "boolean",
  "config_data": "object (optional)"
}
```

**Response:**
```json
{
  "status": "success",
  "tool_id": "string",
  "tenant_id": "string"
}
```

### 3. GET `/tools/tenants/{tenant_id}`
**List Tenant Tools**

**Authentication:** At least ADMIN role required

**Response:**
```json
{
  "tools": ["object"],
  "context": "object"
}
```

### 4. POST `/tools/maintainer`
**Create Tool (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Request:**
```json
{
  "tool_name": "string",
  "description": "string",
  "tool_type": "string",
  "config_schema": "object (optional)",
  "is_system": "boolean (optional)"
}
```

**Response:**
```json
{
  "tool": "object",
  "status": "created"
}
```

### 5. PUT `/tools/maintainer/{tool_id}`
**Update Tool (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Request:** Tool update data

**Response:**
```json
{
  "status": "updated",
  "tool_id": "string"
}
```

### 6. DELETE `/tools/maintainer/{tool_id}`
**Delete Tool (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "status": "deleted",
  "tool_id": "string"
}
```

### 7. POST `/tools/maintainer/{tool_id}/tenants/{tenant_id}/enable`
**Enable Tool for Tenant (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Request:**
```json
{
  "is_enabled": "boolean",
  "config_data": "object (optional)"
}
```

**Response:**
```json
{
  "status": "success",
  "tool_id": "string",
  "tenant_id": "string"
}
```

### 8. DELETE `/tools/maintainer/{tool_id}/tenants/{tenant_id}`
**Remove Tool from Tenant (MAINTAINER)**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "status": "removed",
  "tool_id": "string",
  "tenant_id": "string"
}
```

---

## 🔧 Other Utility Endpoints (`others.py`)

### 1. GET `/others/timezones`
**Get Supported Timezones**

**Authentication:** None

**Response:**
```json
{
  "groups": [
    {
      "region": "string",
      "timezones": [
        {
          "value": "string",
          "label": "string",
          "country": "string"
        }
      ]
    }
  ],
  "total_timezones": "integer"
}
```

### 2. GET `/others/locales`
**Get Supported Languages**

**Authentication:** None

**Response:**
```json
{
  "languages": ["vi", "en", "kr", "ja"],
  "default_language": "en"
}
```

---

## 👑 Maintainer-Only Endpoints (`maintainer.py`)

### 1. GET `/maintainer/stats`
**Get System Statistics**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "total_tenants": "integer",
  "total_users": "integer",
  "total_agents": "integer",
  "total_tools": "integer",
  "active_sessions": "integer",
  "system_health": "string",
  "timestamp": "string"
}
```

### 2. GET `/maintainer/audit-logs`
**Get Audit Logs**

**Authentication:** MAINTAINER role required

**Query Parameters:**
- `tenant_id`: string (optional)
- `user_id`: string (optional)
- `action`: string (optional)
- `limit`: integer (default: 50)
- `offset`: integer (default: 0)

**Response:**
```json
{
  "logs": [
    {
      "id": "string",
      "timestamp": "string",
      "user_id": "string",
      "user_email": "string",
      "tenant_id": "string (optional)",
      "tenant_name": "string (optional)",
      "action": "string",
      "resource_type": "string",
      "resource_id": "string",
      "details": "object",
      "ip_address": "string",
      "user_agent": "string"
    }
  ],
  "total": "integer",
  "limit": "integer",
  "offset": "integer"
}
```

### 3. GET `/maintainer/tenants/{tenant_id}/usage`
**Get Tenant Usage Statistics**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "tenant_id": "string",
  "tenant_name": "string",
  "user_count": "integer",
  "department_count": "integer",
  "agent_count": "integer",
  "configured_tools_count": "integer",
  "created_at": "string (optional)",
  "last_updated": "string (optional)"
}
```

### 4. GET `/maintainer/health/detailed`
**Get Detailed System Health**

**Authentication:** MAINTAINER role required

**Response:**
```json
{
  "database": {
    "status": "string",
    "connection": "string"
  },
  "resources": {
    "tenants": "integer",
    "users": "integer",
    "agents": "integer",
    "tools": "integer",
    "providers": "integer"
  },
  "workflows": {
    "total": "integer",
    "active": "integer",
    "inactive": "integer"
  },
  "system_load": {
    "cpu_percent": "number",
    "memory_percent": "number",
    "disk_percent": "number"
  },
  "overall_status": "string"
}
```

---

## Authentication Levels

### Role Hierarchy (from lowest to highest):
- **USER**: Basic user access
- **DEPT_MANAGER**: Department manager
- **DEPT_ADMIN**: Department admin
- **ADMIN**: Tenant admin
- **MAINTAINER**: System maintainer (highest level)

### Public Endpoints (no authentication required):
- `POST /auth/login`
- `POST /auth/refresh-token`
- `POST /auth/validate-invite-token`
- `POST /auth/accept-invite`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /tenants/{tenant_id}/public-info`
- `GET /health*`
- `GET /others/*`

### Notes:
- All endpoints require proper authentication unless marked as public
- Role-based access control is enforced via middleware
- Bearer tokens are used for API authentication
- Some endpoints support both path-based and subdomain-based tenant identification
- SSE (Server-Sent Events) is used for real-time chat streaming
- File uploads use multipart/form-data encoding
