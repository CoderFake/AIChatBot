"use client"

import React, { useState, useEffect } from "react"
import { X, CheckCircle, XCircle, AlertCircle, Info } from "lucide-react"
import { cn } from "@/lib/utils"

export interface ToastNotificationProps {
  id: string
  title?: string
  message: string
  type: "success" | "error" | "warning" | "info"
  duration?: number
  onClose: (id: string) => void
}

export function ToastNotification({
  id,
  title,
  message,
  type,
  duration = 5000,
  onClose
}: ToastNotificationProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [isLeaving, setIsLeaving] = useState(false)

  useEffect(() => {
    setTimeout(() => setIsVisible(true), 10)

    if (duration > 0) {
      const timer = setTimeout(() => {
        handleClose()
      }, duration)

      return () => clearTimeout(timer)
    }
  }, [duration])

  const handleClose = () => {
    setIsLeaving(true)
    setTimeout(() => onClose(id), 300)
  }

  const getToastStyles = () => {
    const baseStyles = "border-l-4 rounded-r-lg shadow-lg mb-4 transform transition-all duration-300 ease-in-out"

    switch (type) {
      case "success":
        return cn(baseStyles, "bg-green-50 border-green-500 text-green-800")
      case "error":
        return cn(baseStyles, "bg-red-50 border-red-500 text-red-800")
      case "warning":
        return cn(baseStyles, "bg-yellow-50 border-yellow-500 text-yellow-800")
      case "info":
        return cn(baseStyles, "bg-blue-50 border-blue-500 text-blue-800")
      default:
        return cn(baseStyles, "bg-gray-50 border-gray-500 text-gray-800")
    }
  }

  const getIcon = () => {
    const iconClass = "w-5 h-5 flex-shrink-0"

    switch (type) {
      case "success":
        return <CheckCircle className={cn(iconClass, "text-green-500")} />
      case "error":
        return <XCircle className={cn(iconClass, "text-red-500")} />
      case "warning":
        return <AlertCircle className={cn(iconClass, "text-yellow-500")} />
      case "info":
        return <Info className={cn(iconClass, "text-blue-500")} />
      default:
        return <Info className={cn(iconClass, "text-gray-500")} />
    }
  }

  return (
    <div
      className={cn(
        getToastStyles(),
        "max-w-md w-full p-4 flex items-start space-x-3",
        isVisible && !isLeaving ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"
      )}
    >
      <div className="flex-shrink-0">
        {getIcon()}
      </div>

      <div className="flex-1 min-w-0">
        {title && (
          <h4 className="text-sm font-semibold mb-1">
            {title}
          </h4>
        )}
        <p className="text-sm leading-relaxed">
          {message}
        </p>
      </div>

      <button
        onClick={handleClose}
        className="flex-shrink-0 ml-4 p-1 rounded hover:bg-black/10 transition-colors duration-200"
        aria-label="Close toast"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

export interface ToastNotificationContainerProps {
  toasts: Array<{
    id: string
    title?: string
    message: string
    type: "success" | "error" | "warning" | "info"
    duration?: number
  }>
  onRemove: (id: string) => void
}

export function ToastNotificationContainer({ toasts, onRemove }: ToastNotificationContainerProps) {
  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-md">
      {toasts.map((toast) => (
        <ToastNotification
          key={toast.id}
          id={toast.id}
          title={toast.title}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={onRemove}
        />
      ))}
    </div>
  )
}
