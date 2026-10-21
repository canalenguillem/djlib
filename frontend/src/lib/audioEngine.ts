/** Motor de audio de la mesa de mezclas.
 *
 *  Se usa AudioBufferSourceNode y no un <audio> por dos motivos:
 *
 *  - Los saltos a un punto de cue tienen que ser inmediatos y exactos. Con un
 *    <audio> el salto depende del buffer de red y se nota el retardo.
 *  - Al cambiar el tempo, el tono debe cambiar con el, como en un plato de
 *    verdad. Los elementos <audio> corrigen el tono por defecto, que es lo
 *    contrario de lo que espera un DJ.
 *
 *  El precio es la memoria: un tema de cuatro minutos descodificado ocupa unos
 *  80 MB por plato. En un portatil no es problema; en un movil si, y por eso
 *  esta pantalla esta pensada para el escritorio.
 */

let contexto: AudioContext | null = null

export function audioContext(): AudioContext {
  if (contexto === null || contexto.state === 'closed') {
    contexto = new AudioContext()
  }
  return contexto
}

/** Las tres bandas del ecualizador de canal, de arriba abajo en la mesa. */
export type EqBand = 'high' | 'mid' | 'low'

/** Recorrido de cada potenciometro, el de una mesa Pioneer DJM: casi elimina
 *  la banda girandolo del todo a la izquierda y la refuerza un poco a la
 *  derecha. */
export const EQ_MIN_DB = -26
export const EQ_MAX_DB = 6

/** Posicion del potenciometro (-1 a 1, 0 a las 12) a decibelios. La escala no
 *  es simetrica, como en la mesa: el centro es 0 dB. */
export function eqDb(posicion: number): number {
  return posicion < 0 ? -posicion * EQ_MIN_DB : posicion * EQ_MAX_DB
}

export interface DeckSnapshot {
  playing: boolean
  position: number
  duration: number
}

export class Deck {
  private readonly ctx: AudioContext
  /** Ecualizador del canal. Los cortes son los de la forma de onda, asi que
   *  quitar los bajos quita justo lo que se pinta en azul. */
  private readonly eq: Record<EqBand, BiquadFilterNode>
  /** Volumen del canal, lo que mueve el fader vertical. */
  readonly volume: GainNode
  /** Posicion en el crossfader; se controla desde fuera. */
  readonly crossfade: GainNode

  private buffer: AudioBuffer | null = null
  private source: AudioBufferSourceNode | null = null
  private offset = 0
  private startedAt = 0
  private rate = 1
  /** Empujon temporal del jog, encima del tempo: 1 es sin tocar. */
  private bend = 1

  playing = false
  onEnded?: () => void

  constructor(destino: AudioNode) {
    this.ctx = audioContext()
    this.eq = {
      low: this.filtro('lowshelf', 200),
      mid: this.filtro('peaking', 1000),
      high: this.filtro('highshelf', 2500),
    }
    // Un medio ancho, que cubra la banda entre los otros dos
    this.eq.mid.Q.value = 0.7
    this.volume = this.ctx.createGain()
    this.crossfade = this.ctx.createGain()
    this.eq.low.connect(this.eq.mid)
    this.eq.mid.connect(this.eq.high)
    this.eq.high.connect(this.volume)
    this.volume.connect(this.crossfade)
    this.crossfade.connect(destino)
  }

  get duration(): number {
    return this.buffer?.duration ?? 0
  }

  get loaded(): boolean {
    return this.buffer !== null
  }

  /** El audio descodificado, para dibujar su onda. */
  get audio(): AudioBuffer | null {
    return this.buffer
  }

  /** Posicion actual en segundos del propio tema, no del reloj. */
  get position(): number {
    if (!this.playing) return this.offset
    return Math.min(this.duration, this.offset + (this.ctx.currentTime - this.startedAt) * this.rate * this.bend)
  }

  async load(datos: ArrayBuffer): Promise<void> {
    this.stop()
    this.buffer = await this.ctx.decodeAudioData(datos)
    this.offset = 0
  }

  play(): void {
    if (!this.buffer || this.playing) return
    void this.ctx.resume()

    const source = this.ctx.createBufferSource()
    source.buffer = this.buffer
    source.playbackRate.value = this.rate * this.bend
    source.connect(this.eq.low)
    source.onended = () => {
      // onended salta tanto al terminar como al parar nosotros: solo interesa
      // el primer caso.
      if (this.source === source && this.playing) {
        this.playing = false
        this.offset = this.duration
        this.onEnded?.()
      }
    }
    source.start(0, Math.min(this.offset, this.duration))

    this.source = source
    this.startedAt = this.ctx.currentTime
    this.playing = true
  }

  pause(): void {
    if (!this.playing) return
    const donde = this.position
    this.stop()
    this.offset = donde
  }

  /** Va a un punto concreto, siguiendo o no segun estuviera. */
  seek(segundos: number): void {
    const destino = Math.max(0, Math.min(segundos, this.duration))
    const sonaba = this.playing
    this.stop()
    this.offset = destino
    if (sonaba) this.play()
  }

  setTempo(valor: number): void {
    this.cambiarVelocidad(() => (this.rate = valor))
  }

  /** Frena o acelera un momento sin tocar el tempo, como al rozar el borde
   *  del jog: sirve para cuadrar los golpes cuando ya van al mismo BPM. */
  setBend(valor: number): void {
    this.cambiarVelocidad(() => (this.bend = valor))
  }

  private cambiarVelocidad(cambio: () => void): void {
    // Se apunta donde vamos antes de cambiar el ritmo del reloj, o la cuenta
    // de la posicion se descuadra.
    const donde = this.position
    cambio()
    if (this.playing) {
      this.offset = donde
      this.startedAt = this.ctx.currentTime
      if (this.source) this.source.playbackRate.value = this.rate * this.bend
    }
  }

  /** Ganancia de una banda, en decibelios. */
  setEq(banda: EqBand, db: number): void {
    this.eq[banda].gain.setTargetAtTime(db, this.ctx.currentTime, 0.01)
  }

  private filtro(type: BiquadFilterType, frequency: number): BiquadFilterNode {
    const nodo = this.ctx.createBiquadFilter()
    nodo.type = type
    nodo.frequency.value = frequency
    return nodo
  }

  setVolume(valor: number): void {
    this.volume.gain.setTargetAtTime(valor, this.ctx.currentTime, 0.01)
  }

  private stop(): void {
    if (this.source) {
      this.source.onended = null
      try {
        this.source.stop()
      } catch {
        // Ya estaba parado
      }
      this.source.disconnect()
      this.source = null
    }
    this.playing = false
  }

  dispose(): void {
    this.stop()
    this.buffer = null
    for (const nodo of Object.values(this.eq)) nodo.disconnect()
    this.volume.disconnect()
    this.crossfade.disconnect()
  }
}

/** Curva de potencia constante: con el fader en el centro suenan los dos a la
 *  vez sin que baje el volumen general, que es lo que pasaria con una mezcla
 *  lineal. */
export function crossfadeGains(posicion: number): [number, number] {
  const x = Math.max(0, Math.min(1, posicion))
  return [Math.cos((x * Math.PI) / 2), Math.cos(((1 - x) * Math.PI) / 2)]
}

export function formatClock(segundos: number): string {
  if (!Number.isFinite(segundos) || segundos < 0) return '0:00'
  const m = Math.floor(segundos / 60)
  const s = Math.floor(segundos % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
