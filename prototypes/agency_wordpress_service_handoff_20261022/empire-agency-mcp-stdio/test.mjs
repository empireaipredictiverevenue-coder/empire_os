import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { createServer as createHttpServer } from 'node:http'
import { Client, InMemoryTransport } from '@modelcontextprotocol/client'
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio'
import { createAgencyServer, runStdio } from './server.mjs'

const fixture = {
  capabilities: async () => ({
    schema: 'empire.agency.integration.capabilities.v1',
    environment: 'synthetic_staging',
    writes_available: false,
    mcp_endpoint_live: false,
    crm_connected: false,
    payments_connected: false,
    operations: ['capabilities:read', 'vehicles:read'],
    private_token: 'MUST_NOT_LEAK'
  }),
  vehicles: async ({page,limit}) => ({
    schema: 'empire.agency.inventory.v1',
    environment: 'synthetic_staging',
    page, limit, has_more: false,
    items: [{
      id: 14, title: 'SYNTHETIC DEMO VAN', make: 'Fictional',
      model: 'Test', year: 2026, odometer_km: 100, fuel: 'Demo',
      status: 'available', fictional: true,
      customer_email: 'blocked@example.invalid',
      booking_reference: 'blocked-reference'
    }]
  })
}

async function clientPair(readers = fixture) {
  const server = createAgencyServer(readers)
  const client = new Client({ name: 'synthetic-test-client', version: '1.0.0' })
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair()
  await server.connect(serverTransport)
  await client.connect(clientTransport)
  return { client, server }
}

test('real MCP protocol handshake, tools listed and read-only responses', async () => {
  const { client, server } = await clientPair()
  try {
    const listed = await client.listTools()
    assert.deepEqual(listed.tools.map(x => x.name).sort(), [
      'agency_get_capabilities','agency_list_demo_vehicles'
    ])
    const capabilities = await client.callTool({
      name: 'agency_get_capabilities', arguments: {}
    })
    assert.equal(capabilities.isError, undefined)
    const described = JSON.parse(capabilities.content[0].text)
    assert.equal(described.writes_available, false)
    assert.equal(described.mcp_endpoint_live, false)
    assert.equal(described.private_token, undefined)

    const response = await client.callTool({
      name: 'agency_list_demo_vehicles', arguments: {page:1,limit:2}
    })
    assert.equal(response.isError, undefined)
    const inventory = JSON.parse(response.content[0].text)
    assert.equal(inventory.fictional, true)
    assert.equal(inventory.items[0].id, 14)
    assert.equal(inventory.items[0].customer_email, undefined)
    assert.equal(inventory.items[0].booking_reference, undefined)
    assert.equal(inventory.limit, 2)
  } finally {
    await client.close(); await server.close()
  }
})

test('schema refuses oversized pagination and unregistered write tools', async () => {
  const { client, server } = await clientPair()
  try {
    const tooMany = await client.callTool({
      name: 'agency_list_demo_vehicles', arguments: {page:1,limit:500}
    })
    assert.ok(tooMany.isError === true)
    await assert.rejects(client.callTool({
      name: 'agency_create_booking', arguments: {}
    }), /Tool agency_create_booking not found/)
  } finally { await client.close(); await server.close() }
})

test('malicious backend claiming write authority fails closed', async () => {
  const { client, server } = await clientPair({
    ...fixture,
    capabilities: async () => ({ ...await fixture.capabilities(), writes_available: true })
  })
  try {
    const result = await client.callTool({
      name: 'agency_get_capabilities', arguments: {}
    })
    assert.ok(result.isError === true)
  } finally { await client.close(); await server.close() }
})

test('no MCP service starts unless explicitly enabled', async () => {
  const launched = spawnSync('node',['server.mjs'],{
    cwd: import.meta.dirname, env: {PATH:process.env.PATH},
    encoding:'utf8',timeout:5000
  })
  assert.equal(launched.status,1)
  assert.equal(launched.stdout,'')
  assert.ok(launched.stderr.includes('not authorised'))
})

