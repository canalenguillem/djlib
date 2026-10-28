import type { Menu, User } from '../types/api'

/** Los apartados que se dan o quitan a cada usuario, en el orden del menu.
 *  "Mi cuenta" no esta: cada uno tiene que poder cambiar su contrasena. */
export const MENUS: { key: Menu; to: string; label: string }[] = [
  { key: 'library', to: '/library', label: 'Biblioteca' },
  { key: 'recognize', to: '/recognize', label: 'Reconocer' },
  { key: 'mixer', to: '/mixer', label: 'Mezclar' },
  { key: 'spotify', to: '/spotify', label: 'Spotify' },
  { key: 'beatport', to: '/beatport', label: 'Beatport' },
  { key: 'crates', to: '/crates', label: 'Crates' },
  { key: 'downloads', to: '/downloads', label: 'Descargas' },
  { key: 'listen', to: '/listen', label: 'Escuchar' },
  { key: 'artists', to: '/artists', label: 'Artistas' },
  { key: 'tags', to: '/tags', label: 'Etiquetas' },
]

/** El servidor ya manda la lista resuelta: el admin la tiene entera. */
export function puedeVer(user: User | null, menu: Menu): boolean {
  return !!user && user.menus.includes(menu)
}

/** Adonde mandar a alguien al entrar: el primer apartado que tenga. */
export function inicio(user: User | null): string {
  return MENUS.find((m) => puedeVer(user, m.key))?.to ?? '/account'
}
