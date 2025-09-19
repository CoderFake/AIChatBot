"use client"

import { useTranslation } from "react-i18next"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Globe } from "lucide-react"

const languages = [
  { code: "en", name: "English", flag: "🇺🇸" },
  { code: "vi", name: "Tiếng Việt", flag: "🇻🇳" },
  { code: "kr", name: "한국어", flag: "🇰🇷" },
  { code: "ja", name: "日本語", flag: "🇯🇵" },
]

export function LanguageSelector() {
  const { i18n } = useTranslation()

  return (
    <Select value={i18n.language} onValueChange={(value) => i18n.changeLanguage(value)}>
      <SelectTrigger className="w-[180px]">
        <Globe className="h-4 w-4 mr-2" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {languages.map((lang) => (
          <SelectItem key={lang.code} value={lang.code}>
            <span className="mr-2">{lang.flag}</span>
            {lang.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
