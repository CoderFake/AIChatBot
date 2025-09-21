'use client'

import type React from 'react'
import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/lib/use-toast'
import { apiService } from '@/lib/api/index'
import type { UpdateTenantRequest, UpdateTenantResponse } from '@/types'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { ArrowLeft, Building2, Bot, Wrench } from 'lucide-react'

export default function EditTenantPage() {
  const router = useRouter()
  const params = useParams()
  const tenantId = params.id as string
  const { t } = useTranslation()
  const { showError, showSuccess } = useToast()

  const [formData, setFormData] = useState<UpdateTenantRequest>({
    tenant_name: '',
    timezone: 'UTC',
    locale: 'en',
    sub_domain: '',
    description: '',
    allowed_providers: [],
    allowed_tools: [],
  })
  const [isLoading, setIsLoading] = useState(false)
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [availableTools, setAvailableTools] = useState<any[]>([])
  const [availableProviders, setAvailableProviders] = useState<any[]>([])
  const [selectedProviderIds, setSelectedProviderIds] = useState<string[]>([])
  const [timezones, setTimezones] = useState<any[]>([])
  const [locales, setLocales] = useState<any[]>([])

  useEffect(() => {
    const loadData = async () => {
      try {
        const [
          tenantRes,
          tzRes,
          localeRes,
          providersRes,
          toolsRes
        ] = await Promise.all([
          apiService.tenants.getDetail(tenantId),
          apiService.tenants.getTimezones(),
          apiService.tenants.getLocales(),
          apiService.tenants.getAvailableProviders(),
          apiService.tenants.getAvailableTools(),
        ])

        setFormData({
          tenant_name: tenantRes.tenant_name || '',
          timezone: tenantRes.timezone || 'UTC',
          locale: tenantRes.locale || 'en',
          sub_domain: tenantRes.sub_domain || '',
          description: tenantRes.description || '',
          allowed_providers: tenantRes.allowed_providers || [],
          allowed_tools: tenantRes.allowed_tools || [],
        })

        // Set selected providers and tools from tenant data
        setSelectedProviderIds(tenantRes.allowed_providers || [])
        setSelectedTools(tenantRes.allowed_tools || [])

        const timezoneOptions: any[] = []
        if (tzRes.groups) {
          tzRes.groups.forEach((group: any) => {
            group.timezones.forEach((tz: any) => {
              timezoneOptions.push({ value: tz.value, label: `${tz.label} (${tz.country})` })
            })
          })
        }
        setTimezones(timezoneOptions)

        const localeOptions: any[] = []
        if (localeRes.languages) {
          localeRes.languages.forEach((lang: string) => {
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
            localeOptions.push({ value: lang, label })
          })
        }
        setLocales(localeOptions)

        setAvailableProviders(providersRes.providers || [])
        setAvailableTools(toolsRes.tools || [])
      } catch (error) {
        console.error('Failed to load tenant data:', error)
      }
    }

    loadData()
  }, [tenantId, t])

  useEffect(() => {
    setFormData((prev) => ({
      ...prev,
      allowed_tools: selectedTools,
      allowed_providers: selectedProviderIds,
    }))
  }, [selectedTools, selectedProviderIds])

  const handleInputChange =
    (field: keyof UpdateTenantRequest) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const value = e.target.value
      setFormData((prev) => ({
        ...prev,
        [field]: value || undefined,
      }))
    }

  const handleSelectChange = (field: keyof UpdateTenantRequest) => (value: string) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const cleanedData: UpdateTenantRequest = {
        ...formData,
        sub_domain: formData.sub_domain?.trim() || undefined,
        description: formData.description?.trim() || undefined,
        allowed_providers: selectedProviderIds.length > 0 ? selectedProviderIds : undefined,
        allowed_tools: selectedTools.length > 0 ? selectedTools : undefined,
      }

      const updateData: UpdateTenantRequest = Object.fromEntries(
        Object.entries(cleanedData).filter(([_, value]) => value !== undefined)
      ) as UpdateTenantRequest

      await apiService.tenants.update(tenantId, updateData)
      showSuccess(t('notifications.operationCompleted'))
      router.push(`/system-admin/tenants/${tenantId}`)
    } catch (err) {
      showError(err instanceof Error ? err.message : t('messages.errors.failedToUpdateTenant'))
    } finally {
      setIsLoading(false)
    }
  }

  const handleBack = () => {
    router.push(`/system-admin/tenants/${tenantId}`)
  }

  return (
    <div className="space-y-6">
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
          <h1 className="text-3xl font-bold font-sans">{t('messages.info.editTenant')}</h1>
          <p className="text-muted-foreground font-serif">{t('tenant.createTenantDescription')}</p>
        </div>
      </div>

      <div className="max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle className="font-sans">{t('messages.info.tenantInformation')}</CardTitle>
            <CardDescription className="font-serif">{t('messages.info.basicTenantConfigurationAndSettings')}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="tenant_name" className="font-serif">
                  {t('tenant.tenantName')} *
                </Label>
                <Input
                  id="tenant_name"
                  value={formData.tenant_name}
                  onChange={handleInputChange('tenant_name')}
                  required
                  disabled={isLoading}
                  className="font-serif"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="sub_domain" className="font-serif">
                  {t('tenant.subdomain')}
                </Label>
                <Input
                  id="sub_domain"
                  value={formData.sub_domain}
                  onChange={handleInputChange('sub_domain')}
                  disabled={isLoading}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">
                  {t('tenant.subdomainHelper')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="timezone" className="font-serif">
                  {t('tenant.timezone')} *
                </Label>
                <Select value={formData.timezone} onValueChange={handleSelectChange('timezone')} disabled={isLoading}>
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

              <div className="space-y-2">
                <Label htmlFor="locale" className="font-serif">
                  {t('tenant.locale')} *
                </Label>
                <Select value={formData.locale} onValueChange={handleSelectChange('locale')} disabled={isLoading}>
                  <SelectTrigger className="font-serif">
                    <SelectValue placeholder={t('tenant.localePlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {locales.map((l) => (
                      <SelectItem key={l.value} value={l.value} className="font-serif">
                        {l.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description" className="font-serif">
                  {t('tenant.description')}
                </Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={handleInputChange('description')}
                  disabled={isLoading}
                  rows={3}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">
                  {t('tenant.descriptionHelper')}
                </p>
              </div>

              <div className="space-y-4 pt-6 border-t">
                <div className="flex items-center space-x-2">
                  <Bot className="w-4 h-4 text-muted-foreground" />
                  <Label className="font-serif text-base">{t('tenant.selectAllowedProviders')}</Label>
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
                              setSelectedProviderIds((prev) => [...prev, provider.name])
                            } else {
                              setSelectedProviderIds((prev) => prev.filter((id) => id !== provider.name))
                            }
                          }}
                          disabled={isLoading}
                        />
                        <div className="flex-1 min-w-0">
                          <Label htmlFor={`provider-checkbox-${index}-${provider.name}`} className="font-serif font-medium cursor-pointer text-sm">
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
                    <p className="text-sm text-muted-foreground">{t('tenant.noProvidersAvailable')}</p>
                  )}
                </div>
              </div>

              <div className="space-y-4 pt-6 border-t">
                <div className="flex items-center space-x-2">
                  <Wrench className="w-4 h-4 text-muted-foreground" />
                  <Label className="font-serif text-base">{t('tenant.selectTools')}</Label>
                </div>
                <div className="space-y-4">
                  <p className="text-xs text-muted-foreground font-serif">{t('tenant.toolsDescription')}</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {availableTools.map((tool, index) => (
                      <div key={`tool-${index}-${tool.id}`} className="flex items-start space-x-3 p-3 border rounded-lg">
                        <Checkbox
                          id={`tool-checkbox-${index}-${tool.id}`}
                          checked={selectedTools.includes(tool.id)}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedTools((prev) => [...prev, tool.id])
                            } else {
                              setSelectedTools((prev) => prev.filter((t) => t !== tool.id))
                            }
                          }}
                          disabled={isLoading}
                        />
                        <div className="flex-1 min-w-0">
                          <Label htmlFor={`tool-checkbox-${index}-${tool.id}`} className="font-serif font-medium cursor-pointer">
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
                    <p className="text-sm text-muted-foreground">{t('tenant.noToolsAvailable')}</p>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-end space-x-4 pt-6 border-t">
                <Button type="button" variant="outline" onClick={handleBack} disabled={isLoading} className="font-sans bg-transparent">
                  {t('common.cancel')}
                </Button>
                <Button type="submit" disabled={isLoading} className="font-sans">
                  {isLoading ? t('common.loading') : t('common.save')}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