test('networked sources restricted to explicit authenticated loopback', async () => {
  await assert.rejects(
    runStdio({
      EMPIRE_AGENCY_MCP_STAGING_ENABLED:'1',
      EMPIRE_AGENCY_MCP_SOURCE:'wordpress_loopback',
      EMPIRE_AGENCY_MCP_WP_URL:'https://production.example.org',
      EMPIRE_AGENCY_MCP_USER:'admin',
      EMPIRE_AGENCY_MCP_APP_PASSWORD:'synthetic'
    }),
    /loopback/
  )
  await assert.rejects(
    runStdio({
      EMPIRE_AGENCY_MCP_STAGING_ENABLED:'1',
      EMPIRE_AGENCY_MCP_SOURCE:'wordpress_loopback',
      EMPIRE_AGENCY_MCP_WP_URL:'http://127.0.0.1:5555',
      EMPIRE_AGENCY_MCP_USER:'admin'
    }),
    /credentials/
  )
})

test('stdio MCP process reads only from authenticated 127.0.0.1 WordPress-shaped API', async () => {
  let calls = 0
  const mockWordPress = createHttpServer((request, response) => {
    calls++
    const isAuthorized = request.headers.authorization ===
      'Basic ' + Buffer.from('synthetic-admin:synthetic-staging-application-password').toString('base64')
    const pathname = new URL(request.url, 'http://127.0.0.1').pathname
    if (!isAuthorized || request.method !== 'GET') {
      response.writeHead(403).end(); return
    }
    response.setHeader('Content-Type','application/json')
    response.setHeader('Cache-Control','private, no-store')
    if (pathname === '/wp-json/empire-agency/v1/capabilities') {
      response.end(JSON.stringify({
        schema:'empire.agency.integration.capabilities.v1',
        environment:'synthetic_staging',
        operations:['capabilities:read','vehicles:read'],
        writes_available:false,mcp_endpoint_live:false,
        crm_connected:false,payments_connected:false
      }))
    } else if (pathname === '/wp-json/empire-agency/v1/vehicles') {
      response.end(JSON.stringify({
        schema:'empire.agency.inventory.v1',
        environment:'synthetic_staging',items:[{
          id:5,title:'Fictional test car',make:'Demo',model:'Concept',
          year:2026,odometer_km:100,fuel:'Electric',status:'available',fictional:true
        }],page:1,limit:2,has_more:false
      }))
    } else {
      response.writeHead(404).end()
    }
  })
  await new Promise(resolve => mockWordPress.listen(0,'127.0.0.1',resolve))
  const address = mockWordPress.address()
  const client = new Client({name:'agency-e2e-test-client',version:'0.1.0'})
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: ['server.mjs'],
    cwd: import.meta.dirname,
    env: {
      ...process.env,
      EMPIRE_AGENCY_MCP_STAGING_ENABLED:'1',
      EMPIRE_AGENCY_MCP_SOURCE:'wordpress_loopback',
      EMPIRE_AGENCY_MCP_WP_URL:'http://127.0.0.1:'+address.port,
      EMPIRE_AGENCY_MCP_USER:'synthetic-admin',
      EMPIRE_AGENCY_MCP_APP_PASSWORD:'synthetic-staging-application-password'
    }
  })
  try {
    await client.connect(transport)
    const capabilities = await client.callTool({name:'agency_get_capabilities',arguments:{}})
    assert.equal(capabilities.isError,undefined)
    assert.equal(JSON.parse(capabilities.content[0].text).mcp_endpoint_live,false)
    const vehicles = await client.callTool({name:'agency_list_demo_vehicles',
      arguments:{page:1,limit:2}})
    assert.equal(vehicles.isError,undefined)
    const parsed = JSON.parse(vehicles.content[0].text)
    assert.equal(parsed.items[0].title,'Fictional test car')
    assert.equal(parsed.items[0].fictional,true)
    assert.equal(calls,2)
  } finally {
    await client.close()
    await new Promise(resolve=>mockWordPress.close(resolve))
  }
})
