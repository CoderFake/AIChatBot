"use client"

import { useState, useCallback } from "react"
import { useTranslation } from "react-i18next"

export interface ToastNotification {
  id: string
  title?: string
  message: string
  type: "success" | "error" | "warning" | "info"
  duration?: number
}

export function useToastNotification() {
  const { t } = useTranslation()
  const [toasts, setToasts] = useState<ToastNotification[]>([])

  const addToast = useCallback((toast: Omit<ToastNotification, "id">) => {
    const id = Date.now().toString() + Math.random().toString(36).substr(2, 9)
    const newToast: ToastNotification = {
      id,
      duration: 5000,
      ...toast
    }

    setToasts(prev => [newToast, ...prev])

    return id
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id))
  }, [])

  const showSuccess = useCallback((message: string, title?: string) => {
    return addToast({
      title: title || t("notifications.success"),
      message,
      type: "success"
    })
  }, [addToast, t])

  const showError = useCallback((message: string, title?: string) => {
    return addToast({
      title: title || t("notifications.error"),
      message,
      type: "error"
    })
  }, [addToast, t])

  const showWarning = useCallback((message: string, title?: string) => {
    return addToast({
      title: title || t("notifications.warning"),
      message,
      type: "warning"
    })
  }, [addToast, t])

  const showInfo = useCallback((message: string, title?: string) => {
    return addToast({
      title: title || t("notifications.info"),
      message,
      type: "info"
    })
  }, [addToast, t])

  const toast = useCallback((config: Omit<ToastNotification, "id">) => {
    return addToast(config)
  }, [addToast])

  return {
    toasts,
    toast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    removeToast
  }
}
