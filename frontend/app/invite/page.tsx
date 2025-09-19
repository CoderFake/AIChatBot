"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function InviteRedirectPage() {
  const router = useRouter()

  useEffect(() => {
    const handleInviteRedirect = async () => {
      try {
        const hash = window.location.hash
        const tokenMatch = hash.match(/#token=([^&]+)/)
        const token = tokenMatch ? tokenMatch[1] : null

        if (!token) {
          console.error("No token found in URL")
          router.push("/")
          return
        }
        const { apiService } = await import("@/lib/api/index")

        const tokenInfo = await apiService.auth.validateInviteToken(token)

        if (!tokenInfo || !tokenInfo.tenant_id) {
          console.error("Invalid token or missing tenant info")
          router.push("/")
          return
        }

        router.push(`/${tokenInfo.tenant_id}/invite?token=${token}`)

      } catch (error) {
        console.error("Failed to process invite redirect:", error)
        router.push("/")
      }
    }

    handleInviteRedirect()
  }, [router])

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="text-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900 mx-auto mb-4"></div>
        <p className="text-muted-foreground">Processing your invitation...</p>
      </div>
    </div>
  )
}
