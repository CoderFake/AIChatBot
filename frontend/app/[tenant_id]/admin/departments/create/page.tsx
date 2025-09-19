"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ArrowLeft, Building2 } from "lucide-react"
import { useTenant } from "@/lib/tenant-context"
import { apiService } from "@/lib/api/index"
import { useToast } from "@/lib/use-toast"
import { useTranslation } from "react-i18next"

export default function CreateDepartmentPage() {
  const router = useRouter()
  const { tenantId } = useTenant()
  const { showError, showSuccess } = useToast()
  const { t } = useTranslation()
  const [formData, setFormData] = useState({
    department_name: "",
    description: "",
    agent_name: "",
    agent_description: "",
    provider_id: "",
    model_id: "",
  })
  const [providers, setProviders] = useState<any[]>([])
  const [models, setModels] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingProviders, setIsLoadingProviders] = useState(true)

  // Load providers on component mount
  useEffect(() => {
    const loadProviders = async () => {
      if (!tenantId) return
      
      try {
        setIsLoadingProviders(true)
        const data = await apiService.tenantSettings.getProviders()
        setProviders(data.providers || [])
      } catch (err) {
        showError(t("messages.errors.failedToLoadProviders"))
      } finally {
        setIsLoadingProviders(false)
      }
    }

    loadProviders()
  }, [tenantId, showError, t])

  // Load models when provider changes
  useEffect(() => {
    const loadModels = async () => {
      if (!formData.provider_id) {
        setModels([])
        return
      }
      
      try {
        // Find the selected provider and get its models
        const selectedProvider = providers.find(p => p.id === formData.provider_id)
        setModels(selectedProvider?.models || [])
      } catch (err) {
        showError(t("messages.errors.failedToLoadModels"))
        setModels([])
      }
    }

    loadModels()
  }, [formData.provider_id, providers, showError, t])

  const handleInputChange =
    (field: keyof typeof formData) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setFormData((prev) => ({
        ...prev,
        [field]: e.target.value,
      }))
    }

  const handleSelectChange = (field: keyof typeof formData) => (value: string) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tenantId) return

    setIsLoading(true)

    try {
      const department = await apiService.tenantAdmin.createDepartment({
        department_name: formData.department_name,
        description: formData.description,
        agent_name: formData.agent_name,
        agent_description: formData.agent_description,
        provider_id: formData.provider_id,
        model_id: formData.model_id,
      })
      showSuccess(t("department.createDepartment"), t("messages.success.departmentCreated"))
      router.push(`/${tenantId}/admin/departments/${department.id}`)
    } catch (err) {
      showError(err instanceof Error ? err.message : t("messages.errors.failedToCreateDepartment"))
    } finally {
      setIsLoading(false)
    }
  }

  const handleBack = () => {
    router.push(`/${tenantId}/admin/departments`)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="sm" onClick={handleBack} className="font-serif">
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t("department.backToDepartments")}
        </Button>
      </div>

      <div className="flex items-center space-x-3">
        <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
          <Building2 className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-3xl font-bold font-sans">{t("department.createDepartment")}</h1>
          <p className="text-muted-foreground font-serif">{t("department.addNewDepartment")}</p>
        </div>
      </div>

      {/* Form */}
      <div className="max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle className="font-sans">{t("department.departmentInformation")}</CardTitle>
            <CardDescription className="font-serif">
              {t("department.provideBasicInformation")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Department Name */}
              <div className="space-y-2">
                <Label htmlFor="department_name" className="font-serif">
                  {t("department.departmentName")} *
                </Label>
                <Input
                  id="department_name"
                  placeholder={t("department.enterDepartmentName")}
                  value={formData.department_name}
                  onChange={handleInputChange("department_name")}
                  required
                  disabled={isLoading}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">{t("department.displayNameDescription")}</p>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="description" className="font-serif">
                  {t("department.description")}
                </Label>
                <Textarea
                  id="description"
                  placeholder={t("department.enterDescription")}
                  value={formData.description}
                  onChange={handleInputChange("description")}
                  disabled={isLoading}
                  rows={3}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">
                  {t("department.descriptionHelper")}
                </p>
              </div>

              {/* Agent Name */}
              <div className="space-y-2">
                <Label htmlFor="agent_name" className="font-serif">
                  Agent Name *
                </Label>
                <Input
                  id="agent_name"
                  placeholder="Enter agent name (e.g., HR Agent, IT Agent)"
                  value={formData.agent_name}
                  onChange={handleInputChange("agent_name")}
                  required
                  disabled={isLoading}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">
                  Name for the AI agent that will handle this department's queries
                </p>
              </div>

              {/* Agent Description */}
              <div className="space-y-2">
                <Label htmlFor="agent_description" className="font-serif">
                  Agent Description *
                </Label>
                <Textarea
                  id="agent_description"
                  placeholder="Describe what this agent specializes in..."
                  value={formData.agent_description}
                  onChange={handleInputChange("agent_description")}
                  required
                  disabled={isLoading}
                  rows={3}
                  className="font-serif"
                />
                <p className="text-xs text-muted-foreground font-serif">
                  Describe the agent's capabilities and specialization
                </p>
              </div>

              {/* Provider Selection */}
              <div className="space-y-2">
                <Label htmlFor="provider_id" className="font-serif">
                  LLM Provider *
                </Label>
                <Select
                  value={formData.provider_id}
                  onValueChange={handleSelectChange("provider_id")}
                  disabled={isLoading || isLoadingProviders}
                >
                  <SelectTrigger className="font-serif">
                    <SelectValue placeholder="Select a provider..." />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id}>
                        {provider.provider_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground font-serif">
                  Choose the LLM provider for this agent
                </p>
              </div>

              {/* Model Selection */}
              {formData.provider_id && (
                <div className="space-y-2">
                  <Label htmlFor="model_name" className="font-serif">
                    Model *
                  </Label>
                  <Select
                    value={formData.model_id}
                    onValueChange={handleSelectChange("model_id")}
                    disabled={isLoading || models.length === 0}
                  >
                    <SelectTrigger className="font-serif">
                      <SelectValue placeholder="Select a model..." />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((model, index) => (
                        <SelectItem key={model.id || index} value={model.id}>
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground font-serif">
                    Choose the specific model for this agent
                  </p>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-end space-x-4 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleBack}
                  disabled={isLoading}
                  className="font-sans bg-transparent"
                >
                  {t("common.cancel")}
                </Button>
                <Button type="submit" disabled={isLoading} className="font-sans">
                  {isLoading ? t("department.creating") : t("department.createDepartment")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
