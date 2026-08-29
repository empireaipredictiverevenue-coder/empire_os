/**
 * Empire OS v3 - Cloudflare Worker for Geo-Routing
 * Routes API requests to nearest regional hub based on CF-IPCountry/CF-Region
 * 
 * Deploy: wrangler deploy
 * Bindings: KV namespace for rate limiting, D1 for logging
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const pathname = url.pathname;
    
    // Skip non-API paths
    if (!pathname.startsWith('/v1/')) {
      return new Response('Not Found', { status: 404 });
    }
    
    // Health check - no geo-routing needed
    if (pathname === '/health' || pathname === '/v1/health') {
      return fetch(request, { cf: { resolveOverride: 'empire-hub:8081' } });
    }
    
    // Public endpoints - no geo-routing needed
    const publicPaths = ['/v1/leads/intake', '/v1/cortex/signup'];
    const isPublic = publicPaths.some(p => pathname.startsWith(p));
    
    // Determine target region from CF headers
    const country = request.headers.get('cf-ipcountry') || 'US';
    const region = request.headers.get('cf-region') || '';
    const city = request.headers.get('cf-city') || '';
    
    // Map country/region to Empire OS regional hub
    const targetHub = getRegionalHub(country, region);
    
    // Rate limiting check (using KV)
    const clientIp = request.headers.get('cf-connecting-ip') || 'unknown';
    const rateLimitKey = `ratelimit:${clientIp}:${Math.floor(Date.now() / 60000)}`;
    const currentCount = await env.RATE_LIMIT_KV.get(rateLimitKey) || 0;
    
    if (currentCount > 100) { // 100 requests/minute default
      return new Response(JSON.stringify({
        error: 'Rate limit exceeded',
        retry_after: 60
      }), {
        status: 429,
        headers: { 'Content-Type': 'application/json', 'Retry-After': '60' }
      });
    }
    
    await env.RATE_LIMIT_KV.put(rateLimitKey, String(currentCount + 1), { expirationTtl: 60 });
    
    // Build upstream URL
    const upstreamUrl = `http://${targetHub}${pathname}${url.search}`;
    
    // Forward request with geo headers
    const upstreamRequest = new Request(upstreamUrl, {
      method: request.method,
      headers: {
        ...Object.fromEntries(request.headers),
        'x-forwarded-for': clientIp,
        'x-forwarded-country': country,
        'x-forwarded-region': region,
        'x-forwarded-city': city,
        'x-empire-region': targetHub.split('.')[0], // usa-east, usa-central, usa-west
        'x-empire-geo': `${country},${region},${city}`,
      },
      body: request.body,
      redirect: 'follow',
    });
    
    // Add auth headers if present
    const apiKey = request.headers.get('x-api-key');
    if (apiKey) {
      upstreamRequest.headers.set('x-api-key', apiKey);
    }
    
    try {
      const response = await fetch(upstreamRequest);
      
      // Add response headers
      const responseHeaders = new Headers(response.headers);
      responseHeaders.set('x-empire-region', targetHub.split('.')[0]);
      responseHeaders.set('x-empire-cache', response.headers.get('x-cache') || 'MISS');
      
      // Log to analytics (async, don't await)
      ctx.waitUntil(logRequest(env, {
        timestamp: new Date().toISOString(),
        ip: clientIp,
        country,
        region,
        city,
        path: pathname,
        method: request.method,
        status: response.status,
        region: targetHub,
        response_time: 0, // would need performance.now()
      }));
      
      return new Response(response.body, {
        status: response.status,
        headers: responseHeaders,
      });
    } catch (err) {
      // Fallback to primary hub
      const fallbackUrl = `http://empire-hub:8081${pathname}${new URL(request.url).search}`;
      const fallbackResponse = await fetch(fallbackUrl, {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });
      
      return new Response(fallbackResponse.body, {
        status: fallbackResponse.status,
        headers: fallbackResponse.headers,
      });
    }
  },
};

function getRegionalHub(country, region) {
  // US regional mapping
  const usEast = ['NY', 'MA', 'PA', 'DC', 'VA', 'MD', 'NC', 'SC', 'GA', 'FL', 'CT', 'RI', 'VT', 'NH', 'ME', 'WV', 'OH', 'MI', 'IN', 'KY', 'TN'];
  const usCentral = ['IL', 'TX', 'CO', 'MN', 'WI', 'IA', 'MO', 'AR', 'LA', 'OK', 'KS', 'NE', 'SD', 'ND', 'MT', 'WY', 'UT', 'AZ', 'NM'];
  const usWest = ['CA', 'OR', 'WA', 'NV', 'ID', 'UT', 'AZ', 'HI', 'AK'];
  
  // Normalize region code
  const regionUpper = region.toUpperCase();
  const countryUpper = country.toUpperCase();
  
  if (countryUpper !== 'US') {
    // Non-US defaults to east for latency
    return 'usa-east-hub.empire-os.internal:8081';
  }
  
  if (usEast.includes(regionUpper)) {
    return 'usa-east-hub.empire-os.internal:8081';
  }
  if (usCentral.includes(regionUpper)) {
    return 'usa-central-hub.empire-os.internal:8081';
  }
  if (usWest.includes(regionUpper)) {
    return 'usa-west-hub.empire-os.internal:8081';
  }
  
  // Default fallback
  return 'empire-hub.empire-os.internal:8081';
}

async function logRequest(env, data) {
  try {
    // Log to D1 or KV for analytics
    const key = `analytics:${Date.now()}:${Math.random().toString(36).substr(2, 9)}`;
    await env.ANALYTICS_KV.put(key, JSON.stringify(data), { expirationTtl: 86400 * 7 });
  } catch (e) {
    // Silent fail
  }
}