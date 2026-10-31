import { useEffect, useRef, useState } from 'react'

import * as artistsApi from '../api/artists'
import * as tracksApi from '../api/tracks'
import { formatDuration } from '../lib/format'
import { VersionChips, nombreVersion } from '../lib/versiones'
import type { SearchCandidate, Track, Version } from '../types/api'
import { CrateSelect } from './CrateSelect'
import { PauseIcon, PlayIcon } from './icons'

const SEPARA = /\s*(?:,|&|\bx\b|\bfeat\.?|\bft\.?|\bvs\.?)\s*/i
// "(Kennan Mashup Edit)", "[DJ Larry G Remix]": quien hizo la version
const AUTOR_VERSION = /[([]([^()[\]]+?)\s+(?:remix|mashup|edit|rework|bootleg|extended|mix)\b/gi
// Trozos de titulo que no son de nadie: "(Lyric Video / Remix)"
const NO_ES_NOMBRE = /[/@#]|\b(?:video|lyrics?|letra|visualizer|audio)\b/i
const NO_SON_NOMBRES = /^(official|video|audio|lyric|letra|visualizer|extended|radio|club|original|dj|the|mashup|remix)$/i

/** Nombres que salen en un resultado y por los que puede interesar buscar mas:
 *  el canal, los artistas de antes del guion y quien firma el remix o mashup. */
function nombresDe(candidate: SearchCandidate): string[] {
  const nombres: string[] = []
  const guion = candidate.title.split(/\s+[-–|]\s+/)
  if (guion.length > 1) nombres.push(...guion[0].split(SEPARA))
  for (const m of candidate.title.matchAll(AUTOR_VERSION)) nombres.push(m[1])
  if (candidate.channel) nombres.push(candidate.channel.replace(/\s*-\s*Topic$/i, ''))
  const vistos = new Set<string>()
  return nombres
    .map((n) => n.replace(/\b(?:official|oficial)\b.*$/i, '').trim())
    .map((n) => n.replace(/\s+mix$/i, '').trim())
    .filter((n) => n.length > 1 && n.length <= 40 && !NO_SON_NOMBRES.test(n) && !NO_ES_NOMBRE.test(n))
    .filter((n) => {
      const clave = n.toLowerCase()
      if (vistos.has(clave)) return false
      vistos.add(clave)
      return true
    })
    .slice(0, 5)
}

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

  // Busqueda de un artista o DJ que ha salido en los resultados: se ve aqui
  // mismo, en lugar de la de antes, hasta que se vuelve
  const [otra, setOtra] = useState<{ nombre: string; version: Version | null; lista: SearchCandidate[] } | null>(null)
  const [escrito, setEscrito] = useState('')
  const [buscandoOtra, setBuscandoOtra] = useState(false)
  const [guardado, setGuardado] = useState<string | null>(null)

  async function buscarArtista(nombre: string, enVersion: Version | null = null) {
    const limpio = nombre.trim()
    if (!limpio) return
    parar()
    setFallo(null)
    setBuscandoOtra(true)
    try {
      const resultado = await tracksApi.previewSearch(null, limpio, enVersion)
      setOtra({ nombre: limpio, version: enVersion, lista: resultado.candidates })
      setEscrito('')
    } catch (err) {
      setFallo(err instanceof Error ? err.message : 'La busqueda ha fallado.')
    } finally {
      setBuscandoOtra(false)
    }
  }

  async function guardarArtista(nombre: string) {
    setFallo(null)
    try {
      await artistsApi.createArtist(nombre)
      setGuardado(nombre)
    } catch (err) {
      setFallo(err instanceof Error ? err.message : 'No se pudo guardar el artista.')
    }
  }

  const lista = otra ? otra.lista : candidates

  // Lo que ya se tenia antes de buscar no se ofrece: estorba para ver lo nuevo.
  // Lo anadido desde aqui si se queda, para poder elegirle crate
  const [verTenidas, setVerTenidas] = useState(false)
  const tenidas = lista.filter((c) => c.already_in_library && !nuevas[c.video_id])
  const visibles = verTenidas ? lista : lista.filter((c) => !tenidas.includes(c))

  const versiones = otra ? (
    <VersionChips version={otra.version} onChange={(v) => void buscarArtista(otra.nombre, v)} disabled={buscandoOtra} />
  ) : (
    onVersion && <VersionChips version={version} onChange={onVersion} />
  )
  const cabecera = (
    <>
      {otra && (
        <div className="candidates__otra">
          <strong>Más de «{otra.nombre}»</strong>
          <button type="button" className="btn btn--ghost" onClick={() => setOtra(null)}>
            ← Volver a la búsqueda
          </button>
          {guardado === otra.nombre ? (
            <span className="badge badge--ok">guardado en Artistas</span>
          ) : (
            <button
              type="button"
              className="btn btn--ghost"
              title="Para tenerlo en Artistas y volver a él cuando quieras"
              onClick={() => void guardarArtista(otra.nombre)}
            >
              Guardar en Artistas
            </button>
          )}
        </div>
      )}
      <form
        className="candidates__otra"
        onSubmit={(e) => {
          e.preventDefault()
          void buscarArtista(escrito)
        }}
      >
        <input
          value={escrito}
          placeholder="Buscar más de un artista o DJ..."
          aria-label="Artista o DJ"
          onChange={(e) => setEscrito(e.target.value)}
        />
        <button type="submit" className="btn btn--ghost" disabled={buscandoOtra || !escrito.trim()}>
          {buscandoOtra ? 'Buscando...' : 'Buscar'}
        </button>
      </form>
      {versiones}
    </>
  )
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

  if (lista.length === 0) {
    return (
      <>
        {cabecera}
        {fallo && <p className="candidate__fallo">{fallo}</p>}
        <p className="muted">YouTube no ha devuelto resultados. Prueba con otras palabras.</p>
      </>
    )
  }

  return (
    <>
      {cabecera}
      {fallo && <p className="candidate__fallo">{fallo}</p>}
      {avisoTenidas}
      {visibles.length === 0 && lista.length > 0 && (
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
                  <span className="badge badge--off">
                    no parece {nombreVersion(otra ? otra.version : version).toLowerCase()}
                  </span>
                )}
                {inLibrary && <span className="badge badge--ok">ya en la biblioteca</span>}
              </div>
              <div className="candidate__nombres">
                {nombresDe(candidate).map((nombre) => (
                  <button
                    key={nombre}
                    type="button"
                    className="candidate__nombre"
                    title={`Buscar más de ${nombre}`}
                    disabled={buscandoOtra}
                    onClick={() => void buscarArtista(nombre)}
                  >
                    {nombre}
                  </button>
                ))}
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
                sugerir={nueva !== undefined}
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
