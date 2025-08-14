'use client'
import React, {useState} from 'react'
import {useToast} from '../../../components/ToastProvider'

export default function ForgotPasswordPage() {
  const {show} = useToast()
  const [username_or_email, setValue] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async()=>{
    try {
      setLoading(true)
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/auth/forgot-password`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ username_or_email })
      })
      if (!res.ok) throw new Error(await res.text())
      show('If account exists, an email has been sent', 'success')
    } catch(e:any){
      show('Request failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Quên mật khẩu</h2>
          <p className="mt-2 text-gray-600">
            Nhập tên đăng nhập hoặc email để nhận liên kết đặt lại mật khẩu
          </p>
        </div>

        <div className="card">
          <div className="space-y-6">
            <div className="form-group">
              <label className="form-label">
                Tên đăng nhập hoặc Email
              </label>
              <input 
                type="text"
                placeholder="Nhập username hoặc email" 
                value={username_or_email} 
                onChange={e=>setValue(e.target.value)}
                className="input-field"
              />
            </div>

            <button 
              onClick={submit} 
              disabled={loading}
              className="btn-primary w-full"
            >
              {loading ? 'Đang gửi...' : 'Gửi liên kết đặt lại'}
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


