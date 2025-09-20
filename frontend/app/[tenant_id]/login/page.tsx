"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslation } from "react-i18next"
import { LoginForm } from "@/components/auth/login-form"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Building2 } from "lucide-react"
import { RouteGuard } from "@/components/auth/route-guard"
import { useTenant, useTenantSettings } from "@/lib/tenant-context"

interface TenantLoginPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function TenantLoginPage({ params }: TenantLoginPageProps) {
  return (
    <RouteGuard requireAuth={false}>
      <TenantLoginContent params={params} />
    </RouteGuard>
  )
}

function TenantLoginContent({ params }: TenantLoginPageProps) {
  const router = useRouter()
  const { t } = useTranslation()
  const { tenant_id: tenantId } = use(params)
  const [tenantInfo, setTenantInfo] = useState<{
    tenant_name: string
    logo_url?: string
    description?: string
  } | null>(null)
  const [isLoadingInfo, setIsLoadingInfo] = useState(true)

  useEffect(() => {
    const fetchTenantInfo = async () => {
      try {
        setIsLoadingInfo(true)
        const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL
        const response = await fetch(`${apiUrl}/tenants/${tenantId}/public-info`)
        if (response.ok) {
          const data = await response.json()
          setTenantInfo({
            tenant_name: data.tenant_name,
            logo_url: data.logo_url,
            description: data.description
          })
        } else {
          setTenantInfo({
            tenant_name: tenantId,
            logo_url: undefined,
            description: undefined
          })
        }
      } catch (error) {
        console.error('Failed to fetch tenant info:', error)
        setTenantInfo({
          tenant_name: tenantId,
          logo_url: undefined,
          description: undefined
        })
      } finally {
        setIsLoadingInfo(false)
      }
    }

    if (tenantId) {
      fetchTenantInfo()
    }
  }, [tenantId])

  const logoUrl = tenantInfo?.logo_url
  const tenantName = tenantInfo?.tenant_name || tenantId

  const handleLoginSuccess = () => {
  }

  const handleBackToHome = () => {
    router.push("/")
  }

  const handleForgotPassword = () => {
    router.push(`/${tenantId}/forgot-password`)
  }

  if (!tenantId) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center font-sans" suppressHydrationWarning>
              {t("auth.invalidTenant")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Button onClick={handleBackToHome} className="w-full font-sans" suppressHydrationWarning>
              {t("common.returnHome")}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="h-dvh flex overflow-hidden">
      {/* Mobile Header - Gradient Background */}
      <div className="hidden lg:hidden w-full h-1/3 bg-gradient-to-br from-blue-600 via-purple-600 to-pink-500 p-8 text-white relative overflow-hidden">
        <div className="relative z-10 w-full h-full flex items-center">
          <div className="flex items-center space-x-4 min-w-0 w-full">
            <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
              {logoUrl ? (
                <img
                  src={logoUrl}
                  alt="Logo"
                  className="w-8 h-8 rounded-full object-cover"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement
                    target.style.display = "none"
                    target.parentElement!.innerHTML = `
                      <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                      </svg>
                    `
                  }}
                />
              ) : (
                <Building2 className="w-6 h-6 text-white" />
              )}
            </div>
            <h2 className="text-xl font-bold leading-tight text-white min-w-0 truncate">
              {tenantName}
            </h2>
          </div>
        </div>

        {/* Decorative Elements for Mobile */}
        <div className="absolute top-10 right-10 w-20 h-20 bg-white/5 rounded-full"></div>
        <div className="absolute bottom-10 right-20 w-16 h-16 bg-white/5 rounded-full"></div>
      </div>

      {/* Desktop Left Side - Gradient Background with Chat Preview */}
      <div className="hidden lg:flex lg:flex-1 lg:h-full bg-gradient-to-br from-blue-600 via-purple-600 to-pink-500 p-10 lg:p-16 text-white relative overflow-hidden items-center">
        <div className="relative z-10 w-full">
          <div className="mx-auto max-w-3xl space-y-8 lg:space-y-10">
            <div className="text-center space-y-2" suppressHydrationWarning>
              <div className="flex items-center justify-center gap-4">
                <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
                  {logoUrl ? (
                    <img
                      src={logoUrl}
                      alt="Logo"
                      className="w-12 h-12 rounded-full object-cover"
                      onError={(e) => {
                        const target = e.target as HTMLImageElement
                        target.style.display = "none"
                        target.parentElement!.innerHTML = `
                          <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                          </svg>
                        `
                      }}
                    />
                  ) : (
                    <Building2 className="w-8 h-8 text-white" />
                  )}
                </div>
                <h2 className="text-4xl lg:text-5xl font-bold leading-tight text-white min-w-0">
                  {tenantName}
                </h2>
              </div>
            </div>

            {/* Chat Bubbles */}
            <div className="space-y-5 mt-8 lg:mt-12">
              <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-5 max-w-2xl">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center">
                    <span className="text-xs">👤</span>
                  </div>
                  <span className="text-sm opacity-80">User</span>
                </div>
                <p className="text-base">Please help me find some internal company procedures</p>
              </div>

              <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-5 max-w-2xl ml-10 lg:ml-12">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center">
                    <span className="text-xs">🤖</span>
                  </div>
                  <span className="text-sm opacity-80">Newwave Chatbot</span>
                </div>
                <p className="text-base">I can help you access our internal procedures and documentation. Here are some available resources:</p>
                <div className="mt-3 space-y-2 text-sm opacity-90">
                  <p>1. HR Policies: Employee handbook, leave policies, and performance review procedures</p>
                  <p>2. IT Guidelines: Security protocols, software access requests, and technical support procedures</p>
                  <p>3. Finance Procedures: Expense reporting, budget approval workflows, and procurement guidelines</p>
                </div>
              </div>

              <p className="text-base opacity-80 mt-6">These are the main internal procedure categories for your organization. You can ask me for specific details about any of these areas. How can I assist you further?</p>
            </div>

            {/* Input Preview */}
            <div className="bg-white/10 backdrop-blur-sm rounded-full p-5 flex items-center gap-3 max-w-2xl mt-8 lg:mt-10">
              <div className="w-9 h-9 bg-white/20 rounded-full flex items-center justify-center">
                <span className="text-sm">😊</span>
              </div>
              <span className="text-sm opacity-70 flex-1">Reply...</span>
              <div className="w-9 h-9 bg-blue-500 rounded-full flex items-center justify-center">
                <span className="text-sm">→</span>
              </div>
            </div>
          </div>
        </div>

        {/* Decorative Elements */}
        <div className="absolute top-20 right-20 w-40 h-40 bg-white/5 rounded-full"></div>
        <div className="absolute bottom-20 right-48 w-24 h-24 bg-white/5 rounded-full"></div>
        <div className="absolute top-1/2 right-10 w-20 h-20 bg-white/5 rounded-full"></div>
      </div>

      {/* Login Form Section */}
      <div className="w-full lg:w-1/3 bg-white lg:p-8 lg:px-12 lg:py-10 p-6 flex flex-col justify-center lg:justify-center">
        <div className="max-w-sm mx-auto w-full">
          <div className="lg:hidden text-center mb-6">
            <h2 className="text-2xl font-bold text-transparent bg-gradient-to-r from-blue-600 via-purple-600 to-pink-500 bg-clip-text">
              {`SIGN IN TO ${tenantName}`.toUpperCase()}
            </h2>
          </div>

          <div className="hidden lg:block">
            <h2 className="text-3xl font-bold text-transparent bg-gradient-to-r from-blue-600 via-purple-600 to-pink-500 bg-clip-text mb-8">{`SIGN IN TO ${tenantName}`.toUpperCase()}</h2>
          </div>

          <div suppressHydrationWarning>
            <LoginForm
              title=""
              description=""
              onSuccess={handleLoginSuccess}
              loginType="tenant"
              tenantId={tenantId}
              onForgotPassword={handleForgotPassword}
            />
          </div>
        </div>
      </div>
    </div>
  )
}