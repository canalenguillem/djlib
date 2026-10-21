/** Rejilla de tiempos, la de las lineas de la pantalla del CDJ: una por golpe
 *  y en rojo la primera de cada compas. Con las dos rejillas a la vista se ve
 *  si los platos van a la par.
 *
 *  El BPM de la biblioteca es un entero, y eso no basta: 128 contra 128,3 son
 *  casi dos tiempos de desfase al final de un tema de cuatro minutos. Aqui se
 *  afina a partir de la onda de bajos, que es donde estan los bombos.
 */

import type { DeckWaveformData } from './waveform'

export interface BeatGrid {
  /** Tempo afinado, con decimales. */
  bpm: number
  /** Segundo del tema en el que cae un primer tiempo de compas. La rejilla
   *  sigue hacia delante y hacia atras cada 60/bpm segundos. */
  first: number
}

// Tiempos por compas: todo lo que se pincha en una cabina va en 4/4
export const BEATS_PER_BAR = 4

// Divisiones de un tiempo al buscar la fase: a 128 BPM, unos 5 ms cada una
const FASES = 96

/** Donde empiezan los golpes de bombo: subidas de la energia de los graves. */
function arranques(data: DeckWaveformData): Float32Array {
  const graves = data.low
  const salida = new Float32Array(graves.length)
  for (let i = 1; i < graves.length; i++) salida[i] = Math.max(0, graves[i] - graves[i - 1])
  return salida
}

/** Que tal encaja un tempo: se pliegan todos los golpes sobre un solo tiempo y
 *  se mira cuanto se amontonan en la misma fase. Con el tempo bueno caen
 *  todos juntos; con uno malo se reparten. */
function encaje(golpes: Float32Array, indices: Int32Array, rate: number, bpm: number) {
  const periodo = (60 * rate) / bpm
  const histograma = new Float32Array(FASES)
  for (const i of indices) {
    const fase = (i / periodo) % 1
    histograma[Math.floor(fase * FASES)] += golpes[i]
  }
  let mejor = -1
  let fase = 0
  for (let k = 0; k < FASES; k++) {
    // Se suman los vecinos para que un golpe a caballo entre dos casillas
    // cuente entero
    const v = histograma[(k + FASES - 1) % FASES] + histograma[k] + histograma[(k + 1) % FASES]
    if (v > mejor) {
      mejor = v
      fase = k
    }
  }
  return { puntuacion: mejor, fase: (fase + 0.5) / FASES }
}

function buscar(
  golpes: Float32Array,
  indices: Int32Array,
  rate: number,
  desde: number,
  hasta: number,
  paso: number,
) {
  let mejor = { bpm: desde, puntuacion: -1, fase: 0 }
  for (let bpm = desde; bpm <= hasta + 1e-9; bpm += paso) {
    const r = encaje(golpes, indices, rate, bpm)
    if (r.puntuacion > mejor.puntuacion) mejor = { bpm, ...r }
  }
  return mejor
}

/** Calcula la rejilla de un tema. `bpmAproximado` es el de la biblioteca: si
 *  no hay, se busca entre 70 y 180, que es mas lento. */
export function detectBeatGrid(data: DeckWaveformData, bpmAproximado: number | null): BeatGrid | null {
  const golpes = arranques(data)
  // Solo los golpes claros: los pequenos temblores de la onda no dicen nada
  let maximo = 0
  for (const v of golpes) if (v > maximo) maximo = v
  if (maximo === 0) return null
  const umbral = maximo * 0.15
  const lista: number[] = []
  for (let i = 0; i < golpes.length; i++) if (golpes[i] >= umbral) lista.push(i)
  if (lista.length < 16) return null
  const indices = Int32Array.from(lista)
  const rate = data.rate

  let aprox = bpmAproximado
    ? buscar(golpes, indices, rate, bpmAproximado - 0.6, bpmAproximado + 0.6, 0.01)
    : buscar(golpes, indices, rate, 70, 180, 0.05)
  aprox = buscar(golpes, indices, rate, aprox.bpm - 0.02, aprox.bpm + 0.02, 0.001)

  const periodo = 60 / aprox.bpm
  // La fase sale en fraccion de tiempo; el primer golpe fuerte del tema se toma
  // como el 1 del compas, que es como suelen empezar los temas de club. Si no
  // acierta, se corrige con "Marcar el 1 aqui".
  const fase = aprox.fase * periodo
  const primerGolpe = lista.find((i) => golpes[i] >= maximo * 0.4) ?? lista[0]
  const t = primerGolpe / rate
  const first = fase + Math.round((t - fase) / periodo) * periodo
  return { bpm: aprox.bpm, first }
}

/** En que tiempo va el tema: 0 es el primer tiempo del compas que contiene
 *  `first`, 1,5 es a medio camino entre el segundo y el tercero... */
export function beatPosition(grid: BeatGrid, segundos: number): number {
  return ((segundos - grid.first) * grid.bpm) / 60
}

/** Mueve la rejilla para que el golpe mas cercano a `segundos` sea el 1. */
export function setDownbeat(grid: BeatGrid, segundos: number): BeatGrid {
  const periodo = 60 / grid.bpm
  return { ...grid, first: grid.first + Math.round((segundos - grid.first) / periodo) * periodo }
}

/** Resto que siempre sale positivo, tambien con negativos. */
export function modulo(a: number, n: number): number {
  return ((a % n) + n) % n
}
