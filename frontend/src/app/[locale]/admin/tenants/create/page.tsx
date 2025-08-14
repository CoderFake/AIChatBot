'use client'
import React, {FormEvent, useEffect, useMemo, useState} from 'react'
import {useToast} from '../../../../../components/ToastProvider'
import {apiFetch} from '../../../../../lib/api'

export default function CreateTenantPage() {
  const {show} = useToast()
  const [tenant_name, setTenantName] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [sub_domain, setSubDomain] = useState('')
  const [locale, setLocale] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Data for selects
  type LocaleResp = { languages: string[]; default_language: string }
  type TzInfo = { value: string; label: string; country: string }
  type TzGroup = { region: string; timezones: TzInfo[] }
  type TzResp = { groups: TzGroup[]; total_timezones: number }

  const [languages, setLanguages] = useState<string[]>([])
  const [defaultLanguage, setDefaultLanguage] = useState<string>('en')
  const [tzGroups, setTzGroups] = useState<TzGroup[]>([])

  const languageToLocale = useMemo(() => ({
    vi: 'vi_VN',
    en: 'en_US',
    ja: 'ja_JP',
    kr: 'ko_KR'
  } as Record<string, string>), [])

  useEffect(() => {
    const loadAux = async () => {
      try {
        const [loc, tz] = await Promise.all([
          apiFetch<LocaleResp>('/api/v1/others/locales'),
          apiFetch<TzResp>('/api/v1/others/timezones')
        ])
        setLanguages(loc.languages)
        setDefaultLanguage(loc.default_language)
        setLocale(languageToLocale[loc.default_language] || 'en_US')
        setTzGroups(tz.groups)
        if (tz.groups?.length) {
          const first = tz.groups[0].timezones?.[0]?.value
          if (first) setTimezone(first)
        }
      } catch (e) {
      }
    }
    loadAux()
  }, [languageToLocale])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    try {
      setLoading(true)
      const res = await apiFetch('/api/v1/admin/tenants', {
        method: 'POST',
        body: JSON.stringify({ tenant_name, timezone, sub_domain, locale: locale || languageToLocale[defaultLanguage] || 'en_US', description })
      })
      setSuccess('Created tenant successfully')
      show('Tenant created', 'success')
      setTenantName(''); setSubDomain(''); setDescription('')
    } catch (e: any) {
      setError(e?.message || 'Failed to create tenant')
      show('Failed to create tenant', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Tạo Tenant mới</h1>
          <p className="mt-2 text-gray-600">Điền thông tin để tạo tổ chức mới trong hệ thống</p>
        </div>

        <div className="card">
          <form onSubmit={onSubmit} className="space-y-6">
            <div className="form-group">
              <label className="form-label">Tên tổ chức *</label>
              <input 
                type="text"
                value={tenant_name} 
                onChange={(e)=>setTenantName(e.target.value)} 
                required 
                className="input-field"
                placeholder="Nhập tên tổ chức"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Subdomain *</label>
              <input 
                type="text"
                value={sub_domain} 
                onChange={(e)=>setSubDomain(e.target.value)} 
                required 
                className="input-field"
                placeholder="tenant-slug"
              />
              <p className="mt-1 text-sm text-gray-500">
                Subdomain sẽ được sử dụng trong URL: https://subdomain.domain.com
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">Múi giờ *</label>
              <select 
                value={timezone} 
                onChange={(e)=>setTimezone(e.target.value)} 
                required 
                className="input-field"
              >
                {tzGroups.map((g)=> (
                  <optgroup key={g.region} label={g.region}>
                    {g.timezones.map((z)=> (
                      <option key={z.value} value={z.value}>{z.label} ({z.country})</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Ngôn ngữ *</label>
              <select 
                value={locale} 
                onChange={(e)=>setLocale(e.target.value)} 
                required 
                className="input-field"
              >
                {languages.map((lng)=> (
                  <option key={lng} value={languageToLocale[lng] || lng}>
                    {lng === 'vi' ? 'Tiếng Việt' : lng === 'en' ? 'English' : lng === 'ja' ? '日本語' : lng === 'kr' ? '한국어' : lng}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Mô tả</label>
              <textarea 
                value={description} 
                onChange={(e)=>setDescription(e.target.value)} 
                rows={3} 
                className="input-field"
                placeholder="Mô tả về tổ chức (tùy chọn)"
              />
            </div>

            <div className="flex items-center justify-between pt-6 border-t border-gray-200">
              <a 
                href="../tenants" 
                className="btn-secondary"
              >
                ← Quay lại
              </a>
              <button 
                type="submit" 
                disabled={loading} 
                className="btn-primary"
              >
                {loading ? 'Đang tạo...' : 'Tạo Tenant'}
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
    </div>
  )
}


