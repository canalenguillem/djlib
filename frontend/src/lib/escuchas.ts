import { registerListen } from '../api/listens'
import type { ListenSource } from '../types/api'

// Lo que tiene que sonar una cancion para contar como escuchada, como hace
// Spotify. Si es mas corta, con la mitad basta.
const SEGUNDOS_PARA_CONTAR = 30

// Un salto mayor que esto entre dos lecturas es que se ha movido la aguja, un
// cue o un bucle: eso no se ha oido
const SALTO_MAXIMO = 3

/** Lleva la cuenta de lo que ha sonado de una cancion y avisa al servidor una
 *  sola vez, al pasar del minimo. Se le pasa la posicion cada poco rato; con la
 *  cancion parada no avanza y no suma. */
export class ContadorEscucha {
  private oido = 0
  private anterior: number | null = null
  private contada = false
  private readonly minimo: number

  constructor(
    readonly trackId: number,
    private readonly origen: ListenSource,
    duracion: number | null,
  ) {
    this.minimo = duracion ? Math.min(SEGUNDOS_PARA_CONTAR, duracion / 2) : SEGUNDOS_PARA_CONTAR
  }

  avanza(posicion: number): void {
    if (this.contada) return
    if (this.anterior !== null) {
      const paso = posicion - this.anterior
      if (paso > 0 && paso < SALTO_MAXIMO) this.oido += paso
    }
    this.anterior = posicion
    if (this.oido >= this.minimo) {
      this.contada = true
      // Si falla se pierde una escucha: no merece molestar a nadie con un error
      void registerListen(this.trackId, this.origen).catch(() => undefined)
    }
  }
}
