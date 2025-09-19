'use client'

import { use } from 'react'
import { TenantDashboard } from '@/components/tenant-admin/dashboard'

interface TenantAdminPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function TenantAdminDashboard({ params }: TenantAdminPageProps) {
  const { tenant_id: tenantId } = use(params)

  return <TenantDashboard tenantId={tenantId} />
}
