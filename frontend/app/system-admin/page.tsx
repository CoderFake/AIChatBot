"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function SystemAdminPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace("/system-admin/dashboard")
  }, [router])

  return null
}
