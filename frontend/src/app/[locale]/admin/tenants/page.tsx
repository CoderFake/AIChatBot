'use client'
import React, {useEffect, useState} from 'react'
import {apiFetch} from '../../../../lib/api'
import {useToast} from '../../../../components/ToastProvider'

type Tenant = {
  id: string
  tenant_name: string
  timezone: string
  locale: string
  sub_domain?: string
  is_active: boolean
  created_at: string
}

type TenantListResponse = {
  tenants: Tenant[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export default function TenantsPage() {
  const {show} = useToast()
  const [data, setData] = useState<TenantListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const res = await apiFetch<TenantListResponse>('/api/v1/admin/tenants')
        setData(res)
      } catch (e: any) {
        const msg = e?.message || 'Failed to load'
        setError(msg)
        show(msg, 'error')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-lg text-gray-600">Loading...</div>
    </div>
  )
  
  if (error) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-4">
        Error: {error}
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Quản lý Tenants</h1>
          <p className="mt-2 text-gray-600">Danh sách và quản lý các tổ chức trong hệ thống</p>
        </div>
        
        <div className="mb-6">
          <a href="tenants/create" className="btn-primary">
            + Tạo Tenant mới
          </a>
        </div>
        
        <div className="card">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Tên tổ chức</th>
                  <th>Subdomain</th>
                  <th>Múi giờ</th>
                  <th>Ngôn ngữ</th>
                  <th>Trạng thái</th>
                  <th>Ngày tạo</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data?.tenants.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="font-medium text-gray-900">{t.tenant_name}</td>
                    <td className="text-gray-500">{t.sub_domain || '-'}</td>
                    <td className="text-gray-500">{t.timezone}</td>
                    <td className="text-gray-500">{t.locale}</td>
                    <td>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        t.is_active 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {t.is_active ? 'Hoạt động' : 'Tạm dừng'}
                      </span>
                    </td>
                    <td className="text-gray-500 text-sm">
                      {new Date(t.created_at).toLocaleDateString('vi-VN')}
                    </td>
                    <td>
                      <a 
                        href={`tenants/${t.id}`} 
                        className="text-primary-600 hover:text-primary-800 font-medium"
                      >
                        Xem chi tiết
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {data && (
            <div className="mt-6 flex items-center justify-between border-t border-gray-200 pt-4">
              <div className="text-sm text-gray-700">
                Tổng cộng: <span className="font-medium">{data.total}</span> tenant
              </div>
              <div className="text-sm text-gray-500">
                Trang {data.page} {data.has_more && '• Có thêm dữ liệu'}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


