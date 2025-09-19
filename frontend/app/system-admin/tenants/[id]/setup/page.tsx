'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/lib/use-toast'
import { apiService } from '@/lib/api/index'
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
import { Checkbox } from '@/components/ui/checkbox'
import { ArrowLeft } from 'lucide-react'

export default function TenantSetupPage() {
  const router = useRouter()
  const params = useParams()
  const tenantId = params.id as string
  const { t } = useTranslation()
  const { showError, showSuccess } = useToast()

  const [providerName, setProviderName] = useState('')
  const [modelName, setModelName] = useState('')
  const [apiKeys, setApiKeys] = useState('')
  const [availableTools, setAvailableTools] = useState<any[]>([])
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    const loadTools = async () => {
      try {
        const toolsRes = await apiService.tenants.getAvailableTools()
        setAvailableTools(toolsRes.tools || [])
      } catch (err) {
        console.error('Failed to load tools:', err)
      }
    }
    loadTools()
  }, [])

  const handleBack = () => {
    router.push(`/system-admin/tenants/${tenantId}`)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      const keyList = apiKeys
        .split('\n')
        .map((k) => k.trim())
        .filter(Boolean)

      await apiService.tenants.configureProvider(tenantId, {
        provider_name: providerName,
        model_name: modelName,
        api_keys: keyList,
      })

      await apiService.tenants.setupWorkflowAgent(tenantId, {
        provider_name: providerName,
        model_name: modelName,
      })

      if (selectedTools.length > 0) {
        await apiService.tenants.enableTools(tenantId, selectedTools)
      }

      await apiService.tenants.completeSetup({
        tenant_id: tenantId,
        provider_name: providerName,
        model_name: modelName,
        api_keys: keyList,
      })

      showSuccess(t('notifications.operationCompleted'))
      router.push(`/system-admin/tenants/${tenantId}`)
    } catch (err) {
      console.error('Failed to setup tenant:', err)
      showError(t('notifications.operationFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="sm" onClick={handleBack} className="font-serif">
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('messages.info.backToTenants')}
        </Button>
      </div>

      <div>
        <h1 className="text-3xl font-bold font-sans">{t('tenant.setupTenant')}</h1>
        <p className="text-muted-foreground font-serif">{t('tenant.setupTenantDescription')}</p>
      </div>

      <div className="max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle className="font-sans">{t('tenant.configureProvider')}</CardTitle>
            <CardDescription className="font-serif">{t('tenant.providersDescription')}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="provider" className="font-serif">{t('tenant.providerName')}</Label>
                <Input
                  id="provider"
                  value={providerName}
                  onChange={(e) => setProviderName(e.target.value)}
                  disabled={isSubmitting}
                  className="font-serif"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="model" className="font-serif">{t('tenant.modelName')}</Label>
                <Input
                  id="model"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  disabled={isSubmitting}
                  className="font-serif"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="apiKeys" className="font-serif">{t('tenant.apiKeys')}</Label>
                <Textarea
                  id="apiKeys"
                  value={apiKeys}
                  onChange={(e) => setApiKeys(e.target.value)}
                  disabled={isSubmitting}
                  rows={3}
                  placeholder={t('tenant.apiKeysPlaceholder') as string}
                  className="font-serif"
                />
              </div>

              <div className="space-y-4 pt-6 border-t">
                <div className="flex items-center space-x-2">
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
                          disabled={isSubmitting}
                        />
                        <div className="flex-1 min-w-0">
                          <Label htmlFor={`tool-checkbox-${index}-${tool.id}`} className="font-serif font-medium cursor-pointer">
                            {tool.name}
                          </Label>
                          <p className="text-sm text-muted-foreground font-serif mt-1">{tool.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-4 pt-6 border-t">
                <Button type="button" variant="outline" onClick={handleBack} disabled={isSubmitting} className="font-sans bg-transparent">
                  {t('common.cancel')}
                </Button>
                <Button type="submit" disabled={isSubmitting} className="font-sans">
                  {isSubmitting ? t('tenant.setupInProgress') : t('tenant.completeSetup')}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

