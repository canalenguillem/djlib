/** SOUND COLOR FX de una mesa Pioneer DJM: un efecto elegido con un boton,
 *  que cada canal aplica con su rueda COLOR. La rueda en el centro no hace
 *  nada; a un lado y a otro el efecto cambia de caracter, y cuanto mas se gira
 *  mas se nota. La rueda PARAMETER, comun a la mesa, retoca el efecto.
 *
 *  Las recetas se han hecho a oido a partir del manual de la DJM-900NXS2: se
 *  parecen, no son el DSP de Pioneer.
 */

export type ColorFxId = 'space' | 'dubEcho' | 'sweep' | 'noise' | 'crush' | 'filter'

export const COLOR_FX: { id: ColorFxId; label: string; ayuda: string }[] = [
  {
    id: 'space',
    label: 'SPACE',
    ayuda: 'Reverb. A la izquierda sobre graves y medios, a la derecha sobre medios y agudos. PARAMETER: lo que dura.',
  },
  {
    id: 'dubEcho',
    label: 'DUB ECHO',
    ayuda: 'Eco a tempo que se va apagando. A la izquierda oscuro, a la derecha brillante. PARAMETER: cuanto se repite.',
  },
  {
    id: 'sweep',
    label: 'SWEEP',
    ayuda: 'A la izquierda una puerta que deja solo los golpes; a la derecha un filtro de banda que barre. PARAMETER: lo cerrado.',
  },
  {
    id: 'noise',
    label: 'NOISE',
    ayuda: 'Mete ruido blanco filtrado: a la izquierda grave, a la derecha agudo. PARAMETER: el tono del ruido.',
  },
  {
    id: 'crush',
    label: 'CRUSH',
    ayuda: 'Rompe el sonido bajandole la calidad. A la derecha ademas le quita los graves. PARAMETER: lo roto.',
  },
  {
    id: 'filter',
    label: 'FILTER',
    ayuda: 'A la izquierda quita agudos (paso bajo), a la derecha quita graves (paso alto). PARAMETER: la resonancia.',
  },
]

// Con la rueda tan cerca del centro se considera apagado, como el clic de la mesa
const ZONA_MUERTA = 0.02

/** Rompe el sonido (menos bits y menos muestras) y hace de puerta (deja pasar
 *  solo lo que suena fuerte). Va en un worklet porque las dos cosas se hacen
 *  muestra a muestra y no hay nodos del navegador que lo hagan. */
const WORKLET = `
class ColorFxProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'crush', defaultValue: 0, minValue: 0, maxValue: 1 },
      { name: 'gate', defaultValue: 0, minValue: 0, maxValue: 1 },
    ]
  }
  constructor() {
    super()
    this.retenido = []
    this.cuenta = []
    this.envolvente = 0
    this.pico = 0
    this.ganancia = 1
  }
  process(inputs, outputs, parameters) {
    const entrada = inputs[0]
    const salida = outputs[0]
    if (!entrada.length) return true
    const crush = parameters.crush[0]
    const gate = parameters.gate[0]
    const bits = 16 - crush * 13
    const pasos = Math.pow(2, bits - 1)
    const sostener = 1 + Math.floor(crush * crush * 24)
    const n = entrada[0].length
    // La puerta se decide con la mezcla de los dos canales
    for (let i = 0; i < n; i++) {
      let nivel = 0
      for (let c = 0; c < entrada.length; c++) nivel = Math.max(nivel, Math.abs(entrada[c][i]))
      this.envolvente = Math.max(nivel, this.envolvente * 0.9990)
      this.pico = Math.max(this.envolvente, this.pico * 0.99998)
      const abierta = this.envolvente > this.pico * (0.15 + gate * 0.75)
      const objetivo = gate > 0 && !abierta ? 0 : 1
      this.ganancia += (objetivo - this.ganancia) * (objetivo > this.ganancia ? 0.05 : 0.002)
      for (let c = 0; c < salida.length; c++) {
        const x = (entrada[c] || entrada[0])[i]
        let y = x
        if (crush > 0) {
          this.cuenta[c] = (this.cuenta[c] || 0) + 1
          if (this.cuenta[c] >= sostener) {
            this.cuenta[c] = 0
            this.retenido[c] = Math.round(x * pasos) / pasos
          }
          y = this.retenido[c] ?? x
        }
        salida[c][i] = y * this.ganancia
      }
    }
    return true
  }
}
registerProcessor('color-fx', ColorFxProcessor)
`

const workletsCargados = new WeakMap<BaseAudioContext, Promise<void>>()

function cargarWorklet(ctx: AudioContext): Promise<void> {
  let carga = workletsCargados.get(ctx)
  if (!carga) {
    const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }))
    carga = ctx.audioWorklet.addModule(url).finally(() => URL.revokeObjectURL(url))
    workletsCargados.set(ctx, carga)
  }
  return carga
}

