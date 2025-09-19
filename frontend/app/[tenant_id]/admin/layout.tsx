"use client"

import type React from "react"
import { RouteGuard } from "@/components/auth/route-guard"
import { TenantAdminSidebar } from "@/components/tenant-admin/sidebar"
import { TenantAdminHeader } from "@/components/tenant-admin/header"
import { NavigationBreadcrumb } from "@/components/routing/navigation-breadcrumb"
import { Toaster } from "@/components/ui/toaster"

export default function TenantAdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RouteGuard requireAuth requiredRoles={["ADMIN", "MAINTAINER"]}>
      <div className="min-h-screen bg-background overflow-y-auto">
        <TenantAdminSidebar />
        <div className="lg:pl-64">
          <TenantAdminHeader />
          <main className="p-6">
            <NavigationBreadcrumb />
            {children}
          </main>
        </div>
        <Toaster />
      </div>
    </RouteGuard>
  )
}
