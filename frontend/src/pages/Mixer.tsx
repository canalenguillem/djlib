import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'

import * as cratesApi from '../api/crates'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { DeckPanel } from '../components/DeckPanel'
import { SyncView } from '../components/SyncView'
import { Loading } from '../components/Loading'
import { Knob } from '../components/Knob'
import { Deck, audioContext, crossfadeGains, eqDb } from '../lib/audioEngine'
import type { EqBand } from '../lib/audioEngine'
import { COLOR_FX } from '../lib/colorFx'
import type { ColorFxId } from '../lib/colorFx'
import { ContadorEscucha } from '../lib/escuchas'
import { EQUIPOS, equipoGuardado, guardarEquipo, rangoCercano } from '../lib/equipos'
import type { Equipo } from '../lib/equipos'
import { BANDS, analyzeBuffer } from '../lib/waveform'
import { detectBeatGrid, setDownbeat } from '../lib/beatgrid'
import type { BeatGrid } from '../lib/beatgrid'
import type { DeckWaveformData } from '../lib/waveform'
import { formatDuration } from '../lib/format'
import type { CrateSummary, Track } from '../types/api'

// De arriba abajo, como en la mesa. Cada uno con el color de su banda en la
// onda, para ver lo que se esta quitando.
const EQ: Array<{ band: EqBand; label: string }> = [
  { band: 'high', label: 'Agudos' },
  { band: 'mid', label: 'Medios' },
  { band: 'low', label: 'Bajos' },
]
const COLOR_BANDA = Object.fromEntries(BANDS.map((b) => [b.key, b.color])) as Record<EqBand, string>

// Duracion del intercambio de ecualizador, en compases de 4 tiempos: es como
// se cuenta una mezcla. 0 es un corte seco.
const VELOCIDADES = [0, 1, 2, 4]
// Si no suena nada con BPM conocido, se cuenta a un tempo tipico de house
const BPM_POR_DEFECTO = 120

function textoDb(posicion: number, equipo: Equipo): string {
  const db = Math.round(eqDb(posicion, equipo.eqMinDb, equipo.eqMaxDb))
  return db === 0 ? '0 dB' : `${db > 0 ? '+' : '−'}${Math.abs(db)} dB`
}

interface EstadoPlato {
  track: Track | null
  loading: boolean
  playing: boolean
  position: number
  duration: number
  tempo: number
  volume: number
  /** Posicion de cada potenciometro del ecualizador, de -1 a 1. */
  eq: Record<EqBand, number>
  range: number
  /** Rueda COLOR del canal, de -1 a 1: en el centro no hay efecto. */
  color: number
  cues: Array<number | null>
  /** El cue principal, el del boton CUE. Al cargar, el principio del tema. */
  mainCue: number
  waveform: DeckWaveformData | null
  analyzing: boolean
  /** Rejilla de tiempos, sacada de la onda. */
  grid: BeatGrid | null
}

function platoInicial(equipo: Equipo): EstadoPlato {
  return { ...PLATO_VACIO, range: equipo.rangoInicial, cues: Array(equipo.hotCues).fill(null) }
}

const PLATO_VACIO: EstadoPlato = {
  track: null,
  loading: false,
  playing: false,
  position: 0,
  duration: 0,
  tempo: 1,
  volume: 0.8,
  eq: { high: 0, mid: 0, low: 0 },
  range: 10,
  color: 0,
  cues: [],
  mainCue: 0,
  waveform: null,
  analyzing: false,
  grid: null,
}

