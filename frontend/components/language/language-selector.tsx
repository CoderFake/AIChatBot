"use client"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Globe } from "lucide-react"
import { useLanguage } from "./language-provider"
import { languageApi } from "@/lib/api/language"
import { useAuth } from "@/lib/auth-context"
import { useToast } from "@/lib/use-toast"

export function LanguageSelector() {
  const { t } = useTranslation()
  const { currentLanguage, changeLanguage } = useLanguage()
  const { user } = useAuth()
  const { showSuccess } = useToast()

  if (user?.role !== "MAINTAINER") {
    return null
  }

  const languages = languageApi.getSystemLanguages()
  const currentLang = languages.find((lang) => lang.code === currentLanguage)

  const handleLanguageChange = async (languageCode: string) => {
    const selectedLang = languages.find((lang) => lang.code === languageCode)
    if (selectedLang) {
      await changeLanguage(languageCode)
      showSuccess(t("notifications.languageChanged", { language: selectedLang.nativeName }))
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2">
          <Globe className="h-4 w-4" />
          <span className="hidden sm:inline">
            {currentLang?.flag} {currentLang?.nativeName || t("language.select")}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {languages.map((language) => (
          <DropdownMenuItem
            key={language.code}
            onClick={() => handleLanguageChange(language.code)}
            className={`flex items-center gap-3 ${currentLanguage === language.code ? "bg-accent" : ""}`}
          >
            <span className="text-lg">{language.flag}</span>
            <div className="flex flex-col">
              <span className="font-medium">{language.name}</span>
              <span className="text-xs text-muted-foreground">{language.nativeName}</span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
