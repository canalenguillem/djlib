/** "1 h 12 min" — la duracion total de un crate, que es lo que le importa a
 *  un DJ cuando prepara un set de una hora. */
export function formatTotal(seconds: number): string {
  if (!seconds) return '0 min'
  const horas = Math.floor(seconds / 3600)
  const minutos = Math.round((seconds % 3600) / 60)
  if (horas === 0) return `${minutos} min`
  return minutos === 0 ? `${horas} h` : `${horas} h ${minutos} min`
}
