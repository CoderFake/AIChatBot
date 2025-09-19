"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useTenant } from "@/lib/tenant-context"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Building2, ChevronDown, Plus } from "lucide-react"
import { useTenantSettings } from "@/lib/tenant-context"

export function TenantSwitcher() {
  const { tenant, tenantId } = useTenant()
  const { user } = useAuth()
  const { getLogoUrl } = useTenantSettings()
  const router = useRouter()
  const [isOpen, setIsOpen] = useState(false)

  const logoUrl = getLogoUrl()

  if (!user || !tenantId) {
    return null
  }


  const handleCreateTenant = () => {
    router.push("/system-admin/tenants/create")
    setIsOpen(false)
  }

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="w-full justify-between font-serif bg-transparent">
          <div className="flex items-center">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Logo"
                className="w-4 h-4 mr-2 rounded object-cover"
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.style.display = "none"
                  target.parentElement!.innerHTML = `
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                    </svg>
                  `
                }}
              />
            ) : (
              <Building2 className="w-4 h-4 mr-2" />
            )}
            <span className="truncate">{tenant?.tenant_name || tenantId}</span>
          </div>
          <ChevronDown className="w-4 h-4 ml-2 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="start">
        <DropdownMenuLabel className="font-sans">Switch Workspace</DropdownMenuLabel>
        <DropdownMenuSeparator />

        {/* Current tenant */}
        <DropdownMenuItem disabled className="font-serif">
          <Building2 className="w-4 h-4 mr-2" />
          {tenant?.tenant_name || tenantId} (Current)
        </DropdownMenuItem>

        {/* Note: No other workspaces shown - no public API available per requirements */}
        <DropdownMenuItem disabled className="font-serif text-muted-foreground">
          No other workspaces available
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Create new tenant (for maintainers) */}
        {user.role === "MAINTAINER" && (
          <DropdownMenuItem onClick={handleCreateTenant} className="font-serif">
            <Plus className="w-4 h-4 mr-2" />
            Create New Workspace
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
