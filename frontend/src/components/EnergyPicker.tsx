const NIVELES = [1, 2, 3, 4, 5]

const ETIQUETAS: Record<number, string> = {
  1: 'Warm-up, entra la gente',
  2: 'Suave',
  3: 'Ritmo constante',
  4: 'Subiendo',
  5: 'Pico de la noche',
}

interface Props {
  value: number | null
  disabled?: boolean
  onChange: (energy: number) => void
}

/** Intensidad de 1 a 5, como las estrellas que usan los DJ.
 *
 *  No es una nota de calidad: es para que al montar un set sepas de un vistazo
 *  con que empezar y que guardarte para el final.
 */
export function EnergyPicker({ value, disabled, onChange }: Props) {
  return (
    <span className="energy" role="group" aria-label="Energia">
      {NIVELES.map((nivel) => (
        <button
          key={nivel}
          type="button"
          className={nivel <= (value ?? 0) ? 'energy__dot energy__dot--on' : 'energy__dot'}
          disabled={disabled}
          title={ETIQUETAS[nivel]}
          aria-label={`Energia ${nivel}: ${ETIQUETAS[nivel]}`}
          aria-pressed={nivel === value}
          onClick={() => onChange(nivel)}
        />
      ))}
    </span>
  )
}
