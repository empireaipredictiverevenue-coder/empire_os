import dotenv from "dotenv";
dotenv.config();

export const CONFIG = {
  PORT: parseInt(process.env.PORT || "3000", 10),
  REDIS_URL: process.env.REDIS_URL || "redis://127.0.0.1:6379",

  PG: {
    host: process.env.PG_HOST || "127.0.0.1",
    port: parseInt(process.env.PG_PORT || "5432", 10),
    database: process.env.PG_DB || "empire_relay",
    user: process.env.PG_USER || "empire",
    password: process.env.PG_PASSWORD || "empire2026",
  },

  GLM: {
    apiKey: process.env.GLM_API_KEY,
    baseUrl: process.env.GLM_BASE_URL || "https://integrate.api.nvidia.com/v1",
    model: process.env.GLM_MODEL || process.env.GLM_MODEL || "deepseek-ai/deepseek-v4-flash-0731",
    maxTokens: 1024,
    temperature: 0.4,
  },

  RESEND: {
    apiKey: process.env.RESEND_API_KEY,
    from: process.env.RESEND_FROM || "Empire AI <founder@empire-ai.co.uk>",
  },

  TWENTY: {
    url: process.env.TWENTY_CRM_URL || "http://127.0.0.1:80",
    apiKey: process.env.TWENTY_CRM_API_KEY || "",
  },

  RATE_LIMITS: {
    resend: parseInt(process.env.RATE_LIMIT_RESEND || "30", 10),
    twenty: parseInt(process.env.RATE_LIMIT_TWENTY || "60", 10),
    waterfall: parseInt(process.env.RATE_LIMIT_WATERFALL || "20", 10),
    glm: parseInt(process.env.RATE_LIMIT_GLM || "50", 10),
  },

  GAUNTLET: {
    maxIterations: parseInt(process.env.GAUNTLET_MAX_ITERATIONS || "3", 10),
    qualityThreshold: parseInt(process.env.GAUNTLET_QUALITY_THRESHOLD || "7", 10),
  },

  SELF_HEAL: {
    enabled: process.env.SELF_HEAL_ENABLED === "true",
    maxRetries: parseInt(process.env.SELF_HEAL_MAX_RETRIES || "2", 10),
  },

  HUB_DB: process.env.HUB_DB_PATH || "/root/empire_os/empire_os.db",

  SERPER_KEY: process.env.SERPER_API_KEY,
  WATERFALL_SOURCES: (process.env.WATERFALL_SOURCES || "serper,scrapecreators,reddit").split(","),
};
