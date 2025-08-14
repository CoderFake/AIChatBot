import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AIChatBot Admin',
  description: 'Multi-tenant AIChatBot',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}


