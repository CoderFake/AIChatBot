
export interface User {
  id: string
  username: string
  email: string
  first_name?: string
  last_name?: string
  name?: string
  is_active: boolean
  role: UserRole
  tenant_id?: string
  department_id?: string
  permissions: Permission[]
  force_password_change?: boolean
  created_at: string
  updated_at: string
}

export interface Tenant {
  id: string
  tenant_name: string
  tenant_id?: string
  sub_domain?: string
  timezone: string
  locale: string
  description?: string
  status: "active" | "inactive" | "pending" | "suspended"
  is_active: boolean
  created_at: string
  updated_at: string
  admin_count?: number
  user_count?: number
  allowed_providers?: string[]
  allowed_tools?: string[]
  settings?: {
    chatbot?: {
      name?: string
      avatar?: string
      description?: string
    }
    branding?: {
      logo_url?: string
      primary_color?: string

    }

  }
}

export interface Department {
  id: string
  department_name: string
  description?: string
  is_active: boolean
  agent_count?: number
  user_count?: number
  tenant_id: string
  created_at: string
  updated_at: string
  tenant_name?: string

  // Agent details
  agent?: {
    id: string
    agent_name: string
    description: string
    is_enabled: boolean
    provider_id: string
    provider_name: string
    model_id: string
    model_name: string
    created_at: string
  }

  // Tool assignments
  tool_assignments?: {
    tool_id: string
    tool_name: string
    description: string
    status: string
  }[]
}

export interface PublicTenant {
  id: string
  tenant_name: string
  timezone: string
  locale: string
  sub_domain?: string
  description?: string
  created_at: string
  updated_at: string
  chatbot_name?: string
  chatbot_description?: string
  is_active: boolean
  user_count?: number
  department_count?: number
}

export interface Permission {
  id: string
  name: string
  description?: string
  resource: string
  action: string
}

export interface UserGroup {
  id: string
  name: string
  description?: string
  tenant_id: string
  permissions: Permission[]
  users: User[]
}

export interface Agent {
  id: string
  agent_name: string
  description: string
  department_id: string
  department_name: string
  provider_id?: string
  model_id?: string
  is_enabled: boolean
  is_system: boolean
}

export interface Tool {
  id: string
  name: string
  description?: string
  is_active: boolean
  config_schema?: Record<string, any>
}

export interface Provider {
  id: string
  name: string
  type: "LLM" | "API" | "SERVICE"
  config: Record<string, any>
  tenant_id: string
  is_active: boolean
}

export interface Invite {
  id: string
  email: string
  role: UserRole
  tenant_id: string
  department_id?: string
  token: string
  expires_at: string
  is_accepted: boolean
  invited_by: string
  created_at: string
}

export type UserRole = "MAINTAINER" | "ADMIN" | "DEPT_ADMIN" | "DEPT_MANAGER" | "USER"

export type TenantDetectionMethod = "subdomain" | "path_prefix"

export interface LoginRequest {
  username_or_email: string
  password: string
  remember_me?: boolean
}

export interface AuthResponse {
  user: User
  tenant?: Tenant
  access_token: string
  refresh_token: string
  expires_in: number
}

export interface LoginResponse {
  user_id: string
  username: string
  email: string
  full_name?: string
  role: UserRole
  tenant_id?: string
  department_id?: string
  is_verified: boolean
  last_login?: string
  first_login: boolean
  force_password_change?: boolean
  access_token: string
  refresh_token: string
  token_type?: string
}

export interface RefreshTokenResponse {
  access_token: string
  token_type?: string
  expires_in?: number
}

export interface ProviderConfig {
  provider_name: string
  api_keys?: { [key: string]: string }
  provider_model_config?: { [key: string]: any }
}

export interface CreateTenantRequest {
  tenant_name: string
  timezone: string
  locale: string
  sub_domain?: string
  description?: string
  allowed_providers?: string[]
  allowed_tools?: string[]
}

