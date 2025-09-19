"use client"

import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { AlertTriangle, Home, LogOut, ArrowLeft } from "lucide-react"
import { useEffect, useState } from "react"

export default function UnauthorizedPage() {
  const router = useRouter()
  const { user, logout } = useAuth()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const handleGoBack = () => {
    router.back()
  }

  const handleGoHome = () => {
    if (user?.role === 'MAINTAINER') {
      router.push('/system-admin/dashboard')
    } else if (user?.tenant_id) {
      router.push(`/${user.tenant_id}/dashboard`)
    } else {
      router.push('/')
    }
  }

  const handleLogout = async () => {
    try {
      await logout()
      router.push('/')
    } catch (error) {
      console.error('Logout failed:', error)
      router.push('/')
    }
  }

  if (!mounted) {
    return null
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Error Card */}
        <Card className="border-red-200">
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-600" />
            </div>
            <CardTitle className="text-2xl text-red-600">Không có quyền truy cập</CardTitle>
            <CardDescription className="text-red-500">
              Bạn không có quyền truy cập vào trang này
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <div className="text-sm text-muted-foreground space-y-2">
              <p>
                Trang bạn đang cố gắng truy cập yêu cầu quyền hạn cao hơn hoặc 
                vai trò khác với tài khoản hiện tại của bạn.
              </p>
              {user && (
                <div className="bg-muted/50 rounded-lg p-3 mt-4">
                  <p className="font-medium text-foreground">Thông tin tài khoản:</p>
                  <p className="text-sm">
                    <span className="font-medium">Tên đăng nhập:</span> {user.username}
                  </p>
                  <p className="text-sm">
                    <span className="font-medium">Vai trò:</span>{" "}
                    <span className="font-mono px-2 py-1 bg-background rounded text-xs">
                      {user.role}
                    </span>
                  </p>
                  {user.tenant_id && (
                    <p className="text-sm">
                      <span className="font-medium">Tổ chức:</span> {user.tenant_id}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col space-y-3 pt-4">
              <Button
                onClick={handleGoBack}
                variant="outline"
                className="w-full"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Quay lại trang trước
              </Button>
              
              <Button
                onClick={handleGoHome}
                className="w-full"
              >
                <Home className="w-4 h-4 mr-2" />
                Về trang chủ
              </Button>
              
              <Button
                onClick={handleLogout}
                variant="destructive"
                className="w-full"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Đăng xuất
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Help Text */}
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-6">
            <div className="text-sm text-blue-700 space-y-2">
              <p className="font-medium">Cần trợ giúp?</p>
              <p>
                Nếu bạn cho rằng đây là lỗi hoặc cần quyền truy cập, 
                vui lòng liên hệ với quản trị viên hệ thống hoặc 
                quản lý tổ chức của bạn.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Debug Info (only in development) */}
        {process.env.NODE_ENV === 'development' && (
          <Card className="bg-gray-50 border-gray-200">
            <CardContent className="pt-6">
              <div className="text-xs font-mono text-gray-600 space-y-1">
                <p className="font-semibold text-gray-700">Debug Info:</p>
                <p>Current Path: {typeof window !== 'undefined' ? window.location.pathname : 'N/A'}</p>
                <p>User Role: {user?.role || 'None'}</p>
                <p>Tenant ID: {user?.tenant_id || 'None'}</p>
                <p>Department ID: {user?.department_id || 'None'}</p>
                <p>Authenticated: {user ? 'Yes' : 'No'}</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}