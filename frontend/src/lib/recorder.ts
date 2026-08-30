/** Grabacion desde el microfono, con las diferencias entre navegadores
 *  encapsuladas aqui para que la pantalla solo se ocupe de la interfaz. */

// Por orden de preferencia. Opus comprime mucho mejor, lo que importa cuando
// se sube desde datos moviles; Safari en iOS solo admite mp4.
const FORMATS: Array<{ mime: string; extension: string }> = [
  { mime: 'audio/webm;codecs=opus', extension: 'webm' },
  { mime: 'audio/webm', extension: 'webm' },
  { mime: 'audio/ogg;codecs=opus', extension: 'ogg' },
  { mime: 'audio/mp4', extension: 'm4a' },
  { mime: 'audio/aac', extension: 'aac' },
]

export class RecorderError extends Error {
  readonly kind: 'insecure' | 'denied' | 'no-mic' | 'unsupported' | 'unknown'

  constructor(kind: RecorderError['kind'], message: string) {
    super(message)
    this.kind = kind
  }
}

export function pickFormat(): { mime: string; extension: string } | null {
  if (typeof MediaRecorder === 'undefined') return null
  for (const format of FORMATS) {
    if (MediaRecorder.isTypeSupported(format.mime)) return format
  }
  return null
}

export function checkSupport(): RecorderError | null {
  // getUserMedia solo existe en contextos seguros: HTTPS o localhost. Por IP y
  // sin TLS el navegador ni siquiera ofrece el permiso.
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    return new RecorderError(
      'insecure',
      'El navegador solo da acceso al microfono por HTTPS. Entra por el dominio ' +
        'seguro en vez de por la IP.',
    )
  }
  if (pickFormat() === null) {
    return new RecorderError('unsupported', 'Este navegador no permite grabar audio.')
  }
  return null
}

function translateError(error: unknown): RecorderError {
  const name = (error as { name?: string })?.name
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return new RecorderError(
      'denied',
      'Has denegado el acceso al microfono. Dale permiso desde el candado de la ' +
        'barra de direcciones y vuelve a intentarlo.',
    )
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return new RecorderError('no-mic', 'No se ha encontrado ningun microfono.')
  }
  return new RecorderError('unknown', 'No se ha podido acceder al microfono.')
}

export interface Recording {
  blob: Blob
  filename: string
}

/** Graba durante `seconds`. `onTick` recibe los segundos transcurridos. */
export async function record(
  seconds: number,
  onTick: (elapsed: number) => void,
  signal: { stop: () => void },
): Promise<Recording> {
  const format = pickFormat()
  if (format === null) throw new RecorderError('unsupported', 'Este navegador no permite grabar audio.')

  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (error) {
    throw translateError(error)
  }

  return new Promise<Recording>((resolve, reject) => {
    const chunks: BlobPart[] = []
    let recorder: MediaRecorder
    try {
      recorder = new MediaRecorder(stream, { mimeType: format.mime })
    } catch (error) {
      stream.getTracks().forEach((t) => t.stop())
      reject(translateError(error))
      return
    }

    const cleanup = () => {
      window.clearInterval(timer)
      window.clearTimeout(limit)
      stream.getTracks().forEach((t) => t.stop())
    }

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    recorder.onerror = () => {
      cleanup()
      reject(new RecorderError('unknown', 'La grabacion ha fallado.'))
    }
    recorder.onstop = () => {
      cleanup()
      resolve({
        blob: new Blob(chunks, { type: format.mime }),
        filename: `fragmento.${format.extension}`,
      })
    }

    let elapsed = 0
    const timer = window.setInterval(() => {
      elapsed += 1
      onTick(elapsed)
    }, 1000)
    const limit = window.setTimeout(() => {
      if (recorder.state !== 'inactive') recorder.stop()
    }, seconds * 1000)

    // Permite cortar antes de tiempo desde la interfaz
    signal.stop = () => {
      if (recorder.state !== 'inactive') recorder.stop()
    }

    recorder.start()
    onTick(0)
  })
}
