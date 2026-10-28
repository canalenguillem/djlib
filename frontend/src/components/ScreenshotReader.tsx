import { useEffect, useRef, useState } from 'react'

import * as recognitionApi from '../api/recognition'
import * as tracksApi from '../api/tracks'
import type { DetectedSong, SearchCandidate } from '../types/api'
import { Alert } from './Alert'
import { AutoDownloadBar, EstadoDescarga, claveCancion, useAutoDownload } from './AutoDownload'
import { SearchCandidates } from './SearchCandidates'

// Capturas leidas a la vez: el modelo tarda un par de segundos por imagen, y
// mandarlas todas de golpe solo serviria para chocar con el limite de OpenAI
const EN_PARALELO = 3

/** Lectura de capturas de pantalla.
 *
 *  Pensado para la lista de Shazam: si lo dejas identificando solo durante la
 *  noche, subes las capturas al dia siguiente y salen todas de una vez, en vez
 *  de teclearlas una por una. Se pueden subir muchas a la vez; las canciones
 *  se juntan en una sola lista sin repetidas.
 */
export function ScreenshotReader() {
  const [songs, setSongs] = useState<DetectedSong[] | null>(null)
  // Progreso de la tanda en curso
  const [progreso, setProgreso] = useState<{ hechas: number; total: number } | null>(null)
  const [fallos, setFallos] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [arrastrando, setArrastrando] = useState(false)
  const vistas = useRef(new Set<string>())
  const reading = progreso !== null

  // Descarga automatica, una tras otra
  const auto = useAutoDownload('capturas')

  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const [candidates, setCandidates] = useState<SearchCandidate[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [addedIds, setAddedIds] = useState<string[]>([])
  const [addingId, setAddingId] = useState<string | null>(null)

  /** Lee una tanda de capturas y suma sus canciones a la lista. */
  async function leer(files: File[]) {
    const imagenes = files.filter((f) => f.type.startsWith('image/'))
    if (imagenes.length === 0 || reading) return
    setError(null)
    setFallos([])
    setProgreso({ hechas: 0, total: imagenes.length })
    setSongs((prev) => prev ?? [])

    let siguiente = 0
    async function trabajador() {
      while (siguiente < imagenes.length) {
        const file = imagenes[siguiente++]
        try {
          const resultado = await recognitionApi.readScreenshot(file)
          const nuevas = resultado.songs.filter((song) => {
            const clave = claveCancion(song)
            if (vistas.current.has(clave)) return false
            vistas.current.add(clave)
            return true
          })
          // Se van mostrando segun llegan, sin esperar a toda la tanda
          if (nuevas.length) setSongs((prev) => [...(prev ?? []), ...nuevas])
        } catch (err) {
          const motivo = err instanceof Error ? err.message : 'no se ha podido leer'
          setFallos((prev) => [...prev, `${file.name || 'Captura pegada'}: ${motivo}`])
        } finally {
          setProgreso((prev) => prev && { ...prev, hechas: prev.hechas + 1 })
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(EN_PARALELO, imagenes.length) }, trabajador))
    setProgreso(null)
  }

  function empezarDeCero() {
    vistas.current = new Set()
    auto.reiniciar()
    setSongs(null)
    setFallos([])
    setCandidates(null)
    setOpenIndex(null)
  }

  // El pegado se escucha una sola vez: llama siempre a la version al dia
  const leerRef = useRef(leer)
  leerRef.current = leer

  // Pegar con Ctrl+V es la forma natural en el escritorio: haces la captura y
  // la pegas sin pasar por guardarla en disco.
  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const files = [...(event.clipboardData?.items ?? [])]
        .filter((i) => i.type.startsWith('image/'))
        .map((i) => i.getAsFile())
        .filter((f): f is File => f !== null)
      if (files.length) {
        event.preventDefault()
        void leerRef.current(files)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [])

  async function buscar(index: number, song: DetectedSong) {
    setOpenIndex(index)
    setCandidates(null)
    setSearching(true)
    setError(null)
    try {
      const resultado = await tracksApi.previewSearch(song.title, song.artist)
      setCandidates(resultado.candidates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La busqueda ha fallado.')
    } finally {
      setSearching(false)
    }
  }

  async function anadir(candidate: SearchCandidate) {
    setAddingId(candidate.video_id)
    setError(null)
    try {
      const nueva = await tracksApi.addFromUrl(candidate.url, auto.crateElegido)
      setAddedIds((prev) => [...prev, candidate.video_id])
      return nueva
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setAddingId(null)
    }
  }

  return (
    <section
      className={`card${arrastrando ? ' card--drop' : ''}`}
      onDragOver={(e) => {
        if (![...e.dataTransfer.items].some((i) => i.kind === 'file')) return
        e.preventDefault()
        setArrastrando(true)
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setArrastrando(false)
      }}
      onDrop={(e) => {
        e.preventDefault()
        setArrastrando(false)
        void leer([...e.dataTransfer.files])
      }}
    >
      <h2>Desde capturas</h2>
      <p className="muted">
        Si dejas Shazam identificando solo durante la noche, sube aquí las capturas
        de la lista: puedes elegir muchas a la vez, y las canciones se juntan en una
        sola lista sin repetir las que salgan en dos capturas. También vale cualquier
        otra pantalla donde se lean títulos. En el ordenador puedes arrastrarlas aquí
        o pegarlas con Ctrl+V; cada tanda nueva se suma a la lista.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <label className="field">
        <span>Capturas</span>
        <input
          type="file"
          multiple
          accept="image/png,image/jpeg,image/webp,image/gif"
          disabled={reading}
          onChange={(e) => {
            void leer([...(e.target.files ?? [])])
            // Para poder volver a elegir las mismas
            e.target.value = ''
          }}
        />
      </label>

      {progreso && (
        <p className="muted" role="status">
          Leyendo {progreso.total === 1 ? 'la captura' : `capturas: ${progreso.hechas} de ${progreso.total}`}...
        </p>
      )}

      {fallos.length > 0 && (
        <Alert kind="error">
          {fallos.length === 1 ? 'Una captura no se ha podido leer:' : `${fallos.length} capturas no se han podido leer:`}
          <ul>
            {fallos.map((fallo) => (
              <li key={fallo}>{fallo}</li>
            ))}
          </ul>
        </Alert>
      )}

      {songs !== null &&
        (songs.length === 0 ? (
          reading ? null : 
          <Alert kind="info">
            No se ha leído ninguna canción. Prueba con capturas donde los títulos se
            vean con claridad.
          </Alert>
        ) : (
          <>
            <div className="detected__head">
              <p className="muted">
                {songs.length} {songs.length === 1 ? 'canción leída' : 'canciones leídas'}:
              </p>
              <button type="button" className="btn btn--ghost" disabled={reading || auto.enCola} onClick={empezarDeCero}>
                Empezar de cero
              </button>
            </div>

            <AutoDownloadBar canciones={songs} auto={auto} nombreTanda="Capturas" disabled={reading} />
            <ul className="detected">
              {songs.map((song, index) => {
                const estado = auto.estados[claveCancion(song)]
                return (
                <li key={`${song.title}-${index}`} className="detected__item">
                  <div className="detected__row">
                    <div className="track__info">
                      <div className="track__title">{song.title}</div>
                      <div className="track__meta">
                        <span>{song.artist ?? 'Artista desconocido'}</span>
                        <EstadoDescarga estado={estado} />
                      </div>
                      {estado?.tipo === 'error' && <div className="track__error">{estado.motivo}</div>}
                    </div>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={searching}
                      onClick={() => buscar(index, song)}
                    >
                      {searching && openIndex === index ? 'Buscando...' : 'Buscar en YouTube'}
                    </button>
                  </div>
                  {openIndex === index && candidates !== null && (
                    <SearchCandidates
                      candidates={candidates}
                      addedIds={addedIds}
                      addingId={addingId}
                      onAdd={anadir}
                    />
                  )}
                </li>
                )
              })}
            </ul>
          </>
        ))}
    </section>
  )
}
