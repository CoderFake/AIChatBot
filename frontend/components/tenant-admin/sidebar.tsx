"use client"

import { usePathname, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { useTenant, useTenantSettings } from "@/lib/tenant-context"
import { useAuth } from "@/lib/auth-context"
import {
  LayoutDashboard,
  Building2,
  Users,
  UserCheck,
  Settings,
  Wrench,
  Database,
  ArrowLeft,
  Shield,
  FileText,
  Mail,
} from "lucide-react"

import { useTranslation } from "react-i18next"


const getNavigation = (t: (key: string) => string) => [
  {
    name: t("admin.dashboard"),
    href: "/admin",
    icon: LayoutDashboard,
  },
  {
    name: t("department.departments"),
    href: "/admin/departments",
    icon: Building2,
  },
  {
    name: t("documents.title"),
    href: "/admin/documents",
    icon: FileText,
  },
  {
    name: t("admin.users.title"),
    href: "/admin/users",
    icon: Users,
  },
  {
    name: t("invite.inviteUsers"),
    href: "/admin/invite",
    icon: Mail,
  },
  {
    name: t("admin.userGroups"),
    href: "/admin/groups",
    icon: UserCheck,
  },
  {
    name: t("admin.tools"),
    href: "/admin/tools",
    icon: Wrench,
  },
  {
    name: t("admin.providers"),
    href: "/admin/providers",
    icon: Database,
  },
  {
    name: t("admin.settings"),
    href: "/admin/settings",
    icon: Settings,
  },
]

export function TenantAdminSidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { tenant, tenantId } = useTenant()
  const { user } = useAuth()
  const { t } = useTranslation()
  const { getLogoUrl } = useTenantSettings()

  const navigation = getNavigation(t)
  const logoUrl = getLogoUrl()

  const handleNavigation = (href: string) => {
    router.push(`/${tenantId}${href}`)
  }

  const handleBackToDashboard = () => {
    router.push(`/${tenantId}/dashboard`)
  }

  return (
    <div className="fixed inset-y-0 left-0 z-50 w-64 bg-card border-r border-border lg:block hidden">
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex h-16 items-center px-6 border-b border-border">
          <div className="flex items-center space-x-2">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Logo"
                className="w-8 h-8 rounded-lg object-cover"
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.style.display = "none"
                  target.parentElement!.innerHTML = `
                    <div class="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                      <svg class="w-5 h-5 text-primary-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
                      </svg>
                    </div>
                  `
                }}
              />
            ) : (
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <Shield className="w-5 h-5 text-primary-foreground" />
              </div>
            )}
            <div>
              <h2 className="text-lg font-bold font-sans">{t("admin.administration")}</h2>
              <p className="text-xs text-muted-foreground font-serif truncate">{tenant?.tenant_name || tenantId}</p>
            </div>
          </div>
        </div>  

        {/* Navigation */}
        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {navigation.map((item) => {
              const fullHref = `/${tenantId}${item.href}`
              let isActive = false

              if (item.href === "/admin") {
                isActive = pathname === fullHref || pathname === `${fullHref}/`
              } else {
                isActive = pathname === fullHref || pathname.startsWith(`${fullHref}/`)
              }

              return (
                <Button
                  key={item.name}
                  variant={isActive ? "secondary" : "ghost"}
                  className="w-full justify-start font-serif"
                  onClick={() => handleNavigation(item.href)}
                >
                  <item.icon className="w-4 h-4 mr-3" />
                  {item.name}
                </Button>
              )
            })}
          </nav>
        </ScrollArea>

        <Separator />

        {/* Back to Dashboard */}
        <div className="p-3">
          <Button variant="ghost" className="w-full justify-start font-serif" onClick={handleBackToDashboard}>
            <ArrowLeft className="w-4 h-4 mr-3" />
            {t("admin.dashboard")}
          </Button>
        </div>
      </div>
    </div>
  )
}
