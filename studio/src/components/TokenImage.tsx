// A picture EAOS took, wherever the Studio runs: live, the server gives it with the launch token (/api/report-image for
// the check's pictures, /api/screen for the safety flow's); opened as a snapshot, it is the file next to the report.
import { useEffect, useState, type ImgHTMLAttributes } from 'react'
import { liveToken, tokenImage } from '../data/live'

type Props = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & { path: string; api?: '/api/report-image' | '/api/screen' }

export function TokenImage({ path, api = '/api/report-image', onError, ...rest }: Props) {
  const live = liveToken() !== null
  const [src, setSrc] = useState<string | null | undefined>(live ? undefined : `../${path}`)
  useEffect(() => {
    if (!live) return
    let on = true
    setSrc(undefined)
    tokenImage(`${api}?path=${encodeURIComponent(path)}`).then((found) => { if (on) setSrc(found) })
    return () => { on = false }
  }, [api, live, path])
  useEffect(() => { if (src === null) onError?.({} as never) }, [src, onError])
  return src ? <img src={src} onError={onError} {...rest} /> : null
}