/** Frecuencia en escala logaritmica: de `desde` a `hasta` segun t de 0 a 1. */
function barrido(desde: number, hasta: number, t: number): number {
  return desde * Math.pow(hasta / desde, t)
}

/** Respuesta de una sala: ruido que se apaga. Sin ficheros de impulso, que
 *  pesarian mas que toda la pagina. */
function impulsoSala(ctx: AudioContext, segundos: number): AudioBuffer {
  const largo = Math.floor(ctx.sampleRate * segundos)
  const buffer = ctx.createBuffer(2, largo, ctx.sampleRate)
  for (let c = 0; c < 2; c++) {
    const datos = buffer.getChannelData(c)
    for (let i = 0; i < largo; i++) datos[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / largo, 3)
  }
  return buffer
}

function ruidoBlanco(ctx: AudioContext): AudioBuffer {
  const buffer = ctx.createBuffer(2, ctx.sampleRate * 2, ctx.sampleRate)
  for (let c = 0; c < 2; c++) {
    const datos = buffer.getChannelData(c)
    for (let i = 0; i < datos.length; i++) datos[i] = Math.random() * 2 - 1
  }
  return buffer
}

/** El efecto de un canal. Se intercala entre el ecualizador y el fader. */
export class ColorFx {
  readonly input: GainNode
  readonly output: GainNode
  private readonly ctx: AudioContext
  /** Filtro en el camino de la senal: FILTER, SWEEP y el paso alto de CRUSH. */
  private readonly filtro: BiquadFilterNode
  private procesador: AudioWorkletNode | null = null
  private readonly seco: GainNode

  private readonly envioEco: GainNode
  private readonly eco: DelayNode
  private readonly realimentacion: GainNode
  private readonly filtroEco: BiquadFilterNode

  private readonly envioSala: GainNode
  private readonly sala: ConvolverNode
  private readonly filtroSala: BiquadFilterNode
  private duracionSala = 0

  private readonly ruido: AudioBufferSourceNode
  private readonly filtroRuido: BiquadFilterNode
  private readonly volumenRuido: GainNode

  private ultimo: { efecto: ColorFxId | null; color: number; parametro: number } = {
    efecto: null,
    color: 0,
    parametro: 0.5,
  }
  /** Tempo del tema, para que el eco caiga a tiempo. */
  private bpm = 120

  constructor(ctx: AudioContext) {
    this.ctx = ctx
    this.input = ctx.createGain()
    this.output = ctx.createGain()
    this.filtro = ctx.createBiquadFilter()
    this.seco = ctx.createGain()

    // Camino principal: filtro, y el worklet cuando haya cargado
    this.input.connect(this.filtro)
    this.filtro.connect(this.seco)
    this.seco.connect(this.output)

    // Eco: se envia una parte y se realimenta pasando por un filtro, como un
    // eco de cinta que pierde brillo en cada vuelta
    this.envioEco = ctx.createGain()
    this.eco = ctx.createDelay(4)
    this.realimentacion = ctx.createGain()
    this.filtroEco = ctx.createBiquadFilter()
    this.input.connect(this.envioEco)
    this.envioEco.connect(this.eco)
    this.eco.connect(this.filtroEco)
    this.filtroEco.connect(this.realimentacion)
    this.realimentacion.connect(this.eco)
    this.filtroEco.connect(this.output)

    this.envioSala = ctx.createGain()
    this.sala = ctx.createConvolver()
    this.filtroSala = ctx.createBiquadFilter()
    this.input.connect(this.envioSala)
    this.envioSala.connect(this.sala)
    this.sala.connect(this.filtroSala)
    this.filtroSala.connect(this.output)

    this.ruido = ctx.createBufferSource()
    this.ruido.buffer = ruidoBlanco(ctx)
    this.ruido.loop = true
    this.filtroRuido = ctx.createBiquadFilter()
    this.volumenRuido = ctx.createGain()
    this.ruido.connect(this.filtroRuido)
    this.filtroRuido.connect(this.volumenRuido)
    this.volumenRuido.connect(this.output)
    this.ruido.start()

    this.aplicar(null, 0, 0.5)

    cargarWorklet(ctx)
      .then(() => {
        const nodo = new AudioWorkletNode(ctx, 'color-fx', { outputChannelCount: [2] })
        this.filtro.disconnect(this.seco)
        this.filtro.connect(nodo)
        nodo.connect(this.seco)
        this.procesador = nodo
        const { efecto, color, parametro } = this.ultimo
        this.aplicar(efecto, color, parametro)
      })
      // Sin worklet, CRUSH y la puerta de SWEEP no suenan; lo demas si
      .catch(() => undefined)
  }

