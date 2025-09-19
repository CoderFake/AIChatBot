"use client"

import React from "react"
import { useToastNotification } from "@/hooks/use-toast-notification"
import { ToastNotificationContainer } from "@/components/ui/toast-notification"

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const { toasts, removeToast } = useToastNotification()

  return (
    <>
      {children}
      <ToastNotificationContainer
        toasts={toasts}
        onRemove={removeToast}
      />
    </>
  )
}
