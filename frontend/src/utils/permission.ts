import { useUserStore } from '@/stores/user'

export function hasPermission(code?: string | string[]) {
  if (!code) return true
  const store = useUserStore()
  const user = store.userInfo
  if (user?.is_admin) return true
  const permissions = new Set<string>(user?.permissions || [])
  if (permissions.has('*')) return true
  const codes = Array.isArray(code) ? code : [code]
  return codes.some((item) => permissions.has(item))
}

export function hasAnyPermission(codes: string[]) {
  return hasPermission(codes)
}
