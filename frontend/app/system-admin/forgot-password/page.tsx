"use client"

import type React from "react"

import { useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/lib/auth-context"
import { useToast } from "@/lib/use-toast"
import { useTranslation } from "react-i18next"

export default function SystemAdminForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const { requestPasswordReset } = useAuth()
  const { showError, showSuccess } = useToast()
  const { t } = useTranslation()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await requestPasswordReset(email)
      showSuccess(t("auth.resetPassword"), t("messages.success.resetEmailSent"))
      setSuccess(true)
    } catch (err) {
      showError(err instanceof Error ? err.message : t("messages.errors.failedToSendResetEmail"))
    } finally {
      setIsLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center font-sans">{t("auth.checkYourEmail")}</CardTitle>
            <CardDescription className="text-center font-serif">
              {t("auth.resetLinkSent", { email })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/system-admin/login">
              <Button className="w-full font-sans">{t("auth.returnToLogin")}</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
            <CardTitle className="text-center font-sans">{t("auth.resetPassword")}</CardTitle>
          <CardDescription className="text-center font-serif">
            {t("auth.enterEmailForReset")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="font-serif">
                {t("common.email")}
              </Label>
              <Input
                id="email"
                type="email"
                placeholder={t("forms.placeholders.enterEmail")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
                className="font-serif"
              />
            </div>

            <Button type="submit" className="w-full font-sans" disabled={isLoading}>
              {isLoading ? t("forms.buttons.sending") : t("forms.buttons.sendResetLink")}
            </Button>
          </form>

          <div className="mt-4 text-center">
            <Link href="/system-admin/login" className="text-sm text-primary hover:underline font-serif">
              {t("auth.returnToLogin")}
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
