'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Settings, Key, Wrench, Building, Users, Edit, AlertTriangle, Loader2, Plus, Trash2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from 'react-i18next'
import { apiService } from '@/lib/api/index'
import { Department } from '@/types'

interface DepartmentManagementProps {
  tenantId: string
}

export function DepartmentManagement({ tenantId }: DepartmentManagementProps) {
  const router = useRouter()
  const { toast } = useToast()
  const { t } = useTranslation()
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [selectedDepartment, setSelectedDepartment] = useState<Department | null>(null)
  const [departmentName, setDepartmentName] = useState('')
  const [departmentDescription, setDepartmentDescription] = useState('')

  // Edit form states
  const [editAgentName, setEditAgentName] = useState('')
  const [editAgentDescription, setEditAgentDescription] = useState('')
  const [editSelectedProvider, setEditSelectedProvider] = useState('')
  const [editSelectedModel, setEditSelectedModel] = useState('')
  const [editSelectedToolIds, setEditSelectedToolIds] = useState<string[]>([])
  const [editExistingAgentNames, setEditExistingAgentNames] = useState<string[]>([])
  const [editValidationErrors, setEditValidationErrors] = useState<string[]>([])

  // Agent configuration
  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')

  // Provider configuration
  const [providers, setProviders] = useState<any[]>([])
  const [models, setModels] = useState<any[]>([])
  const [selectedProvider, setSelectedProvider] = useState('')
  const [selectedModel, setSelectedModel] = useState('')

  // Tools
  const [availableTools, setAvailableTools] = useState<any[]>([])
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([])

  const [creating, setCreating] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [existingAgentNames, setExistingAgentNames] = useState<string[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])


  useEffect(() => {
    loadDepartments()
    loadDynamicData()
    loadExistingAgentNames()
  }, [tenantId])


  useEffect(() => {
    if (selectedProvider) {
      loadModelsForProvider(selectedProvider)
    }
  }, [selectedProvider])

  useEffect(() => {
    if (editSelectedProvider) {
      loadModelsForEditProvider(editSelectedProvider)
    }
  }, [editSelectedProvider])

  const loadDepartments = async () => {
    try {
      setLoading(true)
      const response = await apiService.departments.list(tenantId)
      setDepartments(response || [])
    } catch (error) {
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToLoadDepartments'),
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const loadDynamicData = async () => {
    try {
      const dynamicData = await apiService.tenantAdmin.getDynamicData()
      setProviders(dynamicData.providers || [])
      setAvailableTools(dynamicData.tools || [])
    } catch (error) {
    }
  }

  const loadExistingAgentNames = async () => {
    try {
      const response = await apiService.departments.list(tenantId)
      const departments = response || []
      const agentNames: string[] = []
      
      if (Array.isArray(departments) && departments.length > 0) {
        departments.forEach((dept: any) => {
          if (dept.agents && Array.isArray(dept.agents)) {
            dept.agents.forEach((agent: any) => {
              if (agent.agent_name && typeof agent.agent_name === 'string') {
                agentNames.push(agent.agent_name.toLowerCase())
              }
            })
          }
        })
      }

      setExistingAgentNames(agentNames)
    } catch (error) {
      setExistingAgentNames([])
    }
  }

  const loadModelsForProvider = async (providerId: string) => {
    try {
      const provider = providers.find(p => p.id === providerId)
      if (provider) {
        setModels(provider.models || [])
        setSelectedModel('')
      }
    } catch (error) {
      // Failed to load models
    }
  }

  const loadModelsForEditProvider = async (providerId: string) => {
    try {
      const provider = providers.find(p => p.id === providerId)
      if (provider) {
        setModels(provider.models || [])
      }
    } catch (error) {
    }
  }



  const validateForm = () => {
    const errors = []

    if (!departmentName.trim()) {
      errors.push("Department name is required")
    }

    if (!agentName.trim()) {
      errors.push("Agent name is required")
    }

    if (!selectedProvider) {
      errors.push("Provider selection is required")
    }


    return errors
  }

  const isFormValid = () => {
    return (
      departmentName.trim() !== '' &&
      agentName.trim() !== '' &&
      selectedProvider !== '' &&
      validationErrors.length === 0
    )
  }

  const validateFormRealTime = useCallback(() => {
    const errors: string[] = []

    if (existingAgentNames.length > 0 && agentName.trim() && existingAgentNames.includes(agentName.trim().toLowerCase())) {
      errors.push(`Agent name "${agentName}" already exists`)
    }

    setValidationErrors(errors)
    return errors
  }, [agentName, existingAgentNames])

  const validateEditFormRealTime = useCallback(() => {
    const errors: string[] = []

    if (editExistingAgentNames.length > 0 && editAgentName.trim()) {
      const currentAgentName = selectedDepartment?.agent?.agent_name?.toLowerCase()
      const newAgentName = editAgentName.trim().toLowerCase()

      // Only check for conflicts if the name is actually changing
      if (currentAgentName !== newAgentName && editExistingAgentNames.includes(newAgentName)) {
        errors.push(`Agent name "${editAgentName}" already exists`)
      }
    }

    setEditValidationErrors(errors)
    return errors
  }, [editAgentName, editExistingAgentNames, selectedDepartment])

  useEffect(() => {
    validateFormRealTime()
  }, [validateFormRealTime])

  useEffect(() => {
    validateEditFormRealTime()
  }, [validateEditFormRealTime])

  const handleCreateDepartment = async () => {
    const validationErrors = validateForm()

    if (validationErrors.length > 0) {
      toast({
        title: "Validation Error",
        description: validationErrors.join(", "),
        variant: "destructive",
      })
      return
    }

    if (!departmentName.trim() || !agentName.trim() || !selectedProvider) {
      toast({
        title: "Validation Error",
        description: "All required fields must be filled",
        variant: "destructive",
      })
      return
    }

    try {
      setCreating(true)

      const requestData = {
        department_name: departmentName.trim(),
        description: departmentDescription.trim(),
        agent_name: agentName.trim(),
        agent_description: agentDescription.trim(),
        provider_id: selectedProvider,
        model_id: selectedModel || undefined,
        provider_config: undefined,
        tool_ids: selectedToolIds
      }

      const response = await apiService.departments.create(requestData)

      toast({
        title: t('notifications.success'),
        description: t('messages.success.departmentCreated'),
      })

      setIsCreateDialogOpen(false)
      resetCreateForm()
      loadDepartments()
    } catch (error: any) {
      let errorMessage = t('messages.errors.failedToCreateDepartment')
      
      if (error?.response?.data?.detail) {
        const detail = error.response.data.detail
        if (detail.includes('duplicate key value violates unique constraint "uq_agent_tenant_name"')) {
          errorMessage = `Agent name "${agentName}" already exists. Please choose a different name.`
          loadExistingAgentNames()
        } else if (detail.includes('duplicate key value violates unique constraint "uq_department_tenant_name"')) {
          errorMessage = `Department name "${departmentName}" already exists. Please choose a different name.`
        }else if (detail.includes('duplicate')) {
          errorMessage = 'A department or agent with this name already exists. Please choose different names.'
        } else {
          errorMessage = detail
        }
      }
      
      toast({
        title: t('notifications.error'),
        description: errorMessage,
        variant: "destructive",
      })
    } finally {
      setCreating(false)
    }
  }

  const resetCreateForm = () => {
    setDepartmentName('')
    setDepartmentDescription('')
    setAgentName('')
    setAgentDescription('')
    setSelectedProvider('')
    setSelectedModel('')
    setSelectedToolIds([])
    setValidationErrors([])
  }

  const resetEditForm = () => {
    setSelectedDepartment(null)
    setDepartmentName('')
    setDepartmentDescription('')
    setEditAgentName('')
    setEditAgentDescription('')
    setEditSelectedProvider('')
    setEditSelectedModel('')
    setEditSelectedToolIds([])
    setEditExistingAgentNames([])
    setEditValidationErrors([])
  }

  const handleUpdateDepartment = async () => {
    if (!selectedDepartment || !departmentName.trim() || !editAgentName.trim()) return

    try {
      setUpdating(true)

      const updateData = {
        department_name: departmentName.trim(),
        description: departmentDescription.trim(),
        agent_name: editAgentName.trim(),
        agent_description: editAgentDescription.trim(),
        provider_id: editSelectedProvider,
        model_id: editSelectedModel || undefined,
        tool_ids: editSelectedToolIds
      }

      await apiService.departments.update(selectedDepartment.id, updateData)

      toast({
        title: t('notifications.success'),
        description: t('messages.success.departmentUpdated'),
      })

      setIsEditDialogOpen(false)
      resetEditForm()
      loadDepartments()
    } catch (error: any) {
      let errorMessage = t('messages.errors.failedToUpdateDepartment')

      if (error?.response?.data?.detail) {
        const detail = error.response.data.detail
        if (detail.includes('duplicate key value violates unique constraint "uq_agent_tenant_name"')) {
          errorMessage = `Agent name "${editAgentName}" already exists. Please choose a different name.`
        } else if (detail.includes('duplicate key value violates unique constraint "uq_department_tenant_name"')) {
          errorMessage = `Department name "${departmentName}" already exists. Please choose a different name.`
        } else if (detail.includes('duplicate')) {
          errorMessage = 'A department or agent with this name already exists. Please choose different names.'
        } else {
          errorMessage = detail
        }
      }

      toast({
        title: t('notifications.error'),
        description: errorMessage,
        variant: "destructive",
      })
    } finally {
      setUpdating(false)
    }
  }

  const handleDeleteDepartment = async (departmentId: string) => {
    try {
      setDeleting(departmentId)
      await apiService.departments.delete(departmentId)

      toast({
        title: t('notifications.success'),
        description: t('messages.success.departmentDeleted'),
      })

      loadDepartments()
    } catch (error) {
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToDeleteDepartment'),
        variant: "destructive",
      })
    } finally {
      setDeleting(null)
    }
  }

  const openEditDialog = async (department: Department) => {
    try {
      setSelectedDepartment(department)
      setDepartmentName(department.department_name)
      setDepartmentDescription(department.description || '')

      // Load agent information
      if (department.agent) {
        const providerId = department.agent.provider_id || ''
        const modelId = department.agent.model_id || ''

        setEditAgentName(department.agent.agent_name || '')
        setEditAgentDescription(department.agent.description || '')

        if (providerId) {
          setEditSelectedProvider(providerId)
          setEditSelectedModel(modelId)
          
          const provider = providers.find(p => p.id === providerId)
          if (provider) {
            setModels(provider.models || [])
          }
        } else {
          setEditSelectedProvider('')
          setEditSelectedModel('')
        }
      } else {
        setEditAgentName('')
        setEditAgentDescription('')
        setEditSelectedProvider('')
        setEditSelectedModel('')
      }

      // Load tool assignments
      if (department.tool_assignments) {
        const toolIds = department.tool_assignments.map((tool: any) => tool.tool_id)
        setEditSelectedToolIds(toolIds)
      } else {
        setEditSelectedToolIds([])
      }

      const response = await apiService.departments.list(tenantId)
      const allDepartments = response || []
      const agentNames: string[] = []

      if (Array.isArray(allDepartments) && allDepartments.length > 0) {
        allDepartments.forEach((dept: any) => {
          if (dept.id !== department.id && dept.agent?.agent_name) {
            agentNames.push(dept.agent.agent_name.toLowerCase())
          }
        })
      }

      setEditExistingAgentNames(agentNames)
      setEditValidationErrors([])

      setIsEditDialogOpen(true)
    } catch (error) {
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToLoadDepartmentData'),
        variant: "destructive",
      })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('admin.departmentManagement')}</h1>
          <p className="text-muted-foreground">
            {t('admin.createAndManageDepartments')}
          </p>
        </div>

        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2" onClick={() => {
              loadDynamicData()
            }}>
              <Plus className="h-4 w-4" />
              {t('tenant.addDepartment')}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col" style={{ overflow: 'visible' }}>
            <DialogHeader className="flex-shrink-0">
              <DialogTitle>{t('tenant.createNewDepartment')}</DialogTitle>
              <DialogDescription>
                {t('department.createNewDepartmentDescription')}
              </DialogDescription>
            </DialogHeader>

            <div className="flex-1" style={{ overflow: 'visible' }}>
              <Tabs defaultValue="department" className="w-full h-full flex flex-col">
                <TabsList className="grid w-full grid-cols-4 flex-shrink-0">
                  <TabsTrigger value="department" className="flex items-center gap-2">
                    <Building className="h-4 w-4" />
                    {t('tenant.department')}
                  </TabsTrigger>
                  <TabsTrigger value="agent" className="flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    {t('tenant.agents')}
                  </TabsTrigger>
                  <TabsTrigger value="provider" className="flex items-center gap-2">
                    <Key className="h-4 w-4" />
                    {t('tenant.provider')}
                  </TabsTrigger>
                  <TabsTrigger value="tools" className="flex items-center gap-2">
                    <Wrench className="h-4 w-4" />
                    {t('tenant.tool')}
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="department" className="flex-1 overflow-y-auto space-y-4 pl-2 pr-2">
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                    <Label htmlFor="department-name">{t('tenant.departmentName')} *</Label>
                <Input
                  id="department-name"
                  value={departmentName}
                  onChange={(e) => setDepartmentName(e.target.value)}
                      placeholder={t('tenant.enterDepartmentName')}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="department-description">{t('tenant.descriptionDepartment')}</Label>
                    <Textarea
                      id="department-description"
                      value={departmentDescription}
                      onChange={(e) => setDepartmentDescription(e.target.value)}
                      placeholder={t('tenant.enterDescription')}
                      rows={3}
                    />
                  </div>
                </div>
              </TabsContent>

                <TabsContent value="agent" className="flex-1 overflow-y-auto space-y-4 pl-2 pr-2">
                  <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="agent-name">Agent Name *</Label>
                    <Input
                      id="agent-name"
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                      placeholder="Enter agent name"
                      className={validationErrors.some(error => error.includes('Agent name')) ? 'border-red-500' : ''}
                    />
                    {validationErrors.some(error => error.includes('Agent name')) && (
                      <p className="text-red-500 text-xs mt-1">
                        {validationErrors.find(error => error.includes('Agent name'))}
                      </p>
                    )}
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="agent-description">Agent Description</Label>
                    <Textarea
                      id="agent-description"
                      value={agentDescription}
                      onChange={(e) => setAgentDescription(e.target.value)}
                      placeholder="Describe what this agent does"
                      rows={3}
                    />
                  </div>
                </div>
              </TabsContent>

                <TabsContent value="provider" className="flex-1 space-y-4" style={{ overflow: 'visible' }}>
                  <div className="space-y-6 py-4 pl-2 pr-4 max-h-[400px] overflow-y-auto" 
                       style={{ 
                         scrollbarWidth: 'thin', 
                         scrollbarColor: '#d1d5db #f3f4f6' 
                       }}>
                  {/* Provider Selection */}
                  <div className="space-y-2 relative z-10">
                    <Label htmlFor="provider" className="text-sm font-medium">Provider *</Label>
                    <Select 
                      value={selectedProvider} 
                      onValueChange={(value) => {
                        setSelectedProvider(value)
                        setSelectedModel('')
                      }}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a provider for the agent" />
                      </SelectTrigger>
                      <SelectContent 
                        className="max-h-64 overflow-y-auto"
                        position="popper"
                        side="bottom"
                        align="start"
                        sideOffset={5}
                        avoidCollisions={false}
                      >
                        {providers.filter(provider => provider.models && provider.models.length > 0).map((provider, index) => (
                          <SelectItem
                            key={provider.id}
                            value={provider.id}
                            className="py-3 px-3"
                          >
                            <div className="flex flex-col items-start w-full min-w-0">
                              <span className="font-medium text-sm truncate w-full">{provider.name}</span>
                              <span className="text-xs text-muted-foreground">
                                {provider.models?.length || 0} models available
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selectedProvider && (
                      <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                        <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                        Provider selected: {providers.find(p => p.id === selectedProvider)?.name}
                      </p>
                    )}
                  </div>

                  {/* Model Selection - Always reserve space to prevent layout shift */}
                  <div className="space-y-2 border-t pt-4 min-h-[60px] relative z-10">
                    {selectedProvider && (
                      <>
                        <Label htmlFor="model" className="text-sm font-medium">Model</Label>
                      <Select value={selectedModel} onValueChange={setSelectedModel}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a model for the agent" />
                        </SelectTrigger>
                        <SelectContent 
                          className="max-h-48 overflow-y-auto"
                          position="popper"
                          side="bottom"
                          align="start"
                          sideOffset={5}
                          avoidCollisions={false}
                        >
                          {models.map((model, index) => (
                            <SelectItem
                              key={`model-${model.id || index}`}
                              value={model.id}
                              className="py-2 px-3"
                            >
                              <span className="text-sm truncate w-full block">{model.name}</span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {selectedModel && (
                        <p className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
                          <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                          Model selected: {models.find(m => m.id === selectedModel)?.name || selectedModel}
                        </p>
                      )}
                      </>
                    )}
                  </div>

                </div>
              </TabsContent>

                <TabsContent value="tools" className="flex-1 overflow-y-auto space-y-4 pr-2">
                  <div className="grid gap-4 py-4">
                  <div className="space-y-2">
                    <Label className="text-base font-medium">Select Tools to Assign to Agent</Label>
                    <div className="grid grid-cols-1 gap-3 max-h-64 overflow-y-auto border rounded-lg p-4 pr-4 bg-gray-50 dark:bg-gray-900"
                         style={{ 
                           scrollbarWidth: 'thin', 
                           scrollbarColor: '#d1d5db #f9fafb' 
                         }}>
                      {availableTools.map((tool) => (
                        <div key={tool.id} className="flex items-start space-x-3 p-2 rounded-md hover:bg-white dark:hover:bg-gray-800 transition-colors">
                          <Checkbox
                            id={`tool-${tool.id}`}
                            checked={selectedToolIds.includes(tool.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedToolIds([...selectedToolIds, tool.id])
                              } else {
                                setSelectedToolIds(selectedToolIds.filter(id => id !== tool.id))
                              }
                            }}
                            className="mt-1"
                          />
                          <div className="flex-1 min-w-0">
                            <Label
                              htmlFor={`tool-${tool.id}`}
                              className="text-sm font-medium cursor-pointer text-gray-900 dark:text-gray-100"
                            >
                              {tool.tool_name || tool.name}
                            </Label>
                            {tool.description && (
                              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 leading-relaxed">
                                {tool.description}
                              </p>
                            )}
                            {tool.category && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 mt-1">
                                {tool.category}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    {availableTools.length === 0 && (
                      <p className="text-sm text-muted-foreground text-center py-8">No tools available for this tenant</p>
                    )}
                    {selectedToolIds.length > 0 && (
                      <p className="text-sm text-green-600 dark:text-green-400">
                        ✓ {selectedToolIds.length} tool{selectedToolIds.length > 1 ? 's' : ''} selected
                      </p>
                    )}
                  </div>
                </div>
              </TabsContent>
              </Tabs>
            </div>

            {/* Form Summary */}
            <div className="border-t pt-4 mt-4 flex-shrink-0">
              <div className="flex items-center justify-between text-sm">
                <div className="flex gap-4 flex-wrap">
                  <span className={departmentName.trim() ? "text-green-600" : "text-red-500 font-medium"}>
                    {departmentName.trim() ? "✓" : "✗"} Department: {departmentName.trim() || "Required"}
                  </span>
                  <span className={agentName.trim() ? "text-green-600" : "text-red-500 font-medium"}>
                    {agentName.trim() ? "✓" : "✗"} Agent: {agentName.trim() || "Required"}
                  </span>
                  <span className={selectedProvider ? "text-green-600" : "text-red-500 font-medium"}>
                    {selectedProvider ? "✓" : "✗"} Provider: {selectedProvider ? providers.find(p => p.id === selectedProvider)?.name : "Required"}
                  </span>
                  <span className={selectedToolIds.length > 0 ? "text-green-600" : "text-gray-400"}>
                    ✓ Tools: {selectedToolIds.length} (Optional)
                  </span>
                </div>
              </div>
              {(!isFormValid() || validationErrors.length > 0) && (
                <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
                  <strong>Issues found:</strong>
                  <ul className="mt-1 list-disc list-inside">
                    {!departmentName.trim() && <li>Department name is required</li>}
                    {!agentName.trim() && <li>Agent name is required</li>}
                    {!selectedProvider && <li>Provider selection is required</li>}
                    {validationErrors.map((error, index) => (
                      <li key={index}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <DialogFooter className="flex-shrink-0 border-t pt-4 mt-4">
              <Button
                variant="outline"
                onClick={() => setIsCreateDialogOpen(false)}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateDepartment}
                disabled={creating || !isFormValid()}
                className={!isFormValid() && !creating ? "opacity-50 cursor-not-allowed" : ""}
              >
                {creating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create Department"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Departments Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {departments.map((dept) => (
          <Card key={dept.id} className="hover:shadow-md transition-shadow">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-xl">{dept.department_name}</CardTitle>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditDialog(dept)}
                    className="h-8 w-8 p-0"
                  >
                    <Edit className="h-4 w-4" />
                  </Button>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                        disabled={deleting === dept.id}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t('tenant.deleteDepartment')}</AlertDialogTitle>
                        <AlertDialogDescription>
                          {t('tenant.areYouSureYouWantToDelete', { name: dept.department_name })}
                          {t('tenant.thisActionCannotBeUndoneAndWillAlsoDeleteAllAssociatedAgents')}
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => handleDeleteDepartment(dept.id)}
                          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                          {t('common.delete')}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>
              <CardDescription>
                Created {new Date(dept.created_at).toLocaleDateString()}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <Badge variant="secondary" className="gap-1">
                  <Users className="h-3 w-3" />
                  {dept.agent_count} {t('tenant.agents')}
                </Badge>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push(`/${tenantId}/admin/departments/${dept.id}`)}
                >
                  {t('tenant.manageAgents')}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}

        {departments.length === 0 && (
          <div className="col-span-full text-center py-12">
            <Building className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">{t('tenant.noDepartmentsYet')}</h3>
            <p className="text-muted-foreground">
              {t('tenant.getStartedByCreatingYourFirstDepartment')}
            </p>
          </div>
        )}
      </div>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col" style={{ overflow: 'visible' }}>
          <DialogHeader className="flex-shrink-0">
            <DialogTitle>{t('tenant.editDepartment')}</DialogTitle>
            <DialogDescription>
              {t('tenant.updateDepartmentInformation')}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1" style={{ overflow: 'visible' }}>
            <Tabs defaultValue="department" className="w-full h-full flex flex-col">
              <TabsList className="grid w-full grid-cols-4 flex-shrink-0">
                <TabsTrigger value="department" className="flex items-center gap-2">
                  <Building className="h-4 w-4" />
                  {t('tenant.department')}
                </TabsTrigger>
                <TabsTrigger value="agent" className="flex items-center gap-2">
                  <Settings className="h-4 w-4" />
                  {t('tenant.agents')}
                </TabsTrigger>
                <TabsTrigger value="provider" className="flex items-center gap-2">
                  <Key className="h-4 w-4" />
                  {t('tenant.provider')}
                </TabsTrigger>
                <TabsTrigger value="tools" className="flex items-center gap-2">
                  <Wrench className="h-4 w-4" />
                  {t('tenant.tool')}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="department" className="flex-1 overflow-y-auto space-y-4 pl-2 pr-2">
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="edit-department-name">{t('tenant.departmentName')} *</Label>
                    <Input
                      id="edit-department-name"
                      value={departmentName}
                      onChange={(e) => setDepartmentName(e.target.value)}
                      placeholder={t('tenant.enterDepartmentName')}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="edit-department-description">{t('tenant.descriptionDepartment')}</Label>
                    <Textarea
                      id="edit-department-description"
                      value={departmentDescription}
                      onChange={(e) => setDepartmentDescription(e.target.value)}
                      placeholder={t('tenant.enterDescription')}
                      rows={3}
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="agent" className="flex-1 overflow-y-auto space-y-4 pl-2 pr-2">
                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="edit-agent-name">Agent Name *</Label>
                    <Input
                      id="edit-agent-name"
                      value={editAgentName}
                      onChange={(e) => setEditAgentName(e.target.value)}
                      placeholder="Enter agent name"
                      className={editValidationErrors.some(error => error.includes('Agent name')) ? 'border-red-500' : ''}
                    />
                    {editValidationErrors.some(error => error.includes('Agent name')) && (
                      <p className="text-red-500 text-xs mt-1">
                        {editValidationErrors.find(error => error.includes('Agent name'))}
                      </p>
                    )}
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="edit-agent-description">Agent Description</Label>
                    <Textarea
                      id="edit-agent-description"
                      value={editAgentDescription}
                      onChange={(e) => setEditAgentDescription(e.target.value)}
                      placeholder="Describe what this agent does"
                      rows={3}
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="provider" className="flex-1 space-y-4" style={{ overflow: 'visible' }}>
                <div className="space-y-6 py-4 pl-2 pr-4 max-h-[400px] overflow-y-auto"
                     style={{
                       scrollbarWidth: 'thin',
                       scrollbarColor: '#d1d5db #f3f4f6'
                     }}>
                  {/* Provider Selection */}
                  <div className="space-y-2 relative z-10">
                    <Label htmlFor="edit-provider" className="text-sm font-medium">Provider *</Label>
                    <Select
                      value={editSelectedProvider}
                      onValueChange={(value) => {
                        setEditSelectedProvider(value)
                        setEditSelectedModel('')
                      }}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a provider for the agent" />
                      </SelectTrigger>
                      <SelectContent
                        className="max-h-64 overflow-y-auto"
                        position="popper"
                        side="bottom"
                        align="start"
                        sideOffset={5}
                        avoidCollisions={false}
                      >
                        {providers.filter(provider => provider.models && provider.models.length > 0).map((provider, index) => (
                          <SelectItem
                            key={provider.id}
                            value={provider.id}
                            className="py-3 px-3"
                          >
                            <div className="flex flex-col items-start w-full min-w-0">
                              <span className="font-medium text-sm truncate w-full">{provider.name}</span>
                              <span className="text-xs text-muted-foreground">
                                {provider.models?.length || 0} models available
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {editSelectedProvider && (
                      <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                        <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                        Provider selected: {providers.find(p => p.id === editSelectedProvider)?.name}
                      </p>
                    )}
                  </div>

                  {/* Model Selection - Always reserve space to prevent layout shift */}
                  <div className="space-y-2 border-t pt-4 min-h-[60px] relative z-10">
                    {editSelectedProvider && (
                      <>
                        <Label htmlFor="edit-model" className="text-sm font-medium">Model</Label>
                        <Select value={editSelectedModel} onValueChange={setEditSelectedModel}>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select a model for the agent" />
                          </SelectTrigger>
                          <SelectContent
                            className="max-h-48 overflow-y-auto"
                            position="popper"
                            side="bottom"
                            align="start"
                            sideOffset={5}
                            avoidCollisions={false}
                          >
                            {models.map((model, index) => (
                              <SelectItem
                                key={`edit-model-${model.id || index}`}
                                value={model.id}
                                className="py-2 px-3"
                              >
                                <span className="text-sm truncate w-full block">{model.name}</span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {editSelectedModel && (
                          <p className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
                            <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                            Model selected: {models.find(m => m.id === editSelectedModel)?.name || editSelectedModel}
                          </p>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="tools" className="flex-1 overflow-y-auto space-y-4 pr-2">
                <div className="grid gap-4 py-4">
                  <div className="space-y-2">
                    <Label className="text-base font-medium">Select Tools to Assign to Agent</Label>
                    <div className="grid grid-cols-1 gap-3 max-h-64 overflow-y-auto border rounded-lg p-4 pr-4 bg-gray-50 dark:bg-gray-900"
                         style={{
                           scrollbarWidth: 'thin',
                           scrollbarColor: '#d1d5db #f9fafb'
                         }}>
                      {availableTools.map((tool) => (
                        <div key={tool.id} className="flex items-start space-x-3 p-2 rounded-md hover:bg-white dark:hover:bg-gray-800 transition-colors">
                          <Checkbox
                            id={`edit-tool-${tool.id}`}
                            checked={editSelectedToolIds.includes(tool.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setEditSelectedToolIds([...editSelectedToolIds, tool.id])
                              } else {
                                setEditSelectedToolIds(editSelectedToolIds.filter(id => id !== tool.id))
                              }
                            }}
                            className="mt-1"
                          />
                          <div className="flex-1 min-w-0">
                            <Label
                              htmlFor={`edit-tool-${tool.id}`}
                              className="text-sm font-medium cursor-pointer text-gray-900 dark:text-gray-100"
                            >
                              {tool.tool_name || tool.name}
                            </Label>
                            {tool.description && (
                              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 leading-relaxed">
                                {tool.description}
                              </p>
                            )}
                            {tool.category && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 mt-1">
                                {tool.category}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    {availableTools.length === 0 && (
                      <p className="text-sm text-muted-foreground text-center py-8">No tools available for this tenant</p>
                    )}
                    {editSelectedToolIds.length > 0 && (
                      <p className="text-sm text-green-600 dark:text-green-400">
                        ✓ {editSelectedToolIds.length} tool{editSelectedToolIds.length > 1 ? 's' : ''} selected
                      </p>
                    )}
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>

          {/* Form Summary */}
          <div className="border-t pt-4 mt-4 flex-shrink-0">
            <div className="flex items-center justify-between text-sm">
              <div className="flex gap-4 flex-wrap">
                <span className={departmentName.trim() ? "text-green-600" : "text-red-500 font-medium"}>
                  {departmentName.trim() ? "✓" : "✗"} Department: {departmentName.trim() || "Required"}
                </span>
                <span className={editAgentName.trim() ? "text-green-600" : "text-red-500 font-medium"}>
                  {editAgentName.trim() ? "✓" : "✗"} Agent: {editAgentName.trim() || "Required"}
                </span>
                <span className={editSelectedProvider ? "text-green-600" : "text-red-500 font-medium"}>
                  {editSelectedProvider ? "✓" : "✗"} Provider: {editSelectedProvider ? providers.find(p => p.id === editSelectedProvider)?.name : "Required"}
                </span>
                <span className={editSelectedToolIds.length > 0 ? "text-green-600" : "text-gray-400"}>
                  ✓ Tools: {editSelectedToolIds.length} (Optional)
                </span>
              </div>
            </div>
            {(editValidationErrors.length > 0 || !departmentName.trim() || !editAgentName.trim() || !editSelectedProvider) && (
              <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
                <strong>Issues found:</strong>
                <ul className="mt-1 list-disc list-inside">
                  {!departmentName.trim() && <li>Department name is required</li>}
                  {!editAgentName.trim() && <li>Agent name is required</li>}
                  {!editSelectedProvider && <li>Provider selection is required</li>}
                  {editValidationErrors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <DialogFooter className="flex-shrink-0 border-t pt-4 mt-4">
            <Button
              variant="outline"
              onClick={() => {
                setIsEditDialogOpen(false)
                resetEditForm()
              }}
              disabled={updating}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateDepartment}
              disabled={updating || !departmentName.trim() || !editAgentName.trim() || !editSelectedProvider || editValidationErrors.length > 0}
              className={(!departmentName.trim() || !editAgentName.trim() || !editSelectedProvider || editValidationErrors.length > 0) && !updating ? "opacity-50 cursor-not-allowed" : ""}
            >
              {updating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                "Update Department"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
