'use client'
import {useEffect, useState, FormEvent} from 'react'
import {useToast} from '../../../../../components/ToastProvider'
import {apiFetch} from '../../../../../lib/api'
import {useParams, useRouter} from 'next/navigation'

type Tenant = {
  id: string
  tenant_name: string
  timezone: string
  locale: string
  sub_domain?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export default function TenantDetailPage() {
  const params = useParams<{tenantId: string, locale: string}>()
  const router = useRouter()
  const tenantId = params.tenantId

  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [tenant_name, setTenantName] = useState('')
  const [timezone, setTimezone] = useState('')
  const [sub_domain, setSubDomain] = useState('')
  const [locale, setLocale] = useState('')
  const [is_active, setIsActive] = useState(true)
  const [emails, setEmails] = useState('')
  const {show} = useToast()

  useEffect(()=>{
    const load = async()=>{
      try {
        setLoading(true)
        const data = await apiFetch<Tenant>(`/api/v1/admin/tenants/${tenantId}`)
        setTenant(data)
        setTenantName(data.tenant_name)
        setTimezone(data.timezone)
        setSubDomain(data.sub_domain || '')
        setLocale(data.locale)
        setIsActive(data.is_active)
      } catch(e:any){
        setError(e?.message || 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [tenantId])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null); setSuccess(null)
    try {
      setLoading(true)
      await apiFetch(`/api/v1/admin/tenants/${tenantId}`, {
        method: 'PUT',
        body: JSON.stringify({ tenant_name, timezone, sub_domain, locale, is_active })
      })
      setSuccess('Updated')
    } catch(e:any){
      setError(e?.message || 'Failed to update')
    } finally {
      setLoading(false)
    }
  }

  const onDelete = async () => {
    if (!confirm('Soft delete this tenant?')) return
    try {
      setLoading(true)
      await apiFetch(`/api/v1/admin/tenants/${tenantId}`, { method: 'DELETE' })
      router.push(`/${params.locale}/admin/tenants`)
    } catch(e:any){
      setError(e?.message || 'Failed to delete')
    } finally {
      setLoading(false)
    }
  }

  const inviteAdmins = async () => {
    const list = emails.split(',').map(s=>s.trim()).filter(Boolean)
    if (!list.length) { show('Please enter at least one email', 'warn'); return }
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/auth/maintainer/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('token') || ''}` },
        body: JSON.stringify({ tenant_id: tenantId, emails: list })
      })
      if (!res.ok) throw new Error(await res.text())
      show('Invites sent', 'success')
    } catch (e:any) {
      show('Failed to send invites', 'error')
    }
  }

  if (loading && !tenant) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-lg text-gray-600">Loading...</div>
    </div>
  )
  
  if (error && !tenant) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg p-4">
        Error: {error}
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Chi tiết Tenant</h1>
              <p className="mt-2 text-gray-600">Chỉnh sửa thông tin và quản lý tenant</p>
            </div>
            <a 
              href="../tenants" 
              className="btn-secondary"
            >
              ← Quay lại danh sách
            </a>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Form */}
          <div className="lg:col-span-2">
            <div className="card">
              <h2 className="text-xl font-semibold text-gray-900 mb-6">Thông tin cơ bản</h2>
              
              <form onSubmit={onSubmit} className="space-y-6">
                <div className="form-group">
                  <label className="form-label">Tên tổ chức *</label>
                  <input 
                    type="text"
                    value={tenant_name} 
                    onChange={(e)=>setTenantName(e.target.value)} 
                    required 
                    className="input-field"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Subdomain</label>
                  <input 
                    type="text"
                    value={sub_domain} 
                    onChange={(e)=>setSubDomain(e.target.value)} 
                    className="input-field"
                    placeholder="tenant-slug"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Múi giờ *</label>
                  <input 
                    type="text"
                    value={timezone} 
                    onChange={(e)=>setTimezone(e.target.value)} 
                    required 
                    className="input-field"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Ngôn ngữ *</label>
                  <input 
                    type="text"
                    value={locale} 
                    onChange={(e)=>setLocale(e.target.value)} 
                    required 
                    className="input-field"
                  />
                </div>

                <div className="form-group">
                  <div className="flex items-center">
                    <input 
                      id="is_active"
                      type="checkbox" 
                      checked={is_active} 
                      onChange={(e)=>setIsActive(e.target.checked)}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <label htmlFor="is_active" className="ml-2 block text-sm text-gray-700">
                      Tenant đang hoạt động
                    </label>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-6 border-t border-gray-200">
                  <button 
                    type="button" 
                    onClick={onDelete} 
                    disabled={loading} 
                    className="btn-danger"
                  >
                    Xóa Tenant
                  </button>
                  <button 
                    type="submit" 
                    disabled={loading} 
                    className="btn-primary"
                  >
                    {loading ? 'Đang lưu...' : 'Lưu thay đổi'}
                  </button>
                </div>

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-800">{error}</p>
                  </div>
                )}
                
                {success && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <p className="text-green-800">{success}</p>
                  </div>
                )}
              </form>
            </div>
          </div>

          {/* Invite Section */}
          <div className="lg:col-span-1">
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Mời Admin</h3>
              <p className="text-sm text-gray-600 mb-4">
                Nhập các email cách nhau bằng dấu phẩy để mời admin cho tenant này
              </p>
              
              <div className="space-y-4">
                <div className="form-group">
                  <label className="form-label">Email addresses</label>
                  <textarea
                    value={emails} 
                    onChange={(e)=>setEmails(e.target.value)} 
                    placeholder="admin1@example.com, admin2@example.com"
                    rows={3}
                    className="input-field"
                  />
                </div>
                
                <button 
                  type="button" 
                  onClick={inviteAdmins} 
                  className="btn-primary w-full"
                >
                  Gửi lời mời
                </button>
              </div>
            </div>

            {/* Tenant Info */}
            {tenant && (
              <div className="card mt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Thông tin</h3>
                <dl className="space-y-3">
                  <div>
                    <dt className="text-sm font-medium text-gray-500">ID</dt>
                    <dd className="text-sm text-gray-900 font-mono">{tenant.id}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Ngày tạo</dt>
                    <dd className="text-sm text-gray-900">
                      {new Date(tenant.created_at).toLocaleDateString('vi-VN')}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Cập nhật lần cuối</dt>
                    <dd className="text-sm text-gray-900">
                      {new Date(tenant.updated_at).toLocaleDateString('vi-VN')}
                    </dd>
                  </div>
                </dl>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


