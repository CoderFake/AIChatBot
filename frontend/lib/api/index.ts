import { AuthAPI } from "./auth"
import { TenantsAPI } from "./tenants"
import { UsersAPI } from "./users"
import { TenantAdminAPI } from "./tenant-admin"
import { DepartmentsAPI } from "./departments"
import { DocumentsAPI } from "./documents"
import { ChatAPI } from "./chat"
import { TenantSettingsAPI } from "./tenant-settings"
import { APIInterceptor } from "./interceptor"

class APIService {
  private baseURL: string
  public auth: AuthAPI
  public tenants: TenantsAPI
  public users: UsersAPI
  public tenantAdmin: TenantAdminAPI
  public departments: DepartmentsAPI
  public documents: DocumentsAPI
  public chat: ChatAPI
  public tenantSettings: TenantSettingsAPI
  private interceptor: APIInterceptor
  client: string | undefined

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1"
    this.interceptor = new APIInterceptor(this.baseURL)
    this.interceptor.setupInterceptors()

    this.auth = new AuthAPI(this.baseURL)
    this.tenants = new TenantsAPI(this.baseURL)
    this.users = new UsersAPI(this.baseURL)
    this.tenantAdmin = new TenantAdminAPI(this.baseURL)
    this.tenantSettings = new TenantSettingsAPI(this.baseURL)
    this.departments = new DepartmentsAPI(this.baseURL)
    this.documents = new DocumentsAPI(this.baseURL)
    this.chat = new ChatAPI(this.baseURL)
  }

  setToken(token: string) {
    this.interceptor.setToken(token)
  }

  removeToken() {
    this.interceptor.removeToken()
  }
}

export { APIService }
export const apiService = new APIService()
export const api = apiService
