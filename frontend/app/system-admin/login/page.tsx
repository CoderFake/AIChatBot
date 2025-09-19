"use client"

import React, { useState } from "react"
import { Eye, EyeOff } from "lucide-react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { useToast } from "@/lib/use-toast"
import { useTranslation } from "react-i18next"
import { RouteGuard } from "@/components/auth/route-guard"

export default function SystemAdminLoginPage() {
  return (
    <RouteGuard requireAuth={false}>
      <SystemAdminLoginContent />
    </RouteGuard>
  )
}

function SystemAdminLoginContent() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const router = useRouter()
  const { login } = useAuth()
  const { showError, showSuccess } = useToast()
  const { t } = useTranslation()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await login(username, password)
      showSuccess(t("auth.loginSuccess"))
      // Redirect will be handled by auth context automatically
      // User will be redirected based on their role
    } catch (err) {
      showError(err instanceof Error ? err.message : t("auth.invalidCredentials"))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="h-dvh flex overflow-hidden">
      {/* Left Side - Gradient Background with Chat Preview */}
      <div className="hidden lg:flex lg:flex-1 lg:h-full bg-gradient-to-br from-blue-600 via-purple-600 to-pink-500 p-10 lg:p-16 text-white relative overflow-hidden items-center">
        <div className="relative z-10 w-full">
          <div className="mx-auto max-w-3xl space-y-8 lg:space-y-10">
            <h2 className="text-4xl lg:text-5xl font-bold leading-tight">
              Learn, Discover &<br />
              Automate in One Place.
            </h2>

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

      {/* Right Side - Login Form */}
      <div className="w-full lg:w-1/3 bg-white p-8 lg:px-12 lg:py-10 flex flex-col justify-center">
        <div className="max-w-sm mx-auto w-full">
          <h2 className="text-4xl font-bold text-transparent bg-gradient-to-r from-blue-600 via-purple-600 to-pink-500 bg-clip-text mb-8">{t("auth.loginTitle").toUpperCase()}</h2>

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("common.username")}*
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t("forms.placeholders.enterUsername")}
                className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("common.password")}*
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("forms.placeholders.enterPassword")}
                  className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-border-transparent pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            <button
              onClick={handleLogin}
              disabled={submitting}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-60"
            >
              {submitting ? t("forms.buttons.signingIn") : t("common.login")}
            </button>
          </div>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              <a href="/system-admin/forgot-password" className="text-blue-600 hover:text-blue-700 font-medium">
                {t("auth.forgotPassword")}
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
