/** Actual REST-on-MariaDB <-> authenticated WordPress Application Password <-> MCP stdio. */
import { Client } from '../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/node_modules/@modelcontextprotocol/client/dist/index.mjs'
import { StdioClientTransport } from '../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/node_modules/@modelcontextprotocol/client/dist/stdio.mjs'
import { resolveScopedConnector } from '../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/scoped-server.mjs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
const base=process.env.YARD_BASE_URL
const pw=process.env.YARD_MCP_APP_PASSWORD
const user='demo_yard_admin'
const endpoint='/wp-json/empire-agency/v1/'
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base ?? '') || typeof pw!=='string'|| pw.length < 20) {
  throw new Error('Disposable WordPress credentials/origin unavailable')
}
const authorization='Basic '+Buffer.from(user+':'+pw).toString('base64')
async function get(path, authorized=false) {
  const res=await fetch(base+endpoint+path,{
    headers: authorized ? {Authorization:authorization,Accept:'application/json'} : {Accept:'application/json'},
    redirect:'error',signal:AbortSignal.timeout(7000)
  })
  return {status:res.status,body:await res.text()}
}
const checks={}
function prove(label,condition) {
  if(!condition) throw new Error('REAL_WORDPRESS_MCP_CHECK_FAILED: '+label)
  checks[label]=true
}
const env={
  ...process.env,
  EMPIRE_AGENCY_MCP_STAGING_ENABLED:'1',
  EMPIRE_AGENCY_MCP_SOURCE:'wordpress_loopback',
  EMPIRE_AGENCY_MCP_CONNECTOR_ID:'wp-synthetic-inventory-read-v1',
  EMPIRE_AGENCY_MCP_TENANT_ID:'empire-agency-demo',
  EMPIRE_AGENCY_MCP_SITE_ID:'car-yard-synthetic',
  EMPIRE_AGENCY_MCP_WP_URL:base,
  EMPIRE_AGENCY_MCP_USER:user,
  EMPIRE_AGENCY_MCP_APP_PASSWORD:pw
}
const scope=resolveScopedConnector(env)
prove('synthetic_site_and_tenant_bound',scope.tenant_id==='empire-agency-demo'&&scope.site_id==='car-yard-synthetic')
prove('no_write_operations',scope.read_only===true&&scope.operations.every(x=>x.endsWith(':read')))
const unauth=await get('vehicles?page=1&limit=2')
prove('real_wp_anonymous_denied',unauth.status===401)
const auth=await get('vehicles?page=1&limit=2',true)
prove('real_wp_authenticated_rest_ok',auth.status===200)
const payload=JSON.parse(auth.body)
prove('real_wp_mariadb_inventory_fixture',payload.schema==='empire.agency.inventory.v1'&&payload.items.length===1&&payload.items[0].title==='SYNTHETIC DEMO BLUE VAN')
prove('real_wp_private_data_not_exposed',!auth.body.includes('customer_email')&&!auth.body.includes('private@example.invalid')&&!auth.body.includes(pw))
const src=resolve(dirname(fileURLToPath(import.meta.url)),'../../prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio')
const client=new Client({name:'empire-disposable-e2e-reader',version:'0.1.0'})
const transport=new StdioClientTransport({
  command:process.execPath,args:['scoped-server.mjs'],cwd:src,env
})
try {
  await client.connect(transport)
  const tools=await client.listTools()
  prove('live_mcp_two_read_tools_only',JSON.stringify(tools.tools.map(t=>t.name).sort())===JSON.stringify(['agency_get_capabilities','agency_list_demo_vehicles']))
  const cap=await client.callTool({name:'agency_get_capabilities',arguments:{}})
  const c=JSON.parse(cap.content[0].text)
  prove('live_mcp_authenticated_capability_read',cap.isError!==true&&c.writes_available===false&&c.crm_connected===false&&c.payments_connected===false)
  const items=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:2}})
  const inventory=JSON.parse(items.content[0].text)
  prove('live_mcp_authenticated_real_wp_stock_read',items.isError!==true&&inventory.items.length===1&&inventory.items[0].title==='SYNTHETIC DEMO BLUE VAN')
  prove('live_mcp_bounded_fields',inventory.items[0].fictional===true&&!JSON.stringify(inventory).includes(pw)&&!('customer_email' in inventory.items[0]))
  let missingWrite=false
  try { await client.callTool({name:'agency_create_booking',arguments:{}}) }
  catch { missingWrite=true }
  prove('live_mcp_booking_write_unavailable',missingWrite)
  const oversized=await client.callTool({name:'agency_list_demo_vehicles',arguments:{page:1,limit:500}})
  prove('live_mcp_unbounded_query_denied',oversized.isError===true)
} finally {
  await client.close()
}
console.log(JSON.stringify({
  status:'AUTHENTICATED_MCP_TO_REAL_WORDPRESS_MARIADB_PASS',
  checks,checks_passed:Object.keys(checks).length,
  registry_connector:scope.id,tenant_id:scope.tenant_id,site_id:scope.site_id,
  live_wp_rest_http_status:auth.status,anonymous_http_status:unauth.status,
  production_changes:false,real_customer_data:false
}))
