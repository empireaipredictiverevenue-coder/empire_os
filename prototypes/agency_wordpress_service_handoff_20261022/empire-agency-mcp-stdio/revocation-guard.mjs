/**
 * Guard adapter for a separately trusted MCP launcher.
 *
 * The unmodified historic server.mjs remains staging-only. This wrapper adds
 * a fresh, async owner-supplied authorization check *before each tool's
 * WordPress HTTP read*. No environment variable or caller-supplied tenant
 * string is accepted as an authority callback.
 *
 * The actual canonical membership/site/registry resolver lives in EmpireOS,
 * not in this package. Missing authority fails closed.
 */
import { createAgencyServer } from './server.mjs'

export function createRevocationGuardedAgencyServer(readers, freshAuthorizeRead) {
  if (typeof freshAuthorizeRead !== 'function') {
    throw new Error('Trusted canonical agency membership and site authority required')
  }
  if (!readers || typeof readers.capabilities !== 'function' ||
      typeof readers.vehicles !== 'function') {
    throw new Error('Explicit authenticated WordPress read functions required')
  }
  let closed = false
  async function verify(operation) {
    if (closed) {
      throw new Error('Agency connector session closed')
    }
    try {
      if ((operation !== 'capabilities:read' && operation !== 'vehicles:read') ||
          await freshAuthorizeRead(operation) !== true) {
        throw new Error('not authorized')
      }
    } catch {
      throw new Error('Agency tenant/site authority unavailable or revoked')
    }
  }
  return {
    server: createAgencyServer({
      capabilities: async () => {
        await verify('capabilities:read')
        return readers.capabilities()
      },
      vehicles: async opts => {
        await verify('vehicles:read')
        return readers.vehicles(opts)
      }
    }),
    closeAuthority: () => { closed = true }
  }
}
