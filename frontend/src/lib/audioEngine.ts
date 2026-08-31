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

export interface DeckSnapshot {
  playing: boolean
  position: number
  duration: number
}

export class Deck {
  private readonly ctx: AudioContext
  /** Volumen del canal, lo que mueve el fader vertical. */
  readonly volume: GainNode
  /** Posicion en el crossfader; se controla desde fuera. */
  readonly crossfade: GainNode

  private buffer: AudioBuffer | null = null
  private source: AudioBufferSourceNode | null = null
  private offset = 0
  private startedAt = 0
  private rate = 1

  playing = false
  onEnded?: () => void

  constructor(destino: AudioNode) {
    this.ctx = audioContext()
    this.volume = this.ctx.createGain()
    this.crossfade = this.ctx.createGain()
    this.volume.connect(this.crossfade)
    this.crossfade.connect(destino)
  }

  get duration(): number {
    return this.buffer?.duration ?? 0
  }

  get loaded(): boolean {
    return this.buffer !== null
  }

  /** Posicion actual en segundos del propio tema, no del reloj. */
  get position(): number {
    if (!this.playing) return this.offset
    return Math.min(this.duration, this.offset + (this.ctx.currentTime - this.startedAt) * this.rate)
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
    source.playbackRate.value = this.rate
    source.connect(this.volume)
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
    // Se apunta donde vamos antes de cambiar el ritmo del reloj, o la cuenta
    // de la posicion se descuadra.
    const donde = this.position
    this.rate = valor
    if (this.playing) {
      this.offset = donde
      this.startedAt = this.ctx.currentTime
      if (this.source) this.source.playbackRate.value = valor
    }
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
