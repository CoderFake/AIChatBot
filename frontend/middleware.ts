import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export function middleware(request: NextRequest) {
  const { pathname, hostname } = request.nextUrl
  const url = request.nextUrl.clone()

  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/system-admin") ||
    pathname.includes(".")
  ) {
    return NextResponse.next()
  }

  // Detect tenant from subdomain or path
  const tenantId = extractTenantId(request)

  if (tenantId) {
    const isPrivateRoute = pathname.includes("/private/")
    const isPublicRoute = pathname.includes("/public/")

    if (isPrivateRoute || isPublicRoute) {
      // For chat routes, we'll let the page components handle auth checks
      // but we still need to set the tenant context
      const response = NextResponse.next()
      response.headers.set("x-tenant-id", tenantId)
      return response
    }

    const response = NextResponse.next()
    response.headers.set("x-tenant-id", tenantId)
    return response
  }

  return NextResponse.next()
}

function extractTenantId(request: NextRequest): string | null {
  const { pathname, hostname } = request.nextUrl
  const detectionMethod = process.env.NEXT_PUBLIC_TENANT_DETECTION_METHOD || "path_prefix"

  if (detectionMethod === "subdomain") {
    const parts = hostname.split(".")

    if (hostname === "localhost" || /^\d+\.\d+\.\d+\.\d+$/.test(hostname)) {
      return extractFromPath(pathname)
    }

    if (parts.length > 2) {
      return parts[0]
    }
  } else {
    return extractFromPath(pathname)
  }

  return null
}

function extractFromPath(pathname: string): string | null {
  const pathSegments = pathname.split("/").filter(Boolean)

  if (pathSegments[0] === "system-admin" || pathSegments[0] === "api") {
    return null
  }

  return pathSegments[0] || null
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
}
