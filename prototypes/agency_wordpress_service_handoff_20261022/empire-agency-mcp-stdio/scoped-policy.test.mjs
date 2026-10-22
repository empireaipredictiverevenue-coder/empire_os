import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveScopedConnector } from './scoped-server.mjs'
const valid = {
  EMPIRE_AGENCY_MCP_STAGING_ENABLED:'1',
  EMPIRE_AGENCY_MCP_SOURCE:'wordpress_loopback',
  EMPIRE_AGENCY_MCP_CONNECTOR_ID:'wp-synthetic-inventory-read-v1',
  EMPIRE_AGENCY_MCP_TENANT_ID:'empire-agency-demo',
  EMPIRE_AGENCY_MCP_SITE_ID:'car-yard-synthetic',
  EMPIRE_AGENCY_MCP_USER:'synthetic-admin',
  EMPIRE_AGENCY_MCP_APP_PASSWORD:'synthetic-password-not-real',
  EMPIRE_AGENCY_MCP_WP_URL:'http://127.0.0.1:23456'
}
test('scoped registry allows only synthetic read-only WordPress tenant/site',()=>{
  const resolved=resolveScopedConnector(valid)
  assert.equal(resolved.read_only,true)
  assert.deepEqual(resolved.operations,['capabilities:read','vehicles:read'])
  assert.ok(!JSON.stringify(resolved).includes('synthetic-password'))
})
test('invalid tenant, site, connector, credentials or origin fail closed',()=>{
  for (const [key,value] of [
    ['EMPIRE_AGENCY_MCP_TENANT_ID','another-tenant'],
    ['EMPIRE_AGENCY_MCP_SITE_ID','another-site'],
    ['EMPIRE_AGENCY_MCP_CONNECTOR_ID','payment-connector'],
    ['EMPIRE_AGENCY_MCP_STAGING_ENABLED','0'],
    ['EMPIRE_AGENCY_MCP_SOURCE','external'],
    ['EMPIRE_AGENCY_MCP_APP_PASSWORD',''],
    ['EMPIRE_AGENCY_MCP_WP_URL','https://api.some-company.invalid'],
    ['EMPIRE_AGENCY_MCP_WP_URL','http://127.0.0.1:23456/another/']
  ]) {
    assert.throws(()=>resolveScopedConnector({...valid,[key]:value}),undefined,key)
  }
})
