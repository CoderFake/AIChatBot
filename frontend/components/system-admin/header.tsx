"use client"

import { useAuth } from "@/lib/auth-context"
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
import { LanguageSelector } from "@/components/language/language-selector"

export function SystemAdminHeader() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const { t } = useTranslation()

  const userInitials =
    user?.first_name && user?.last_name
      ? `${user.first_name[0]}${user.last_name[0]}`
      : user?.username?.[0]?.toUpperCase() || "SA"

  const handleLogout = () => {
    logout()
    router.push("/system-admin/login")
  }

  return (
    <header className="h-16 bg-background border-b border-border flex items-center justify-between px-6">
      <div className="flex items-center space-x-4">
        <h1 className="text-xl font-semibold font-sans">{t("admin.systemAdministration")}</h1>
      </div>

      <div className="flex items-center space-x-4">
        <LanguageSelector />

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
              {t("common.profile")}
            </DropdownMenuItem>
            <DropdownMenuItem className="font-serif">
              <Settings className="w-4 h-4 mr-2" />
              {t("common.settings")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="font-serif">
              <LogOut className="w-4 h-4 mr-2" />
              {t("admin.signOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
