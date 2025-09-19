"use client"

import type React from "react"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { X, ExternalLink, FileText, Download } from "lucide-react"
import { MarkdownMessage } from "./markdown-message"
import { api } from "@/lib/api/index"

interface DocumentPreviewProps {
  documentId: string
  url: string
  isOpen: boolean
  onClose: () => void
}

export function DocumentPreview({ documentId, url, isOpen, onClose }: DocumentPreviewProps) {
  const [document, setDocument] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [width, setWidth] = useState(595) // A4 width in pixels
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen && documentId) {
      fetchDocument()
    }
  }, [isOpen, documentId])

  const fetchDocument = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const documentData = await api.documents.getDocument(documentId)
      setDocument(documentData)
    } catch (error) {
      console.error("Error fetching document:", error)
      setError("Failed to load document. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsResizing(true)
    e.preventDefault()
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return

      const newWidth = window.innerWidth - e.clientX
      const minWidth = 400 // Minimum readable width
      const maxWidth = Math.min(window.innerWidth * 0.9, 1200) // Max 90% of screen or 1200px

      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      setIsResizing(false)
    }

    if (isResizing) {
      globalThis.document?.addEventListener("mousemove", handleMouseMove)
      globalThis.document?.addEventListener("mouseup", handleMouseUp)
    }

    return () => {
      if (typeof globalThis !== "undefined" && globalThis.document) {
        globalThis.document.removeEventListener("mousemove", handleMouseMove)
        globalThis.document.removeEventListener("mouseup", handleMouseUp)
      }
    }
  }, [isResizing])

  return (
    <div
      className={`fixed top-0 right-0 h-full bg-background border-l border-border shadow-2xl transform transition-transform duration-300 ease-in-out z-50 ${
        isOpen ? "translate-x-0" : "translate-x-full"
      }`}
      style={{ width: `${width}px` }}
    >
      <div
        ref={resizeRef}
        className="absolute left-0 top-0 w-2 h-full cursor-col-resize hover:bg-primary/10 transition-colors group flex items-center justify-center"
        onMouseDown={handleMouseDown}
      >
        <div className="w-1 h-8 bg-border group-hover:bg-primary/30 rounded-full transition-colors" />
      </div>

      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="p-4 border-b border-border bg-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              <div>
                <h3 className="font-semibold text-sm">{document?.title || "Document Preview"}</h3>
                {document?.type && <p className="text-xs text-muted-foreground uppercase">{document.type}</p>}
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" onClick={() => window.open(url, "_blank")} className="h-8 w-8">
                <ExternalLink className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Download className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1">
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
              </div>
            </div>
          ) : error ? (
            <div className="p-4 text-center">
              <p className="text-destructive text-sm">{error}</p>
              <Button variant="outline" size="sm" onClick={fetchDocument} className="mt-2 bg-transparent">
                Retry
              </Button>
            </div>
          ) : document ? (
            <div className="p-4">
              <MarkdownMessage content={document.content} onDocumentClick={() => {}} />

              {/* Document metadata */}
              <div className="mt-6 pt-4 border-t border-border">
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>
                    <strong>Created:</strong> {new Date(document.createdAt).toLocaleDateString()}
                  </p>
                  <p>
                    <strong>Updated:</strong> {new Date(document.updatedAt).toLocaleDateString()}
                  </p>
                  <p>
                    <strong>Type:</strong> {document.type.toUpperCase()}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </ScrollArea>
      </div>
    </div>
  )
}
