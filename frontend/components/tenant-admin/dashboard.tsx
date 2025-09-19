'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Users, Building, Plus, UserPlus } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import type { Department } from '@/types'
import { apiService } from '@/lib/api/index'


interface TenantDashboardProps {
  tenantId: string
}



export function TenantDashboard({ tenantId }: TenantDashboardProps) {
  const router = useRouter()
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const {t} = useTranslation()

  useEffect(() => {
    loadDashboardData()
  }, [tenantId])

  const loadDashboardData = async () => {
    try {
      setLoading(true)

      const departments = await apiService.departments.list(tenantId)
      setDepartments(departments || [])

    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const stats = [
    {
      title: `${t("department.departments")}`,
      value: departments.length,
      description: `${t("department.activeDepartments")}`,
      icon: Building,
      color: 'text-blue-600'
    },
    {
      title: `${t("department.users")}`,
      value: departments.reduce((total, dept) => total + (dept.user_count || 0), 0),
      description: `${t("department.activeUsers")}`,
      icon: UserPlus,
      color: 'text-orange-600'
    }
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("tenant.tenantDashboard")}</h1>
            <p className="text-muted-foreground">
              {t("tenant.manageYourOrganizationDepartmentsAndAgents")}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => router.push(`/${tenantId}/admin/departments`)}
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            {t("admin.departmentManagement")}
          </Button>
          <Button
            variant="outline"
            onClick={() => router.push(`/${tenantId}/invite`)}
            className="gap-2"
          >
            <UserPlus className="h-4 w-4" />
            {t("tenant.inviteUsers")}
          </Button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {stat.title}
              </CardTitle>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">
                {stat.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Departments Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">{t("tenant.departments")}</h2>
          <Button
            onClick={() => router.push(`/${tenantId}/admin/departments`)}
            size="sm"
          >
            <Plus className="h-4 w-4 mr-2" />
            {t("tenant.createNewDepartment")}
          </Button>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {departments.map((dept) => (
            <Card key={dept.id} className="cursor-pointer hover:shadow-md transition-shadow">
              <CardHeader>
                <CardTitle className="text-lg">{dept.department_name}</CardTitle>
                <CardDescription>
                  {t("common.created")} {new Date(dept.created_at).toLocaleDateString()}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <Badge variant="secondary">
                    {dept.user_count || 0} {t("tenant.users")}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push(`/${tenantId}/admin/departments`)}
                  >
                    {t("tenant.manage")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
