"use client"

import type React from "react"

import { use, useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { CheckCircle, UserPlus, Building2 } from "lucide-react"
import { apiService } from "@/lib/api/index"
import { useToast } from "@/lib/use-toast"

export const dynamic = 'force-dynamic'

interface InviteAcceptPageProps {
  params: Promise<{
    tenant_id: string
  }>
}

export default function InviteAcceptPage({ params }: InviteAcceptPageProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { t } = useTranslation()
  const { showError } = useToast()
  const { tenant_id: tenantId } = use(params)

  const [token, setToken] = useState<string | null>(null)

  const [formData, setFormData] = useState({
    new_password: "",
    confirm_password: "",
  })
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [error, setError] = useState("")
  const [inviteInfo, setInviteInfo] = useState<{
    email: string
    username: string
    role: string
    tenant_id: string
    tenant_name: string
    token_type: string
  } | null>(null)
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsClient(true)
      const hash = window.location.hash
      if (hash.startsWith('#token=')) {
        const tokenValue = hash.substring(7) 
        setToken(tokenValue)
      } else {
        setToken(searchParams.get("token")) 
      }
    }
  }, [searchParams])

  useEffect(() => {
    const validateToken = async () => {
      if (!isClient || !token) {
        return
      }

      try {
        const tokenInfo = await apiService.auth.validateInviteToken(token)

        if (tokenInfo.tenant_id && tokenInfo.tenant_id !== tenantId) {
          router.push(`/${tokenInfo.tenant_id}/invite#token=${token}`)
          return
        }

        setInviteInfo({
          email: tokenInfo.email,
          username: tokenInfo.username,
          role: tokenInfo.role,
          tenant_id: tokenInfo.tenant_id || tenantId,
          tenant_name: tokenInfo.tenant_name || tenantId.toUpperCase(),
          token_type: tokenInfo.token_type,
        })
        setError("") 
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : ""
        if (errorMessage.includes("expired")) {
          setError(t("invite.inviteTokenExpired"))
        } else if (errorMessage.includes("already been used")) {
          setError(t("invite.inviteTokenUsed"))
          setTimeout(() => router.push(`/${tenantId}/login`), 3000)
        } else {
          setError(t("invite.invalidInviteToken"))
        }
      }
    }

    validateToken()
  }, [isClient, token, tenantId, t, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (formData.new_password !== formData.confirm_password) {
      setError(t("invite.passwordsNotMatch"))
      return
    }

    if (formData.new_password.length < 8) {
      setError(t("invite.passwordTooShort"))
      return
    }

    if (!token) {
      setError(t("invite.invalidInviteToken"))
      return
    }

    setIsLoading(true)

    try {
      await apiService.auth.acceptInvite(token, formData.new_password)
      if (inviteInfo?.username) {
        try {
          await apiService.auth.login({
            username: inviteInfo.username,
            password: formData.new_password,
            remember_me: false
          })
          setIsSuccess(true)
        } catch (loginError) {
          console.error("Auto-login failed:", loginError)
          setIsSuccess(true)
        }
      } else {
        setIsSuccess(true)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t("invite.acceptFailed")
      showError(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoToDashboard = () => {
    router.push(`/${tenantId}/dashboard`)
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
            <CardTitle className="font-sans" suppressHydrationWarning>{t("invite.welcomeToTeam")}</CardTitle>
            <CardDescription className="font-serif" suppressHydrationWarning>{t("invite.accountCreated")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleGoToDashboard} className="w-full font-sans" suppressHydrationWarning>
              {t("invite.goToDashboard")}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!isClient || (!inviteInfo && !error)) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
            </div>
            <CardTitle className="font-sans" suppressHydrationWarning>{t("invite.validatingInvite")}</CardTitle>
            <CardDescription className="font-serif" suppressHydrationWarning>{t("invite.pleaseWait")}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (error || !inviteInfo) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="font-sans" suppressHydrationWarning>{t("invite.invalidInvite")}</CardTitle>
            <CardDescription className="font-serif" suppressHydrationWarning>{error || t("invite.inviteExpired")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push("/")} className="w-full font-sans" suppressHydrationWarning>
              {t("invite.returnHome")}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center font-sans" suppressHydrationWarning>Loading...</CardTitle>
          </CardHeader>
        </Card>
      </div>
    }>
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <UserPlus className="w-8 h-8 text-primary" />
            </div>
            <CardTitle className="font-sans" suppressHydrationWarning>{t("invite.acceptInvitation")}</CardTitle>
            <CardDescription className="font-serif" suppressHydrationWarning>
              {t("invite.invitedToJoin", {
                tenant_name: inviteInfo.tenant_name,
                role: inviteInfo.role
              })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-6 p-4 bg-card rounded-lg border">
              <div className="flex items-center space-x-3">
                <Building2 className="w-5 h-5 text-primary" />
                <div>
                  <p className="font-medium font-sans">{inviteInfo.tenant_name}</p>
                  <p className="text-sm text-muted-foreground font-serif">{inviteInfo.email}</p>
                  <p className="text-sm text-secondary font-serif">Role: {inviteInfo.role}</p>
                </div>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="new_password" className="font-serif" suppressHydrationWarning>
                  {t("invite.setYourPassword")}
                </Label>
                <Input
                  id="new_password"
                  type="password"
                  placeholder={t("forms.placeholders.enterPassword")}
                  value={formData.new_password}
                  onChange={handleInputChange("new_password")}
                  required
                  disabled={isLoading}
                  className="font-serif"
                  suppressHydrationWarning
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm_password" className="font-serif" suppressHydrationWarning>
                  {t("invite.confirmPassword")}
                </Label>
                <Input
                  id="confirm_password"
                  type="password"
                  placeholder={t("forms.placeholders.confirmPassword")}
                  value={formData.confirm_password}
                  onChange={handleInputChange("confirm_password")}
                  required
                  disabled={isLoading}
                  className="font-serif"
                  suppressHydrationWarning
                />
              </div>

              <div className="text-xs text-muted-foreground font-serif" suppressHydrationWarning>
                <p>{t("invite.passwordMinLength")}</p>
              </div>

              <Button type="submit" className="w-full font-sans" disabled={isLoading || !token} suppressHydrationWarning>
                {isLoading ? t("invite.creatingAccount") : t("invite.acceptInvitationButton")}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </Suspense>
  )
}
