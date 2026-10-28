/** Equipos que simula el mezclador. Cada uno guarda lo que cambia de un
 *  modelo a otro; lo demas (motor de audio, onda, rejilla) es comun. Para
 *  anadir un modelo basta con anadir una entrada aqui y, si trae algo que los
 *  demas no tienen, ensenarle esa pieza al mezclador. */

import type { ColorFxId } from './colorFx'

export interface Equipo {
  id: string
  /** Lo que sale en el selector. */
  nombre: string
  reproductor: string
  mezclador: string
  /** Recorridos del fader de tempo, en %. 100 es el WIDE de Pioneer. */
  rangosTempo: number[]
  rangoInicial: number
  /** Botones de hot cue por plato. */
  hotCues: number
  /** Recorrido de cada potenciometro del ecualizador. */
  eqMinDb: number
  eqMaxDb: number
  /** Botones de SOUND COLOR FX de la mesa; vacio si no tiene. */
  colorFx: ColorFxId[]
  /** Rueda CFX por canal, la de las controladoras: un filtro sin botones. */
  cfx: boolean
}

export const EQUIPOS: Equipo[] = [
  {
    id: 'pioneer-nxs2',
    nombre: 'Pioneer CDJ-2000NXS2 + DJM-900NXS2',
    reproductor: 'CDJ-2000NXS2',
    mezclador: 'DJM-900NXS2',
    // TEMPO RANGE del CDJ: ±6, ±10, ±16 y WIDE
    rangosTempo: [6, 10, 16, 100],
    rangoInicial: 10,
    // Hot cues A a H
    hotCues: 8,
    // EQ de 3 bandas de la DJM: casi quita la banda y refuerza un poco
    eqMinDb: -26,
    eqMaxDb: 6,
    colorFx: ['space', 'dubEcho', 'sweep', 'noise', 'crush', 'filter'],
    cfx: false,
  },
  {
    id: 'pioneer-flx4',
    nombre: 'Pioneer DDJ-FLX4',
    reproductor: 'DDJ-FLX4',
    mezclador: 'DDJ-FLX4',
    // Los recorridos que da SHIFT + BEAT SYNC con Mixxx
    rangosTempo: [6, 10, 16, 25],
    rangoInicial: 10,
    // Ocho pads por plato en modo HOT CUE
    hotCues: 8,
    // Sin dato del fabricante: el mismo EQ que la DJM mientras no se confirme
    eqMinDb: -26,
    eqMaxDb: 6,
    colorFx: [],
    cfx: true,
  },
]

const CLAVE = 'mixer.equipo'

export function equipoGuardado(): Equipo {
  let id: string | null = null
  try {
    id = localStorage.getItem(CLAVE)
  } catch {
    // Sin almacenamiento se empieza con el primero
  }
  return EQUIPOS.find((e) => e.id === id) ?? EQUIPOS[0]
}

export function guardarEquipo(equipo: Equipo): void {
  try {
    localStorage.setItem(CLAVE, equipo.id)
  } catch {
    // Solo se pierde el recordarlo
  }
}

/** "±10%", o "WIDE" para el recorrido entero. */
export function textoRango(rango: number): string {
  return rango >= 100 ? 'WIDE' : `±${rango}%`
}

/** El recorrido de este equipo mas parecido al que habia: al cambiar de
 *  modelo, el plato no deberia pegar un salto de tempo si se puede evitar. */
export function rangoCercano(equipo: Equipo, rango: number): number {
  return equipo.rangosTempo.reduce((mejor, r) => (Math.abs(r - rango) < Math.abs(mejor - rango) ? r : mejor))
}
