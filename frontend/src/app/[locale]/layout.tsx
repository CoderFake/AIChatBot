import '../globals.css'
import type { Metadata } from 'next'
import {NextIntlClientProvider} from 'next-intl'
import {notFound} from 'next/navigation'

export const metadata: Metadata = {
  title: 'AIChatBot Admin',
  description: 'Multi-tenant AIChatBot'
}

export default async function LocaleLayout({children, params: {locale}}: {children: React.ReactNode; params: {locale: string}}) {
  let messages
  try {
    messages = (await import(`../../i18n/messages/${locale}.json`)).default
  } catch (error) {
    notFound()
  }
  return (
    <html lang={locale}>
      <body>
        <div id="toast-root" className="toast-container" />
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  )
}


