import {useTranslations} from 'next-intl'
import Link from 'next/link'

export default function HomePage() {
  const t = useTranslations()
  return (
    <main className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">{t('app.title')}</h1>
          <p className="text-lg text-gray-600">{t('app.welcome')}</p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Admin Panel</h3>
            <p className="text-gray-600 mb-4">Quản lý tenant và người dùng hệ thống</p>
            <Link href="/vi/admin/tenants" className="btn-primary inline-block">
              Quản trị Tenants
            </Link>
          </div>
          
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Quên mật khẩu</h3>
            <p className="text-gray-600 mb-4">Đặt lại mật khẩu tài khoản</p>
            <Link href="/vi/forgot-password" className="btn-secondary inline-block">
              Quên mật khẩu
            </Link>
          </div>
          
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Đặt lại mật khẩu</h3>
            <p className="text-gray-600 mb-4">Nhập mật khẩu mới với token</p>
            <Link href="/vi/reset" className="btn-secondary inline-block">
              Đặt lại
            </Link>
          </div>
          
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Chấp nhận lời mời</h3>
            <p className="text-gray-600 mb-4">Kích hoạt tài khoản từ lời mời</p>
            <Link href="/vi/invite" className="btn-secondary inline-block">
              Chấp nhận lời mời
            </Link>
          </div>
          
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Đổi mật khẩu</h3>
            <p className="text-gray-600 mb-4">Thay đổi mật khẩu hiện tại</p>
            <Link href="/vi/change-password" className="btn-secondary inline-block">
              Đổi mật khẩu
            </Link>
          </div>
        </div>
      </div>
    </main>
  )
}


