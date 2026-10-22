/** Tenant/site-scoped, fail-closed connector launch policy. No credentials stored. */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { runStdio } from './server.mjs'
const registry = JSON.parse(readFileSync(fileURLToPath(new URL('./connector-registry.staging.json', import.meta.url)), 'utf8'))
const knownKeys = ['capabilities:read', 'vehicles:read']

export function resolveScopedConnector(env) {
  if (registry.schema !== 'empire.agency.connector-registry.v1' ||
      registry.environment !== 'synthetic_staging' ||
      !Array.isArray(registry.connectors) || registry.connectors.length !== 1) {
    throw new Error('Invalid synthetic connector registry')
  }
  if (env.EMPIRE_AGENCY_MCP_STAGING_ENABLED !== '1' ||
      env.EMPIRE_AGENCY_MCP_SOURCE !== 'wordpress_loopback') {
    throw new Error('Scoped synthetic MCP disabled')
  }
  const connector = registry.connectors[0]
  if (env.EMPIRE_AGENCY_MCP_CONNECTOR_ID !== connector.id ||
      env.EMPIRE_AGENCY_MCP_TENANT_ID !== connector.tenant_id ||
      env.EMPIRE_AGENCY_MCP_SITE_ID !== connector.site_id) {
    throw new Error('Connector tenant/site authority denied')
  }
  if (connector.allow_writes !== false ||
      connector.enabled_by_default !== false ||
      connector.credential_binding !== 'runtime_environment_only' ||
      connector.auth_type !== 'wordpress_application_password' ||
      connector.source !== 'wordpress_rest' ||
      connector.transport !== 'stdio_to_wordpress_loopback' ||
      JSON.stringify(connector.allowed_operations) !== JSON.stringify(knownKeys)) {
    throw new Error('Unexpected or elevated connector permissions')
  }
  const password = env.EMPIRE_AGENCY_MCP_APP_PASSWORD
  const user = env.EMPIRE_AGENCY_MCP_USER
  if (typeof password !== 'string' || password.length < 20 ||
      typeof user !== 'string' || !/^[A-Za-z0-9_-]{3,60}$/.test(user)) {
    throw new Error('Runtime-injected WordPress application password required')
  }
  const url = new URL(env.EMPIRE_AGENCY_MCP_WP_URL ?? '')
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' ||
      !url.port || url.pathname !== '/' || url.search || url.hash ||
      url.username || url.password) {
    throw new Error('Connector only accepts explicit disposable loopback WordPress')
  }
  return Object.freeze({
    id: connector.id, tenant_id: connector.tenant_id, site_id: connector.site_id,
    url: url.origin, read_only: true, operations: Object.freeze([...knownKeys]),
    // No password/token value is returned by the registry.
  })
}

export async function launchScopedConnector(env = process.env) {
  resolveScopedConnector(env)
  return runStdio(env)
}

if (process.argv[1] && import.meta.url === new URL('file://' + process.argv[1]).href) {
  launchScopedConnector().catch(() => {
    console.error('Empire Agency scoped MCP rejected or unavailable.')
    process.exitCode = 1
  })
}
