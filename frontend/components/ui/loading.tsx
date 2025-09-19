import React from "react"
import { cn } from "@/lib/utils"

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg"
  className?: string
}

export function LoadingSpinner({ size = "md", className }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "w-4 h-4 border-2",
    md: "w-8 h-8 border-4", 
    lg: "w-12 h-12 border-4"
  }

  return (
    <div
      className={cn(
        "border-primary border-t-transparent rounded-full animate-spin",
        sizeClasses[size],
        className
      )}
      role="status"
      aria-label="Loading"
    />
  )
}

interface LoadingPageProps {
  title?: string
  subtitle?: string
  showSpinner?: boolean
  className?: string
}

export function LoadingPage({
  title = "Đang tải...",
  subtitle = "Vui lòng chờ trong giây lát",
  showSpinner = true,
  className
}: LoadingPageProps) {
  return (
    <div className={cn("min-h-screen bg-background flex items-center justify-center", className)}>
      <div className="text-center space-y-4">
        {showSpinner && <LoadingSpinner size="lg" className="mx-auto" />}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>
    </div>
  )
}

interface LoadingOverlayProps {
  visible: boolean
  title?: string
  subtitle?: string
  className?: string
  backdropClassName?: string
}

export function LoadingOverlay({
  visible,
  title = "Đang xử lý...",
  subtitle,
  className,
  backdropClassName
}: LoadingOverlayProps) {
  if (!visible) return null

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center",
        backdropClassName
      )}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      
      {/* Content */}
      <div className={cn(
        "relative bg-background rounded-lg shadow-lg p-6 mx-4 min-w-[200px]",
        className
      )}>
        <div className="text-center space-y-4">
          <LoadingSpinner size="lg" className="mx-auto" />
          <div className="space-y-2">
            <h3 className="font-semibold text-foreground">{title}</h3>
            {subtitle && (
              <p className="text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

interface LoadingCardProps {
  title?: string
  subtitle?: string
  className?: string
}

export function LoadingCard({
  title = "Đang tải dữ liệu...",
  subtitle,
  className
}: LoadingCardProps) {
  return (
    <div className={cn(
      "border rounded-lg p-8 bg-card text-card-foreground",
      className
    )}>
      <div className="text-center space-y-4">
        <LoadingSpinner size="lg" className="mx-auto" />
        <div className="space-y-2">
          <h3 className="font-semibold">{title}</h3>
          {subtitle && (
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>
    </div>
  )
}

interface LoadingButtonProps {
  loading: boolean
  children: React.ReactNode
  className?: string
  disabled?: boolean
  [key: string]: any
}

export function LoadingButton({
  loading,
  children,
  className,
  disabled,
  ...props
}: LoadingButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      disabled={loading || disabled}
      {...props}
    >
      {loading && <LoadingSpinner size="sm" />}
      {children}
    </button>
  )
}

// Skeleton loaders
interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-muted",
        className
      )}
    />
  )
}

export function SkeletonText({ lines = 3, className }: { lines?: number, className?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            "h-4",
            i === lines - 1 ? "w-3/4" : "w-full"
          )}
        />
      ))}
    </div>
  )
}

export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div className={cn("border rounded-lg p-6 space-y-4", className)}>
      <div className="space-y-2">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-3/5" />
      </div>
      <div className="flex space-x-2">
        <Skeleton className="h-8 w-20" />
        <Skeleton className="h-8 w-20" />
      </div>
    </div>
  )
}

export function SkeletonTable({ 
  rows = 5, 
  columns = 4,
  className 
}: { 
  rows?: number
  columns?: number
  className?: string 
}) {
  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex space-x-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-6 flex-1" />
        ))}
      </div>
      
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex space-x-4">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={colIndex}
              className={cn(
                "h-4 flex-1",
                colIndex === 0 && "w-2/5",
                colIndex === columns - 1 && "w-1/5"
              )}
            />
          ))}
        </div>
      ))}
    </div>
  )
}