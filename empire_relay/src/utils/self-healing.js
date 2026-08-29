import { callGLM } from "../utils/glm-client.js";
import { query } from "../utils/database.js";
import { CONFIG } from "../config/index.js";
import { promises as fs } from "fs";
import path from "path";

/**
 * MODULE 6: Self-healing diagnostics loop.
 *
 * When an external API throws an unexpected error, catch the stack trace,
 * feed the error context to GLM-5.2 to rewrite the failing function,
 * test the fix, and resume the pipeline automatically.
 */

/**
 * Wrap an async function with self-healing retry + GLM code rewrite.
 * Usage:
 *   const safeFn = withSelfHeal(apiCallFn, { module: ' TwentyCRM.push', filePath: '...' });
 *   await safeFn(args);
 */
export function withSelfHeal(fn, opts = {}) {
  const { module = "unknown", maxRetries = CONFIG.SELF_HEAL.maxRetries } = opts;

  return async function healed(...args) {
    let lastError = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn(...args);
      } catch (err) {
        lastError = err;
        console.error(`[SelfHeal] ${module} attempt ${attempt + 1} failed: ${err.message}`);

        if (attempt < maxRetries && CONFIG.SELF_HEAL.enabled) {
          // Try to rewrite the failing function via GLM
          const fix = await _rewriteFunction(err, fn, opts).catch(() => null);

          if (fix?.rewrittenFn) {
            try {
              // Test the rewritten function
              const testResult = await fix.rewrittenFn(...args);
              console.log(`[SelfHeal] ${module} fix applied successfully`);
              await _logSelfHeal(module, err, fix.description, true);

              // Optionally write the fix to disk
              if (opts.filePath && fix.code) {
                await _writeFix(opts.filePath, fix.code);
              }

              return testResult;
            } catch (fixErr) {
              console.warn(`[SelfHeal] ${module} fix also failed: ${fixErr.message}`);
              await _logSelfHeal(module, err, `Fix failed: ${fixErr.message}`, false);
            }
          } else {
            // Exponential backoff before next attempt
            const delay = Math.pow(2, attempt) * 1000;
            await new Promise((r) => setTimeout(r, delay));
          }
        }
      }
    }

    throw lastError;
  };
}

async function _rewriteFunction(error, originalFn, opts) {
  const errorContext = {
    error: error.message,
    stack: error.stack?.split("\n").slice(0, 10).join("\n"),
    moduleName: opts.module || "unknown",
  };

  const messages = [
    {
      role: "system",
      content:
        "You are a JavaScript debugging expert. An external API call is failing. " +
        "Analyze the error and provide a rewritten function that handles the failure gracefully. " +
        "Return ONLY valid JavaScript code (no markdown fences) for the corrected function body. " +
        "The function should be an async function that takes the same arguments and returns a similar result, " +
        "but with proper error handling, retries, or fallback logic as needed.",
    },
    {
      role: "user",
      content:
        `Module: ${errorContext.moduleName}\n` +
        `Error: ${errorContext.error}\n` +
        `Stack:\n${errorContext.stack}\n\n` +
        `Provide a corrected async function that handles this error. ` +
        `Return raw JavaScript: async function fixedFn(...args) { ... }`,
    },
  ];

  try {
    const result = await callGLM(messages, { maxTokens: 800, temperature: 0.2 });
    const code = result.content.trim();

    // Extract function from response
    const fnMatch = code.match(/async\s+function\s+\w+\s*\([^)]*\)\s*\{[\s\S]*\}/);
    if (!fnMatch) return null;

    // Create the rewritten function
    const rewrittenFn = new Function(`return ${fnMatch[0]}`)();

    return {
      rewrittenFn,
      code: fnMatch[0],
      description: `GLM-rewrote ${opts.module} function`,
    };
  } catch (glmErr) {
    console.warn(`[SelfHeal] GLM rewrite failed: ${glmErr.message}`);
    return null;
  }
}

async function _logSelfHeal(module, error, fixApplied, success) {
  try {
    await query(
      `INSERT INTO self_heal_log (module, error, stack_trace, fix_applied, success)
       VALUES ($1, $2, $3, $4, $5)`,
      [module, error.message, error.stack, fixApplied, success]
    );
  } catch (e) {
    // logging should never crash the pipeline
  }
}

async function _writeFix(filePath, code) {
  try {
    // Back up original
    const backupPath = `${filePath}.bak.${Date.now()}`;
    const original = await fs.readFile(filePath, "utf-8");
    await fs.writeFile(backupPath, original, "utf-8");

    // Write fix
    await fs.writeFile(filePath, code, "utf-8");
    console.log(`[SelfHeal] wrote fix to ${filePath} (backup: ${path.basename(backupPath)})`);
  } catch (e) {
    console.warn(`[SelfHeal] could not write fix: ${e.message}`);
  }
}

/**
 * Get recent self-heal events for monitoring.
 */
export async function getSelfHealHistory(limit = 20) {
  const res = await query(
    "SELECT * FROM self_heal_log ORDER BY created_at DESC LIMIT $1",
    [limit]
  );
  return res.rows;
}