  setBpm(bpm: number | null): void {
    this.bpm = bpm && bpm > 0 ? bpm : 120
    if (this.ultimo.efecto === 'dubEcho') this.aplicar(this.ultimo.efecto, this.ultimo.color, this.ultimo.parametro)
  }

  /** Coloca el efecto segun el boton elegido, la rueda COLOR (-1 a 1) y la
   *  rueda PARAMETER (0 a 1). */
  aplicar(efecto: ColorFxId | null, color: number, parametro: number): void {
    this.ultimo = { efecto, color, parametro }
    const t = this.ctx.currentTime
    const suave = 0.015
    const fijar = (p: AudioParam, v: number) => p.setTargetAtTime(v, t, suave)
    const activo = efecto !== null && Math.abs(color) > ZONA_MUERTA
    const cuanto = activo ? Math.abs(color) : 0
    const derecha = color > 0

    // Todo en reposo, y luego se enciende solo lo del efecto elegido
    this.filtro.type = 'lowpass'
    fijar(this.filtro.frequency, 22000)
    fijar(this.filtro.Q, 0.7)
    fijar(this.seco.gain, 1)
    fijar(this.envioEco.gain, 0)
    fijar(this.envioSala.gain, 0)
    fijar(this.volumenRuido.gain, 0)
    let crush = 0
    let gate = 0

    if (activo) {
      switch (efecto) {
        case 'filter':
          this.filtro.type = derecha ? 'highpass' : 'lowpass'
          fijar(this.filtro.frequency, derecha ? barrido(20, 12000, cuanto) : barrido(22000, 60, cuanto))
          fijar(this.filtro.Q, 0.7 + parametro * 12)
          break
        case 'sweep':
          if (derecha) {
            this.filtro.type = 'bandpass'
            fijar(this.filtro.frequency, barrido(150, 9000, cuanto))
            fijar(this.filtro.Q, 0.8 + parametro * 6)
          } else {
            gate = cuanto * (0.4 + parametro * 0.6)
          }
          break
        case 'space': {
          const segundos = Math.round((1 + parametro * 5) * 2) / 2
          if (segundos !== this.duracionSala) {
            this.sala.buffer = impulsoSala(this.ctx, segundos)
            this.duracionSala = segundos
          }
          this.filtroSala.type = derecha ? 'highpass' : 'lowpass'
          fijar(this.filtroSala.frequency, derecha ? 700 : 2500)
          fijar(this.envioSala.gain, cuanto * 1.4)
          // Muy girada, la sala se come un poco el sonido seco
          fijar(this.seco.gain, 1 - cuanto * 0.35)
          break
        }
        case 'dubEcho': {
          // Eco de tres cuartos de tiempo, el del dub de toda la vida
          this.eco.delayTime.setTargetAtTime(Math.min(3.9, (60 / this.bpm) * 0.75), t, 0.05)
          this.filtroEco.type = derecha ? 'highpass' : 'lowpass'
          fijar(this.filtroEco.frequency, derecha ? 900 : 1800)
          fijar(this.envioEco.gain, cuanto)
          fijar(this.realimentacion.gain, 0.35 + parametro * 0.5)
          break
        }
        case 'noise':
          this.filtroRuido.type = derecha ? 'highpass' : 'lowpass'
          fijar(this.filtroRuido.frequency, derecha ? barrido(200, 12000, cuanto) : barrido(16000, 300, cuanto))
          fijar(this.filtroRuido.Q, 0.7 + parametro * 10)
          fijar(this.volumenRuido.gain, cuanto * 0.12)
          break
        case 'crush':
          crush = cuanto * (0.5 + parametro * 0.5)
          if (derecha) {
            this.filtro.type = 'highpass'
            fijar(this.filtro.frequency, barrido(20, 2500, cuanto))
          }
          break
      }
    }

    // Al salir del eco, las repeticiones que quedan se dejan morir solas, como
    // en la mesa; las de la sala tambien, porque solo se cierra el envio
    if (efecto !== 'dubEcho') fijar(this.realimentacion.gain, 0.35 + parametro * 0.5)

    if (this.procesador) {
      fijar(this.procesador.parameters.get('crush')!, crush)
      fijar(this.procesador.parameters.get('gate')!, gate)
    }
  }

  dispose(): void {
    try {
      this.ruido.stop()
    } catch {
      // Ya estaba parado
    }
    for (const nodo of [
      this.input, this.output, this.filtro, this.seco, this.envioEco, this.eco, this.realimentacion,
      this.filtroEco, this.envioSala, this.sala, this.filtroSala, this.ruido, this.filtroRuido,
      this.volumenRuido, this.procesador,
    ]) {
      nodo?.disconnect()
    }
  }
}
