import { useEffect, useRef, useState } from 'react'

import * as tracksApi from '../api/tracks'
import { formatDuration } from '../lib/format'
import { VersionChips, nombreVersion } from '../lib/versiones'
import type { SearchCandidate, Track, Version } from '../types/api'
import { CrateSelect } from './CrateSelect'
import { PauseIcon, PlayIcon } from './icons'

interface Props {
  candidates: SearchCandidate[]
  addedIds: string[]
  addingId: string | null
  /** Devuelve la cancion creada, para poder meterla en un crate desde aqui. */
  onAdd: (candidate: SearchCandidate) => Promise<Track | undefined> | void
  /** Con esto se ven botones para repetir la busqueda en otra version. */
  version?: Version | null
  onVersion?: (version: Version | null) => void
}

/** Resultados de YouTube para que el usuario elija.
 *
 *  Se respeta el orden de relevancia de YouTube en vez de reordenarlos: lo que
 *  hace falta no es adivinar por el usuario, sino que vea la duracion y el
 *  canal y decida. El primer resultado de una busqueda imprecisa suele ser un
 *  mix de una hora, y con la duracion delante eso se ve de un vistazo.
 */
export function SearchCandidates({ candidates, addedIds, addingId, onAdd, version = null, onVersion }: Props) {
  // Fragmento que se esta escuchando, si hay alguno
  const [sonando, setSonando] = useState<string | null>(null)
  const [cargando, setCargando] = useState<string | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const objeto = useRef<string | null>(null)
  // Las que se han anadido desde esta lista, por id de video
  const [nuevas, setNuevas] = useState<Record<string, Track>>({})

  async function anadir(candidate: SearchCandidate) {
    const track = await onAdd(candidate)
    if (track) setNuevas((prev) => ({ ...prev, [candidate.video_id]: track }))
  }

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

  // Lo que ya se tenia antes de buscar no se ofrece: estorba para ver lo nuevo.
  // Lo anadido desde aqui si se queda, para poder elegirle crate
  const [verTenidas, setVerTenidas] = useState(false)
  const tenidas = candidates.filter((c) => c.already_in_library && !nuevas[c.video_id])
  const visibles = verTenidas ? candidates : candidates.filter((c) => !tenidas.includes(c))

  const versiones = onVersion && <VersionChips version={version} onChange={onVersion} />
  const avisoTenidas = tenidas.length > 0 && (
    <p className="muted candidates__tenidas">
      {verTenidas
        ? `Se ven también las ${tenidas.length} que ya tienes.`
        : `${tenidas.length === 1 ? 'Oculta 1 que ya tienes' : `Ocultas ${tenidas.length} que ya tienes`}.`}{' '}
      <button type="button" className="btn btn--ghost" onClick={() => setVerTenidas((v) => !v)}>
        {verTenidas ? 'Ocultarlas' : 'Verlas'}
      </button>
    </p>
  )

  if (candidates.length === 0) {
    return (
      <>
        {versiones}
        <p className="muted">YouTube no ha devuelto resultados. Prueba con otras palabras.</p>
      </>
    )
  }

  return (
    <>
      {versiones}
      {fallo && <p className="candidate__fallo">{fallo}</p>}
      {avisoTenidas}
      {visibles.length === 0 && candidates.length > 0 && (
        <p className="muted">Todo lo que ha encontrado YouTube ya lo tienes. Prueba otra versión.</p>
      )}
    <ul className="candidates">
      {visibles.map((candidate) => {
        const added = addedIds.includes(candidate.video_id)
        const inLibrary = candidate.already_in_library || added
        const nueva = nuevas[candidate.video_id]
        const enBiblioteca = nueva
          ? { id: nueva.id, crateIds: nueva.crate_ids, pending: nueva.pending_crate_id }
          : candidate.track_id !== null
            ? { id: candidate.track_id, crateIds: candidate.crate_ids, pending: candidate.pending_crate_id }
            : null
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
                {candidate.duration_seconds !== null && candidate.duration_seconds < 90 && (
                  <span className="badge badge--off">muy corta, quizá un avance</span>
                )}
                {!candidate.matches_version && (
                  <span className="badge badge--off">no parece {nombreVersion(version).toLowerCase()}</span>
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
            {enBiblioteca ? (
              <CrateSelect
                key={enBiblioteca.id}
                trackId={enBiblioteca.id}
                crateIds={enBiblioteca.crateIds}
                pendingCrateId={enBiblioteca.pending}
              />
            ) : (
              <button
                type="button"
                className="btn btn--primary"
                disabled={inLibrary || addingId !== null}
                onClick={() => void anadir(candidate)}
              >
                {addingId === candidate.video_id ? 'Anadiendo...' : 'Anadir'}
              </button>
            )}
          </li>
        )
      })}
    </ul>
    </>
  )
}
