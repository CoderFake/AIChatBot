"use client"

import { useState, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Upload, Settings, Bot, Image, Eye, EyeOff, Plus, Trash2 } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { RouteGuard } from "@/components/auth/route-guard"
import { apiService } from "@/lib/api/index"
import type { APIService } from "@/lib/api/index"

const typedApiService = apiService as APIService

interface WorkflowAgentConfig {
  id: string
  tenant_id: string
  provider_name: string
  model_name: string
  model_configuration: Record<string, any>
  max_iterations: number
  timeout_seconds: number
  confidence_threshold: number
  is_active: boolean
  api_keys?: string[]
}

interface TenantSettings {
  tenant_name: string
  description?: string
  timezone: string
  locale: string
  chatbot_name?: string
  logo_url?: string
  branding?: {
    bot_name?: string
    logo_url?: string
  }
}

interface DynamicData {
  providers: Array<{
    id: string
    name: string
    models: Array<{
      id: string
      name: string
    }>
  }>
  timezones: Array<{
    code: string
    name: string
  }>
  locales: Array<{
    code: string
    name: string
  }>
}

export default function SettingsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const router = useRouter()

  // Settings state
  const [settings, setSettings] = useState<TenantSettings>({
    tenant_name: "",
    description: "",
    timezone: "UTC",
    locale: "en_US",
    chatbot_name: "",
    logo_url: ""
  })

  const [workflowAgent, setWorkflowAgent] = useState<WorkflowAgentConfig | null>(null)

  const [dynamicData, setDynamicData] = useState<DynamicData>({
    providers: [],
    timezones: [],
    locales: []
  })

  // UI state
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // API Key management state
  const [apiKeys, setApiKeys] = useState<string[]>([""])
  const [showApiKeys, setShowApiKeys] = useState<boolean[]>([false])
  const [loadingApiKeys, setLoadingApiKeys] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      const settingsData = await typedApiService.tenantSettings.getSettings()
      setSettings({
        tenant_name: settingsData.tenant_name || "",
        description: settingsData.description || "",
        timezone: settingsData.timezone || "UTC",
        locale: settingsData.locale || "en_US",
        chatbot_name: settingsData.chatbot_name || "",
        logo_url: settingsData.branding?.logo_url || "",
        branding: settingsData.branding
      })

      try {
        const agentData = await typedApiService.tenantSettings.getWorkflowAgent()
        setWorkflowAgent(agentData)

        if (agentData?.provider_name) {
          try {
            await loadApiKeysForProvider(agentData.provider_name)
          } catch (apiKeyError) {
            console.error("Failed to load API keys for workflow agent provider:", apiKeyError)
          }
        }
      } catch (agentError) {
        setWorkflowAgent(null)
      }

      try {
        const dynamicData = await typedApiService.tenantSettings.getDynamicData()
        setDynamicData(dynamicData)
      } catch (dynamicError) {
        setDynamicData({
          providers: [],
          timezones: [
            { code: "UTC", name: "UTC" },
            { code: "Asia/Ho_Chi_Minh", name: "Asia/Ho_Chi_Minh" }
          ],
          locales: [
            { code: "en_US", name: "English" },
            { code: "vi_VN", name: "Tiếng Việt" }
          ]
        })
      }

    } catch (error) {
      console.error("Failed to load settings:", error)
      setError("failedToLoadSettings")
    } finally {
      setLoading(false)
    }
  }

  const handleSaveSettings = async () => {
    try {
      setSaving(true)
      setError(null)
      setSuccess(null)

      await typedApiService.tenantSettings.updateSettings({
        tenant_name: settings.tenant_name,
        description: settings.description,
        timezone: settings.timezone,
        locale: settings.locale,
        bot_name: settings.chatbot_name,
        branding: {
          logo_url: settings.logo_url
        }
      })

      setSuccess("settingsSavedSuccessfully")

    } catch (error) {
      console.error("Failed to save settings:", error)
      setError("failedToSaveSettings")
    } finally {
      setSaving(false)
    }
  }

  const handleSaveWorkflowAgent = async () => {
    if (!workflowAgent) return

    const validApiKeys = apiKeys.filter(key => key.trim() !== "")
    if (validApiKeys.length === 0) {
      setError("apiKeyRequired")
      return
    }

    try {
      setSaving(true)
      setError(null)
      setSuccess(null)

      await typedApiService.tenantSettings.updateProviderApiKeys({
        provider_name: workflowAgent.provider_name,
        api_keys: validApiKeys
      })

      await typedApiService.tenantSettings.updateWorkflowAgent({
        provider_name: workflowAgent.provider_name,
        model_name: workflowAgent.model_name,
        model_configuration: workflowAgent.model_configuration,
        max_iterations: workflowAgent.max_iterations,
        timeout_seconds: workflowAgent.timeout_seconds,
        confidence_threshold: workflowAgent.confidence_threshold
      })

      await loadApiKeysForProvider(workflowAgent.provider_name)

      setSuccess("workflowAgentSavedSuccessfully")

    } catch (error) {
      setError("failedToSaveWorkflowAgent")
    } finally {
      setSaving(false)
    }
  }

  const handleLogoUrlChange = (url: string) => {
    setSettings(prev => ({ ...prev, logo_url: url }))
  }

  const handleBotNameChange = (name: string) => {
    setSettings(prev => ({ ...prev, chatbot_name: name }))
  }

  // API Key management functions
  const loadApiKeysForProvider = async (providerName: string) => {
    if (!providerName) return

    try {
      setLoadingApiKeys(true)
      const response = await typedApiService.tenantSettings.getProviderApiKeys(providerName)
      const existingKeys = response.api_keys || []

      if (existingKeys.length > 0) {
        setApiKeys(existingKeys)
        setShowApiKeys(new Array(existingKeys.length).fill(false))
      } else {
        setApiKeys([""])
        setShowApiKeys([false])
      }
    } catch (error) {
      console.error("Failed to load API keys:", error)
      setApiKeys([""])
      setShowApiKeys([false])
    } finally {
      setLoadingApiKeys(false)
    }
  }

  const addApiKey = () => {
    setApiKeys(prev => [...prev, ""])
    setShowApiKeys(prev => [...prev, false])
  }

  const removeApiKey = (index: number) => {
    if (apiKeys.length > 1) {
      setApiKeys(prev => prev.filter((_, i) => i !== index))
      setShowApiKeys(prev => prev.filter((_, i) => i !== index))
    }
  }

  const updateApiKey = (index: number, value: string) => {
    setApiKeys(prev => prev.map((key, i) => i === index ? value : key))
  }

  const toggleApiKeyVisibility = (index: number) => {
    setShowApiKeys(prev => prev.map((show, i) => i === index ? !show : show))
  }

  if (loading) {
    return (
      <RouteGuard requireAuth requiredRoles={["ADMIN"]}>
        <div className="flex items-center justify-center min-h-screen">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      </RouteGuard>
    )
  }

  return (
    <RouteGuard requireAuth requiredRoles={["ADMIN"]}>
      <div className="container mx-auto p-6 space-y-6">
        <div className="flex items-center gap-3">
          <Settings className="h-8 w-8" />
          <div>
            <h1 className="text-3xl font-bold">{t("admin.tenantSettings")}</h1>
            <p className="text-muted-foreground">{t("admin.configureTenantSettings")}</p>
          </div>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{t(`admin.${error}`)}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert>
            <AlertDescription>{t(`admin.${success}`)}</AlertDescription>
          </Alert>
        )}

        {/* General Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              {t("admin.generalSettings")}
            </CardTitle>
            <CardDescription>
              {t("admin.configureBasicTenantInfo")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tenant_name">{t("admin.tenantName")}</Label>
                <Input
                  id="tenant_name"
                  value={settings.tenant_name}
                  onChange={(e) => setSettings(prev => ({ ...prev, tenant_name: e.target.value }))}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="timezone">{t("admin.timezone")}</Label>
                <Select
                  value={settings.timezone}
                  onValueChange={(value) => setSettings(prev => ({ ...prev, timezone: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {dynamicData.timezones.map((tz) => (
                      <SelectItem key={tz.code} value={tz.code}>
                        {tz.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="locale">{t("admin.language")}</Label>
                <Select
                  value={settings.locale}
                  onValueChange={(value) => setSettings(prev => ({ ...prev, locale: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {dynamicData.locales.map((locale) => (
                      <SelectItem key={locale.code} value={locale.code}>
                        {locale.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="logo_url">{t("admin.logoUrl")}</Label>
                <Input
                  id="logo_url"
                  value={settings.logo_url || ""}
                  onChange={(e) => handleLogoUrlChange(e.target.value)}
                  placeholder={t("admin.logoUrlPlaceholder")}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">{t("admin.tenantDescription")}</Label>
              <Textarea
                id="description"
                value={settings.description || ""}
                onChange={(e) => setSettings(prev => ({ ...prev, description: e.target.value }))}
                placeholder={t("admin.descriptionPlaceholder")}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="chatbot_name">{t("admin.botName")}</Label>
              <Input
                id="chatbot_name"
                value={settings.chatbot_name || ""}
                onChange={(e) => handleBotNameChange(e.target.value)}
                placeholder={t("admin.botNamePlaceholder")}
              />
            </div>

            <Button
              onClick={handleSaveSettings}
              disabled={saving}
              className="w-full md:w-auto"
            >
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("admin.saveSettings")}
            </Button>
          </CardContent>
        </Card>

        {/* Workflow Agent Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              {t("admin.workflowAgent")}
            </CardTitle>
            <CardDescription>
              {t("admin.configureWorkflowAgent")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {workflowAgent ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="provider_name">{t("admin.provider")}</Label>
                  <Select
                    value={workflowAgent.provider_name}
                    onValueChange={(value) => {
                      setWorkflowAgent(prev => prev ? { ...prev, provider_name: value } : null)
                      loadApiKeysForProvider(value)
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {dynamicData.providers.map((provider) => (
                        <SelectItem key={provider.id || provider.name} value={provider.name}>
                          {provider.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="model_name">{t("admin.model")}</Label>
                  <Select
                    value={workflowAgent.model_name}
                    onValueChange={(value) => setWorkflowAgent(prev => prev ? { ...prev, model_name: value } : null)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {dynamicData.providers
                        .find(p => p.name === workflowAgent.provider_name)
                        ?.models.map((model) => (
                          <SelectItem key={model.id} value={model.name}>
                            {model.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="max_iterations">{t("admin.maxIterations")}</Label>
                  <Input
                    id="max_iterations"
                    type="number"
                    value={workflowAgent.max_iterations}
                    onChange={(e) => setWorkflowAgent(prev => prev ? { ...prev, max_iterations: parseInt(e.target.value) } : null)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="timeout_seconds">{t("admin.timeoutSeconds")}</Label>
                  <Input
                    id="timeout_seconds"
                    type="number"
                    value={workflowAgent.timeout_seconds}
                    onChange={(e) => setWorkflowAgent(prev => prev ? { ...prev, timeout_seconds: parseInt(e.target.value) } : null)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confidence_threshold">{t("admin.confidenceThreshold")}</Label>
                  <Input
                    id="confidence_threshold"
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={workflowAgent.confidence_threshold}
                    onChange={(e) => setWorkflowAgent(prev => prev ? { ...prev, confidence_threshold: parseFloat(e.target.value) } : null)}
                  />
                </div>

                {/* API Keys Section */}
                <div className="col-span-full space-y-4">
                  <div className="flex items-center justify-between">
                    <Label className="text-base font-medium">{t("admin.apiKeys")}</Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={addApiKey}
                      disabled={loadingApiKeys}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      {t("admin.addApiKey")}
                    </Button>
                  </div>

                  <div className="space-y-3">
                    {apiKeys.map((apiKey, index) => (
                      <div key={index} className="flex items-center space-x-2">
                        <div className="flex-1 relative">
                          <Input
                            type={showApiKeys[index] ? "text" : "password"}
                            placeholder={`API Key ${index + 1}`}
                            value={apiKey}
                            onChange={(e) => updateApiKey(index, e.target.value)}
                            disabled={loadingApiKeys}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6 p-0"
                            onClick={() => toggleApiKeyVisibility(index)}
                          >
                            {showApiKeys[index] ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </Button>
                        </div>

                        {apiKeys.length > 1 && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => removeApiKey(index)}
                            disabled={loadingApiKeys}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>

                  {loadingApiKeys && (
                    <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Loading existing API keys...</span>
                    </div>
                  )}

                  <p className="text-sm text-muted-foreground">
                    {t("admin.apiKeysDescription")}
                  </p>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground mb-4">
                  {t("admin.workflowAgentNotConfigured")}
                </p>
                <Button
                  onClick={() => {
                    const defaultProvider = dynamicData.providers[0];
                    setWorkflowAgent({
                      id: "",
                      tenant_id: user?.tenant_id || "",
                    provider_name: defaultProvider?.name || "gemini",
                    model_name: defaultProvider?.models[0]?.name || "gemini-pro",
                    model_configuration: { temperature: 0.7, max_tokens: 2048 },
                    max_iterations: 10,
                    timeout_seconds: 300,
                    confidence_threshold: 0.7,
                    is_active: true
                    })
                  }}
                >
                  {t("admin.configureWorkflowAgentNow")}
                </Button>
              </div>
            )}

            {workflowAgent && (
              <Button
                onClick={handleSaveWorkflowAgent}
                disabled={saving}
                className="w-full md:w-auto"
              >
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {t("admin.saveWorkflowAgent")}
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </RouteGuard>
  )
}
