"use client"

import { useAuth } from "@/lib/auth-context"
import { useTenant } from "@/lib/tenant-context"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Bell, Settings, User, LogOut } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslation } from "react-i18next"

export function TenantAdminHeader() {
  const { user, logout } = useAuth()
  const { tenant, tenantId } = useTenant()
  const router = useRouter()
  const { t } = useTranslation()

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }

  const userInitials =
    user?.first_name && user?.last_name
      ? `${user.first_name[0]}${user.last_name[0]}`
      : user?.username?.[0]?.toUpperCase() || "A"

  return (
    <header className="h-16 bg-background border-b border-border flex items-center justify-between px-6">
      <div className="flex items-center space-x-4">
        <h1 className="text-xl font-semibold font-sans">{tenant?.tenant_name || tenantId} {t("admin.administration")}</h1>
      </div>

      <div className="flex items-center space-x-4">
        {/* Notifications */}
        <Button variant="ghost" size="sm">
          <Bell className="w-4 h-4" />
        </Button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-8 w-8 rounded-full">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="text-xs font-sans">{userInitials}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end">
            <DropdownMenuLabel className="font-sans">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium">
                  {user?.first_name && user?.last_name ? `${user.first_name} ${user.last_name}` : user?.username}
                </p>
                <p className="text-xs text-muted-foreground font-serif">{user?.email}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="font-serif">
              <User className="w-4 h-4 mr-2" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem className="font-serif">
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="font-serif">
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
