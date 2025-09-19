// lib/tenant-utils.ts
import type { UserRole } from "@/types"

/**
 * Role hierarchy levels for comparison
 */
const ROLE_HIERARCHY: Record<UserRole, number> = {
  'USER': 1,
  'DEPT_MANAGER': 2,
  'DEPT_ADMIN': 3,
  'ADMIN': 4,
  'MAINTAINER': 5,
}

/**
 * Check if user has the required role or higher
 * @param userRole Current user's role
 * @param requiredRoles Array of acceptable roles
 * @returns boolean indicating if user has sufficient role
 */
export function hasRole(userRole: UserRole, requiredRoles: UserRole[]): boolean {
  if (!userRole || !requiredRoles || requiredRoles.length === 0) {
    return false
  }

  // Check if user role is in the required roles list
  if (requiredRoles.includes(userRole)) {
    return true
  }

  // Check role hierarchy - if user has higher role than any required role
  const userLevel = ROLE_HIERARCHY[userRole] || 0
  const minRequiredLevel = Math.min(...requiredRoles.map(role => ROLE_HIERARCHY[role] || 0))
  
  return userLevel >= minRequiredLevel
}

/**
 * Tenant detector utility for URL manipulation
 */
export const tenantDetector = {
  /**
   * Extract tenant ID from URL (support both subdomain and path-based)
   */
  extractTenantFromUrl(url: string): string | null {
    try {
      const urlObj = new URL(url)
      const hostname = urlObj.hostname

      // Check for subdomain (e.g., tenant1.example.com -> tenant1)
      const hostnameParts = hostname.split('.')
      if (hostnameParts.length >= 3) {
        // Skip common subdomains like www, api, etc.
        const commonSubdomains = ['www', 'api', 'app', 'dev', 'staging', 'prod']
        const subdomain = hostnameParts[0].toLowerCase()

        if (!commonSubdomains.includes(subdomain)) {
          return subdomain
        }
      }

      // Fallback to path-based extraction
      const pathSegments = urlObj.pathname.split('/').filter(Boolean)

      // Skip system-admin paths
      if (pathSegments[0] === 'system-admin') {
        return null
      }

      // First segment is tenant ID
      return pathSegments[0] || null
    } catch {
      return null
    }
  },

  /**
   * Generate tenant-specific URL (support both subdomain and path-based)
   */
  generateTenantUrl(tenantId: string | null, path: string = '/dashboard'): string {
    if (!tenantId) {
      return path.startsWith('/') ? path : `/${path}`
    }

    // Check if current URL uses subdomain routing
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname
      const hostnameParts = hostname.split('.')
      if (hostnameParts.length >= 3) {
        // Using subdomain routing, don't include tenant in path
        return path.startsWith('/') ? path : `/${path}`
      }
    }

    // Path-based routing, include tenant in path
    // Remove leading slash from path if present
    const cleanPath = path.startsWith('/') ? path.slice(1) : path

    // If path is empty or just '/', go to dashboard
    const finalPath = cleanPath || 'dashboard'

    return `/${tenantId}/${finalPath}`
  }
}

/**
 * Check if user has specific permission
 * @param userPermissions Array of user's permissions
 * @param requiredPermission Required permission code
 * @returns boolean indicating if user has the permission
 */
export function hasPermission(userPermissions: string[], requiredPermission: string): boolean {
  if (!userPermissions || !requiredPermission) {
    return false
  }

  // Check for exact permission match
  if (userPermissions.includes(requiredPermission)) {
    return true
  }

  // Check for wildcard permissions
  if (userPermissions.includes('*')) {
    return true
  }

  // Check for resource-based permissions (e.g., "users.*" matches "users.create")
  const wildcardPermissions = userPermissions.filter(p => p.endsWith('.*'))
  for (const wildcardPerm of wildcardPermissions) {
    const prefix = wildcardPerm.slice(0, -2) // Remove ".*"
    if (requiredPermission.startsWith(prefix + '.')) {
      return true
    }
  }

  return false
}

/**
 * Check if user has all required permissions
 * @param userPermissions Array of user's permissions
 * @param requiredPermissions Array of required permissions
 * @returns boolean indicating if user has all required permissions
 */
export function hasAllPermissions(userPermissions: string[], requiredPermissions: string[]): boolean {
  if (!requiredPermissions || requiredPermissions.length === 0) {
    return true
  }

  return requiredPermissions.every(permission => hasPermission(userPermissions, permission))
}

/**
 * Check if user has any of the required permissions
 * @param userPermissions Array of user's permissions
 * @param requiredPermissions Array of required permissions
 * @returns boolean indicating if user has at least one required permission
 */
export function hasAnyPermission(userPermissions: string[], requiredPermissions: string[]): boolean {
  if (!requiredPermissions || requiredPermissions.length === 0) {
    return true
  }

  return requiredPermissions.some(permission => hasPermission(userPermissions, permission))
}

/**
 * Get the highest role from an array of roles
 * @param roles Array of roles
 * @returns The highest role or null if no valid roles
 */
export function getHighestRole(roles: UserRole[]): UserRole | null {
  if (!roles || roles.length === 0) {
    return null
  }

  let highestRole = roles[0]
  let highestLevel = ROLE_HIERARCHY[highestRole] || 0

  for (const role of roles) {
    const level = ROLE_HIERARCHY[role] || 0
    if (level > highestLevel) {
      highestRole = role
      highestLevel = level
    }
  }

  return highestRole
}

/**
 * Check if a role is higher than another role
 * @param roleA First role
 * @param roleB Second role
 * @returns true if roleA is higher than roleB
 */
