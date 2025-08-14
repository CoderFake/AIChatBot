'use client'
import React, {useEffect, useState} from 'react'
import {useToast} from '../../../components/ToastProvider'

export default function ResetPasswordPage() {
  const {show} = useToast()
  const [token, setToken] = useState('')
  const [new_password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(()=>{
    const t = (typeof window !== 'undefined') ? new URL(window.location.href).hash.replace('#','') : ''
    const params = new URLSearchParams(t)
    setToken(params.get('token') || '')
  }, [])

  const submit = async () => {
    if (!token || !new_password) { show('Missing token or password', 'warn'); return }
    try {
      setLoading(true)
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/auth/reset-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password })
      })
      if (!res.ok) throw new Error(await res.text())
      show('Password reset successfully', 'success')
    } catch(e:any) {
      show('Reset link invalid or expired', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Đặt lại mật khẩu</h2>
          <p className="mt-2 text-gray-600">
            Nhập mật khẩu mới cho tài khoản của bạn
          </p>
        </div>

        <div className="card">
          <div className="space-y-6">
            <div className="form-group">
              <label className="form-label">
                Mật khẩu mới
              </label>
              <input 
                type="password" 
                placeholder="Nhập mật khẩu mới" 
                value={new_password} 
                onChange={e=>setPassword(e.target.value)}
                className="input-field"
                minLength={6}
              />
              <p className="mt-1 text-sm text-gray-500">
                Mật khẩu phải có ít nhất 6 ký tự
              </p>
            </div>

            <button 
              onClick={submit} 
              disabled={loading || !token || !new_password}
              className="btn-primary w-full"
            >
              {loading ? 'Đang xử lý...' : 'Đặt lại mật khẩu'}
            </button>

            <div className="text-center">
              <a href="/" className="text-sm text-primary-600 hover:text-primary-800">
                ← Quay về trang chủ
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


