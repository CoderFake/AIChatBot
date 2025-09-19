'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Bot, Settings, Plus, Edit, Trash2, Play, Pause } from 'lucide-react'
import { TenantsAPI } from '@/lib/api/tenants'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from 'react-i18next'
import { apiService } from '@/lib/api/index'

interface Agent {
  id: string
  agent_name: string
  description: string
  is_enabled: boolean
  department_id: string
  department_name: string
  provider_id: string
  model_id: string
  is_system: boolean
}

interface Department {
  id: string
  name: string
  tenant_id: string
}

interface Provider {
  id: string
  name: string
}

interface Model {
  id: string
  name: string
  display_name?: string
  provider?: string
}

interface AgentManagementProps {
  tenantId: string
}

export function AgentManagement({ tenantId }: AgentManagementProps) {
  const { toast } = useToast()
  const { t } = useTranslation()
  const [agents, setAgents] = useState<Agent[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [agentName, setAgentName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [creating, setCreating] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  const tenantsAPI = new TenantsAPI(apiService.client)

  useEffect(() => {
    loadData()
  }, [tenantId])

  const loadData = async () => {
    try {
      setLoading(true)

      const [agentResponse, deptResponse] = await Promise.all([
        tenantsAPI.listAgents(tenantId),
        tenantsAPI.listDepartments(tenantId)
      ])

      setAgents(agentResponse.agents || [])
      setDepartments(deptResponse || [])

      try {
        const providersResponse = await apiService.tenants.getAvailableProviders()
        const providersData = providersResponse.providers || []

        const transformedProviders = providersData.map(p => ({
          id: p.id,
          name: p.tenant_name,
          display_name: p.tenant_name
        }))

        setProviders(transformedProviders)

        const loadModelsFromDB = async () => {
          try {
            const allModels: Model[] = []

            for (const provider of transformedProviders) {
              try {
                const modelsResponse = await apiService.tenants.getProviderModels(provider.name)
                if (modelsResponse.models && modelsResponse.models.length > 0) {
                  modelsResponse.models.forEach(model => {
                    allModels.push({
                      id: `${provider.name}_${model.name}`,
                      name: model.name,
                      display_name: model.display_name,
                      provider: provider.name
                    })
                  })
                }
              } catch (error) {
                console.warn(`Failed to load models for provider ${provider.name}:`, error)
              }
            }

            setModels(allModels)
          } catch (error) {
            console.error('Failed to load models from database:', error)
            setModels([])
          }
        }

        await loadModelsFromDB() 

      } catch (error) {
        console.error('Failed to load providers and models:', error)
        setProviders([])
        setModels([])
      }

    } catch (error) {
      console.error('Failed to load data:', error)
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToLoadAgents'),
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const handleCreateAgent = async () => {
    if (!agentName.trim() || !description.trim() || !selectedDepartment || !selectedProvider) return

    try {
      setCreating(true)
      const agentData = {
        agent_name: agentName.trim(),
        description: description.trim(),
        department_id: selectedDepartment,
        provider_id: selectedProvider,
        model_name: selectedModel || 'default',
        model_id: selectedModel || 'default'
      }

      await tenantsAPI.createAgent(agentData)

      toast({
        title: t('notifications.success'),
        description: t('messages.success.agentCreated'),
      })

      setIsCreateDialogOpen(false)
      resetForm()
      loadData()
    } catch (error) {
      console.error('Failed to create agent:', error)
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToCreateAgent'),
        variant: "destructive",
      })
    } finally {
      setCreating(false)
    }
  }

  const handleUpdateAgent = async () => {
    if (!selectedAgent || !agentName.trim() || !description.trim()) return

    try {
      setUpdating(true)
      const updateData = {
        agent_name: agentName.trim(),
        description: description.trim(),
        provider_id: selectedProvider || selectedAgent.provider_id,
        model_name: selectedModel || selectedAgent.model_id,
        model_id: selectedModel || selectedAgent.model_id
      }

      await tenantsAPI.updateAgent(selectedAgent.id, updateData)

      toast({
        title: t('notifications.success'),
        description: t('messages.success.agentUpdated'),
      })

      setIsEditDialogOpen(false)
      setSelectedAgent(null)
      resetForm()
      loadData()
    } catch (error) {
      console.error('Failed to update agent:', error)
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToUpdateAgent'),
        variant: "destructive",
      })
    } finally {
      setUpdating(false)
    }
  }

  const handleDeleteAgent = async (agentId: string) => {
    try {
      setDeleting(agentId)
      await tenantsAPI.deleteAgent(agentId)

      toast({
        title: t('notifications.success'),
        description: t('messages.success.agentDeleted'),
      })

      loadData()
    } catch (error) {
      console.error('Failed to delete agent:', error)
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToDeleteAgent'),
        variant: "destructive",
      })
    } finally {
      setDeleting(null)
    }
  }

  const handleToggleAgent = async (agent: Agent) => {
    try {
      toast({
        title: t('notifications.info'),
        description: t('forms.buttons.toggleAgentStatus'),
      })
    } catch (error) {
      console.error('Failed to toggle agent:', error)
      toast({
        title: t('notifications.error'),
        description: t('messages.errors.failedToToggleAgent'),
        variant: "destructive",
      })
    }
  }

  const resetForm = () => {
    setAgentName('')
    setDescription('')
    setSelectedDepartment('')
    setSelectedProvider('')
    setSelectedModel('')
  }

  const openEditDialog = (agent: Agent) => {
    setSelectedAgent(agent)
    setAgentName(agent.agent_name)
    setDescription(agent.description)
    setSelectedDepartment(agent.department_id)
    setSelectedProvider(agent.provider_id)
    setSelectedModel(agent.model_id)
    setIsEditDialogOpen(true)
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
          <h1 className="text-3xl font-bold tracking-tight">Agent Management</h1>
          <p className="text-muted-foreground">
            Configure and manage AI agents for your departments
          </p>
        </div>

        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Create Agent
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New Agent</DialogTitle>
              <DialogDescription>
                Configure a new AI agent for your department
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="agent-name">Agent Name</Label>
                <Input
                  id="agent-name"
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  placeholder={t('forms.placeholders.enterAgentName')}
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="agent-description">Description</Label>
                <Textarea
                  id="agent-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t('forms.placeholders.describeAgent')}
                  rows={3}
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="department-select">Department</Label>
                <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('forms.placeholders.selectDepartment')} />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map((dept) => (
                      <SelectItem key={dept.id} value={dept.id}>
                        {dept.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="provider-select">AI Provider</Label>
                  <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('forms.placeholders.selectProvider')} />
                    </SelectTrigger>
                    <SelectContent>
                      {providers.map((provider) => (
                        <SelectItem key={provider.id} value={provider.id}>
                          {provider.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="model-select">AI Model</Label>
                  <Select value={selectedModel} onValueChange={setSelectedModel}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('forms.placeholders.selectModel')} />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setIsCreateDialogOpen(false)
                  resetForm()
                }}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateAgent}
                disabled={!agentName.trim() || !description.trim() || !selectedDepartment || !selectedProvider || creating}
              >
                {creating ? 'Creating...' : 'Create Agent'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Agents Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => (
          <Card key={agent.id} className="hover:shadow-md transition-shadow">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-xl">{agent.agent_name}</CardTitle>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={agent.is_enabled}
                    onCheckedChange={() => handleToggleAgent(agent)}
                    disabled={agent.is_system}
                  />
                  <Badge variant={agent.is_enabled ? "default" : "secondary"}>
                    {agent.is_enabled ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </div>
              <CardDescription>{agent.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Department:</span>
                  <span className="font-medium">{agent.department_name}</span>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Provider:</span>
                  <span className="font-medium">
                    {providers.find(p => p.id === agent.provider_id)?.name || agent.provider_id}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Model:</span>
                  <span className="font-medium">
                    {models.find(m => m.id === agent.model_id)?.name || agent.model_id}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(agent)}
                      className="h-8 w-8 p-0"
                      disabled={agent.is_system}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                          disabled={agent.is_system || deleting === agent.id}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Agent</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete "{agent.agent_name}"?
                            This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => handleDeleteAgent(agent.id)}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleToggleAgent(agent)}
                    disabled={agent.is_system}
                  >
                    {agent.is_enabled ? (
                      <>
                        <Pause className="h-4 w-4 mr-1" />
                        Disable
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-1" />
                        Enable
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {agents.length === 0 && (
          <div className="col-span-full text-center py-12">
            <Bot className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No agents yet</h3>
            <p className="text-muted-foreground">
              Create your first AI agent to get started
            </p>
          </div>
        )}
      </div>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Agent</DialogTitle>
            <DialogDescription>
              Update agent configuration
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-agent-name">Agent Name</Label>
              <Input
                id="edit-agent-name"
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="Enter agent name"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="edit-agent-description">Description</Label>
              <Textarea
                id="edit-agent-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this agent does"
                rows={3}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="edit-department-select">Department</Label>
              <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                <SelectTrigger>
                  <SelectValue placeholder="Select department" />
                </SelectTrigger>
                <SelectContent>
                  {departments.map((dept) => (
                    <SelectItem key={dept.id} value={dept.id}>
                      {dept.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-provider-select">AI Provider</Label>
                <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id}>
                        {provider.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="edit-model-select">AI Model</Label>
                <Select value={selectedModel} onValueChange={setSelectedModel}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {models.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsEditDialogOpen(false)
                setSelectedAgent(null)
                resetForm()
              }}
              disabled={updating}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateAgent}
              disabled={!agentName.trim() || !description.trim() || updating}
            >
              {updating ? 'Updating...' : 'Update Agent'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
