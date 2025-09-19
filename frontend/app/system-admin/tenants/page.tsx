"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Plus, Search, MoreHorizontal, Eye, Edit, Trash2, Building2, LogIn } from "lucide-react"
import { apiService } from "@/lib/api/index"
import type { Tenant } from "@/types"

interface TenantListResponse {
  tenants: Tenant[]
  total: number
  page: number
  limit: number
  has_more: boolean
}
import { useTranslation } from "react-i18next"
import { useToast } from "@/lib/use-toast"

export default function TenantsPage() {
  const router = useRouter()
  const { t } = useTranslation()
  const { showSuccess, showError } = useToast()
  const [tenants, setTenants] = useState<TenantListResponse>({
    tenants: [],
    total: 0,
    page: 1,
    limit: 10,
    has_more: false,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [currentPage, setCurrentPage] = useState(1)

  useEffect(() => {
    loadTenants()
  }, [currentPage, searchQuery])

  const loadTenants = async () => {
    setIsLoading(true)
    try {
      const response = await apiService.tenants.list({
        page: currentPage,
        limit: 10,
        search: searchQuery || undefined,
        sort_by: "created_at",
        sort_order: "desc",
      }) as unknown as TenantListResponse
      setTenants({
        tenants: response?.tenants || [],
        total: response.total || 0,
        page: response.page || 1,
        limit: response.limit || 10,
        has_more: response?.has_more || false,
      })
    } catch (error) {
      console.error("Failed to load tenants:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = (query: string) => {
    setSearchQuery(query)
    setCurrentPage(1)
  }

  const handleCreateTenant = () => {
    router.push("/system-admin/tenants/create")
  }

  const handleViewTenant = (tenantId: string) => {
    router.push(`/system-admin/tenants/${tenantId}`)
  }

  const handleEditTenant = (tenantId: string) => {
    router.push(`/system-admin/tenants/${tenantId}/edit`)
  }

  const handleLoginToTenant = (tenantId: string) => {
    router.push(`/${tenantId}/login`)
  }

  const handleDeleteTenant = async (tenantId: string) => {
    if (!confirm(t("admin.deleteConfirmation"))) {
      return
    }

    try {
      await apiService.tenants.delete(tenantId)
      loadTenants() // Reload the list
      showSuccess(t("admin.deleteSuccess"))
    } catch (error) {
      console.error("Failed to delete tenant:", error)
      showError(t("admin.deleteFailed"))
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold font-sans">{t("admin.organizations")}</h1>
        </div>
        <Button onClick={handleCreateTenant} className="font-sans">
          <Plus className="w-4 h-4 mr-2" />
          {t("admin.createTenant")}
        </Button>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="font-sans">{t("admin.searchAndFilter")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t("admin.searchTenantsPlaceholder")}
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="pl-10 font-serif"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tenants Table */}
      <Card>
        <CardHeader>
          <CardDescription className="font-serif">
            {(tenants?.total || 0) === 0 ? t("admin.noOrganizationsFound") : `Showing ${(tenants?.tenants || []).length} of ${tenants?.total || 0} organizations`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-12 bg-muted rounded"></div>
                </div>
              ))}
            </div>
          ) : (!tenants || !tenants.tenants || tenants.tenants.length === 0) ? (
            <div className="text-center py-12">
              <Building2 className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold font-sans mb-2">No organizations found</h3>
              <p className="text-muted-foreground font-serif mb-4">
                {searchQuery ? "Try adjusting your search criteria" : "Get started by creating your first organization"}
              </p>
              <Button onClick={handleCreateTenant} className="font-sans">
                <Plus className="w-4 h-4 mr-2" />
                {t("admin.createOrganization")}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-sans">{t("admin.name")}</TableHead>
                    <TableHead className="font-sans">{t("admin.subdomain")}</TableHead>
                    <TableHead className="font-sans">{t("admin.status")}</TableHead>
                    <TableHead className="font-sans">{t("admin.timezone")}</TableHead>
                    <TableHead className="font-sans">{t("admin.created")}</TableHead>
                    <TableHead className="w-[70px] font-sans">{t("admin.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(tenants.tenants || []).map((tenant) => (
                    <TableRow key={tenant.id}>
                      <TableCell>
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center overflow-hidden">
                            {tenant.settings?.branding?.logo_url ? (
                              <img
                                src={tenant.settings.branding.logo_url}
                                alt={`${tenant.tenant_name} logo`}
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  const target = e.target as HTMLImageElement
                                  target.style.display = "none"
                                  target.parentElement!.innerHTML = `
                                    <svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                                    </svg>
                                  `
                                }}
                              />
                            ) : (
                              <Building2 className="w-4 h-4 text-primary" />
                            )}
                          </div>
                          <div>
                            <p className="font-medium font-sans">{tenant.tenant_name}</p>
                            <p className="text-sm hidden text-muted-foreground font-serif">{tenant.id}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-serif">
                        {tenant.sub_domain ? (
                          <code className="bg-muted px-2 py-1 rounded text-xs">{tenant.sub_domain}</code>
                        ) : (
                          <span className="text-muted-foreground">{t("admin.none")}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={tenant.is_active ? "default" : "secondary"}>
                          {tenant.is_active ? t("admin.active") : t("admin.inactive")}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-serif">{tenant.timezone}</TableCell>
                      <TableCell className="font-serif">{formatDate(tenant.created_at)}</TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleLoginToTenant(tenant.id)} className="font-serif">
                              {tenant.settings?.branding?.logo_url ? (
                                <img
                                  src={tenant.settings.branding.logo_url}
                                  alt={`${tenant.tenant_name} logo`}
                                  className="w-4 h-4 mr-2 rounded object-cover"
                                  onError={(e) => {
                                    const target = e.target as HTMLImageElement
                                    target.style.display = "none"
                                    target.parentElement!.innerHTML = `
                                      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path>
                                      </svg>
                                    `
                                  }}
                                />
                              ) : (
                                <LogIn className="w-4 h-4 mr-2" />
                              )}
                              {t("admin.loginToTenant", "Login to Tenant")}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleViewTenant(tenant.id)} className="font-serif">
                              <Eye className="w-4 h-4 mr-2" />
                              {t("admin.viewDetails")}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleEditTenant(tenant.id)} className="font-serif">
                              <Edit className="w-4 h-4 mr-2" />
                              {t("admin.edit")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleDeleteTenant(tenant.id)}
                              className="text-destructive font-serif"
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              {t("admin.delete")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {Math.ceil((tenants?.total || 0) / (tenants?.limit || 10)) > 1 && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground font-serif">
                    {t("admin.page")} {tenants?.page || 1} {t("admin.of")} {Math.ceil((tenants?.total || 0) / (tenants?.limit || 10))}
                  </p>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                      className="font-sans"
                    >
                      {t("admin.previous")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage >= Math.ceil((tenants?.total || 0) / (tenants?.limit || 10))}
                      className="font-sans"
                    >
                      {t("admin.next")}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
