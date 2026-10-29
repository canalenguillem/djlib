/** Ofrece al navegador un fichero traido por fetch, como si fuera un enlace
 *  de descarga normal. */
export function guardarFichero(blob: Blob, nombre: string): void {
  const href = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = href
  enlace.download = nombre
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(href)
}

const EXTENSIONES: Record<string, string> = {
  'audio/mpeg': '.mp3',
  'audio/mp4': '.m4a',
  'audio/aac': '.aac',
  'audio/wav': '.wav',
  'audio/x-wav': '.wav',
  'audio/aiff': '.aiff',
  'audio/x-aiff': '.aiff',
  'audio/flac': '.flac',
  'audio/ogg': '.ogg',
  'audio/webm': '.webm',
}

/** "Artista - Titulo" con la extension de lo que ha llegado: casi siempre mp3,
 *  pero si el servidor no pudo convertirla viene en su formato. */
export function nombreCancion(
  track: { artist_text: string | null; title: string },
  blob: Blob,
): string {
  const nombre = [track.artist_text, track.title].filter(Boolean).join(' - ') || 'track'
  return `${nombre}${EXTENSIONES[blob.type] ?? '.mp3'}`
}
