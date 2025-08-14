'use client'
import {useState} from 'react'
import {useToast} from '../../../components/ToastProvider'

export default function ChangePasswordPage() {
  const {show} = useToast()
  const [current_password, setCurrent] = useState('')
  const [new_password, setNew] = useState('')
  const [confirm_password, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async()=>{
    if (!current_password || !new_password || !confirm_password) { show('Fill all fields', 'warn'); return }
    try {
      setLoading(true)
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/auth/change-password`, {
        method:'POST', headers:{'Content-Type':'application/json', 'Authorization':`Bearer ${localStorage.getItem('token')||''}`},
        body: JSON.stringify({ current_password, new_password, confirm_password })
      })
      if (!res.ok) throw new Error(await res.text())
      show('Password changed', 'success')
      setCurrent(''); setNew(''); setConfirm('')
    } catch(e:any){
      show('Change password failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Đổi mật khẩu</h2>
          <p className="mt-2 text-gray-600">
            Cập nhật mật khẩu hiện tại của bạn
          </p>
        </div>

        <div className="card">
          <div className="space-y-6">
            <div className="form-group">
              <label className="form-label">
                Mật khẩu hiện tại
              </label>
              <input 
                type="password" 
                placeholder="Nhập mật khẩu hiện tại" 
                value={current_password} 
                onChange={e=>setCurrent(e.target.value)}
                className="input-field"
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Mật khẩu mới
              </label>
              <input 
                type="password" 
                placeholder="Nhập mật khẩu mới" 
                value={new_password} 
                onChange={e=>setNew(e.target.value)}
                className="input-field"
                minLength={6}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Xác nhận mật khẩu mới
              </label>
              <input 
                type="password" 
                placeholder="Nhập lại mật khẩu mới" 
                value={confirm_password} 
                onChange={e=>setConfirm(e.target.value)}
                className="input-field"
                minLength={6}
              />
              {new_password && confirm_password && new_password !== confirm_password && (
                <p className="mt-1 text-sm text-red-600">
                  Mật khẩu xác nhận không khớp
                </p>
              )}
            </div>

            <button 
              onClick={submit} 
              disabled={loading || !current_password || !new_password || !confirm_password || new_password !== confirm_password}
              className="btn-primary w-full"
            >
              {loading ? 'Đang lưu...' : 'Đổi mật khẩu'}
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


