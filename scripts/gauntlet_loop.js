// Module 3: Gauntlet Loop Copy Engine
// Implements Gauntlet Loop technique for hyper-personalized outreach
// Sub-agents: researcher, hook_drafts, critic
// Iterates until critic approves

require('dotenv').config();
const { Pool } = require('pg'); // For Supabase/Postgres connection

// Supabase connection for critic patterns + storing wins
const pool = new Pool({
  connectionString: process.env.SUPABASE_DB_URL,
});

// Gauntlet Loop engine
class GauntletEngine {
  constructor() {
    this.winningPatterns = new Map(); // Store approved copy patterns
  }

  // FAN OUT: Create sub-agents
  async runGauntlet(leadProfile, companyContext) {
    const researcher = await this.researchCompany(leadProfile, companyContext);
    const hookDrafts = this.generateHooks(researcher, leadProfile);
    
    // CRITIC: Evaluate against winning patterns
    let iteration = 0;
    let approved = false;
    let currentDraft = hookDrafts[0];
    
    while (!approved && iteration < 10) {
      const criticResult = await this.criticEvaluate(currentDraft, researcher);
      
      if (criticResult.approved) {
        approved = true;
        console.log(`Gauntlet approved after ${iteration + 1} iterations`);
        await this.saveVettedDraft(leadProfile, currentDraft);
        break;
      }
      
      // ITERATE: Force builder to improve
      currentDraft = await this.iterateDraft(currentDraft, criticResult.feedback, researcher, leadProfile);
      iteration++;
    }
    
    if (!approved) {
      console.error('Gauntlet failed to approve after max iterations');
      return null;
    }
    
    return currentDraft;
  }

  // Sub-agent: Research company news/signals
  async researchCompany(leadProfile, companyContext) {
    // Research company news, funding, signals
    const signals = {
      recentNews: 'None found',
      funding: 'None',
      growthSignals: [],
      techStack: 'Unknown'
    };
    
    // Search for company signals
    try {
      // Would use various APIs here
      signals.recentNews = 'Checking news sources...';
      signals.growthSignals = ['Revenue growth indicator'];
    } catch (e) {
      console.error('Research error:', e.message);
    }
    
    return signals;
  }

  // Sub-agent: Draft hooks
  generateHooks(researcher, leadProfile) {
    const hooks = [];
    
    // Generate multiple hook variations based on research
    hooks.push(`Hi ${leadProfile.firstName}, I noticed ${researcher.growthSignals[0]} and thought of you...`);
    hooks.push(`Congrats on ${researcher.recentNews}, I have a relevant opportunity...`);
    hooks.push(`Quick question about ${leadProfile.niche} expansion...`);
    
    return hooks;
  }

  // Critic agent: Evaluate against winning patterns
  async criticEvaluate(draft, researcher) {
    // Check against stored winning patterns from Supabase
    const { data: patterns } = await pool.query(
      `SELECT pattern_text, conversion_rate FROM gauntlet_winning_patterns ORDER BY conversion_rate DESC LIMIT 5`
    );
    
    const feedback = {
      approved: false,
      score: 0,
      feedback: []
    };
    
    // Score the draft against patterns
    let totalScore = 0;
    
    for (const pattern of patterns) {
      const score = this.scoreAgainstPattern(draft, pattern.pattern_text);
      totalScore += score;
      if (score > 0.7) {
        feedback.feedback.push(`Good alignment with: ${pattern.pattern_text.substring(0, 50)}...`);
      }
    }
    
    feedback.score = totalScore / patterns.length;
    feedback.approved = feedback.score >= 0.8;
    feedback.feedback.push(`Overall score: ${Math.round(feedback.score * 100)}%`);
    
    // If not approved, provide specific feedback
    if (!feedback.approved) {
      feedback.feedback.push('Needs more personalization. Reference company-specific details.');
      feedback.feedback.push('Stronger hook needed - focus on pain point, not company name.');
    }
    
    return feedback;
  }

  // Score draft against a pattern
  scoreAgainstPattern(draft, patternText) {
    const draftLower = draft.toLowerCase();
    const patternLower = patternText.toLowerCase();
    
    // Simple keyword overlap scoring
    const patternWords = patternLower.split(' ');
    const matchingWords = patternWords.filter(word => draftLower.includes(word));
    
    return matchingWords.length / patternWords.length;
  }

  // Iterate: Improve the draft based on critic feedback
  async iterateDraft(currentDraft, feedback, researcher, leadProfile) {
    const improved = currentDraft;
    
    // Apply fixes based on feedback
    if (feedback.feedback.some(f => f.includes('personalization'))) {
      // Add company-specific detail
      improved = improved.replace('Hi ', `Hi ${leadProfile.firstName}, I saw that ${leadProfile.company} `);
    }
    
    if (feedback.feedback.some(f => f.includes('hook'))) {
      // Strengthen the hook
      improved = improved.replace('Congrats', 'Impressive growth on');
    }
    
    return improved;
  }

  // Save vetted draft back to CRM/Supabase
  async saveVettedDraft(leadProfile, draft) {
    try {
      await pool.query(
        `INSERT INTO lead_copy_templates (lead_id, company, niche, hook_text, status, created_at) VALUES ($1, $2, $3, $4, 'vetted', NOW())`,
        [leadProfile.id, leadProfile.company, leadProfile.niche, draft]
      );
      console.log('Vetted draft saved to Supabase');
    } catch (e) {
      console.error('Save error:', e.message);
    }
  }
}

// CLI interface
if (require.main === module) {
  const company = process.argv[2];
  const firstName = process.argv[3];
  const niche = process.argv[4];
  
  const leadProfile = { id: uuidv4(), company, firstName, niche };
  
  const engine = new GauntletEngine();
  engine.runGauntlet(leadProfile, {}).then(draft => {
    if (draft) {
      console.log('=== APPROVED DRAFT ===');
      console.log(draft);
    }
    process.exit(0);
  });
}

// Helper
function uuidv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : r & 0x3 | 0x8;
    return v.toString(16);
  });
}

module.exports = { GauntletEngine };
