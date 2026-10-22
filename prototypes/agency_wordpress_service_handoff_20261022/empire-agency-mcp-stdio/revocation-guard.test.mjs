import test from 'node:test'
import assert from 'node:assert/strict'
import { Client, InMemoryTransport } from '@modelcontextprotocol/client'
import { createRevocationGuardedAgencyServer } from './revocation-guard.mjs'

const capabilities = {
  schema: 'empire.agency.integration.capabilities.v1',
  environment: 'synthetic_staging',
  operations: ['capabilities:read', 'vehicles:read'],
  writes_available: false,
  mcp_endpoint_live: false,
  crm_connected: false,
  payments_connected: false
}
const inventory = {
  schema: 'empire.agency.inventory.v1',
  environment: 'synthetic_staging',
  page: 1, limit: 2, has_more: false,
  items: [{id:1, title:'SYNTHETIC DEMO BLUE VAN', make:'Demo',
    model:'Blue Van',year:2026,odometer_km:250,fuel:'Demo',
    status:'available',fictional:true}]
}
async function linkedWithAuthorizer(authorize) {
  let backendReads = 0
  const readers = {
    capabilities: async () => { backendReads++; return capabilities },
    vehicles: async () => { backendReads++; return inventory }
  }
  const {server, closeAuthority} = createRevocationGuardedAgencyServer(readers, authorize)
  const [toClient,toServer]=InMemoryTransport.createLinkedPair()
  const client=new Client({name:'synthetic-agency-membership-revocation',version:'0.2.0'})
  await server.connect(toServer)
  await client.connect(toClient)
  return {client,server,closeAuthority,getReads:()=>backendReads}
}
test('exactly allowed tools, fresh membership revoked MID-SESSION before any further WP reads',async()=>{
  let membershipActive=true
  let grantActive=true
  const calls=[]
  const runtime=await linkedWithAuthorizer(async permission => {
    calls.push(permission)
    return membershipActive && grantActive
  })
  const {client,server,getReads}=runtime
  try {
    assert.deepEqual((await client.listTools()).tools.map(t=>t.name).sort(),
      ['agency_get_capabilities','agency_list_demo_vehicles'])
    const a=await client.callTool({name:'agency_get_capabilities',arguments:{}})
    assert.equal(a.isError,undefined)
    assert.equal(getReads(),1)
    const v=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
    assert.equal(v.isError,undefined)
    assert.equal(getReads(),2)
    membershipActive=false
    const denied=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
    assert.equal(denied.isError,true)
    assert.equal(getReads(),2,'rejected call must never reach WordPress')
    membershipActive=true
    grantActive=false
    const denied2=await client.callTool({name:'agency_get_capabilities',arguments:{}})
    assert.equal(denied2.isError,true)
    assert.equal(getReads(),2)
    assert.deepEqual(calls,
      ['capabilities:read','vehicles:read','vehicles:read','capabilities:read'])
  } finally {await client.close();await server.close()}
})
test('missing auth callback denies guarded MCP creation, no anonymous fallback',()=>{
  const readers={capabilities:async()=>capabilities,vehicles:async()=>inventory}
  assert.throws(()=>createRevocationGuardedAgencyServer(readers,undefined),/trusted/i)
  assert.throws(()=>createRevocationGuardedAgencyServer(readers,true),/trusted/i)
})
test('authority read failure, negative response, or closed context deny without backend fetch',async()=>{
  let active=true
  const session=await linkedWithAuthorizer(async()=>{if(!active)throw Error('NO_SECRET_LOGS');return true})
  try{
    session.closeAuthority()
    const res=await session.client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
    assert.equal(res.isError,true)
    assert.equal(session.getReads(),0)
  }finally{await session.client.close();await session.server.close()}
  const errors=await linkedWithAuthorizer(async()=>{active=false;throw Error('Sensitive credential value')})
  try {
    const res=await errors.client.callTool({name:'agency_get_capabilities',arguments:{}})
    assert.equal(res.isError,true)
    assert.equal(errors.getReads(),0)
    assert.ok(!JSON.stringify(res).includes('Sensitive credential value'))
  }finally{await errors.client.close();await errors.server.close()}
})
