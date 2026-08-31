import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import * as cratesApi from '../api/crates'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { DeckPanel } from '../components/DeckPanel'
import { Loading } from '../components/Loading'
import { Deck, audioContext, crossfadeGains } from '../lib/audioEngine'
import { formatDuration } from '../lib/format'
import type { CrateSummary, Track } from '../types/api'

const PADS = 4

interface EstadoPlato {
  track: Track | null
  loading: boolean
  playing: boolean
  position: number
  duration: number
  tempo: number
  volume: number
  cues: Array<number | null>
}

const PLATO_INICIAL: EstadoPlato = {
  track: null,
  loading: false,
  playing: false,
  position: 0,
  duration: 0,
  tempo: 1,
  volume: 0.8,
  cues: Array(PADS).fill(null),
}

export function MixerPage() {
  const decks = useRef<[Deck, Deck] | null>(null)
  const [estados, setEstados] = useState<[EstadoPlato, EstadoPlato]>([
    { ...PLATO_INICIAL },
    { ...PLATO_INICIAL },
  ])
  const [crossfader, setCrossfader] = useState(0.5)
  const [error, setError] = useState<string | null>(null)

  // Biblioteca desde la que se cargan los platos
  const [tracks, setTracks] = useState<Track[]>([])
  const [crates, setCrates] = useState<CrateSummary[]>([])
  const [crateId, setCrateId] = useState<number | null>(null)
  const [busqueda, setBusqueda] = useState('')
  const [cargandoLista, setCargandoLista] = useState(true)

  // Los platos se crean una vez: el AudioContext no debe recrearse en cada
  // render, y menos con audio sonando.
  useEffect(() => {
    const ctx = audioContext()
    const salida = ctx.destination
    decks.current = [new Deck(salida), new Deck(salida)]
    const [a, b] = decks.current
    a.setVolume(PLATO_INICIAL.volume)
    b.setVolume(PLATO_INICIAL.volume)
    const [ga, gb] = crossfadeGains(0.5)
    a.crossfade.gain.value = ga
    b.crossfade.gain.value = gb
    return () => {
      decks.current?.forEach((d) => d.dispose())
      decks.current = null
    }
  }, [])

  // Refresco de la posicion mientras suena, al ritmo de la pantalla
  useEffect(() => {
    let vivo = true
    function tick() {
      if (!vivo) return
      const platos = decks.current
      if (platos) {
        setEstados((previo) => {
          const siguiente = previo.map((estado, i) => {
            const deck = platos[i]
            if (!deck.loaded) return estado
            if (estado.position === deck.position && estado.playing === deck.playing) {
              return estado
            }
            return { ...estado, position: deck.position, playing: deck.playing }
          }) as [EstadoPlato, EstadoPlato]
          return siguiente
        })
      }
      requestAnimationFrame(tick)
    }
    const id = requestAnimationFrame(tick)
    return () => {
      vivo = false
      cancelAnimationFrame(id)
    }
  }, [])

  const cargarLista = useCallback(async () => {
    try {
      const [pagina, listaCrates] = await Promise.all([
        tracksApi.listTracks({ search: busqueda, status: 'ready' }),
        crates.length ? Promise.resolve(crates) : cratesApi.listCrates(),
      ])
      setTracks(pagina.items)
      setCrates(listaCrates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la biblioteca.')
    } finally {
      setCargandoLista(false)
    }
    // crates solo se piden la primera vez
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busqueda])

  useEffect(() => {
    void cargarLista()
  }, [cargarLista])

  const [crateTracks, setCrateTracks] = useState<Track[] | null>(null)
  useEffect(() => {
    if (crateId === null) {
      setCrateTracks(null)
      return
    }
    cratesApi
      .getCrate(crateId)
      .then((crate) => setCrateTracks(crate.tracks))
      .catch(() => setCrateTracks(null))
  }, [crateId])

  function actualizar(indice: 0 | 1, cambios: Partial<EstadoPlato>) {
    setEstados((previo) => {
      const copia = [...previo] as [EstadoPlato, EstadoPlato]
      copia[indice] = { ...copia[indice], ...cambios }
      return copia
    })
  }

  async function cargarEnPlato(indice: 0 | 1, track: Track) {
    const deck = decks.current?.[indice]
    if (!deck) return
    actualizar(indice, { loading: true, track, playing: false, position: 0, cues: Array(PADS).fill(null) })
    setError(null)
    try {
      const blob = await tracksApi.fetchTrackFile(track.id)
      await deck.load(await blob.arrayBuffer())
      actualizar(indice, { loading: false, duration: deck.duration, position: 0 })
    } catch (err) {
      actualizar(indice, { loading: false, track: null })
      setError(err instanceof Error ? err.message : 'No se pudo cargar el audio.')
    }
  }

  function alternar(indice: 0 | 1) {
    const deck = decks.current?.[indice]
    if (!deck?.loaded) return
    if (deck.playing) deck.pause()
    else deck.play()
    actualizar(indice, { playing: deck.playing })
  }

  function pulsarPad(indice: 0 | 1, pad: number) {
    const deck = decks.current?.[indice]
    if (!deck?.loaded) return
    const cues = estados[indice].cues
    if (cues[pad] === null) {
      // Vacio: marca el punto en el que va la cancion
      const nuevos = [...cues]
      nuevos[pad] = deck.position
      actualizar(indice, { cues: nuevos })
    } else {
      deck.seek(cues[pad] as number)
      actualizar(indice, { position: deck.position })
    }
  }

  function moverCrossfader(valor: number) {
    setCrossfader(valor)
    const platos = decks.current
    if (!platos) return
    const [ga, gb] = crossfadeGains(valor)
    const ctx = audioContext()
    platos[0].crossfade.gain.setTargetAtTime(ga, ctx.currentTime, 0.01)
    platos[1].crossfade.gain.setTargetAtTime(gb, ctx.currentTime, 0.01)
  }

  /** BPM al que suena cada plato ahora mismo, con su tempo aplicado. */
  function sonandoA(indice: 0 | 1): number | null {
    const estado = estados[indice]
    return estado.track?.bpm ? estado.track.bpm * estado.tempo : null
  }

  /** Ajusta el tempo de un plato para que suene al mismo BPM que el otro. */
  function igualar(indice: 0 | 1) {
    const propio = estados[indice].track?.bpm
    const objetivo = sonandoA(indice === 0 ? 1 : 0)
    if (!propio || !objetivo) return
    const ratio = Math.max(0.92, Math.min(1.08, objetivo / propio))
    decks.current?.[indice].setTempo(ratio)
    actualizar(indice, { tempo: ratio })
  }

  const listaVisible = crateTracks ?? tracks

  return (
    <div className="stack">
      <h1>Mesa de mezclas</h1>
      <p className="muted">
        Dos platos con crossfader para practicar transiciones con tu propia
        biblioteca. El tempo cambia el tono, como en un plato de verdad. No sustituye
        a rekordbox ni a Mixxx: para el bolo, exporta el crate a un USB.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <div className="mixer">
        <DeckPanel
          label="A"
          {...estados[0]}
          otherBpm={sonandoA(1)}
          onMatch={() => igualar(0)}
          onPlayPause={() => alternar(0)}
          onSeek={(s) => {
            decks.current?.[0].seek(s)
            actualizar(0, { position: s })
          }}
          onTempo={(v) => {
            decks.current?.[0].setTempo(v)
            actualizar(0, { tempo: v })
          }}
          onVolume={(v) => {
            decks.current?.[0].setVolume(v)
            actualizar(0, { volume: v })
          }}
          onCue={(p) => pulsarPad(0, p)}
          onClearCue={(p) => {
            const nuevos = [...estados[0].cues]
            nuevos[p] = null
            actualizar(0, { cues: nuevos })
          }}
        />

        <div className="crossfader card">
          <span className="crossfader__label">Crossfader</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={crossfader}
            aria-label="Crossfader"
            onChange={(e) => moverCrossfader(Number(e.target.value))}
          />
          {sonandoA(0) !== null && sonandoA(1) !== null && (
            <div className="crossfader__bpm">
              {Math.abs(sonandoA(0)! - sonandoA(1)!) < 0.5 ? (
                <span className="crossfader__match">Platos igualados</span>
              ) : (
                <span className="muted">
                  {Math.abs(sonandoA(0)! - sonandoA(1)!).toFixed(1)} BPM de diferencia
                </span>
              )}
            </div>
          )}
          <div className="crossfader__ends">
            <span>A</span>
            <button type="button" className="btn btn--ghost" onClick={() => moverCrossfader(0.5)}>
              Centrar
            </button>
            <span>B</span>
          </div>
        </div>

        <DeckPanel
          label="B"
          {...estados[1]}
          otherBpm={sonandoA(0)}
          onMatch={() => igualar(1)}
          onPlayPause={() => alternar(1)}
          onSeek={(s) => {
            decks.current?.[1].seek(s)
            actualizar(1, { position: s })
          }}
          onTempo={(v) => {
            decks.current?.[1].setTempo(v)
            actualizar(1, { tempo: v })
          }}
          onVolume={(v) => {
            decks.current?.[1].setVolume(v)
            actualizar(1, { volume: v })
          }}
          onCue={(p) => pulsarPad(1, p)}
          onClearCue={(p) => {
            const nuevos = [...estados[1].cues]
            nuevos[p] = null
            actualizar(1, { cues: nuevos })
          }}
        />
      </div>

      <section className="card">
        <h2>Cargar canciones</h2>
        <div className="filters">
          <form
            className="filters__search"
            onSubmit={(e: FormEvent) => {
              e.preventDefault()
              void cargarLista()
            }}
          >
            <input
              type="search"
              value={busqueda}
              placeholder="Buscar en la biblioteca..."
              disabled={crateId !== null}
              onChange={(e) => setBusqueda(e.target.value)}
            />
            <button type="submit" className="btn btn--ghost" disabled={crateId !== null}>
              Buscar
            </button>
          </form>
          {crates.length > 0 && (
            <div className="filters__group">
              <span className="filters__label">Crate</span>
              <select
                value={crateId ?? ''}
                onChange={(e) => setCrateId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Toda la biblioteca</option>
                {crates.map((crate) => (
                  <option key={crate.id} value={crate.id}>
                    {crate.name} ({crate.track_count})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {cargandoLista ? (
          <Loading />
        ) : listaVisible.length === 0 ? (
          <p className="muted">Nada que cargar.</p>
        ) : (
          <ul className="tracklist">
            {listaVisible.map((track) => (
              <li key={track.id} className="track">
                <div className="track__main">
                  {track.thumbnail_url && (
                    <img className="track__thumb" src={track.thumbnail_url} alt="" loading="lazy" />
                  )}
                  <div className="track__info">
                    <div className="track__title">{track.title}</div>
                    <div className="track__meta">
                      <span>{track.artist_text ?? 'Artista desconocido'}</span>
                      <span>·</span>
                      <span>{formatDuration(track.duration_seconds)}</span>
                    </div>
                  </div>
                  <div className="track__actions">
                    <button type="button" className="btn btn--ghost" onClick={() => cargarEnPlato(0, track)}>
                      → A
                    </button>
                    <button type="button" className="btn btn--ghost" onClick={() => cargarEnPlato(1, track)}>
                      → B
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
