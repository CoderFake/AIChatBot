"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useTranslation } from "react-i18next"
import { useToast } from "@/lib/use-toast"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { ArrowLeft, Building2, Wrench, Bot } from "lucide-react"
import { apiService } from "@/lib/api/index"
import type { CreateTenantRequest } from "@/types"


export default function CreateTenantPage() {
  const router = useRouter()
  const { t } = useTranslation()
  const { showError, showSuccess } = useToast()

  const [formData, setFormData] = useState<CreateTenantRequest>({
    tenant_name: "",
    timezone: "UTC",
    locale: "en_US",
    allowed_providers: [],
    allowed_tools: [],
  })
  const [isLoading, setIsLoading] = useState(false)
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [availableTools, setAvailableTools] = useState<any[]>([])
  const [availableProviders, setAvailableProviders] = useState<any[]>([])
  const [selectedProviderIds, setSelectedProviderIds] = useState<string[]>([])
  const [loadingData, setLoadingData] = useState(true)
  const [timezones, setTimezones] = useState<any[]>([])
  const [locales, setLocales] = useState<any[]>([])

  useEffect(() => {
    const loadAllData = async () => {
      try {
        setLoadingData(true)

        const [
          timezonesResponse,
          localesResponse,
          providersResponse,
          toolsResponse
        ] = await Promise.all([
          apiService.tenants.getTimezones(),
          apiService.tenants.getLocales(),
          apiService.tenants.getAvailableProviders(),
          apiService.tenants.getAvailableTools()
        ])

        const timezoneOptions: any[] = []
        if (timezonesResponse.groups) {
          timezonesResponse.groups.forEach((group: any) => {
            group.timezones.forEach((tz: any) => {
              timezoneOptions.push({
                value: tz.value,
                label: `${tz.label} (${tz.country})`
              })
            })
          })
        }
        setTimezones(timezoneOptions)

        const localeOptions: any[] = []
        if (localesResponse.languages) {
          localesResponse.languages.forEach((lang: string) => {
            let label = lang
            switch (lang) {
              case 'vi':
                label = t('language.vietnamese')
                break
              case 'en':
                label = t('language.english')
                break
              case 'kr':
                label = t('language.korean')
                break
              case 'ja':
                label = t('language.japanese')
                break
            }
            localeOptions.push({
              value: lang,
              label: label
            })
          })
        }
        setLocales(localeOptions)

        const providersData = providersResponse.providers || []
        setAvailableProviders(providersData)

        const toolsData = toolsResponse.tools || []
        setAvailableTools(toolsData)

      } catch (error) {
        console.error('Failed to load data:', error)
        setTimezones([
          { value: "UTC", label: "UTC" },
          { value: "America/New_York", label: t('admin.timezone') }
        ])
        setLocales([
          { value: "en", label: t('language.english') },
          { value: "vi", label: t('language.vietnamese') }
        ])
        setAvailableTools([])
      } finally {
        setLoadingData(false)
      }
    }

    loadAllData()
  }, [])

  useEffect(() => {
    setFormData((prev) => ({
      ...prev,
      allowed_tools: selectedTools,
      allowed_providers: selectedProviderIds,
    }))
  }, [selectedTools, selectedProviderIds])


  const handleInputChange =
    (field: keyof CreateTenantRequest) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const value = e.target.value
      setFormData((prev) => ({
        ...prev,
        [field]: value || undefined,
      }))
    }

  const handleSelectChange = (field: keyof CreateTenantRequest) => (value: string) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const cleanedData: CreateTenantRequest = {
        ...formData,
        sub_domain: formData.sub_domain?.trim() || undefined,
        description: formData.description?.trim() || undefined,
        allowed_providers: selectedProviderIds.length > 0 ? selectedProviderIds : undefined,
        allowed_tools: selectedTools.length > 0 ? selectedTools : undefined,
      }

      const tenant = await apiService.tenants.create(cleanedData)
      showSuccess(t('messages.success.tenantCreated'))
      router.push(`/system-admin/tenants/${tenant.tenant_id}`)
    } catch (err) {
      showError(err instanceof Error ? err.message : t('messages.errors.failedToCreateTenant'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleBack = () => {
    router.push("/system-admin/tenants")
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="sm" onClick={handleBack} className="font-serif">
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('messages.info.backToTenants')}
        </Button>
      </div>

      <div className="flex items-center space-x-3">
        <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
          <Building2 className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-3xl font-bold font-sans">{t('tenant.createOrganization')}</h1>
          <p className="text-muted-foreground font-serif">{t('tenant.createTenantDescription')}</p>
        </div>
      </div>

      {/* Form */}
      <div className="max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle className="font-sans">{t('tenant.createTenantTitle')}</CardTitle>
            <CardDescription className="font-serif">
              {t('tenant.createTenantDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">

              {/* Tenant Name */}
              <div className="space-y-2">
                <Label htmlFor="tenant_name" className="font-serif">
                  {t('tenant.tenantName')} *
                </Label>
                <Input
                  id="tenant_name"
                  placeholder={t('tenant.tenantNamePlaceholder')}
                  value={formData.tenant_name}
                  onChange={handleInputChange("tenant_name")}
                  required
                  disabled={isLoading}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">{t('tenant.tenantNameHelper')}</p>
              </div>

              {/* Subdomain */}
              <div className="space-y-2">
                <Label htmlFor="sub_domain" className="font-serif">
                  {t('tenant.subdomain')}
                </Label>
                <Input
                  id="sub_domain"
                  placeholder={t('tenant.subdomainPlaceholder')}
                  value={formData.sub_domain}
                  onChange={handleInputChange("sub_domain")}
                  disabled={isLoading}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">
                  {t('tenant.subdomainHelper')}
                </p>
              </div>

              {/* Timezone */}
              <div className="space-y-2">
                <Label htmlFor="timezone" className="font-serif">
                  {t('tenant.timezone')} *
                </Label>
                <Select value={formData.timezone} onValueChange={handleSelectChange("timezone")} disabled={isLoading}>
                  <SelectTrigger className="font-serif">
                    <SelectValue placeholder={t('tenant.timezonePlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {timezones.map((tz) => (
                      <SelectItem key={tz.value} value={tz.value} className="font-serif">
                        {tz.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Locale */}
              <div className="space-y-2">
                <Label htmlFor="locale" className="font-serif">
                  {t('tenant.locale')} *
                </Label>
                <Select value={formData.locale} onValueChange={handleSelectChange("locale")} disabled={isLoading}>
                  <SelectTrigger className="font-serif">
                    <SelectValue placeholder={t('tenant.localePlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {locales.map((locale) => (
                      <SelectItem key={locale.value} value={locale.value} className="font-serif">
                        {locale.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="description" className="font-serif">
                  {t('tenant.description')}
                </Label>
                <Textarea
                  id="description"
                  placeholder={t('tenant.descriptionPlaceholder')}
                  value={formData.description}
                  onChange={handleInputChange("description")}
                  disabled={isLoading}
                  rows={3}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">
                  {t('tenant.descriptionHelper')}
                </p>
              </div>

              {/* Provider Selection Section */}
              <div className="space-y-4 pt-6 border-t">
                <div className="flex items-center space-x-2">
                  <Bot className="w-4 h-4 text-muted-foreground" />
                  <Label className="font-serif text-base">
                    {t('tenant.selectAllowedProviders')}
                  </Label>
                </div>

                <div className="space-y-4">
                  <p className="text-xs text-muted-foreground font-serif">
                    {t('tenant.providersDescription')}
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {availableProviders.map((provider, index) => (
                      <div key={`provider-${index}-${provider.name}`} className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted/50">
                        <Checkbox
                          id={`provider-checkbox-${index}-${provider.name}`}
                          checked={selectedProviderIds.includes(provider.name)}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedProviderIds((prev) => {
                                return [...prev, provider.name]
                              })
                            } else {
                              setSelectedProviderIds((prev) => {
                                return prev.filter((id) => id !== provider.name)
                              })
                            }
                          }}
                          disabled={isLoading}
                        />
                        <div className="flex-1 min-w-0">
                          <Label
                            htmlFor={`provider-checkbox-${index}-${provider.name}`}
                            className="font-serif font-medium cursor-pointer text-sm"
                          >
                            {provider.name}
                          </Label>
                        </div>
                      </div>
                    ))}
                  </div>

                  {selectedProviderIds.length > 0 && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span>{selectedProviderIds.length} {t('tenant.providersSelected')}</span>
                    </div>
                  )}

                  {availableProviders.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      {t('tenant.noProvidersAvailable')}
                    </p>
                  )}
                </div>
              </div>

              {/* Tools Selection Section */}
              <div className="space-y-4 pt-6 border-t">
                <div className="flex items-center space-x-2">
                  <Wrench className="w-4 h-4 text-muted-foreground" />
                  <Label className="font-serif text-base">
                    {t('tenant.selectTools')}
                  </Label>
                </div>

                <div className="space-y-4">
                  <p className="text-xs text-muted-foreground font-serif">
                    {t('tenant.toolsDescription')}
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {availableTools.map((tool, index) => (
                      <div key={`tool-${index}-${tool.id}`} className="flex items-start space-x-3 p-3 border rounded-lg">
                        <Checkbox
                          id={`tool-checkbox-${index}-${tool.id}`}
                          checked={selectedTools.includes(tool.id)}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedTools((prev) => {
                                return [...prev, tool.id]
                              })
                            } else {
                              setSelectedTools((prev) => {
                                return prev.filter((t) => t !== tool.id)
                              })
                            }
                          }}
                          disabled={isLoading}
                        />
                        <div className="flex-1 min-w-0">
                          <Label
                            htmlFor={`tool-checkbox-${index}-${tool.id}`}
                            className="font-serif font-medium cursor-pointer"
                          >
                            {tool.name}
                          </Label>
                          <p className="text-sm text-muted-foreground font-serif mt-1">
                            {tool.description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {selectedTools.length > 0 && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span>{selectedTools.length} {t('tenant.toolsSelected')}</span>
                    </div>
                  )}

                  {availableTools.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      {t('tenant.noToolsAvailable')}
                    </p>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end space-x-4 pt-6 border-t">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleBack}
                  disabled={isLoading}
                  className="font-sans bg-transparent"
                >
                  {t('common.cancel')}
                </Button>
                <Button type="submit" disabled={isLoading} className="font-sans">
                  {isLoading ? t('common.creating') : t('tenant.createTenant')}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
