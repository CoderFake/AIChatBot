"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Building2, Users, Activity, TrendingUp, Plus, Eye } from "lucide-react"
import { useRouter } from "next/navigation"
import { apiService } from "@/lib/api/index"
import type { Tenant } from "@/types"
import { useTranslation } from "react-i18next"

interface DashboardStats {
  totalTenants: number
  activeTenants: number
  totalUsers: number
  activeUsers: number
}

export default function SystemAdminDashboard() {
  const router = useRouter()
  const { t } = useTranslation()
  const [stats, setStats] = useState<DashboardStats>({
    totalTenants: 0,
    activeTenants: 0,
    totalUsers: 0,
    activeUsers: 0,
  })
  const [recentTenants, setRecentTenants] = useState<Tenant[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      const tenantsResponse = await apiService.tenants.list({ limit: 5, sort_by: "created_at", sort_order: "desc" })
      setRecentTenants(tenantsResponse.data || [])

      const allTenantsResponse = await apiService.tenants.list({ limit: 1000 })
      const tenantsData = allTenantsResponse.data || []
      const activeTenants = tenantsData.filter((t) => t.is_active).length

      let totalUsers = 0
      let activeUsers = 0

      for (const tenant of tenantsData) {
        totalUsers += tenant.user_count || 0
        if (tenant.is_active) {
          activeUsers += tenant.user_count || 0
        }
      }

      setStats({
        totalTenants: allTenantsResponse.total || 0,
        activeTenants,
        totalUsers,
        activeUsers,
      })
    } catch (error) {
      console.error("Failed to load dashboard data:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateTenant = () => {
    router.push("/system-admin/tenants/create")
  }

  const handleViewAllTenants = () => {
    router.push("/system-admin/tenants")
  }

  const handleViewTenant = (tenantId: string) => {
    router.push(`/system-admin/tenants/${tenantId}`)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold font-sans">{t("admin.dashboard")}</h1>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="animate-pulse">
                  <div className="h-4 bg-muted rounded w-3/4 mb-2"></div>
                  <div className="h-8 bg-muted rounded w-1/2"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold font-sans">{t("admin.dashboard")}</h1>
          <p className="text-muted-foreground font-serif">{t("admin.systemOverview")}</p>
        </div>
        <Button onClick={handleCreateTenant} className="font-sans">
          <Plus className="w-4 h-4 mr-2" />
          {t("admin.createTenant")}
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium font-sans">{t("admin.totalTenants")}</CardTitle>
            <Building2 className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-sans">{stats.totalTenants}</div>
            <p className="text-xs text-muted-foreground font-serif">{stats.activeTenants} {t("admin.active").toLowerCase()}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium font-sans">{t("admin.activeTenants")}</CardTitle>
            <Activity className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-sans">{stats.activeTenants}</div>
            <p className="text-xs text-muted-foreground font-serif">
              {stats.totalTenants > 0 ? Math.round((stats.activeTenants / stats.totalTenants) * 100) : 0}% {t("admin.of")} total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium font-sans">{t("admin.totalUsers")}</CardTitle>
            <Users className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-sans">{stats.totalUsers}</div>
            <p className="text-xs text-muted-foreground font-serif">{t("admin.acrossAllTenants")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium font-sans">{t("admin.growth")}</CardTitle>
            <TrendingUp className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-sans">+12%</div>
            <p className="text-xs text-muted-foreground font-serif">{t("admin.thisMonth")}</p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Tenants */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="font-sans">{t("admin.recentTenants")}</CardTitle>
              <CardDescription className="font-serif">{t("admin.latestTenantRegistrations")}</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={handleViewAllTenants} className="font-sans bg-transparent">
              <Eye className="w-4 h-4 mr-2" />
              {t("admin.viewAll")}
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {!recentTenants || recentTenants.length === 0 ? (
                <p className="text-muted-foreground text-center py-4 font-serif">{t("admin.noTenantsFound")}</p>
              ) : (
                (recentTenants || []).map((tenant) => (
                  <div
                    key={tenant.id}
                    className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                    onClick={() => handleViewTenant(tenant.id)}
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                        <Building2 className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium font-sans">{tenant.tenant_name}</p>
                        <p className="text-sm text-muted-foreground font-serif">
                          {tenant.sub_domain ? `${tenant.sub_domain}.domain.com` : tenant.id}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge variant={tenant.is_active ? "default" : "secondary"}>
                        {tenant.is_active ? t("admin.active") : t("admin.inactive")}
                      </Badge>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* System Health */}
        <Card>
          <CardHeader>
            <CardTitle className="font-sans">{t("admin.systemHealth")}</CardTitle>
            <CardDescription className="font-serif">{t("admin.currentSystemStatus")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-serif">{t("admin.database")}</span>
                <Badge variant="default">{t("admin.healthy")}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-serif">{t("admin.apiServices")}</span>
                <Badge variant="default">{t("admin.operational")}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-serif">{t("admin.authentication")}</span>
                <Badge variant="default">{t("admin.online")}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-serif">{t("admin.storage")}</span>
                <Badge variant="secondary">{t("admin.maintenance")}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="font-sans">{t("admin.quickActions")}</CardTitle>
          <CardDescription className="font-serif">{t("admin.commonAdministrativeTasks")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button variant="outline" onClick={handleCreateTenant} className="h-auto p-4 font-sans bg-transparent">
              <div className="text-center">
                <Plus className="w-6 h-6 mx-auto mb-2" />
                <div className="font-medium">{t("admin.createTenant")}</div>
                <div className="text-xs text-muted-foreground font-serif">{t("admin.addNewOrganization")}</div>
              </div>
            </Button>

            <Button
              variant="outline"
              onClick={() => router.push("/system-admin/users")}
              className="h-auto p-4 font-sans"
            >
              <div className="text-center">
                <Users className="w-6 h-6 mx-auto mb-2" />
                <div className="font-medium">{t("admin.manageUsers")}</div>
                <div className="text-xs text-muted-foreground font-serif">{t("admin.userAdministration")}</div>
              </div>
            </Button>

            <Button
              variant="outline"
              onClick={() => router.push("/system-admin/analytics")}
              className="h-auto p-4 font-sans"
            >
              <div className="text-center">
                <TrendingUp className="w-6 h-6 mx-auto mb-2" />
                <div className="font-medium">{t("admin.viewAnalytics")}</div>
                <div className="text-xs text-muted-foreground font-serif">{t("admin.systemInsights")}</div>
              </div>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
