import type { Version } from '../types/api'

/** Versiones para DJ que se pueden buscar en YouTube. La primera es la normal. */
export const VERSIONES: { valor: Version | null; nombre: string; titulo: string }[] = [
  { valor: null, nombre: 'Original', titulo: 'La versión normal, la de la radio' },
  { valor: 'extended', nombre: 'Extended', titulo: 'Con intro y final largos para mezclar' },
  { valor: 'remix', nombre: 'Remix', titulo: 'Remezclas de otros productores' },
  { valor: 'mashup', nombre: 'Mashup', titulo: 'Dos o más canciones mezcladas en una' },
  { valor: 'edit', nombre: 'DJ edit', titulo: 'Edits, intros, reworks y bootlegs para pinchar' },
]

export function nombreVersion(version: Version | null): string {
  return VERSIONES.find((v) => v.valor === version)?.nombre ?? 'Original'
}

/** Fila de botones para elegir la version. */
export function VersionChips({
  version,
  onChange,
  disabled,
}: {
  version: Version | null
  onChange: (version: Version | null) => void
  disabled?: boolean
}) {
  return (
    <div className="chips" role="group" aria-label="Versión">
      {VERSIONES.map((v) => (
        <button
          key={v.nombre}
          type="button"
          className={v.valor === version ? 'chip chip--on' : 'chip'}
          aria-pressed={v.valor === version}
          title={v.titulo}
          disabled={disabled}
          onClick={() => onChange(v.valor)}
        >
          {v.nombre}
        </button>
      ))}
    </div>
  )
}
