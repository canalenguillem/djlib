import { useEffect, useRef, useState } from 'react'

import * as tracksApi from '../api/tracks'
import { formatDuration } from '../lib/format'
import type { SearchCandidate } from '../types/api'
import { PauseIcon, PlayIcon } from './icons'

interface Props {
  candidates: SearchCandidate[]
  addedIds: string[]
  addingId: string | null
  onAdd: (candidate: SearchCandidate) => void
}

/** Resultados de YouTube para que el usuario elija.
 *
 *  Se respeta el orden de relevancia de YouTube en vez de reordenarlos: lo que
 *  hace falta no es adivinar por el usuario, sino que vea la duracion y el
 *  canal y decida. El primer resultado de una busqueda imprecisa suele ser un
 *  mix de una hora, y con la duracion delante eso se ve de un vistazo.
 */
export function SearchCandidates({ candidates, addedIds, addingId, onAdd }: Props) {
  // Fragmento que se esta escuchando, si hay alguno
  const [sonando, setSonando] = useState<string | null>(null)
  const [cargando, setCargando] = useState<string | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const objeto = useRef<string | null>(null)

  function parar() {
    audio.current?.pause()
    audio.current = null
    if (objeto.current) URL.revokeObjectURL(objeto.current)
    objeto.current = null
    setSonando(null)
  }

  // Al desmontar (cambiar de pantalla, nueva busqueda) no debe seguir sonando
  useEffect(() => parar, [])

  async function escuchar(candidate: SearchCandidate) {
    if (sonando === candidate.video_id) {
      parar()
      return
    }
    parar()
    setFallo(null)
    setCargando(candidate.video_id)
    try {
      const blob = await tracksApi.previewCandidate(candidate.url)
      const url = URL.createObjectURL(blob)
      objeto.current = url
      const elemento = new Audio(url)
      elemento.onended = () => parar()
      audio.current = elemento
      await elemento.play()
      setSonando(candidate.video_id)
    } catch (err) {
      setFallo(err instanceof Error ? err.message : 'No se pudo preparar el fragmento.')
    } finally {
      setCargando(null)
    }
  }

  if (candidates.length === 0) {
    return <p className="muted">YouTube no ha devuelto resultados. Prueba con otras palabras.</p>
  }

  return (
    <>
      {fallo && <p className="candidate__fallo">{fallo}</p>}
    <ul className="candidates">
      {candidates.map((candidate) => {
        const added = addedIds.includes(candidate.video_id)
        const inLibrary = candidate.already_in_library || added
        return (
          <li key={candidate.video_id} className="candidate">
            {candidate.thumbnail_url && (
              <img
                className="candidate__thumb"
                src={candidate.thumbnail_url}
                alt=""
                loading="lazy"
              />
            )}
            <div className="candidate__info">
              <div className="candidate__title">{candidate.title}</div>
              <div className="candidate__meta">
                <span>{candidate.channel ?? 'Canal desconocido'}</span>
                <span>·</span>
                <span className={candidate.too_long ? 'candidate__long' : undefined}>
                  {formatDuration(candidate.duration_seconds)}
                </span>
                {candidate.too_long && (
                  <span className="badge badge--off">parece un mix, no una cancion</span>
                )}
                {inLibrary && <span className="badge badge--ok">ya en la biblioteca</span>}
              </div>
            </div>
            <button
              type="button"
              className="candidate__play"
              title="Escuchar 30 segundos antes de decidir"
              aria-label={
                sonando === candidate.video_id
                  ? `Parar ${candidate.title}`
                  : `Escuchar ${candidate.title}`
              }
              disabled={cargando !== null}
              onClick={() => escuchar(candidate)}
            >
              {cargando === candidate.video_id ? (
                <span className="spinner" aria-hidden="true" />
              ) : sonando === candidate.video_id ? (
                <PauseIcon />
              ) : (
                <PlayIcon />
              )}
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={inLibrary || addingId !== null}
              onClick={() => onAdd(candidate)}
            >
              {addingId === candidate.video_id ? 'Anadiendo...' : 'Anadir'}
            </button>
          </li>
        )
      })}
    </ul>
    </>
  )
}
