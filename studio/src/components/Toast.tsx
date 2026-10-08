// One line in a polite live region for 2.2 s (DESIGN.md §3). React Aria's toast is still UNSTABLE_, so this is ours.
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import css from './Toast.module.css'

const ToastContext = createContext<(message: string) => void>(() => {})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState('')
  const timer = useRef<number | undefined>(undefined)
  const show = useCallback((next: string) => {
    window.clearTimeout(timer.current)
    setMessage('')
    requestAnimationFrame(() => setMessage(next)) // re-announced even when the same message repeats
    timer.current = window.setTimeout(() => setMessage(''), 2200)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className={css.toast} role="status" aria-live="polite" data-on={message ? '' : undefined}>{message}</div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
