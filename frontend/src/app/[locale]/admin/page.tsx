import {useTranslations} from 'next-intl'

export default function AdminHome() {
  const t = useTranslations()
  return (
    <div>
      <h2>{t('nav.home')}</h2>
      <p>Use the sidebar to manage tenants, tools, and settings.</p>
    </div>
  )
}


