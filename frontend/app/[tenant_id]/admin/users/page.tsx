"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Search, MoreHorizontal, Eye, Edit, UserPlus, Users } from "lucide-react"
import { useTenant } from "@/lib/tenant-context"
import { apiService } from "@/lib/api/index"
import { normalizePaginatedResponse } from "@/lib/utils"
import type { User, PaginatedResponse } from "@/types"
import { useTranslation } from "react-i18next"

export default function UsersPage() {
  const router = useRouter()
  const { tenantId } = useTenant()
  const [users, setUsers] = useState<PaginatedResponse<User>>({
    data: [],
    total: 0,
    page: 1,
    limit: 10,
    total_pages: 0,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [currentPage, setCurrentPage] = useState(1)
  const { t } = useTranslation()

  useEffect(() => {
    if (tenantId) {
      loadUsers()
    }
  }, [tenantId, currentPage, searchQuery])

  const loadUsers = async () => {
    if (!tenantId) return

    setIsLoading(true)
    try {
      const response = await apiService.users.list({
        tenant_id: tenantId,
        page: currentPage,
        limit: 10,
        search: searchQuery || undefined,
        sort_by: "created_at",
        sort_order: "desc",
      })
      setUsers({
        data: response.users,
        total: response.total,
        page: response.page,
        limit: response.limit,
        has_more: response.has_more
      })
    } catch (error) {
      console.error("Failed to load users:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = (query: string) => {
    setSearchQuery(query)
    setCurrentPage(1)
  }

  const handleInviteUsers = () => {
    router.push(`/${tenantId}/admin/users/invite`)
  }

  const handleViewUser = (userId: string) => {
    router.push(`/${tenantId}/admin/users/${userId}`)
  }

  const handleEditUser = (userId: string) => {
    router.push(`/${tenantId}/admin/users/${userId}/edit`)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  }

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case "ADMIN":
        return "default"
      case "DEPT_ADMIN":
        return "secondary"
      case "DEPT_MANAGER":
        return "outline"
      default:
        return "outline"
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold font-sans">Users</h1>
          <p className="text-muted-foreground font-serif">Manage organization users</p>
        </div>
        <Button onClick={handleInviteUsers} className="font-sans">
          <UserPlus className="w-4 h-4 mr-2" />
          Invite Users
        </Button>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="font-sans">Search & Filter</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search users by name or email..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="pl-10 font-serif"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="font-sans">{t("admin.users.title")} ({users.total})</CardTitle>
          <CardDescription className="font-serif">
            {users.total === 0 ? t("admin.users.noUsersFound") : t("admin.users.showingUsers", {
              current: normalizePaginatedResponse(users).length,
              total: users.total
            })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-12 bg-muted rounded"></div>
                </div>
              ))}
            </div>
          ) : normalizePaginatedResponse(users).length === 0 ? (
            <div className="text-center py-12">
              <Users className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold font-sans mb-2">{t("admin.users.noUsersFound")}</h3>
              <p className="text-muted-foreground font-serif mb-4">
                {searchQuery ? t("admin.users.tryAdjustingSearchCriteria") : t("admin.users.getStartedByInvitingFirstUsers")}
              </p>
              <Button onClick={handleInviteUsers} className="font-sans">
                <UserPlus className="w-4 h-4 mr-2" />
                {t("admin.users.inviteUsers")}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-sans">User</TableHead>
                    <TableHead className="font-sans">Email</TableHead>
                    <TableHead className="font-sans">Role</TableHead>
                    <TableHead className="font-sans">Status</TableHead>
                    <TableHead className="font-sans">Created</TableHead>
                    <TableHead className="w-[70px] font-sans">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {normalizePaginatedResponse<User>(users).map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-secondary/10 rounded-full flex items-center justify-center">
                            <span className="text-sm font-medium font-sans">
                              {user.first_name?.[0] || user.username[0].toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium font-sans">
                              {user.first_name && user.last_name
                                ? `${user.first_name} ${user.last_name}`
                                : user.username}
                            </p>
                            <p className="text-sm text-muted-foreground font-serif">@{user.username}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-serif">{user.email}</TableCell>
                      <TableCell>
                        <Badge variant={getRoleBadgeVariant(user.role)}>{user.role}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={user.is_active ? "default" : "secondary"}>
                          {user.is_active ? t("admin.users.active") : t("admin.users.inactive")}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-serif">{formatDate(user.created_at)}</TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleViewUser(user.id)} className="font-serif">
                              <Eye className="w-4 h-4 mr-2" />
                              View Details
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleEditUser(user.id)} className="font-serif">
                              <Edit className="w-4 h-4 mr-2" />
                              Edit Permissions
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {(users.total_pages || 0) > 1 && (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground font-serif">
                    Page {users.page} of {users.total_pages || 0}
                  </p>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                      className="font-sans"
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage === (users.total_pages || 0)}
                      className="font-sans"
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
