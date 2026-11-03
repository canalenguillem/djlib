/** La mesa que simula el mezclador: unos platos tipo CDJ y una mesa tipo DJM.
 *  Antes se podia elegir entre varios modelos, pero cambiaban detalles que no
 *  ayudan a practicar; aqui queda una sola con lo mas util de cada uno. */

import type { ColorFxId } from './colorFx'

export interface Equipo {
  /** Recorridos del fader de tempo, en %. 100 es el WIDE de Pioneer. */
  rangosTempo: number[]
  rangoInicial: number
  /** Botones de hot cue por plato. */
  hotCues: number
  /** Recorrido de cada potenciometro del ecualizador. */
  eqMinDb: number
  eqMaxDb: number
  /** Botones de SOUND COLOR FX de la mesa. */
  colorFx: ColorFxId[]
}

export const MESA: Equipo = {
  // TEMPO RANGE del CDJ: ±6, ±10, ±16 y WIDE
  rangosTempo: [6, 10, 16, 100],
  rangoInicial: 10,
  // Hot cues A a H
  hotCues: 8,
  // EQ de 3 bandas de la DJM: casi quita la banda y refuerza un poco
  eqMinDb: -26,
  eqMaxDb: 6,
  colorFx: ['space', 'dubEcho', 'sweep', 'noise', 'crush', 'filter'],
}

/** "±10%", o "WIDE" para el recorrido entero. */
export function textoRango(rango: number): string {
  return rango >= 100 ? 'WIDE' : `±${rango}%`
}

/** El recorrido mas corto en el que cabe un cambio de tempo: SYNC no debe
 *  fallar porque el fader se quede corto. */
export function rangoQueCabe(equipo: Equipo, actual: number, ratio: number): number {
  const necesario = Math.abs(ratio - 1) * 100
  if (necesario <= actual + 1e-9) return actual
  return equipo.rangosTempo.find((r) => necesario <= r + 1e-9) ?? equipo.rangosTempo[equipo.rangosTempo.length - 1]
}
