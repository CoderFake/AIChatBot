import type React from "react"
import { TenantProvider } from "@/lib/tenant-context"
import { TenantLayout } from "@/components/routing/tenant-layout"

interface TenantRootLayoutProps {
  children: React.ReactNode
  params: Promise<{ tenant_id: string }>
}

export default async function TenantRootLayout({ children, params }: TenantRootLayoutProps) {
  const resolvedParams = await params

  return (
    <TenantProvider initialTenantId={resolvedParams.tenant_id}>
      <TenantLayout>{children}</TenantLayout>
    </TenantProvider>
  )
}