export interface UpdateTenantRequest {
  tenant_name?: string
  timezone?: string
  locale?: string
  is_active?: boolean
  sub_domain?: string
  description?: string
  allowed_providers?: string[]
  allowed_tools?: string[]
}

export interface UpdateTenantResponse {
  tenant_id: string
  tenant_name?: string
  timezone?: string
  locale?: string
  sub_domain?: string
  description?: string
  updated_at?: string
  setup_results?: {
    allowed_providers?: {
      tenant_id: string
      allowed_providers: string[]
      created_configs: Array<{
        provider_name: string
        config_id: string
        action: "created" | "updated"
      }>
      updated_count: number
    }
    tools_setup?: {
      tenant_id: string
      enabled_tools: Array<{
        tool_name: string
        config_id: string
        action: "created" | "updated"
      }>
      total_updated: number
    }
  }
}

export interface InviteUsersRequest {
  emails: string[]
  role: UserRole
  tenant_id: string
  department_id?: string
  send_email: boolean
}

export interface ListParams {
  page?: number
  limit?: number
  search?: string
  sort_by?: string
  sort_order?: "asc" | "desc"
}

export interface PaginatedResponse<T> {
  data?: T[] 
  users?: T[]
  total: number
  page: number
  limit: number
  has_more?: boolean
  total_pages?: number
}

export interface WorkflowAgent {
  id: string
  tenant_id: string
  provider_name: string
  model_name: string
  model_configuration: Record<string, any>
  max_iterations: number
  timeout_seconds: number
  confidence_threshold: number
  is_active: boolean
}

export interface TenantSettings {
  tenant_name: string
  description?: string
  timezone: string
  locale: string
  chatbot_name?: string
  logo_url?: string
}

// App State types
export interface AppState {
  auth: {
    user: User | null
    tenant: Tenant | null
    permissions: Permission[]
    is_authenticated: boolean
    loading: boolean
  }
  ui: {
    loading: boolean
    errors: string[]
    notifications: Notification[]
  }
  tenant: {
    current_tenant: Tenant | null
    tenant_config: Record<string, any> | null
  }
}

export interface Notification {
  id: string
  type: "success" | "error" | "warning" | "info"
  title: string
  message: string
  duration?: number
}

export interface FolderInfoContext {
  department_id: string
  folder_id?: string | null
  role: string
  department_name: string
  is_root: boolean
  queried_at: string
}

export interface FolderInfoBreadcrumb {
  id: string
  name: string
  path_display: string
}

export interface FolderInfoPermissions {
  can_access: boolean
  reason: string
}

export interface FolderInfoCollection {
  id?: string | null
  collection_type?: string | null
  is_active?: boolean | null
  vector_config?: Record<string, any> | null
  document_count?: number | null
}

export interface FolderInfoDocument {
  id: string
  department_id: string
  folder_id?: string | null
  collection_id?: string | null
  title: string
  filename: string
  description?: string | null
  access_level: string
  uploaded_by: string
  file_size: number
  file_type: string
  bucket_name: string
  storage_key: string
  storage_path: string
  processing_status: string
  vector_status: string
  chunk_count: number
  collection?: FolderInfoCollection | null
  path_display: string
  permissions: FolderInfoPermissions
  created_at: string
  updated_at?: string | null
}

export interface FolderInfoFolder {
  id: string
  department_id: string
  folder_name: string
  folder_path: string
  path_display: string
  parent_folder_id?: string | null
  access_level: string
  created_by?: string | null
  created_at: string
  updated_at?: string | null
}

export interface FolderInfoCounts {
  folders: number
  documents: number
}

export interface FolderInfoPagination {
  page: number
  page_size: number
  total_folders: number
  total_documents: number
}

export interface FolderInfoResponse {
  context: FolderInfoContext
  folder_child_ids: string[]
  document_ids: string[]
  breadcrumbs: FolderInfoBreadcrumb[]
  folders: FolderInfoFolder[]
  documents: FolderInfoDocument[]
  counts: FolderInfoCounts
  pagination: FolderInfoPagination
}