export function isRoleHigher(roleA: UserRole, roleB: UserRole): boolean {
  const levelA = ROLE_HIERARCHY[roleA] || 0
  const levelB = ROLE_HIERARCHY[roleB] || 0
  return levelA > levelB
}

/**
 * Get user role display name
 * @param role User role
 * @returns Formatted role display name
 */
export function getRoleDisplayName(role: UserRole): string {
  const roleNames: Record<UserRole, string> = {
    'MAINTAINER': 'System Administrator',
    'ADMIN': 'Organization Admin',
    'DEPT_ADMIN': 'Department Admin',
    'DEPT_MANAGER': 'Department Manager',
    'USER': 'User',
  }

  return roleNames[role] || role
}

/**
 * Get role color for UI display
 * @param role User role
 * @returns Tailwind CSS color class
 */
export function getRoleColor(role: UserRole): string {
  const roleColors: Record<UserRole, string> = {
    'MAINTAINER': 'text-red-600 bg-red-50 border-red-200',
    'ADMIN': 'text-blue-600 bg-blue-50 border-blue-200',
    'DEPT_ADMIN': 'text-purple-600 bg-purple-50 border-purple-200',
    'DEPT_MANAGER': 'text-green-600 bg-green-50 border-green-200',
    'USER': 'text-gray-600 bg-gray-50 border-gray-200',
  }

  return roleColors[role] || 'text-gray-600 bg-gray-50 border-gray-200'
}

/**
 * Check if user can access tenant-specific resources
 * @param userTenantId User's tenant ID
 * @param resourceTenantId Resource's tenant ID
 * @param userRole User's role
 * @returns boolean indicating access permission
 */
export function canAccessTenantResource(
  userTenantId: string | null,
  resourceTenantId: string | null,
  userRole: UserRole
): boolean {
  // MAINTAINER can access all tenant resources
  if (userRole === 'MAINTAINER') {
    return true
  }

  // Users must belong to the same tenant as the resource
  if (!userTenantId || !resourceTenantId) {
    return false
  }

  return userTenantId === resourceTenantId
}

/**
 * Check if user can manage other users
 * @param managerRole Manager's role
 * @param managedUserRole Managed user's role
 * @param sameOrganization Whether both users are in the same organization
 * @returns boolean indicating management permission
 */
export function canManageUser(
  managerRole: UserRole,
  managedUserRole: UserRole,
  sameOrganization: boolean = true
): boolean {
  // MAINTAINER can manage all users
  if (managerRole === 'MAINTAINER') {
    return true
  }

  // Must be in same organization (except MAINTAINER)
  if (!sameOrganization) {
    return false
  }

  // Manager must have higher role than managed user
  return isRoleHigher(managerRole, managedUserRole)
}

/**
 * Get available roles that a user can assign to others
 * @param userRole Current user's role
 * @returns Array of roles that can be assigned
 */
export function getAssignableRoles(userRole: UserRole): UserRole[] {
  const allRoles: UserRole[] = ['USER', 'DEPT_MANAGER', 'DEPT_ADMIN', 'ADMIN', 'MAINTAINER']
  const userLevel = ROLE_HIERARCHY[userRole] || 0

  // Users can only assign roles lower than their own
  return allRoles.filter(role => {
    const roleLevel = ROLE_HIERARCHY[role] || 0
    return roleLevel < userLevel
  })
}

/**
 * Format permissions for display
 * @param permissions Array of permission codes
 * @returns Formatted permission names
 */
export function formatPermissions(permissions: string[]): string[] {
  return permissions.map(permission => {
    // Convert snake_case to Title Case
    return permission
      .split('.')
      .map(part => 
        part.split('_')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' ')
      )
      .join(' - ')
  })
}

/**
 * Group permissions by resource type
 * @param permissions Array of permission codes
 * @returns Grouped permissions object
 */
export function groupPermissionsByResource(permissions: string[]): Record<string, string[]> {
  const grouped: Record<string, string[]> = {}

  permissions.forEach(permission => {
    const parts = permission.split('.')
    const resource = parts[0] || 'general'
    
    if (!grouped[resource]) {
      grouped[resource] = []
    }
    
    grouped[resource].push(permission)
  })

  return grouped
}

/**
 * Check if current path requires authentication
 * @param pathname Current pathname
 * @returns boolean indicating if auth is required
 */
export function requiresAuth(pathname: string): boolean {
  const publicPaths = [
    '/',
    '/login',
    '/forgot-password',
    '/reset-password',
    '/invite',
    '/public',
  ]

  // Check for exact matches
  if (publicPaths.includes(pathname)) {
    return false
  }

  // Check for path patterns
  const publicPatterns = [
    /^\/[^\/]+\/login$/,           // /:tenant/login
    /^\/[^\/]+\/forgot-password$/, // /:tenant/forgot-password
    /^\/[^\/]+\/reset-password$/,  // /:tenant/reset-password
    /^\/[^\/]+\/invite$/,          // /:tenant/invite
    /^\/public\//,                 // /public/*
  ]

  return !publicPatterns.some(pattern => pattern.test(pathname))
}

/**
 * Get login redirect path based on current path
 * @param currentPath Current pathname
 * @returns Login path to redirect to
 */
export function getLoginRedirectPath(currentPath: string): string {
  if (currentPath.startsWith('/system-admin') || currentPath === '/') {
    return '/system-admin/login'
  }

  const tenantMatch = currentPath.match(/^\/([^\/]+)/)
  if (tenantMatch && tenantMatch[1] && tenantMatch[1] !== 'system-admin') {
    return `/${tenantMatch[1]}/login`
  }

  return '/system-admin/login'
}