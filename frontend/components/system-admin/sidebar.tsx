"use client"

import { usePathname, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { LayoutDashboard, Building2, Users, Settings, BarChart3, Shield, Database, LogOut } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { useTranslation } from "react-i18next"

const navigationKeys = [
  {
    key: "admin.dashboard",
    href: "/system-admin/dashboard",
    icon: LayoutDashboard,
  },
  {
    key: "admin.tenants",
    href: "/system-admin/tenants",
    icon: Building2,
  },
  {
    key: "admin.adminusers",
    href: "/system-admin/users",
    icon: Users,
  },
  {
    key: "admin.analytics",
    href: "/system-admin/analytics",
    icon: BarChart3,
  },
  {
    key: "admin.security",
    href: "/system-admin/security",
    icon: Shield,
  },
  {
    key: "admin.system",
    href: "/system-admin/system",
    icon: Database,
  },
  {
    key: "admin.settings",
    href: "/system-admin/settings",
    icon: Settings,
  },
]

export function SystemAdminSidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { logout } = useAuth()
  const { t } = useTranslation()
  const logoUrl = null

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }

  return (
    <div className="fixed inset-y-0 left-0 z-50 w-64 bg-card border-r border-border lg:block hidden">
      <div className="flex h-full flex-col">
        {/* Logo/Brand */}
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
              <h2 className="text-lg font-bold font-sans">{t("admin.systemAdministration")}</h2>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {navigationKeys.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(item.href + "/")
              return (
                <Button
                  key={item.key}
                  variant={isActive ? "secondary" : "ghost"}
                  className="w-full justify-start font-serif"
                  onClick={() => router.push(item.href)}
                >
                  <item.icon className="w-4 h-4 mr-3" />
                  {t(item.key)}
                </Button>
              )
            })}
          </nav>
        </ScrollArea>

        <Separator />

        {/* Logout */}
        <div className="p-3">
          <Button variant="ghost" className="w-full justify-start font-serif" onClick={handleLogout}>
            <LogOut className="w-4 h-4 mr-3" />
            {t("admin.signOut")}
          </Button>
        </div>
      </div>
    </div>
  )
}
