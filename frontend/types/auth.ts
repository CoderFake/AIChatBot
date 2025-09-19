// types/auth.ts
export interface LoginRequest {
    username: string
    password: string
    remember_me?: boolean
    tenant_id?: string
    sub_domain?: string
  }
  
  export interface LoginResponse {
    user_id: string
    username: string
    email: string
    full_name?: string
    role: string
    tenant_id?: string
    department_id?: string
    is_verified: boolean
    last_login?: string
    first_login: boolean
    force_password_change: boolean
    access_token: string
    refresh_token: string
    expires_in: number
  }
  
  export interface RefreshTokenRequest {
    refresh_token: string
  }
  
  export interface RefreshTokenResponse {
    access_token: string
    refresh_token?: string
    expires_in: number
  }
  
  export interface LogoutRequest {
    refresh_token: string
    all_devices?: boolean
  }
  
  export interface LogoutResponse {
    success: boolean
    message: string
  }
  
  export interface UserProfileResponse {
    user_id: string
    username: string
    email: string
    full_name?: string
    role: string
    tenant_id?: string
    department_id?: string
    is_verified: boolean
    last_login?: string
    created_at?: string
    force_password_change: boolean
    permissions?: string[]
  }
  
  export interface PasswordResetRequest {
    email: string
    tenant_id?: string
  }
  
  export interface PasswordResetResponse {
    success: boolean
    message: string
  }
  
  export interface PasswordResetConfirmRequest {
    token: string
    new_password: string
    confirm_password: string
  }
  
  export interface PasswordResetConfirmResponse {
    success: boolean
    message: string
  }
  
  export interface ChangePasswordRequest {
    current_password: string
    new_password: string
    confirm_password: string
  }
  
  export interface ChangePasswordResponse {
    success: boolean
    message: string
  }
  
  export interface TokenValidationResponse {
    valid: boolean
    user_id?: string
    expires_at?: string
    permissions?: string[]
  }

  export interface InviteTokenValidationResponse {
    email: string
    username: string
    role: string
    tenant_id: string
    tenant_name: string
    token_type: string
  }
  
  export interface AuthErrorResponse {
    error: string
    message: string
    details?: Record<string, any>
  }
  
  // Auth context types
  export interface AuthState {
    user: User | null
    tenant: Tenant | null
    permissions: Permission[]
    is_authenticated: boolean
    loading: boolean
  }
  
  export interface AuthContextType extends AuthState {
    login: (username: string, password: string) => Promise<void>
    logout: () => Promise<void>
    setCurrentTenant: (tenant: Tenant | null) => void
    requestPasswordReset: (email: string) => Promise<void>
    resetPassword: (token: string, newPassword: string) => Promise<void>
  }
  
  // User and related types
  export interface User {
    id: string
    username: string
    email: string
    first_name?: string
    last_name?: string
    is_active: boolean
    role: UserRole
    tenant_id?: string
    department_id?: string
    permissions: Permission[]
    force_password_change: boolean
    created_at: string
    updated_at: string
  }
  
  export interface Permission {
    id: string
    name: string
    code: string
    description?: string
    resource_type?: string
    resource_id?: string
    created_at: string
    updated_at: string
  }
  
  export interface Tenant {
    id: string
    tenant_name: string
    timezone: string
    locale: string
    sub_domain?: string
    is_active: boolean
    description?: string
    created_at: string
    updated_at: string
    status?: string
    admin_count?: number
    user_count?: number
    is_deleted?: boolean
    deleted_at?: string
    version?: string
    settings?: Record<string, any>
  }
  
  export type UserRole = 
    | 'MAINTAINER' 
    | 'ADMIN' 
    | 'DEPT_ADMIN' 
    | 'DEPT_MANAGER' 
    | 'USER'
  
  // Paginated response type
  export interface PaginatedResponse<T> {
    data?: T[]
    users?: T[]
    total: number
    page: number
    limit: number
    total_pages?: number 
    has_more?: boolean 
  }
  
  // API Response types
  export interface ApiResponse<T = any> {
    success: boolean
    data?: T
    message?: string
    error?: string
    details?: Record<string, any>
  }
  
  export interface OperationResult {
    success: boolean
    message?: string
    error?: string
    data?: any
  }
  
  // Auth middleware types
  export interface JWTPayload {
    user_id: string
    username?: string
    role: string
    tenant_id?: string
    department_id?: string
    jti: string
    exp: number
    iat: number
    token_type: 'access' | 'refresh' | 'reset'
  }
  
  export interface UserContext {
    user_id: string
    username: string
    email: string
    first_name?: string
    last_name?: string
    role: string
    tenant_id?: string
    department_id?: string
    is_verified: boolean
    jti: string
    validated_permissions?: string[]
    api_access_validated?: boolean
    validation_type?: string
  }
  
  // Session types
  export interface UserSession {
    user_id: string
    session_id: string
    login_ip?: string
    user_agent?: string
    tenant_id?: string
    login_method: string
    created_at: string
    expires_at: string
    is_active: boolean
  }
  
  // Token blacklist types
  export interface BlacklistedToken {
    jti: string
    user_id: string
    token_type: 'access' | 'refresh' | 'reset'
    reason: string
    blacklisted_at: string
    expires_at: string
  }