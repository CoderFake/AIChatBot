"use client"

import { useAuth } from "@/lib/auth-context"
import { useTenant } from "@/lib/tenant-context"
import { NavigationBreadcrumb } from "@/components/routing/navigation-breadcrumb"
import { TenantSwitcher } from "@/components/routing/tenant-switcher"
import { RouteGuard } from "@/components/auth/route-guard"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Building2, Users, Settings, MessageSquare } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslation } from "react-i18next"

export default function TenantDashboardPage() {
  const { user } = useAuth()
  const { tenant } = useTenant()
  const router = useRouter()
  const { t } = useTranslation()

  const handleNavigate = (path: string) => {
    router.push(path)
  }

  return (
    <RouteGuard requireAuth>
      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold font-sans">{t("dashboard.dashboard")}</h1>
                <p className="text-muted-foreground font-serif">{t("dashboard.welcomeBack", { name: user?.first_name || user?.username })}</p>
              </div>
              <div className="w-64">
                <TenantSwitcher />
              </div>
            </div>

            <NavigationBreadcrumb />

            {/* Tenant Info */}
            {tenant && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center font-sans">
                    <Building2 className="w-5 h-5 mr-2" />
                    {tenant.tenant_name}
                  </CardTitle>
                  <CardDescription className="font-serif">
                    {tenant.description || "No description available"}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="font-medium font-sans">Timezone:</span>
                      <span className="ml-2 font-serif">{tenant.timezone}</span>
                    </div>
                    <div>
                      <span className="font-medium font-sans">Locale:</span>
                      <span className="ml-2 font-serif">{tenant.locale}</span>
                    </div>
                    {tenant.sub_domain && (
                      <div>
                        <span className="font-medium font-sans">Subdomain:</span>
                        <span className="ml-2 font-serif">{tenant.sub_domain}</span>
                      </div>
                    )}
                    <div>
                      <span className="font-medium font-sans">Status:</span>
                      <span className={`ml-2 font-serif ${tenant.is_active ? "text-green-600" : "text-red-600"}`}>
                        {tenant.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Quick Actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Admin Panel */}
              {(user?.role === "ADMIN" || user?.role === "MAINTAINER") && (
                <Card className="cursor-pointer hover:shadow-md transition-shadow">
                  <CardHeader>
                    <CardTitle className="flex items-center font-sans">
                      <Settings className="w-5 h-5 mr-2" />
                      Administration
                    </CardTitle>
                    <CardDescription className="font-serif">Manage users, departments, and settings</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Button onClick={() => handleNavigate(`/${tenant?.id}/admin`)} className="w-full font-sans">
                      Open Admin Panel
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* Chatbot */}
              <Card className="cursor-pointer hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="flex items-center font-sans">
                    <MessageSquare className="w-5 h-5 mr-2" />
                    Chatbot
                  </CardTitle>
                  <CardDescription className="font-serif">Access the AI-powered chatbot interface</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button onClick={() => handleNavigate(`/${tenant?.id}/chat`)} className="w-full font-sans">
                    Open Chatbot
                  </Button>
                </CardContent>
              </Card>

              {/* Team */}
              <Card className="cursor-pointer hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="flex items-center font-sans">
                    <Users className="w-5 h-5 mr-2" />
                    Team
                  </CardTitle>
                  <CardDescription className="font-serif">View team members and departments</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button
                    onClick={() => handleNavigate(`/${tenant?.id}/team`)}
                    variant="outline"
                    className="w-full font-sans"
                  >
                    View Team
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </RouteGuard>
  )
}
