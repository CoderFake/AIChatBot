"use client"

import { useState, useEffect, use } from "react"
import { useRouter, useParams } from "next/navigation"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ArrowLeft, Edit, RefreshCw, Building2, Wrench } from "lucide-react"
import { apiService } from "@/lib/api/index"
import type { Tenant, User } from "@/types"
import { useTranslation } from "react-i18next"
import { useToast } from "@/lib/use-toast"
import { InviteManagement } from "@/components/tenant-admin/invite-management"

export default function TenantDetailPage() {
  const router = useRouter()
  const params = useParams()
  const tenantId = params.id as string
  const { t } = useTranslation()
  const { showError } = useToast()

  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [admins, setAdmins] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    loadTenantDetails()
  }, [tenantId])

  const loadTenantDetails = async () => {
    setIsLoading(true)
    setError("")

    try {
      const tenantData = await apiService.tenants.getDetail(tenantId)
      setTenant(tenantData)

      const usersResponse = await apiService.users.list({ tenant_id: tenantId, limit: 100 })
      const adminUsers = (usersResponse.users || []).filter((u: User) => u.role === "ADMIN")
      setAdmins(adminUsers)
    } catch (err) {
      setError(err instanceof Error ? err.message : t("messages.errors.failedToLoadTenantDetails"))
    } finally {
      setIsLoading(false)
    }
  }


  const handleRemoveAdmin = async (userId: string) => {
    if (!confirm(t("messages.info.removeAdminConfirmation"))) return

    try {
      loadTenantDetails()
    } catch (err) {
      showError(t("messages.errors.failedToRemoveAdmin"))
    }
  }

  const handleBack = () => {
    router.push("/system-admin/tenants")
  }

  const handleEdit = () => {
    router.push(`/system-admin/tenants/${tenantId}/edit`)
  }

  const handleSetup = () => {
    router.push(`/system-admin/tenants/${tenantId}/setup`)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-muted rounded w-1/4 mb-4"></div>
          <div className="h-12 bg-muted rounded mb-6"></div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="h-64 bg-muted rounded"></div>
            <div className="h-64 bg-muted rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !tenant) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" onClick={handleBack} className="font-serif">
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t("messages.info.backToTenants")}
        </Button>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <h3 className="text-lg font-semibold font-sans mb-2">{t("messages.info.tenantNotFound")}</h3>
              <p className="text-muted-foreground font-serif mb-4">
                {error || "The requested tenant could not be found."}
              </p>
              <Button onClick={handleBack} className="font-sans">
                {t("messages.info.backToTenants")}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="ghost" size="sm" onClick={handleBack} className="font-serif">
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t("messages.info.backToTenants")}
          </Button>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" onClick={loadTenantDetails} size="sm" className="font-sans bg-transparent">
            <RefreshCw className="w-4 h-4 mr-2" />
            {t("messages.info.refresh")}
          </Button>
          <Button variant="outline" onClick={handleSetup} size="sm" className="font-sans">
            <Wrench className="w-4 h-4 mr-2" />
            {t('tenant.setupTenant')}
          </Button>
          <Button onClick={handleEdit} className="font-sans">
            <Edit className="w-4 h-4 mr-2" />
            {t("messages.info.editTenant")}
          </Button>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
          <Building2 className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-3xl font-bold font-sans">{tenant.tenant_name}</h1>
          <p className="text-muted-foreground font-serif">Tenant ID: {tenant.id}</p>
        </div>
        <Badge variant={tenant.is_active ? "default" : "secondary"}>{tenant.is_active ? "Active" : "Inactive"}</Badge>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tenant Information */}
        <Card>
          <CardHeader>
            <CardTitle className="font-sans">{t("messages.info.tenantInformation")}</CardTitle>
            <CardDescription className="font-serif">{t("messages.info.basicTenantConfigurationAndSettings")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="font-serif">Name</Label>
                <p className="font-medium font-sans">{tenant.tenant_name}</p>
              </div>
              <div>
                <Label className="font-serif">Status</Label>
                <div>
                  <Badge variant={tenant.is_active ? "default" : "secondary"}>
                    {tenant.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </div>
              <div>
                <Label className="font-serif">Subdomain</Label>
                <p className="font-mono text-sm">
                  {tenant.sub_domain ? (
                    <code className="bg-muted px-2 py-1 rounded">{tenant.sub_domain}</code>
                  ) : (
                    <span className="text-muted-foreground">{t("messages.info.none")}</span>
                  )}
                </p>
              </div>
              <div>
                <Label className="font-serif">{t("messages.info.timezone")}</Label>
                <p className="font-serif">{tenant.timezone}</p>
              </div>
              <div>
                <Label className="font-serif">{t("messages.info.locale")}</Label>
                <p className="font-serif">{tenant.locale}</p>
              </div>
              <div>
                <Label className="font-serif">{t("messages.info.created")}</Label>
                <p className="font-serif">{formatDate(tenant.created_at)}</p>
              </div>
            </div>

            {tenant.description && (
              <div>
                <Label className="font-serif">{t("messages.info.description")}</Label>
                <p className="text-sm text-muted-foreground font-serif">{tenant.description}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tenant Admins */}
        <Card>
          <CardHeader>
            <CardTitle className="font-sans">{t("messages.info.tenantAdmins")}</CardTitle>
            <CardDescription className="font-serif">
              {t("messages.info.usersWithAdministrativeAccessToThisTenant")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {admins.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground font-serif">
                {t("messages.info.noAdminsAssigned")}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-sans">{t("messages.info.name")}</TableHead>
                    <TableHead className="font-sans">{t("messages.info.email")}</TableHead>
                    <TableHead className="font-sans">{t("messages.info.status")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {admins.map((admin) => (
                    <TableRow key={admin.id}>
                      <TableCell className="font-sans">
                        {admin.first_name && admin.last_name
                          ? `${admin.first_name} ${admin.last_name}`
                          : admin.username}
                      </TableCell>
                      <TableCell className="font-serif">{admin.email}</TableCell>
                      <TableCell>
                        <Badge variant={admin.is_active ? "default" : "secondary"}>
                          {admin.is_active ? t("messages.info.active") : t("messages.info.inactive")}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Invite Management */}
      <div className="mt-6">
        <InviteManagement tenantId={tenantId} context="system_admin" />
      </div>
    </div>
  )
}
