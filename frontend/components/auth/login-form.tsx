"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"
import { useAuth, getPostLoginRedirectPath } from "@/lib/auth-context"
import { useTranslation } from "react-i18next"

interface LoginFormProps {
  title: string
  description: string
  onSuccess?: (redirectPath?: string) => void
  showRememberMe?: boolean
  className?: string
  loginType: "maintainer" | "tenant"
  tenantId?: string
  onForgotPassword?: () => void
}

export function LoginForm({
  title,
  description,
  onSuccess,
  showRememberMe = true,
  className,
  loginType,
  tenantId,
  onForgotPassword,
}: LoginFormProps) {
  const [formData, setFormData] = useState({
    username: "",
    password: "",
    remember_me: false,
  })
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const { login, user } = useAuth()
  const router = useRouter()
  const { t } = useTranslation()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    try {
      await login(formData.username, formData.password, tenantId)

      if (onSuccess) {
        onSuccess()
      } else {
        // Get redirect path based on user role after login
        const redirectPath = getPostLoginRedirectPath(user)
        router.push(redirectPath)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputChange = (field: keyof typeof formData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({
      ...prev,
      [field]: e.target.value,
    }))
  }

  return (
    <Card className={`w-full max-w-md ${className}`}>
      <CardHeader className="space-y-1">
        <CardTitle className="text-2xl font-bold text-center font-sans">{title}</CardTitle>
        <CardDescription className="text-center font-serif">{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Label htmlFor="username" className="font-serif">
              {t("common.username")}
            </Label>
            <Input
              id="username"
              type="text"
              placeholder={t("forms.placeholders.enterUsername")}
              value={formData.username}
              onChange={handleInputChange("username")}
              required
              disabled={isLoading}
              className="font-serif px-3 py-3"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password" className="font-serif">
              {t("common.password")}
            </Label>
            <Input
              id="password"
              type="password"
              placeholder={t("forms.placeholders.enterPassword")}
              value={formData.password}
              onChange={handleInputChange("password")}
              required
              disabled={isLoading}
              className="font-serif px-3 py-3"
            />
          </div>

          <Button type="submit" className="w-full font-sans py-3 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors" disabled={isLoading}>
            {isLoading ? t("forms.buttons.signingIn") : t("common.login")}
          </Button>
          {onForgotPassword && (
            <div className="text-center space-y-2">
              <Button variant="link" onClick={onForgotPassword} className="text-sm font-serif" suppressHydrationWarning>
                {t("auth.forgotPassword")}
              </Button>
            </div>
          )}
        </form>

      </CardContent>
    </Card>
  )
}
