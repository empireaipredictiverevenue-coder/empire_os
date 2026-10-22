/** Verify an actual WP application password has stopped working after revocation. */
const base=process.env.YARD_BASE_URL
const pw=process.env.YARD_MCP_APP_PASSWORD
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base ?? '') || !pw) throw Error('Missing ephemeral context')
const auth='Basic '+Buffer.from('demo_yard_admin:'+pw).toString('base64')
const result=await fetch(base+'/wp-json/empire-agency/v1/vehicles',{headers:{Authorization:auth},signal:AbortSignal.timeout(6000),redirect:'error'})
if(result.status!==401)throw Error('Revoked test credential still authenticated: HTTP '+result.status)
console.log(JSON.stringify({status:'WORDPRESS_EPHEMERAL_CREDENTIAL_REVOCATION_CONFIRMED',http_status:result.status,production_changes:false}))
