'use client'

import { use } from 'react'
import { InviteManagement } from '@/components/tenant-admin/invite-management'

interface InvitePageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function InvitePage({ params }: InvitePageProps) {
  const { tenant_id: tenantId } = use(params)

  return <InviteManagement tenantId={tenantId} />
}
