"use client"

import type React from "react"

import { use, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/lib/use-toast"
import { ArrowLeft, Mail, CheckCircle, Building2 } from "lucide-react"
import { apiService } from "@/lib/api/index"

interface TenantInfo {
  id: string
  tenant_name: string
  settings: {
    description: string
    branding: {
      logo_url: string
      primary_color: string
    }
  }
}

interface ForgotPasswordPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function ForgotPasswordPage({ params }: ForgotPasswordPageProps) {
  const router = useRouter()
  const { t } = useTranslation()
  const { showError, showSuccess } = useToast()
  const { tenant_id: tenantId } = use(params)

  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [error, setError] = useState("")
  const [tenantInfo, setTenantInfo] = useState<TenantInfo | null>(null)

  useEffect(() => {
    const fetchTenantInfo = async () => {
      try {
        const tenant = await apiService.tenants.getPublicInfo(tenantId)
        setTenantInfo({
          id: tenant.id,
          tenant_name: tenant.tenant_name,
          settings: {
            description: tenant.description || "",
            branding: {
              logo_url: tenant.sub_domain ? `https://${tenant.sub_domain}.cdn.logo` : "",
              primary_color: "#6366f1",
            },
          },
        })
      } catch (error) {
        console.error("Error fetching tenant info:", error)
      }
    }

    if (tenantId) {
      fetchTenantInfo()
    }
  }, [tenantId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await apiService.auth.requestPasswordReset(email, tenantId)
      showSuccess(t("auth.resetPassword"), t("messages.success.resetEmailSent"))
      setIsSuccess(true)
    } catch (err) {
      showError(err instanceof Error ? err.message : t("messages.errors.failedToSendResetEmail"))
    } finally {
      setIsLoading(false)
    }
  }

  const handleBackToLogin = () => {
    router.push(`/${tenantId}/login`)
  }

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-secondary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-secondary" />
            </div>
            <CardTitle className="font-sans">{t("auth.checkEmail")}</CardTitle>
            <CardDescription className="font-serif">{t("auth.resetLinkSent", { email })}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-center text-sm text-muted-foreground font-serif">
              <p>{t("auth.didntReceiveEmail")}</p>
            </div>
            <Button onClick={handleBackToLogin} className="w-full font-sans">
              {t("auth.backToLogin")}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="flex items-center justify-center">
          <Button variant="ghost" size="sm" onClick={handleBackToLogin} className="absolute top-4 left-4 font-serif">
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t("auth.backToLogin")}
          </Button>
        </div>

        <Card>
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <Mail className="w-8 h-8 text-primary" />
            </div>
            <CardTitle className="font-sans">{t("auth.resetPassword")}</CardTitle>
            <CardDescription className="font-serif">{t("auth.resetPasswordDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="font-serif">
                  {t("auth.emailAddress")}
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder={t("auth.enterEmail")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={isLoading}
                  className="font-serif"
                />
              </div>

              <Button type="submit" className="w-full font-sans" disabled={isLoading}>
                {isLoading ? t("auth.sending") : t("auth.sendResetLink")}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
