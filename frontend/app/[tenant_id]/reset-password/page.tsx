"use client"

import type React from "react"

import { use, useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useTranslation } from "react-i18next"
import { CheckCircle, Key } from "lucide-react"
import { apiService } from "@/lib/api/index"
import { useToast } from "@/lib/use-toast"

interface ResetPasswordPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

function ResetPasswordPageContent({ params }: ResetPasswordPageProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { t } = useTranslation()
  const { showError, showSuccess } = useToast()
  const { tenant_id: tenantId } = use(params)

  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hash = window.location.hash
      if (hash.startsWith('#token=')) {
        const tokenValue = hash.substring(7) 
        setToken(tokenValue)
      } else {
        const queryToken = searchParams.get("token")
        if (queryToken) {
          setToken(queryToken)
        } else {
          setToken(null)
        }
      }
    }
  }, [searchParams])

  const [formData, setFormData] = useState({
    new_password: "",
    confirm_password: "",
  })
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (formData.new_password !== formData.confirm_password) {
      showError(t("messages.errors.passwordsDoNotMatch"))
      return
    }

    if (formData.new_password.length < 8) {
      showError(t("auth.passwordRequirements"))
      return
    }

    if (!token) {
      showError(t("messages.errors.invalidResetToken"))
      return
    }

    setIsLoading(true)

    try {
      await apiService.auth.resetPassword(token, formData.new_password)
      showSuccess(t("auth.passwordResetSuccessful"), t("auth.passwordUpdated"))
      setIsSuccess(true)
    } catch (err) {
      showError(err instanceof Error ? err.message : t("messages.errors.failedToResetPassword"))
    } finally {
      setIsLoading(false)
    }
  }

  const handleBackToLogin = () => {
    router.push(`/${tenantId}/login`)
  }

  const handleInputChange = (field: keyof typeof formData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({
      ...prev,
      [field]: e.target.value,
    }))
  }

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-secondary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-secondary" />
            </div>
            <CardTitle className="font-sans">{t("auth.passwordResetSuccessful")}</CardTitle>
            <CardDescription className="font-serif">{t("auth.passwordUpdated")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleBackToLogin} className="w-full font-sans">
              {t("auth.signInWithNewPassword")}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <Key className="w-8 h-8 text-primary" />
          </div>
          <CardTitle className="font-sans">{t("auth.setNewPassword")}</CardTitle>
          <CardDescription className="font-serif">{t("auth.enterNewPassword")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new_password" className="font-serif">
                {t("auth.newPassword")}
              </Label>
              <Input
                id="new_password"
                type="password"
                placeholder={t("auth.newPassword")}
                value={formData.new_password}
                onChange={handleInputChange("new_password")}
                required
                disabled={isLoading}
                className="font-serif"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm_password" className="font-serif">
                {t("auth.confirmPassword")}
              </Label>
              <Input
                id="confirm_password"
                type="password"
                placeholder={t("auth.confirmNewPassword")}
                value={formData.confirm_password}
                onChange={handleInputChange("confirm_password")}
                required
                disabled={isLoading}
                className="font-serif"
              />
            </div>

            <div className="text-xs text-muted-foreground font-serif">
              <p>{t("auth.passwordRequirements")}</p>
            </div>

            <Button type="submit" className="w-full font-sans" disabled={isLoading || !token}>
              {isLoading ? t("auth.updating") : t("auth.updatePassword")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export default function ResetPasswordPage({ params }: ResetPasswordPageProps) {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ResetPasswordPageContent params={params} />
    </Suspense>
  )
}
