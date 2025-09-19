import { apiService } from "@/lib/api/index"

export interface TenantLanguageResponse {
  language: string
  timezone: string
  dateFormat: string
  numberFormat: string
}

export interface SystemLanguageOption {
  code: string
  name: string
  nativeName: string
  flag: string
}

// Extract language code from locale (e.g., 'vi_VN' -> 'vi', 'ja_JP' -> 'ja')
export const extractLanguageCode = (locale: string): string => {
  return locale.split('_')[0]?.toLowerCase() || 'en'
}

// Language settings configuration based on language codes
const getLanguageSettings = (locale: string): TenantLanguageResponse => {
  const languageCode = extractLanguageCode(locale)

  const languageConfigs: Record<string, Omit<TenantLanguageResponse, 'language'>> = {
    'vi': {
      timezone: 'Asia/Ho_Chi_Minh',
      dateFormat: 'DD/MM/YYYY',
      numberFormat: 'vi-VN',
    },
    'ja': {
      timezone: 'Asia/Tokyo',
      dateFormat: 'YYYY/MM/DD',
      numberFormat: 'ja-JP',
    },
    'kr': {
      timezone: 'Asia/Seoul',
      dateFormat: 'YYYY-MM-DD',
      numberFormat: 'ko-KR',
    },
    'en': {
      timezone: 'UTC',
      dateFormat: 'MM/DD/YYYY',
      numberFormat: 'en-US',
    },
  }

  const config = languageConfigs[languageCode] || languageConfigs['en']

  return {
    language: languageCode,
    ...config,
  }
}

const systemLanguages: SystemLanguageOption[] = [
  { code: "en", name: "English", nativeName: "English", flag: "🇺🇸" },
  { code: "vi", name: "Vietnamese", nativeName: "Tiếng Việt", flag: "🇻🇳" },
  { code: "kr", name: "Korean", nativeName: "한국어", flag: "🇰🇷" },
  { code: "ja", name: "Japanese", nativeName: "日本語", flag: "🇯🇵" },
]

export const languageApi = {
  getTenantLanguage: async (tenantId: string): Promise<TenantLanguageResponse> => {
    try {
      const tenantInfo = await apiService.tenants.getPublicInfo(tenantId)
      return getLanguageSettings(tenantInfo.locale)
    } catch (error) {
      console.error("Error fetching tenant language:", error)
      return {
        language: "en",
        timezone: "UTC",
        dateFormat: "MM/DD/YYYY",
        numberFormat: "en-US",
      }
    }
  },

  updateTenantLanguage: async (
    tenantId: string,
    settings: Partial<TenantLanguageResponse>,
  ): Promise<TenantLanguageResponse> => {
    try {
      return {
        language: settings.language || "en",
        timezone: settings.timezone || "UTC",
        dateFormat: settings.dateFormat || "MM/DD/YYYY",
        numberFormat: settings.numberFormat || "en-US",
      }
    } catch (error) {
      console.error("Error updating tenant language:", error)
      throw error
    }
  },

  getSystemLanguages: (): SystemLanguageOption[] => {
    return systemLanguages
  },

  getTranslations: async (language: string): Promise<Record<string, any>> => {
    try {
      const translations = await import(`../../locales/${language}.json`)
      return translations.default || translations
    } catch (error) {
      console.error(`Error loading translations for ${language}:`, error)
      const fallback = await import("../../locales/en.json")
      return fallback.default || fallback
    }
  },
}
