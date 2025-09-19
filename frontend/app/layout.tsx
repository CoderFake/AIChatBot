import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { AuthProvider } from "@/lib/auth-context"
import { LanguageProvider } from "@/components/language/language-provider"
import { ThemeProvider } from "@/components/theme-provider"
import { ToastProvider } from "@/components/ui/toast-provider"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "RAG AI System",
  description: "Enterprise AI Chat System with Multi-tenant Architecture",
  keywords: ["AI", "Chat", "Enterprise", "Multi-tenant", "RAG"],
  authors: [{ name: "RAG AI Team" }],
}

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
}

interface RootLayoutProps {
  children: React.ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          <LanguageProvider>
            <AuthProvider>
              <ToastProvider>
                <main className="min-h-screen bg-background">
                  {children}
                </main>
              </ToastProvider>
            </AuthProvider>
          </LanguageProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}