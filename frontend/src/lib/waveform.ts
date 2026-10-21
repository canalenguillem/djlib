/** Forma de onda en tres bandas, como la de los CDJ y rekordbox.
 *
 *  La de la biblioteca llega ya calculada del servidor (400 tramos por
 *  cancion). La de la mesa de mezclas se calcula aqui, a partir del audio que
 *  el plato ya tiene descodificado: necesita mucha mas resolucion, porque la
 *  vista de detalle ensena solo unos segundos alrededor de la aguja.
 */

// Los colores del modo "3 bandas": graves en azul, medios en ambar y agudos en
// blanco, pintados en ese orden uno encima de otro. La ganancia hace que cada
// banda quede dentro de la anterior, como en el CDJ: a escala real los medios
// de una voz tapan los graves y el azul no se veria.
export const BANDS = [
  { key: 'low', color: '#2b6dff', gain: 1 },
  { key: 'mid', color: '#f5a524', gain: 0.6 },
  { key: 'high', color: '#f4f4f4', gain: 0.35 },
] as const

export type BandKey = (typeof BANDS)[number]['key']

/** Un valor de 0 a 255 por tramo y banda. */
export type BandValues = Record<BandKey, ArrayLike<number>>

/** Onda de un plato: `rate` tramos por segundo de cancion. */
export interface DeckWaveformData extends BandValues {
  rate: number
}

/** Ajusta el tamano interno del canvas a su tamano en pantalla, para que no
 *  salga borroso en pantallas de alta densidad. Devuelve el contexto listo. */
export function prepareCanvas(canvas: HTMLCanvasElement) {
  const ratio = window.devicePixelRatio || 1
  const width = Math.round(canvas.clientWidth * ratio)
  const height = Math.round(canvas.clientHeight * ratio)
  if (!width || !height) return null
  // Cambiar el tamano borra el canvas y es caro: solo si ha cambiado de verdad
  if (canvas.width !== width) canvas.width = width
  if (canvas.height !== height) canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.clearRect(0, 0, width, height)
  return { ctx, width, height }
}

/** Pinta las tres bandas en espejo sobre el eje horizontal. `range` dice que
 *  tramos le tocan a cada columna de pixeles; se toma el maximo, para que al
 *  juntar varios no se pierda ningun golpe. */
export function drawBands(
  ctx: CanvasRenderingContext2D,
  data: BandValues,
  width: number,
  height: number,
  range: (x: number) => [number, number],
) {
  const middle = height / 2
  for (const band of BANDS) {
    const values = data[band.key]
    ctx.fillStyle = band.color
    for (let x = 0; x < width; x++) {
      const [start, end] = range(x)
      let peak = 0
      for (let i = Math.max(0, start); i < end && i < values.length; i++) {
        if (values[i] > peak) peak = values[i]
      }
      const half = (peak / 255) * band.gain * middle
      if (half > 0) ctx.fillRect(x, middle - half, 1, half * 2)
    }
  }
}

// --- Analisis en el navegador ----------------------------------------------

// Los mismos cortes que usa el servidor, para que las dos ondas se parezcan
const LOW_CUT = 200
const HIGH_CUT = 2500
// Basta para separar las bandas, y con un tema de cuatro minutos se queda en
// unos pocos MB en vez de los 80 que ocupa a 44,1 kHz.
const ANALYSIS_RATE = 11025
/** Tramos por segundo: a 8 s en pantalla, uno por pixel en un plato normal. */
export const DECK_WAVEFORM_RATE = 150

function filtro(ctx: BaseAudioContext, type: BiquadFilterType, frequency: number) {
  const nodo = ctx.createBiquadFilter()
  nodo.type = type
  nodo.frequency.value = frequency
  return nodo
}

/** Encadena filtros: cada par duplica la pendiente de corte. */
function cadena(origen: AudioNode, nodos: BiquadFilterNode[]): AudioNode {
  return nodos.reduce<AudioNode>((anterior, nodo) => {
    anterior.connect(nodo)
    return nodo
  }, origen)
}

/** Calcula la onda de un tema ya descodificado. Se reproduce en un contexto
 *  sin salida, mas rapido que el tiempo real, con las tres bandas separadas
 *  en tres canales. */
export async function analyzeBuffer(
  buffer: AudioBuffer,
  rate = DECK_WAVEFORM_RATE,
): Promise<DeckWaveformData> {
  const frames = Math.ceil(buffer.duration * ANALYSIS_RATE)
  const ctx = new OfflineAudioContext(3, frames, ANALYSIS_RATE)
  const source = ctx.createBufferSource()
  source.buffer = buffer

  // Cada entrada del merger es mono: el estereo se mezcla solo
  const merger = ctx.createChannelMerger(3)
  cadena(source, [filtro(ctx, 'lowpass', LOW_CUT), filtro(ctx, 'lowpass', LOW_CUT)]).connect(merger, 0, 0)
  cadena(source, [filtro(ctx, 'highpass', LOW_CUT), filtro(ctx, 'lowpass', HIGH_CUT)]).connect(merger, 0, 1)
  cadena(source, [filtro(ctx, 'highpass', HIGH_CUT), filtro(ctx, 'highpass', HIGH_CUT)]).connect(merger, 0, 2)
  merger.connect(ctx.destination)
  source.start()

  const render = await ctx.startRendering()
  const tramos = Math.max(1, Math.ceil(buffer.duration * rate))
  const porTramo = render.length / tramos

  // Energia RMS de cada tramo, banda a banda
  const energias = [0, 1, 2].map((canal) => {
    const muestras = render.getChannelData(canal)
    const salida = new Float32Array(tramos)
    for (let i = 0; i < tramos; i++) {
      const inicio = Math.floor(i * porTramo)
      const fin = Math.max(inicio + 1, Math.floor((i + 1) * porTramo))
      let suma = 0
      for (let j = inicio; j < fin && j < muestras.length; j++) suma += muestras[j] * muestras[j]
      salida[i] = Math.sqrt(suma / (fin - inicio))
    }
    return salida
  })

  // Las tres con el mismo maximo, para que conserven su peso real; la raiz
  // levanta los pasajes flojos. Igual que en el servidor.
  let pico = 0
  for (const banda of energias) for (const v of banda) if (v > pico) pico = v
  const [low, mid, high] = energias.map((banda) => {
    const bytes = new Uint8Array(banda.length)
    if (pico > 0) for (let i = 0; i < banda.length; i++) bytes[i] = Math.round(Math.sqrt(banda[i] / pico) * 255)
    return bytes
  })
  return { rate, low, mid, high }
}
