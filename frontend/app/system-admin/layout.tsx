"use client"

import type React from "react"
import { usePathname } from "next/navigation"
import { RouteGuard } from "@/components/auth/route-guard"
import { SystemAdminSidebar } from "@/components/system-admin/sidebar"
import { SystemAdminHeader } from "@/components/system-admin/header"

export default function SystemAdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  if (pathname === "/system-admin/login") {
    return <>{children}</>
  }

  return (
    <RouteGuard requireAuth requiredRoles={["MAINTAINER"]}>
      <div className="min-h-screen bg-background overflow-y-auto">
        <SystemAdminSidebar />
        <div className="lg:pl-64">
          <SystemAdminHeader />
          <main className="p-6">{children}</main>
        </div>
      </div>
    </RouteGuard>
  )
}
