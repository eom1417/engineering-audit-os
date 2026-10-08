import { RouterProvider } from '@tanstack/react-router'
import { useMemo } from 'react'
import { ToastProvider } from './components/Toast'
import { ActionsProvider } from './data/actions/store'
import { DataProvider } from './data/context'
import { PrefsProvider, usePrefs } from './i18n/prefs'
import { makeRouter } from './router'
import { ChromeProvider } from './shell/chrome'

function Routed() {
  const { dev } = usePrefs()
  const router = useMemo(() => makeRouter(() => dev), [dev])
  return <RouterProvider router={router} />
}

export function App() {
  return (
    <PrefsProvider>
      <DataProvider>
        <ActionsProvider>
          <ToastProvider>
            <ChromeProvider>
              <Routed />
            </ChromeProvider>
          </ToastProvider>
        </ActionsProvider>
      </DataProvider>
    </PrefsProvider>
  )
}
