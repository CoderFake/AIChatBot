'use client'

import { use } from 'react'
import { DepartmentManagement } from '@/components/tenant-admin/department-management'

interface DepartmentsPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function DepartmentsPage({ params }: DepartmentsPageProps) {
  const { tenant_id: tenantId } = use(params)

  return <DepartmentManagement tenantId={tenantId} />
}
