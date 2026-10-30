import type { Menu, User } from '../types/api'

export interface MenuDef {
  key: Menu
  to: string
  label: string
  /** Los de "Fuentes" van juntos en un submenu: de donde sale la musica. */
  fuente?: boolean
}

/** Los apartados que se dan o quitan a cada usuario, en el orden del menu.
 *  "Mi cuenta" no esta: cada uno tiene que poder cambiar su contrasena. */
export const MENUS: MenuDef[] = [
  { key: 'library', to: '/library', label: 'Biblioteca' },
  { key: 'recognize', to: '/recognize', label: 'Reconocer' },
  { key: 'mixer', to: '/mixer', label: 'Mezclar' },
  { key: 'spotify', to: '/fuentes/spotify', label: 'Spotify', fuente: true },
  { key: 'beatport', to: '/fuentes/beatport', label: 'Beatport', fuente: true },
  { key: 'youtube', to: '/fuentes/youtube', label: 'YouTube', fuente: true },
  { key: 'charts', to: '/fuentes/combinar', label: 'Combinar tops', fuente: true },
  { key: 'crates', to: '/crates', label: 'Crates' },
  { key: 'downloads', to: '/downloads', label: 'Descargas' },
  { key: 'listen', to: '/listen', label: 'Escuchar' },
  { key: 'artists', to: '/artists', label: 'Artistas' },
  { key: 'tags', to: '/tags', label: 'Etiquetas' },
]

/** La cola de lo que baja el servidor no es un permiso: la ve quien tenga
 *  alguna fuente. */
export const COLA = '/fuentes/cola'

/** El servidor ya manda la lista resuelta: el admin la tiene entera. */
export function puedeVer(user: User | null, menu: Menu): boolean {
  return !!user && user.menus.includes(menu)
}

/** Adonde mandar a alguien al entrar: el primer apartado que tenga. */
export function inicio(user: User | null): string {
  return MENUS.find((m) => puedeVer(user, m.key))?.to ?? '/account'
}
