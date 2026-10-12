import { RouterProvider } from '@tanstack/react-router'
import { ToastProvider } from './components/Toast'
import { ActionsProvider } from './data/actions/store'
import { DataProvider } from './data/context'
import { ScanProvider } from './data/ScanProvider'
import { PrefsProvider } from './i18n/prefs'
import { router } from './router'
import { ChromeProvider } from './shell/chrome'

export function App() {
  return (
    <PrefsProvider>
      <DataProvider>
        <ScanProvider>
        <ActionsProvider>
          <ToastProvider>
            <ChromeProvider>
              <RouterProvider router={router} />
            </ChromeProvider>
          </ToastProvider>
        </ActionsProvider>
        </ScanProvider>
      </DataProvider>
    </PrefsProvider>
  )
}
