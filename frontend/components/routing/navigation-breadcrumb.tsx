"use client"

import { usePathname } from "next/navigation"
import Link from "next/link"
import { useTenant } from "@/lib/tenant-context"
import { ChevronRight, Home, Building2 } from "lucide-react"
import { useTranslation } from "react-i18next"

const segmentTranslations: Record<string, string> = {
  admin: "admin.dashboard",
  chat: "chat.title",
  departments: "department.departments",
  agents: "admin.agents",
  documents: "documents.title",
  users: "admin.users.title",
  invite: "invite.inviteUsers",
  groups: "admin.userGroups",
  tools: "admin.tools",
  providers: "admin.providers",
  settings: "admin.settings",
  create: "common.create",
  setup: "tenant.setupTenant",
  login: "auth.loginTitle",
  dashboard: "admin.dashboard",
  forgot: "auth.forgotPassword",
  reset: "auth.resetPassword"
}

export function NavigationBreadcrumb() {
  const pathname = usePathname()
  const { tenant, tenantId } = useTenant()
  const { t } = useTranslation()

  if (pathname === "/" || pathname.startsWith("/system-admin")) {
    return null
  }

  const pathSegments = pathname.split("/").filter(Boolean)
  const breadcrumbs: Array<{ label: string; href: string; isActive: boolean }> = []

  breadcrumbs.push({
    label: t("common.home"),
    href: tenantId ? `/${tenantId}/admin` : "/",
    isActive: false,
  })

  if (tenantId) {
    let currentPath = `/${tenantId}`
    for (let i = 1; i < pathSegments.length; i++) {
      const segment = pathSegments[i]
      currentPath += `/${segment}`

      breadcrumbs.push({
        label: formatSegmentLabel(segment, t),
        href: currentPath,
        isActive: i === pathSegments.length - 1,
      })
    }
  }

  if (breadcrumbs.length <= 1) {
    return null
  }

  return (
    <nav className="flex items-center space-x-1 text-sm text-muted-foreground font-serif mb-6">
      {breadcrumbs.map((breadcrumb, index) => (
        <div key={`${breadcrumb.href}-${index}`} className="flex items-center">
          {index > 0 && <ChevronRight className="w-4 h-4 mx-1" />}

          <div className="flex items-center">
            {index === 0 && <Home className="w-4 h-4 mr-1" />}
            {index >= 1 && tenantId && <Building2 className="w-4 h-4 mr-1" />}

            {breadcrumb.isActive ? (
              <span className="font-medium text-foreground">{breadcrumb.label}</span>
            ) : (
              <Link href={breadcrumb.href} className="hover:text-foreground transition-colors">
                {breadcrumb.label}
              </Link>
            )}
          </div>
        </div>
      ))}
    </nav>
  )
}

function formatSegmentLabel(segment: string, t: (key: string) => string): string {
  const translationKey = segmentTranslations[segment]
  if (translationKey) {
    return t(translationKey)
  }

  return segment
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}
