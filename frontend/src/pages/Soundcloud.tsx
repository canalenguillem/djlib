import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { SearchCandidates } from '../components/SearchCandidates'
import { nombreVersion } from '../lib/versiones'
import type { SearchCandidate, SearchHistoryEntry, Version } from '../types/api'

/** Buscar en SoundCloud, que es donde los DJ suben sus edits, bootlegs y
 *  mashups. Se baja igual que de YouTube y se puede guardar todo lo que salga
 *  en una playlist. */
export function SoundcloudPage() {
  const [texto, setTexto] = useState('')
  const [buscado, setBuscado] = useState<string | null>(null)
  const [version, setVersion] = useState<Version | null>(null)
  const [candidatos, setCandidatos] = useState<SearchCandidate[] | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)
  const [anadidos, setAnadidos] = useState<string[]>([])
  const [anadiendo, setAnadiendo] = useState<string | null>(null)
  const [historial, setHistorial] = useState<SearchHistoryEntry[]>([])
  // Lo que se ve viene de un enlace pegado, no de una busqueda
  const [esEnlace, setEsEnlace] = useState(false)

  useEffect(() => {
    if (candidatos !== null) return
    tracksApi
      .searchHistory(30, 'soundcloud')
      .then(setHistorial)
      .catch(() => undefined)
  }, [candidatos])

  async function buscar(consulta: string, enVersion: Version | null) {
    const limpia = consulta.trim()
    if (!limpia) return
    if (/^https?:\/\//i.test(limpia)) {
      await abrirEnlace(limpia)
      return
    }
    setBuscando(true)
    setError(null)
    setOk(null)
    setTexto(limpia)
    setBuscado(limpia)
    setEsEnlace(false)
    setVersion(enVersion)
    try {
      // Va como "artista": asi se piden mas resultados, que en SoundCloud
      // conviene, porque hay muchas versiones de cada tema
      const resultado = await tracksApi.previewSearch(null, limpia, enVersion, 'soundcloud')
      setCandidatos(resultado.candidates)
      setAnadidos([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La búsqueda en SoundCloud ha fallado.')
    } finally {
      setBuscando(false)
    }
  }

  /** Un enlace pegado: una cancion, o todas las de un set, para bajar una o
   *  guardarlas todas en una playlist. */
  async function abrirEnlace(url: string) {
    setBuscando(true)
    setError(null)
    setOk(null)
    setBuscado(url)
    setEsEnlace(true)
    try {
      const resultado = await tracksApi.previewLink(url)
      setCandidatos(resultado.candidates)
      setAnadidos([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo abrir el enlace.')
    } finally {
      setBuscando(false)
    }
  }

  async function anadir(candidato: SearchCandidate) {
    setAnadiendo(candidato.video_id)
    setError(null)
    try {
      const track = await tracksApi.addFromUrl(candidato.url)
      setAnadidos((prev) => [...prev, candidato.video_id])
      setOk(`Descargando: ${candidato.title}`)
      return track
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo añadir la canción.')
    } finally {
      setAnadiendo(null)
    }
  }

  return (
    <div className="stack">
      <h1>SoundCloud</h1>
      <p className="muted">
        Donde los DJ suben sus edits, bootlegs y mashups. Busca un tema, un artista o
        un DJ, o pega el enlace de una canción o de un set, y baja lo que te guste o
        guárdalo todo en una playlist. SoundCloud da el
        audio a 160 kbps como mucho; si el autor deja descargar el original, se baja
        ese.
      </p>

      {error && <Alert kind="error">{error}</Alert>}
      {ok && <Alert kind="success">{ok}</Alert>}

      <section className="card">
        <form
          className="candidates__otra"
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            void buscar(texto, version)
          }}
        >
          <input
            type="search"
            value={texto}
            placeholder="Tema, artista o DJ («bad gyal edit»), o pega un enlace de SoundCloud"
            aria-label="Buscar en SoundCloud"
            onChange={(e) => setTexto(e.target.value)}
          />
          <button type="submit" className="btn btn--primary" disabled={buscando || !texto.trim()}>
            {buscando
              ? 'Buscando...'
              : /^https?:\/\//i.test(texto.trim())
                ? 'Abrir el enlace'
                : 'Buscar en SoundCloud'}
          </button>
          {candidatos !== null && (
            <button type="button" className="btn btn--ghost" onClick={() => setCandidatos(null)}>
              Ver las últimas búsquedas
            </button>
          )}
        </form>

        {candidatos === null && historial.length > 0 && (
          <div className="historial">
            <div className="historial__cabecera">
              <h3>Últimas búsquedas</h3>
            </div>
            <ul className="historial__lista">
              {historial.map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    className="historial__item"
                    disabled={buscando}
                    title="Buscar otra vez"
                    onClick={() => void buscar([b.artist, b.title].filter(Boolean).join(' '), b.version)}
                  >
                    <span>{[b.artist, b.title].filter(Boolean).join(' – ')}</span>
                    {b.version && <span className="badge">{nombreVersion(b.version)}</span>}
                    <span className="muted historial__fecha">
                      {new Date(`${b.created_at}Z`).toLocaleString('es-ES', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {candidatos !== null && buscado && (
          <SearchCandidates
            key={`${buscado}|${version}`}
            candidates={candidatos}
            addedIds={anadidos}
            addingId={anadiendo}
            onAdd={anadir}
            version={version}
            onVersion={esEnlace ? undefined : (v) => void buscar(buscado, v)}
            source="soundcloud"
          />
        )}
      </section>
    </div>
  )
}
