'use client'
import React, {createContext, useCallback, useContext, useMemo, useState} from 'react'

type ToastType = 'success' | 'error' | 'info' | 'warn'

export type ToastItem = { id: string; message: string; type: ToastType }

type ToastContextValue = {
  show: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export function ToastProvider({children}: {children: React.ReactNode}) {
  const [items, setItems] = useState<ToastItem[]>([])

  const remove = useCallback((id: string) => {
    setItems(prev => prev.filter(t => t.id !== id))
  }, [])

  const show = useCallback((message: string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setItems(prev => [...prev, {id, message, type}])
    setTimeout(() => remove(id), 3500)
  }, [remove])

  const value = useMemo(() => ({show}), [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-container">
        {items.map(t => (
          <div key={t.id} className={`toast ${t.type}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}


