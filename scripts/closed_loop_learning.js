// Module 4: Closed Loop Learning Engine
require("dotenv").config();
const { Pool } = require("pg");

const pool = new Pool({
  connectionString: process.env.SUPABASE_DB_URL
});

// Standalone pattern analysis function
function analyzePatterns(examples) {
  var analysis = {
    commonHooks: [],
    effectiveCTAs: [],
    nicheEffectiveness: {}
  };
  
  if (!examples || examples.length === 0) return analysis;
  
  examples.forEach(function(ex) {
    if (ex && ex.hook_structure) {
      analysis.commonHooks.push(ex.hook_structure);
    }
    
    if (ex && ex.email_copy) {
      var ctaMatch = ex.email_copy.match(/(call|reply|meet|schedule|book)/i);
      if (ctaMatch) {
        analysis.effectiveCTAs.push(ctaMatch[0]);
      }
    }
    
    if (ex && ex.company_profile && ex.company_profile.niche) {
      var niche = ex.company_profile.niche;
      if (!analysis.nicheEffectiveness[niche]) {
        analysis.nicheEffectiveness[niche] = { count: 0, outcomes: [] };
      }
      analysis.nicheEffectiveness[niche].count++;
      if (ex && ex.outcome) analysis.nicheEffectiveness[niche].outcomes.push(ex.outcome);
    }
  });
  
  analysis.mostCommonHook = analysis.commonHooks.length > 0 ? analysis.commonHooks[0] : null;
  analysis.mostEffectiveCTA = analysis.effectiveCTAs.length > 0 ? analysis.effectiveCTAs[0] : null;
  
  return analysis;
}

class ClosedLoopLearning {
  constructor() {
    this.successfulCopies = [];
  }

  async captureSuccess(webhookPayload) {
    try {
      var email_copy = webhookPayload.email_copy;
      var hook_structure = webhookPayload.hook_structure;
      var company_profile = webhookPayload.company_profile;
      var outcome = webhookPayload.outcome;
      
      await pool.query(
        "INSERT INTO outreach_success_log (email_copy, hook_structure, company_profile, outcome, created_at) VALUES ($1, $2, $3, $4, NOW())",
        [email_copy, hook_structure, company_profile, outcome]
      );
      
      this.successfulCopies.push({
        email_copy: email_copy,
        hook_structure: hook_structure,
        company_profile: company_profile,
        outcome: outcome,
        timestamp: new Date().toISOString()
      });
      
      console.log("Success captured and logged: " + outcome);
      return true;
    } catch (e) {
      console.error("Capture error: " + e.message);
      return false;
    }
  }

  async dailyReview() {
    try {
      var query = "SELECT email_copy, hook_structure, company_profile, outcome, created_at FROM outreach_success_log ORDER BY created_at DESC LIMIT 20";
      var { data: topExamples, error } = await pool.query(query);
      
      if (error) throw error;
      
      var patterns = analyzePatterns(topExamples || []);
      
      return {
        topPatterns: patterns,
        count: (topExamples || []).length,
        lastReviewed: new Date().toISOString()
      };
    } catch (e) {
      console.error("Daily review error: " + e.message);
      return { topPatterns: [], count: 0, lastReviewed: new Date().toISOString(), error: e.message };
    }
  }
}

module.exports = { ClosedLoopLearning: ClosedLoopLearning, analyzePatterns: analyzePatterns };