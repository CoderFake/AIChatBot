"use client"

import React from "react"
import "./i18n"

interface I18nProviderProps {
  children: React.ReactNode
}

export const I18nProvider: React.FC<I18nProviderProps> = ({ children }) => {
  return <>{children}</>
}
