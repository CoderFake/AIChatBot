'use client'

import { use } from 'react'
import { AgentManagement } from '@/components/tenant-admin/agent-management'

interface AgentsPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function AgentsPage({ params }: AgentsPageProps) {
  const { tenant_id: tenantId } = use(params)

  return <AgentManagement tenantId={tenantId} />
}
