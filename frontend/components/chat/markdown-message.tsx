"use client"

import React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import { FileText } from "lucide-react"

interface MarkdownMessageProps {
  content: string
  className?: string
  onDocumentClick?: (documentId: string, url: string, title?: string) => void
}

export function MarkdownMessage({ content, className = "", onDocumentClick }: MarkdownMessageProps) {
  const processContent = (text: string) => {
    const parts: React.ReactNode[] = []
    let lastIndex = 0

    const documentLinkRegex = /\[([^\]]+)\]$$document:\/\/([^)]+)$$/g
    let match

    while ((match = documentLinkRegex.exec(text)) !== null) {
      const [fullMatch, linkText, documentId] = match
      const startIndex = match.index

      if (startIndex > lastIndex) {
        parts.push(text.slice(lastIndex, startIndex))
      }

      parts.push(
        <Button
          key={`doc-${documentId}-${startIndex}`}
          variant="outline"
          size="sm"
          className="inline-flex items-center gap-1 h-auto py-1 px-2 text-xs bg-transparent hover:bg-muted mx-1"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()

            if (onDocumentClick) {
              onDocumentClick(documentId, `/api/documents/${documentId}`, linkText)
            }
          }}
          type="button"
        >
          <FileText className="h-3 w-3" />
          {linkText}
        </Button>,
      )

      lastIndex = startIndex + fullMatch.length
    }

    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }

    return parts.length > 1 ? parts : text
  }

  const hasDocumentLinks = /\[([^\]]+)\]$$document:\/\/([^)]+)$$/.test(content)

  if (hasDocumentLinks) {
    const processedContent = processContent(content)

    return (
      <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
        {Array.isArray(processedContent) ? (
          <div>
            {processedContent.map((part, index) => (
              <React.Fragment key={index}>
                {typeof part === "string" ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{part}</ReactMarkdown> : part}
              </React.Fragment>
            ))}
          </div>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{processedContent as string}</ReactMarkdown>
        )}
      </div>
    )
  }

  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: ({ node, className, children, ...props }: any) => {
            const inline = (props as any).inline
            if (inline) {
              return (
                <code className="bg-muted px-1 py-0.5 rounded text-sm font-mono" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <pre className="bg-muted p-3 rounded-lg overflow-x-auto">
                <code className="text-sm font-mono" {...props}>
                  {children}
                </code>
              </pre>
            )
          },
          a: ({ href, children }) => {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                {children}
              </a>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
