// A sheet: React Aria's modal dialog (focus trapped and restored, Esc and the scrim close it), drawn as a bottom
// sheet on the phone and a centred dialog on desktop.
import type { ReactNode } from 'react'
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components'
import { usePrefs } from '../i18n/prefs'
import { IconButton } from './Button'
import css from './Sheet.module.css'

export function Sheet({ isOpen, onOpenChange, title, children }:
  { isOpen: boolean; onOpenChange: (open: boolean) => void; title: string; children: ReactNode }) {
  const { t } = usePrefs()
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange} isDismissable className={css.overlay}>
      <Modal className={css.modal}>
        <Dialog className={css.dialog}>
          {({ close }) => (
            <>
              <div className={css.grab} aria-hidden="true" />
              <header className={css.head}>
                <Heading slot="title">{title}</Heading>
                <IconButton icon="x" label={t('close')} onPress={close} />
              </header>
              <div className={css.body}>{children}</div>
            </>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  )
}

export function SheetSub({ children }: { children: ReactNode }) {
  return <h3 className={css.sub}>{children}</h3>
}

export function SheetLead({ children }: { children: ReactNode }) {
  return <p className={css.lead}>{children}</p>
}
