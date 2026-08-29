import { useEffect, useRef, useState } from 'react'

import * as tracksApi from '../api/tracks'
import type { Track } from '../types/api'
import { CloseIcon } from './icons'

interface Props {
  track: Track | null
  onClose: () => void
  onError: (message: string) => void
}

/** Reproductor fijo abajo. El mp3 se pide con la cabecera de autenticacion y
 *  se convierte en una URL de blob, que ademas permite mover la barra. */
export function Player({ track, onClose, onError }: Props) {
  const [src, setSrc] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const audioRef = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    if (!track) {
      setSrc(null)
      return
    }
    let objectUrl: string | null = null
    let cancelled = false
    setLoading(true)
    tracksApi
      .fetchTrackFile(track.id)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      })
      .catch((err) => {
        if (!cancelled) onError(err instanceof Error ? err.message : 'No se pudo reproducir.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [track, onError])

  useEffect(() => {
    if (src && audioRef.current) void audioRef.current.play().catch(() => undefined)
  }, [src])

  if (!track) return null

  return (
    <div className="player">
      <div className="player__info">
        <strong>{track.title}</strong>
        <span className="muted">{track.artist_text ?? 'Artista desconocido'}</span>
      </div>
      {loading ? (
        <span className="muted">Cargando audio...</span>
      ) : (
        <audio ref={audioRef} src={src ?? undefined} controls className="player__audio" />
      )}
      <button type="button" className="btn btn--ghost" onClick={onClose} aria-label="Cerrar reproductor">
        <CloseIcon />
      </button>
    </div>
  )
}