export function MixerPage() {
  const decks = useRef<[Deck, Deck] | null>(null)
  // Lo que ha sonado de cada plato, para contar la escucha como mezcla
  const contadores = useRef<[ContadorEscucha | null, ContadorEscucha | null]>([null, null])
  // Cuantas canciones se han cargado en cada plato: el analisis de la onda es
  // asincrono y no debe pisar el de una cancion cargada despues.
  const cargas = useRef<[number, number]>([0, 0])
  // Si cada plato esta sonando solo mientras se mantiene pulsado el CUE
  const preescucha = useRef<[boolean, boolean]>([false, false])
  // Modelo de cabina que se simula; se recuerda entre visitas
  const [equipo, setEquipo] = useState(equipoGuardado)
  // Para los barridos de EQ, que leen el equipo desde una animacion
  const equipoRef = useRef(equipo)
  equipoRef.current = equipo
  const [estados, setEstados] = useState<[EstadoPlato, EstadoPlato]>(() => [
    platoInicial(equipo),
    platoInicial(equipo),
  ])
  const [crossfader, setCrossfader] = useState(0.5)
  // SOUND COLOR FX: el boton encendido y la rueda PARAMETER, comunes a la mesa
  const [colorFx, setColorFx] = useState<ColorFxId | null>(null)
  const [parametro, setParametro] = useState(0)
  const [compases, setCompases] = useState(1)
  // Barridos de intercambio en marcha, por banda: el id de su animacion
  const barridos = useRef<Partial<Record<EqBand, number>>>({})
  const [barriendo, setBarriendo] = useState<Partial<Record<EqBand, boolean>>>({})
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
    a.setVolume(PLATO_VACIO.volume)
    b.setVolume(PLATO_VACIO.volume)
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
        platos.forEach((deck, i) => {
          if (deck.playing) contadores.current[i]?.avanza(deck.position)
        })
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
    const turno = ++cargas.current[indice]
    actualizar(indice, {
      loading: true,
      track,
      playing: false,
      position: 0,
      cues: Array(equipo.hotCues).fill(null),
      mainCue: 0,
      waveform: null,
      analyzing: false,
      grid: null,
    })
    setError(null)
    try {
      const blob = await tracksApi.fetchTrackFile(track.id)
      await deck.load(await blob.arrayBuffer())
      contadores.current[indice] = new ContadorEscucha(track.id, 'mixer', deck.duration)
      actualizar(indice, { loading: false, duration: deck.duration, position: 0, analyzing: true })
    } catch (err) {
      actualizar(indice, { loading: false, track: null })
      setError(err instanceof Error ? err.message : 'No se pudo cargar el audio.')
      return
    }

    // La onda se calcula despues: el plato ya se puede tocar mientras tanto
    try {
      const onda = deck.audio ? await analyzeBuffer(deck.audio) : null
      // Si mientras tanto se ha cargado otra cancion en el plato, esta onda ya
      // no es la suya
      const grid = onda ? detectBeatGrid(onda, track.bpm) : null
      if (turno === cargas.current[indice]) actualizar(indice, { waveform: onda, analyzing: false, grid })
    } catch {
      if (turno === cargas.current[indice]) actualizar(indice, { analyzing: false })
    }
  }

  function alternar(indice: 0 | 1) {
    const deck = decks.current?.[indice]
    if (!deck?.loaded) return
    // PLAY con el CUE pulsado: como en el CDJ, al soltar el CUE sigue sonando
    if (preescucha.current[indice]) {
      preescucha.current[indice] = false
      return
    }
    if (deck.playing) deck.pause()
    else deck.play()
    actualizar(indice, { playing: deck.playing })
  }

  /** El boton CUE de un CDJ, en el modo por defecto. */
  function pulsarCue(indice: 0 | 1) {
    const deck = decks.current?.[indice]
    if (!deck?.loaded) return
    const cue = estados[indice].mainCue
    if (deck.playing) {
      // Sonando: vuelve al cue y se queda parado, listo para lanzarlo a tiempo
      deck.pause()
      deck.seek(cue)
      actualizar(indice, { playing: false, position: cue })
    } else if (Math.abs(deck.position - cue) > 0.01) {
      // Parado en otro punto: ese punto pasa a ser el cue
      actualizar(indice, { mainCue: deck.position })
    } else {
      // Parado en el cue: suena mientras se mantenga pulsado
      preescucha.current[indice] = true
      deck.play()
      actualizar(indice, { playing: true })
    }
  }

  function soltarCue(indice: 0 | 1) {
    if (!preescucha.current[indice]) return
    preescucha.current[indice] = false
    const deck = decks.current?.[indice]
    if (!deck) return
    const cue = estados[indice].mainCue
    deck.pause()
    deck.seek(cue)
    actualizar(indice, { playing: false, position: cue })
  }

  function cambiarEq(indice: 0 | 1, banda: EqBand, posicion: number) {
    const { eqMinDb, eqMaxDb } = equipoRef.current
    decks.current?.[indice].setEq(banda, eqDb(posicion, eqMinDb, eqMaxDb))
    setEstados((previo) => {
      const copia = [...previo] as [EstadoPlato, EstadoPlato]
      copia[indice] = { ...copia[indice], eq: { ...copia[indice].eq, [banda]: posicion } }
      return copia
    })
  }

  function pararBarrido(banda: EqBand) {
    const id = barridos.current[banda]
    if (id === undefined) return
    cancelAnimationFrame(id)
    delete barridos.current[banda]
    setBarriendo((previo) => ({ ...previo, [banda]: false }))
  }

  // Al salir de la pantalla no puede quedar ningun barrido moviendo nada
  useEffect(() => () => Object.values(barridos.current).forEach((id) => cancelAnimationFrame(id!)), [])

  /** Lo que hace un DJ con las dos manos: cada canal se queda con el valor
   *  que tenia el otro. Si los bajos de A estan arriba y los de B cortados,
   *  A los pierde mientras B los recupera. */
  function intercambiar(banda: EqBand, segundos: number) {
    const a = estados[0].eq[banda]
    const b = estados[1].eq[banda]
    pararBarrido(banda)
    if (a === b) return
    if (segundos <= 0) {
      cambiarEq(0, banda, b)
      cambiarEq(1, banda, a)
      return
    }
    const inicio = performance.now()
    const paso = (ahora: number) => {
      const t = Math.min(1, (ahora - inicio) / (segundos * 1000))
      cambiarEq(0, banda, a + (b - a) * t)
      cambiarEq(1, banda, b + (a - b) * t)
      if (t < 1) {
        barridos.current[banda] = requestAnimationFrame(paso)
      } else {
        delete barridos.current[banda]
        setBarriendo((previo) => ({ ...previo, [banda]: false }))
      }
    }
    barridos.current[banda] = requestAnimationFrame(paso)
    setBarriendo((previo) => ({ ...previo, [banda]: true }))
  }

  function cambiarVolumen(indice: 0 | 1, valor: number) {
    decks.current?.[indice].setVolume(valor)
    actualizar(indice, { volume: valor })
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

  /** BPM del tema: el afinado de la rejilla si ya esta, que tiene decimales. */
  function bpmDe(indice: 0 | 1): number | null {
    const estado = estados[indice]
    return estado.grid?.bpm ?? estado.track?.bpm ?? null
  }

  /** BPM al que suena cada plato ahora mismo, con su tempo aplicado. */
  function sonandoA(indice: 0 | 1): number | null {
    const bpm = bpmDe(indice)
    return bpm ? bpm * estados[indice].tempo : null
  }

  /** Mientras se mantiene, frena o acelera el plato un poco, como empujando
   *  el jog: es como se cuadran los golpes a mano. */
  function empujar(indice: 0 | 1, factor: number) {
    decks.current?.[indice].setBend(factor)
  }

  /** Corrige la rejilla: el golpe mas cercano a la aguja pasa a ser el 1. */
  function marcarUno(indice: 0 | 1) {
    const { grid, position } = estados[indice]
    if (grid) actualizar(indice, { grid: setDownbeat(grid, position) })
  }

  /** Devuelve el plato a la velocidad a la que se grabo el tema. */
  function tempoOriginal(indice: 0 | 1) {
    decks.current?.[indice].setTempo(1)
    actualizar(indice, { tempo: 1 })
  }

  /** Ajusta el tempo de un plato para que suene al mismo BPM que el otro. */
  function igualar(indice: 0 | 1) {
    const propio = bpmDe(indice)
    const objetivo = sonandoA(indice === 0 ? 1 : 0)
    if (!propio || !objetivo) return
    const limite = estados[indice].range / 100
    const ratio = Math.max(1 - limite, Math.min(1 + limite, objetivo / propio))
    decks.current?.[indice].setTempo(ratio)
    actualizar(indice, { tempo: ratio })
  }

  /** Cambiar el recorrido del fader no debe mover el tempo, salvo que el valor
   *  actual se salga del nuevo rango. */
  function cambiarRango(indice: 0 | 1, valor: number) {
    const limite = valor / 100
    const actual = estados[indice].tempo
    const ajustado = Math.max(1 - limite, Math.min(1 + limite, actual))
    if (ajustado !== actual) {
      decks.current?.[indice].setTempo(ajustado)
    }
    actualizar(indice, { range: valor, tempo: ajustado })
  }

  /** Pasar a otro modelo sin parar la musica: lo que suena sigue sonando y
   *  solo cambia lo que el modelo nuevo hace distinto. */
  function cambiarEquipo(id: string) {
    const nuevo = EQUIPOS.find((e) => e.id === id)
    if (!nuevo || nuevo.id === equipo.id) return
    setEquipo(nuevo)
    equipoRef.current = nuevo
    // Si la mesa nueva no tiene el efecto encendido, se apaga
    if (colorFx && !nuevo.colorFx.includes(colorFx)) setColorFx(null)
    guardarEquipo(nuevo)
    estados.forEach((estado, i) => {
      const indice = i as 0 | 1
      const range = rangoCercano(nuevo, estado.range)
      const limite = range / 100
      const tempo = Math.max(1 - limite, Math.min(1 + limite, estado.tempo))
      if (tempo !== estado.tempo) decks.current?.[indice].setTempo(tempo)
      // Los hot cues que caben se conservan; los que sobran se pierden
      const cues = Array.from({ length: nuevo.hotCues }, (_, k) => estado.cues[k] ?? null)
      actualizar(indice, { range, tempo, cues })
      // La rueda de una mesa no significa lo mismo en la otra: vuelve al centro
      decks.current?.[indice].colorFx.aplicar(null, 0, 0.5)
      actualizar(indice, { color: 0 })
      for (const banda of Object.keys(estado.eq) as EqBand[]) {
        decks.current?.[indice].setEq(banda, eqDb(estado.eq[banda], nuevo.eqMinDb, nuevo.eqMaxDb))
      }
    })
  }

  /** Pone el SOUND COLOR FX de un canal como dicen la mesa y su rueda. Con
   *  una rueda CFX de controladora no hay botones: siempre es un filtro. */
  function aplicarColor(indice: 0 | 1, efecto: ColorFxId | null, color: number, param: number) {
    const cfx = equipoRef.current.cfx
    // PARAMETER va de -1 a 1 como todas las ruedas; el efecto lo quiere de 0 a 1
    decks.current?.[indice].colorFx.aplicar(cfx ? 'filter' : efecto, color, cfx ? 0.2 : (param + 1) / 2)
  }

  function elegirColorFx(id: ColorFxId) {
    // Pulsar el que ya esta encendido lo apaga, como en la DJM
    const nuevo = colorFx === id ? null : id
    setColorFx(nuevo)
    ;([0, 1] as const).forEach((i) => aplicarColor(i, nuevo, estados[i].color, parametro))
  }

  function girarColor(indice: 0 | 1, valor: number) {
    actualizar(indice, { color: valor })
    aplicarColor(indice, colorFx, valor, parametro)
  }

  function girarParametro(valor: number) {
    setParametro(valor)
    ;([0, 1] as const).forEach((i) => aplicarColor(i, colorFx, estados[i].color, valor))
  }

  // El DUB ECHO va a tempo de lo que suena en cada plato
  const bpmA = sonandoA(0)
  const bpmB = sonandoA(1)
  useEffect(() => {
    decks.current?.[0].colorFx.setBpm(bpmA)
    decks.current?.[1].colorFx.setBpm(bpmB)
  }, [bpmA, bpmB])

  const listaVisible = crateTracks ?? tracks

  // El intercambio se cuenta al tempo de lo que suena; si suenan los dos,
  // estaran igualados o casi
  const bpmMezcla =
    ([0, 1] as const).map((i) => (estados[i].playing ? sonandoA(i) : null)).find((v) => v) ??
    sonandoA(0) ??
    sonandoA(1) ??
    BPM_POR_DEFECTO
  const segundosIntercambio = (compases * 4 * 60) / bpmMezcla
  const sinDiferencia = (banda: EqBand) => estados[0].eq[banda] === estados[1].eq[banda]

  return (
    <div className="stack">
      <div className="mixer__cabecera">
        <h1>Mesa de mezclas</h1>
        <label className="field mixer__equipo">
          <span>Equipo que se simula</span>
          <select value={equipo.id} onChange={(e) => cambiarEquipo(e.target.value)}>
            {EQUIPOS.map((e) => (
              <option key={e.id} value={e.id}>
                {e.nombre}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">
        Dos platos con crossfader para practicar transiciones con tu propia
        biblioteca. El tempo cambia el tono, como en un plato de verdad. No sustituye
        a rekordbox ni a Mixxx: para el bolo, exporta el crate a un USB.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <SyncView
        decks={[
          { label: 'A', loaded: estados[0].track !== null && !estados[0].loading, ...estados[0], data: estados[0].waveform },
          { label: 'B', loaded: estados[1].track !== null && !estados[1].loading, ...estados[1], data: estados[1].waveform },
        ]}
      />

      <div className="mixer">
        <DeckPanel
          label="A"
          {...estados[0]}
          otherBpm={sonandoA(1)}
          onMatch={() => igualar(0)}
          ranges={equipo.rangosTempo}
          onRange={(v) => cambiarRango(0, v)}
          onResetTempo={() => tempoOriginal(0)}
          onPlayPause={() => alternar(0)}
          onSeek={(s) => {
            decks.current?.[0].seek(s)
            actualizar(0, { position: s })
          }}
          onTempo={(v) => {
            decks.current?.[0].setTempo(v)
            actualizar(0, { tempo: v })
          }}
          onCueDown={() => pulsarCue(0)}
          onNudge={(f) => empujar(0, f)}
          onDownbeat={() => marcarUno(0)}
          onCueUp={() => soltarCue(0)}
          onCue={(p) => pulsarPad(0, p)}
          onClearCue={(p) => {
            const nuevos = [...estados[0].cues]
            nuevos[p] = null
            actualizar(0, { cues: nuevos })
          }}
        />

        <div className="crossfader card">
          {/* Los canales, como en una mesa Pioneer: ecualizador arriba y fader
              debajo, y los dos pasan despues por el crossfader. */}
          <div className="channels">
            {([0, 1] as const).map((indice) => (
              <div key={indice} className="channel">
                <span className="channel__label">{indice === 0 ? 'A' : 'B'}</span>
                {EQ.map(({ band, label }) => (
                  <Knob
                    key={band}
                    label={label}
                    color={COLOR_BANDA[band]}
                    value={estados[indice].eq[band]}
                    valueText={textoDb(estados[indice].eq[band], equipo)}
                    onChange={(v) => {
                      // La mano manda sobre un barrido en marcha
                      pararBarrido(band)
                      cambiarEq(indice, band, v)
                    }}
                  />
                ))}
                {equipo.cfx && (
                  <Knob
                    label="CFX"
                    color="#4fc3f7"
                    value={estados[indice].color}
                    valueText={
                      estados[indice].color === 0
                        ? 'Sin filtro'
                        : estados[indice].color < 0
                          ? `Quita agudos ${Math.round(-estados[indice].color * 100)}`
                          : `Quita graves ${Math.round(estados[indice].color * 100)}`
                    }
                    onChange={(v) => girarColor(indice, v)}
                  />
                )}
                {equipo.colorFx.length > 0 && (
                  <Knob
                    label="COLOR"
                    color={colorFx ? '#f5a623' : '#5b6574'}
                    value={estados[indice].color}
                    valueText={
                      colorFx
                        ? `${COLOR_FX.find((f) => f.id === colorFx)?.label} ${Math.round(estados[indice].color * 100)}`
                        : 'Sin efecto elegido'
                    }
                    onChange={(v) => girarColor(indice, v)}
                  />
                )}
                <input
                  type="range"
                  className="channel__fader"
                  min={0}
                  max={1}
                  step={0.01}
                  value={estados[indice].volume}
                  aria-label={`Volumen del plato ${indice === 0 ? 'A' : 'B'}`}
                  onChange={(e) => cambiarVolumen(indice, Number(e.target.value))}
                />
                <span className="channel__value">{Math.round(estados[indice].volume * 100)}</span>
              </div>
            ))}
          </div>

          {equipo.colorFx.length > 0 && (
            <div className="colorfx">
              <span className="crossfader__label">Sound Color FX</span>
              <div className="colorfx__botones">
                {COLOR_FX.filter((f) => equipo.colorFx.includes(f.id)).map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    className={colorFx === f.id ? 'colorfxbtn colorfxbtn--on' : 'colorfxbtn'}
                    aria-pressed={colorFx === f.id}
                    title={f.ayuda}
                    onClick={() => elegirColorFx(f.id)}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
              <Knob
                label="PARAMETER"
                color="#f5a623"
                value={parametro}
                valueText={`${Math.round(((parametro + 1) / 2) * 100)} %`}
                onChange={girarParametro}
              />
              <p className="muted colorfx__ayuda">
                {colorFx
                  ? COLOR_FX.find((f) => f.id === colorFx)?.ayuda
                  : 'Elige un efecto y gira la rueda COLOR de cada canal. En el centro no suena.'}
              </p>
            </div>
          )}

          {/* Intercambio de ecualizador: lo que en la mesa se hace con dos manos */}
          <div className="swap">
            <span className="crossfader__label">Intercambiar entre A y B</span>
            <div className="swap__bands">
              {EQ.map(({ band, label }) => (
                <button
                  key={band}
                  type="button"
                  className={barriendo[band] ? 'swapbtn swapbtn--running' : 'swapbtn'}
                  style={{ '--band': COLOR_BANDA[band] } as CSSProperties}
                  disabled={sinDiferencia(band) && !barriendo[band]}
                  title={
                    sinDiferencia(band)
                      ? `Los ${label.toLowerCase()} de A y B estan igual: no hay nada que intercambiar`
                      : `Baja los ${label.toLowerCase()} del canal que los tiene subidos y sube los del otro`
                  }
                  onClick={() => intercambiar(band, segundosIntercambio)}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                className="swapbtn swapbtn--all"
                disabled={EQ.every(({ band }) => sinDiferencia(band))}
                title="Intercambia las tres bandas a la vez"
                onClick={() => EQ.forEach(({ band }) => intercambiar(band, segundosIntercambio))}
              >
                Todo
              </button>
            </div>
            <div className="swap__speed">
              {VELOCIDADES.map((opcion) => (
                <button
                  key={opcion}
                  type="button"
                  className={opcion === compases ? 'rangebtn rangebtn--on' : 'rangebtn'}
                  title={
                    opcion === 0
                      ? 'Cambio seco, de golpe'
                      : `${opcion} ${opcion === 1 ? 'compas' : 'compases'}: ${((opcion * 4 * 60) / bpmMezcla).toFixed(1)} s a ${bpmMezcla.toFixed(0)} BPM`
                  }
                  onClick={() => setCompases(opcion)}
                >
                  {opcion === 0 ? 'Corte' : opcion}
                </button>
              ))}
              <span className="muted">{compases === 0 ? 'de golpe' : compases === 1 ? 'compas' : 'compases'}</span>
            </div>
          </div>

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
          ranges={equipo.rangosTempo}
          onRange={(v) => cambiarRango(1, v)}
          onResetTempo={() => tempoOriginal(1)}
          onPlayPause={() => alternar(1)}
          onSeek={(s) => {
            decks.current?.[1].seek(s)
            actualizar(1, { position: s })
          }}
          onTempo={(v) => {
            decks.current?.[1].setTempo(v)
            actualizar(1, { tempo: v })
          }}
          onCueDown={() => pulsarCue(1)}
          onNudge={(f) => empujar(1, f)}
          onDownbeat={() => marcarUno(1)}
          onCueUp={() => soltarCue(1)}
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
