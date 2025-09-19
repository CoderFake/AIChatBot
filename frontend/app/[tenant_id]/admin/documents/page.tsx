'use client'

import { use } from 'react'
import { DocumentManagement } from '@/components/tenant-admin/document-management'

interface DocumentsPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function DocumentsPage({ params }: DocumentsPageProps) {
  const { tenant_id: tenantId } = use(params)

  return <DocumentManagement tenantId={tenantId} />
}
