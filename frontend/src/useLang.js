
import { useState, useEffect } from 'react'
import { getLang, subscribeLang } from './i18n'

/**
 * useLang()
 * Returns the current language code and re-renders the component
 * whenever the language changes via setLang().
 */
export default function useLang() {
  const [lang, setLang] = useState(getLang)

  useEffect(() => {
    return subscribeLang(code => setLang(code))
  }, [])

  return lang
}
