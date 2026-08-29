import { CONFIG } from "../config/index.js";
import { limiters } from "../middleware/rate-limiter.js";

/**
 * GLM-5.2 via NVIDIA NIM — OpenAI-compatible endpoint.
 * Rate-limited via Redis. Used by Gauntlet Loop, Learning Engine, Self-Healing.
 */
export async function callGLM(messages, options = {}) {
  await limiters.glm.waitForSlot();

  const body = {
    model: CONFIG.GLM.model,
    messages,
    temperature: options.temperature ?? CONFIG.GLM.temperature,
    max_tokens: options.maxTokens ?? CONFIG.GLM.maxTokens,
    stream: false,
    // gpt-oss / nemotron reasoning models: cap thinking so content budget survives
    ...(String(CONFIG.GLM.model).includes("gpt-oss")
      ? { reasoning_effort: "low", max_tokens: Math.max(options.maxTokens ?? 0, 1600) }
      : {}),
  };

  const resp = await fetch(`${CONFIG.GLM.baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${CONFIG.GLM.apiKey}`,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new GLMApiError(resp.status, text, body.model);
  }

  const data = await resp.json();
  const content = data.choices?.[0]?.message?.content || "";

  return {
    content,
    tokens: data.usage?.total_tokens || 0,
    model: data.model || CONFIG.GLM.model,
  };
}

/**
 * Streaming GLM call — for real-time copy generation feedback.
 */
export async function callGLMStream(messages, onChunk, options = {}) {
  await limiters.glm.waitForSlot();

  const body = {
    model: CONFIG.GLM.model,
    messages,
    temperature: options.temperature ?? CONFIG.GLM.temperature,
    max_tokens: options.maxTokens ?? CONFIG.GLM.maxTokens,
    stream: true,
  };

  const resp = await fetch(`${CONFIG.GLM.baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${CONFIG.GLM.apiKey}`,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new GLMApiError(resp.status, text, body.model);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let fullContent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split("\n").filter((l) => l.startsWith("data: "));

    for (const line of lines) {
      const json = line.slice(6).trim();
      if (json === "[DONE]") continue;
      try {
        const parsed = JSON.parse(json);
        const delta = parsed.choices?.[0]?.delta?.content || "";
        if (delta) {
          fullContent += delta;
          onChunk?.(delta, fullContent);
        }
      } catch {
        // skip malformed chunks
      }
    }
  }

  return { content: fullContent, model: CONFIG.GLM.model };
}

export class GLMApiError extends Error {
  constructor(status, body, model) {
    super(`GLM API ${status}: ${body.slice(0, 200)}`);
    this.name = "GLMApiError";
    this.status = status;
    this.responseBody = body;
    this.model = model;
  }
}
