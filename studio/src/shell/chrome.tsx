// What a page tells the shell: its title, and on the phone the view it was pushed from (stacked navigation: the
// back button names the list it returns to).
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { Search } from '../components/Go'

export interface Back { to: string; search?: Search; label: string }
export interface Chrome { title: string; back?: Back }

const ChromeContext = createContext<{ chrome: Chrome; set: (chrome: Chrome) => void }>({ chrome: { title: '' }, set: () => {} })

export function ChromeProvider({ children }: { children: ReactNode }) {
  const [chrome, set] = useState<Chrome>({ title: '' })
  return <ChromeContext.Provider value={{ chrome, set }}>{children}</ChromeContext.Provider>
}

export function useChrome(): Chrome {
  return useContext(ChromeContext).chrome
}

// The tab's title: the page's own, after the running work's progress when there is one ("3/26", "✓": ScanBanner).
const tabTitle = { page: typeof document === 'undefined' ? '' : document.title, progress: '' }
function showTitle() {
  document.title = [tabTitle.progress, tabTitle.page].filter(Boolean).join(' · ')
}

/** Puts the running work's progress before the page's title in the tab ('' takes it away). */
export function setTitleProgress(progress: string) {
  tabTitle.progress = progress
  showTitle()
}

/** Called by every page: sets the document title and the shell's title and back target. */
export function usePageChrome(title: string, back?: Back, project?: string) {
  const { set } = useContext(ChromeContext)
  const backKey = back ? `${back.to}|${JSON.stringify(back.search ?? {})}|${back.label}` : ''
  useEffect(() => {
    set({ title, back })
    tabTitle.page = [title, project, 'EAOS Studio'].filter(Boolean).join(' · ')
    showTitle()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, backKey, project, set])
}
