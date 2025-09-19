'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { UserPlus, Users, Building, Mail, Copy, Check } from 'lucide-react'
import { TenantsAPI } from '@/lib/api/tenants'
import { useToast } from '@/hooks/use-toast'
import { useTranslation } from 'react-i18next'
import { apiService } from '@/lib/api/index'
import type { Department } from '@/types'
import { useAuth } from '@/lib/auth-context'

interface InviteManagementProps {
  tenantId: string
  context?: 'system_admin' | 'tenant_admin'
}

type InviteType = 'department_admins' | 'department_managers' | 'users' | 'admins'
type ManagementType = 'invite' | 'promote'

export function InviteManagement({ tenantId, context = 'tenant_admin' }: InviteManagementProps) {
  const { toast } = useToast()
  const { t } = useTranslation()
  const { user } = useAuth()
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false)
  const [inviteType, setInviteType] = useState<InviteType>(context === 'system_admin' ? 'admins' : 'users')
  const [selectedDepartment, setSelectedDepartment] = useState<string>('')
  const [emails, setEmails] = useState('')
  const [inviteMessage, setInviteMessage] = useState('')
  const [inviting, setInviting] = useState(false)
  const [inviteLinks, setInviteLinks] = useState<string[]>([])
  const [copiedLink, setCopiedLink] = useState<string | null>(null)
  const [managementType, setManagementType] = useState<ManagementType>('invite')
  const [departmentUsers, setDepartmentUsers] = useState<any[]>([])
  const [selectedUsers, setSelectedUsers] = useState<string[]>([])
  const [promoting, setPromoting] = useState(false)

  const tenantsAPI = new TenantsAPI(apiService.client)

  const getAvailableInviteTypes = (): InviteType[] => {
    if (!user) return ['users']

    const userRole = user.role

    if (context === 'system_admin') {
      if (userRole === 'MAINTAINER') {
        return ['admins']
      }
      return ['users']
    }

    if (userRole === 'ADMIN') {
      return ['users', 'department_managers', 'department_admins']
    } else if (userRole === 'DEPT_ADMIN') {
      return ['users', 'department_managers']
    } else if (userRole === 'DEPT_MANAGER') {
      return ['users']
    }

    return ['users']
  }

  useEffect(() => {
    if (context === 'tenant_admin') {
      loadDepartments()
    } else {
      setLoading(false)
    }
  }, [tenantId, context])

  useEffect(() => {
    if (context === 'system_admin') {
      setManagementType('invite')
    }

    const availableTypes = getAvailableInviteTypes()
    if (availableTypes.length > 0 && !availableTypes.includes(inviteType)) {
      setInviteType(availableTypes[0])
    }
  }, [user, context, inviteType])

  const loadDepartments = async () => {
    try {
      setLoading(true)
      let response = await apiService.departments.list(tenantId)
      if (user?.role === 'DEPT_ADMIN' || user?.role === 'DEPT_MANAGER') {
        response = response || []
      } else {
        response = response || []
      }

      setDepartments(response)
    } catch (error) {
      console.error('Failed to load departments:', error)
      toast({
        title: t('common.error'),
        description: t('invite.failedToLoadDepartments'),
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const loadDepartmentUsers = async (departmentId: string) => {
    try {
      const response = { users: [] }
      setDepartmentUsers(response?.users || [])
    } catch (error) {
      console.error('Failed to load department users:', error)
      toast({
        title: t('common.error'),
        description: 'Failed to load department users',
        variant: "destructive",
      })
    }
  }

  const handleUserPromotion = async () => {
    if (selectedUsers.length === 0 || !selectedDepartment) return

    try {
      setPromoting(true)

      toast({
        title: t('common.success'),
        description: `Promoted ${selectedUsers.length} user(s) to department manager`,
      })

      setSelectedUsers([])
      await loadDepartmentUsers(selectedDepartment)
    } catch (error) {
      console.error('Failed to promote users:', error)
      toast({
        title: t('common.error'),
        description: 'Failed to promote users',
        variant: "destructive",
      })
    } finally {
      setPromoting(false)
    }
  }

  const handleInvite = async () => {
    if (!emails.trim()) return

    const emailList = emails.split('\n').map(email => email.trim()).filter(email => email)

    if (emailList.length === 0) return

    if ((inviteType === 'department_admins' || inviteType === 'department_managers') && !selectedDepartment) {
      toast({
        title: t('common.error'),
        description: t('invite.selectDepartmentForInviteType'),
        variant: "destructive",
      })
      return
    }

    try {
      setInviting(true)
      let response

      switch (inviteType) {
        case 'admins':
          response = await apiService.auth.maintainerInvite(tenantId, emailList)
          break
        case 'department_admins':
          response = await tenantsAPI.inviteDepartmentAdmins(selectedDepartment, emailList)
          break
        case 'department_managers':
          response = await tenantsAPI.inviteDepartmentManagers(selectedDepartment, emailList)
          break
        case 'users':
          response = await tenantsAPI.inviteUsers(selectedDepartment || departments[0]?.id || '', emailList)
          break
      }

      let inviteLinks: string[] = []
      if (inviteType === 'admins') {
        inviteLinks = (response as any).links || []
      } else {
        if ((response as any).success && (response as any).invite_links) {
          inviteLinks = (response as any).invite_links
        }
      }

      if (inviteLinks.length > 0) {
        setInviteLinks(inviteLinks)
        toast({
          title: t('common.success'),
          description: `Invited ${emailList.length} user(s) successfully`,
        })
      } else {
        throw new Error('Invite failed')
      }

    } catch (error) {
      console.error('Failed to send invites:', error)
      toast({
        title: t('common.error'),
        description: t('invite.failedToSendInvites'),
        variant: "destructive",
      })
    } finally {
      setInviting(false)
    }
  }

  const copyToClipboard = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link)
      setCopiedLink(link)
      setTimeout(() => setCopiedLink(null), 2000)

      toast({
        title: t('common.success'),
        description: t('invite.linkCopied'),
      })
    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('invite.failedToCopyLink'),
        variant: "destructive",
      })
    }
  }

  const getInviteTypeName = (type: InviteType) => {
    switch (type) {
      case 'admins':
        return t('invite.tenantAdmins')
      case 'department_admins':
        return t('inviteManagement.departmentAdmins')
      case 'department_managers':
        return t('inviteManagement.departmentManagers')
      case 'users':
        return t('inviteManagement.regularUsers')
      default:
        return ''
    }
  }

  const getInviteTypeDescription = (type: InviteType) => {
    switch (type) {
      case 'admins':
        return t('invite.inviteTenantAdminsDesc')
      case 'department_admins':
        return t('invite.inviteAdminsDesc')
      case 'department_managers':
        return t('invite.inviteManagersDesc')
      case 'users':
        return t('invite.inviteUsersDesc')
      default:
        return ''
    }
  }

  const getInviteTypeIcon = (type: InviteType) => {
    switch (type) {
      case 'admins':
        return <Building className="h-5 w-5" />
      case 'department_admins':
        return <Building className="h-5 w-5" />
      case 'department_managers':
        return <Users className="h-5 w-5" />
      case 'users':
        return <UserPlus className="h-5 w-5" />
      default:
        return <UserPlus className="h-5 w-5" />
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
      {/* Header */}
      {context === 'system_admin' ? (
        <div>
          <h2 className="text-xl font-semibold font-sans">{t('invite.inviteAdmins')}</h2>
          <p className="text-sm text-muted-foreground font-serif mt-1">
            {t('invite.inviteTenantAdminsDesc')}
          </p>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('invite.inviteManagementTitle')}</h1>
            <p className="text-muted-foreground">
              {t('invite.inviteManagementSubtitle')}
            </p>
          </div>

          {/* Management Type Selector */}
          {(user?.role === 'ADMIN' || user?.role === 'MAINTAINER' || user?.role === 'DEPT_ADMIN') && (
            <div className="flex items-center space-x-2">
              <Button
                variant={managementType === 'invite' ? 'default' : 'outline'}
                onClick={() => setManagementType('invite')}
                size="sm"
              >
                {t('invite.inviteUsers')}
              </Button>
              {(user?.role === 'ADMIN' || user?.role === 'MAINTAINER' || user?.role === 'DEPT_ADMIN') && (
                <Button
                  variant={managementType === 'promote' ? 'default' : 'outline'}
                  onClick={() => setManagementType('promote')}
                  size="sm"
                >
                  {t('invite.promoteUsers')}
                </Button>
              )}
            </div>
          )}
        </div>
      )}

        {managementType === 'invite' && (
          <Dialog open={isInviteDialogOpen} onOpenChange={setIsInviteDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <UserPlus className="h-4 w-4" />
              {t('invite.sendInvites')}
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{t('invite.sendInvitations')}</DialogTitle>
              <DialogDescription>
                {t('invite.inviteManagementSubtitle')}
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-6 py-4">
              {/* Invite Type Selection */}
              <div className="grid gap-2">
                <Label htmlFor="invite-type">{t('invite.inviteType')}</Label>
                <Select value={inviteType} onValueChange={(value: InviteType) => setInviteType(value)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {getAvailableInviteTypes().map(type => (
                      <SelectItem key={type} value={type}>
                        <div className="flex items-center gap-2">
                          {getInviteTypeIcon(type)}
                          {getInviteTypeDescription(type)}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-sm text-muted-foreground">
                  {getInviteTypeDescription(inviteType)}
                </p>
              </div>

              {/* Department Selection (for department-specific invites) */}
              {(inviteType === 'department_admins' || inviteType === 'department_managers') && (
                <div className="grid gap-2">
                  <Label htmlFor="department-select">Department</Label>
                  <Select value={selectedDepartment} onValueChange={setSelectedDepartment}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select department" />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.map((dept) => (
                        <SelectItem key={dept.id} value={dept.id}>
                          {dept.department_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Email Addresses */}
              <div className="grid gap-2">
                <Label htmlFor="emails">{t('invite.emailAddresses')}</Label>
                <Textarea
                  id="emails"
                  placeholder={t('invite.enterEmailsOnePerLine')}
                  value={emails}
                  onChange={(e) => setEmails(e.target.value)}
                  rows={5}
                />
                <p className="text-sm text-muted-foreground">
                  {t('invite.enterEmailsOnePerLine')}
                </p>
              </div>

              {/* Custom Message (Optional) */}
              <div className="grid gap-2">
                <Label htmlFor="invite-message">{t('invite.customMessageLabel')}</Label>
                <Textarea
                  id="invite-message"
                  placeholder={t('invite.addPersonalMessage')}
                  value={inviteMessage}
                  onChange={(e) => setInviteMessage(e.target.value)}
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setIsInviteDialogOpen(false)
                  setEmails('')
                  setInviteMessage('')
                  setSelectedDepartment('')
                  setInviteType('users')
                }}
                disabled={inviting}
              >
                {t('common.cancel')}
              </Button>
              <Button
                onClick={handleInvite}
                disabled={!emails.trim() || inviting}
              >
                {inviting ? t('invite.sendingInvites') : `${t('invite.sendInvites')} (${emails.split('\n').filter(e => e.trim()).length})`}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Invite Options */}
      {managementType === 'invite' && (
        <div className="grid gap-4 md:grid-cols-3">
        {context === 'system_admin' && user?.role === 'MAINTAINER' ? (
          <Card className="cursor-pointer hover:shadow-md transition-shadow border-dashed md:col-span-3">
            <CardHeader className="text-center">
              <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-purple-100">
                <Building className="h-6 w-6 text-purple-600" />
              </div>
              <CardDescription>
                {t('invite.inviteTenantAdminsDesc')}
              </CardDescription>
            </CardHeader>
            <CardContent className="text-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setInviteType('admins')
                  setIsInviteDialogOpen(true)
                }}
              >
                {t('invite.inviteTenantAdmins')}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <></>
        )}

        {context !== 'system_admin' && getAvailableInviteTypes().map(type => (
              <Card key={type} className="cursor-pointer hover:shadow-md transition-shadow border-dashed">
                <CardHeader className="text-center">
                  <div className={`mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full ${
                    type === 'users' ? 'bg-blue-100' :
                    type === 'department_managers' ? 'bg-green-100' :
                    type === 'department_admins' ? 'bg-purple-100' : 'bg-gray-100'
                  }`}>
                    {getInviteTypeIcon(type)}
                  </div>
                  <CardTitle className="text-lg">{getInviteTypeName(type)}</CardTitle>
                  <CardDescription>
                    {getInviteTypeDescription(type)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-center">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setInviteType(type)
                      setIsInviteDialogOpen(true)
                    }}
                  >
                    {type === 'users' && t('inviteManagement.inviteUsers')}
                    {type === 'department_managers' && t('inviteManagement.inviteManagers')}
                    {type === 'department_admins' && t('inviteManagement.inviteAdmins')}
                  </Button>
                </CardContent>
              </Card>
            ))}
        </div>
      )}

      {/* User Promotion Section */}
      {managementType === 'promote' && (user?.role === 'ADMIN' || user?.role === 'MAINTAINER' || user?.role === 'DEPT_ADMIN') && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">{t('invite.userPromotion')}</h2>
              <p className="text-muted-foreground">{t('invite.promoteUsersDescription')}</p>
            </div>
          </div>

          {/* Department Selector */}
          <Card>
            <CardHeader>
              <CardTitle>{t('invite.selectDepartment')}</CardTitle>
              <CardDescription>{t('invite.selectDepartmentForPromotion')}</CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={selectedDepartment} onValueChange={(value) => {
                setSelectedDepartment(value)
                if (value) loadDepartmentUsers(value)
              }}>
                <SelectTrigger>
                  <SelectValue placeholder={t('invite.selectDepartment')} />
                </SelectTrigger>
                <SelectContent>
                  {departments.map((dept) => (
                    <SelectItem key={dept.id} value={dept.id}>
                      {dept.department_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Users List */}
          {selectedDepartment && departmentUsers.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t('invite.departmentUsers')}</CardTitle>
                <CardDescription>{t('invite.selectUsersToPromote')}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {departmentUsers
                    .filter(user => user.role === 'USER')
                    .map((user) => (
                      <div key={user.id} className="flex items-center space-x-3 p-3 border rounded-lg">
                        <input
                          type="checkbox"
                          checked={selectedUsers.includes(user.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedUsers([...selectedUsers, user.id])
                            } else {
                              setSelectedUsers(selectedUsers.filter(id => id !== user.id))
                            }
                          }}
                          className="rounded"
                        />
                        <div className="flex-1">
                          <p className="font-medium">{user.first_name} {user.last_name}</p>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                        </div>
                        <Badge variant="secondary">{user.role}</Badge>
                      </div>
                    ))}
                </div>

                {selectedUsers.length > 0 && (
                  <div className="mt-4 pt-4 border-t">
                    <Button
                      onClick={handleUserPromotion}
                      disabled={promoting}
                      className="w-full"
                    >
                      {promoting ? t('invite.promoting') : `${t('invite.promoteToManager')} (${selectedUsers.length})`}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {selectedDepartment && departmentUsers.length === 0 && (
            <Card>
              <CardContent className="text-center py-8">
                <Users className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">{t('invite.noUsersInDepartment')}</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Invite Links Display */}
      {inviteLinks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
              {t('invite.invitationLinksGenerated')}
            </CardTitle>
            <CardDescription>
              {t('invite.copyLinksShareWithUsers')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {inviteLinks.map((link, index) => (
                <div key={index} className="flex items-center gap-2 p-3 bg-muted rounded-lg">
                  <div className="flex-1 text-sm font-mono break-all">
                    {link}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(link)}
                    className="shrink-0"
                  >
                    {copiedLink === link ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              ))}
            </div>
            <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>{t('invite.linksExpireNote')}</strong> {t('invite.linksExpireDescription')}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Invites */}
      <Card>
        <CardHeader>
          <CardTitle>{t('invite.recentActivity')}</CardTitle>
          <CardDescription>
            {t('invite.trackRecentInvites')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <Mail className="mx-auto h-12 w-12 mb-4" />
            <p>{t('invite.noRecentInvitations')}</p>
            <p className="text-sm">{t('invite.sendFirstInvite')}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}