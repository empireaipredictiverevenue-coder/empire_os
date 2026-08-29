// Module 2: Waterfall Ingestor
// Fetches raw company data, deduplicates against Supabase pgvector, pushes to Twenty CRM

require('dotenv').config();
const fetch = require('node-fetch');
const { Client } = require('@supabase/supabase-js');
const TwentySDK = require('twenty-sdk'); // Hypothetical Twenty SDK

// Supabase connection
const supabase = new Client(
  process.env.SUPABASE_URL,
  { key: process.env.SUPABASE_ANON_KEY }
);

// Twenty CRM connection
const twenty = new TwentySDK({
  apiKey: process.env.TWENTY_API_KEY,
  baseURL: process.env.TWENTY_BASE_URL
});

// Waterfall sources configuration
const waterfallSources = [
  { name: 'universal_scraper', async fetch(company) { ... } },
  { name: 'bing_local', async fetch(company) { ... } },
  { name: 'yelp_scraper', async fetch(company) { ... } },
  { name: 'reddit_scraper', async fetch(company) { ... } },
  { name: 'gmaps_scraper', async fetch(company) { ... } },
  { name: 'permit_source', async fetch(company) { ... } },
  { name: 'enhanced_universal_scraper', async fetch(company) { ... } },
  { name: 'sam_gov', async fetch(company) { ... } },
  { name: 'google_news', async fetch(company) { ... } },
  { name: 'us_permits_metros', async fetch(company) { ... } }
];

async function deduplicate(leadProfile) {
  // Check Supabase pgvector for duplicates
  const { data, error } = await supabase
    .from('leads')
    .select('email, company')
    .or(`email.eq.${leadProfile.email},company.eq.${leadProfile.company}`);
  
  if (error) throw error;
  if (data && data.length > 0) {
    return { isDuplicate: true, existingId: data[0].id };
  }
  return { isDuplicate: false };
}

async function enrichAndPush(company) {
  // 1. Fetch from waterfall sources
  let leadProfile = null;
  for (const source of waterfallSources) {
    try {
      leadProfile = await source.fetch(company);
      if (leadProfile && !leadProfile.error) break;
    } catch (e) {
      console.error(`${source.name} fetch error:`, e.message);
      continue;
    }
  }
  
  if (!leadProfile) {
    console.error(`No data found for ${company}`);
    return false;
  }
  
  // 2. Deduplicate
  const dupCheck = await deduplicate(leadProfile);
  if (dupCheck.isDuplicate) {
    console.log(`Duplicate lead skipped: ${company}`);
    return false;
  }
  
  // 3. Push to Twenty CRM
  try {
    await twenty.leads.create({
      company: leadProfile.company,
      email: leadProfile.email,
      firstName: leadProfile.firstName,
      niche: leadProfile.niche,
      omegaScore: leadProfile.omegaScore,
      source: leadProfile.source,
      status: 'new'
    });
    console.log(`Pushed to Twenty CRM: ${company} - ${leadProfile.email}`);
    
    // 4. Log success
    await supabase
      .from('lead_enrichment_log')
      .insert({ company, email: leadProfile.email, status: 'success', pushedAt: new Date().toISOString() });
    
    return true;
  } catch (e) {
    console.error('Twenty CRM push error:', e.message);
    
    // Log failure for retry
    await supabase
      .from('lead_enrichment_log')
      .insert({ company, email: leadProfile.email, status: 'failed', error: e.message, failedAt: new Date().toISOString() });
    
    return false;
  }
}

// Main ingestion loop
async function runIngestion(companies) {
  const results = [];
  for (const company of companies) {
    const result = await enrichAndPush(company);
    results.push({ company, result });
    // Small delay to avoid rate limiting
    await new Promise(r => setTimeout(r, 500));
  }
  
  // Summary
  const success = results.filter(r => r.result).length;
  const failed = results.length - success;
  console.log(`Ingestion complete: ${success} succeeded, ${failed} failed out of ${results.length}`);
  
  return results;
}

// Run if executed directly
if (require.main === module) {
  const companies = process.argv.slice(2);
  if (companies.length === 0) {
    console.log('Usage: node waterfall_ingestor.js "company1" "company2" ...');
    process.exit(1);
  }
  runIngestion(companies);
}

module.exports = { runIngestion, deduplicate, enrichAndPush };
