'use client'
import React, {useEffect, useState} from 'react'
import {useToast} from '../../../components/ToastProvider'

export default function AcceptInvitePage() {
  const {show} = useToast()
  const [token, setToken] = useState<string>('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(()=>{
    const t = (typeof window !== 'undefined') ? new URL(window.location.href).hash.replace('#','') : ''
    const params = new URLSearchParams(t)
    setToken(params.get('token') || '')
  }, [])

  const submit = async () => {
    if (!token) { show('Missing token', 'error'); return }
    try {
      setLoading(true)
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/auth/accept-invite`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password || undefined })
      })
      if (!res.ok) throw new Error(await res.text())
      show('Invite accepted. You can login now.', 'success')
      setDone(true)
    } catch(e:any) {
      show('Invalid or used invite link', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Chấp nhận lời mời</h2>
          <p className="mt-2 text-gray-600">
            Kích hoạt tài khoản của bạn để bắt đầu sử dụng hệ thống
          </p>
        </div>

        {!done ? (
          <div className="card">
            <div className="space-y-6">
              <div className="form-group">
                <label className="form-label">
                  Mật khẩu mới (tùy chọn)
                </label>
                <input 
                  type="password" 
                  value={password} 
                  onChange={e=>setPassword(e.target.value)}
                  className="input-field"
                  placeholder="Để trống nếu muốn sử dụng mật khẩu tạm thời"
                />
                <p className="mt-1 text-sm text-gray-500">
                  Nếu không nhập, bạn sẽ cần đổi mật khẩu sau lần đăng nhập đầu tiên
                </p>
              </div>

              <button 
                onClick={submit} 
                disabled={loading}
                className="btn-primary w-full"
              >
                {loading ? 'Đang xử lý...' : 'Chấp nhận lời mời'}
              </button>
            </div>
          </div>
        ) : (
          <div className="card text-center">
            <div className="mb-4">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
                <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              Lời mời đã được chấp nhận
            </h3>
            <p className="text-gray-600 mb-4">
              Tài khoản của bạn đã được kích hoạt thành công. Bạn có thể đăng nhập ngay bây giờ.
            </p>
            <a href="/" className="btn-primary">
              Về trang chủ
            </a>
          </div>
        )}
      </div>
    </div>
  )
}


