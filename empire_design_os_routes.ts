import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import Redis from "ioredis";

// ── Initialize Supabase ──────────────────────────────────────────────────
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Redis with 24h TTL for caching identical prompts
const redis = new Redis({
  host: process.env.REDIS_HOST || "127.0.0.1",
  port: Number(process.env.REDIS_PORT || 6379),
  password: process.env.REDIS_PASSWORD || undefined,
});

// ── Dynamic SDK Routing ──────────────────────────────────────────────────
async function routeByModel(modelChoice: string, prompt: string, systemInstructions?: string): Promise<string> {
  switch (modelChoice) {
    case "claude-3-5-sonnet": {
      // Import lazily to avoid unused deps errors
      const { CompletionClient } = await import("@anthropic-vertex/client");
      const client = new CompletionClient({ region: "us-central1" });
      const result = await client.messages.create({
        max_tokens: 4096,
        temperature: 0.7,
        system: systemInstructions || "You are a helpful designer generating HTML/React components.",
        messages: [{ role: "user", content: prompt }],
      });
      return result.content[0].type === "text" ? result.content[0].text : JSON.stringify(result.content);
    }
    case "gpt-4o": {
      const { Configuration, OpenAIApi } = await import("openai");
      const config = new Configuration({ apiKey: process.env.OPENAI_API_KEY });
      const openai = new OpenAIApi(config);
      const result = await openai.createChatCompletion({
        model: "gpt-4o",
        messages: [
          { role: "system", content: systemInstructions || "You are a helpful designer." },
          { role: "user", content: prompt },
        ],
      });
      return result.choices[0].message.content || "";
    }
    case "gemini-1.5-pro": {
      const { GoogleGenerativeAI } = await import("@google/generative-ai");
      const genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY!);
      const model = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });
      const result = await model.generateContent({
        systemInstruction: systemInstructions || "You are a helpful designer.",
        contents: prompt,
      });
      return result.response.text();
    }
    default:
      throw new Error(`Unsupported model_choice: ${modelChoice}`);
  }
}

// ── Caching Helper ──────────────────────────────────────────────────────
async function getCachedPrompt(key: string): Promise<string | null> {
  try {
    const cached = await redis.get(key);
    if (cached) return cached;
    // Set placeholder with 24h TTL to prevent cache stampedes
    await redis.setex(key, 86400, "");
    return null;
  } catch (e) {
    // If Redis fails, just proceed without caching
    return null;
  }
}

async function setCachedPrompt(key: string, value: string): Promise<void> {
  try {
    await redis.setex(key, 86400, value);
  } catch (e) {
    // Redis down — not fatal, proceed without cache
  }
}

// ── Phase 2: Generate API ────────────────────────────────────────────────
export async function POST(request: NextRequest) {
  try {
    const { prompt, model_choice, system_instructions, tenant_id } =
      await request.json();

    if (!prompt || !model_choice || !tenant_id) {
      return NextResponse.json(
        { error: "prompt, model_choice, and tenant_id are required" },
        { status: 400 }
      );
    }

    // ── Redis Cache Check (24h TTL) ─────────────────────────────────────
    const cacheKey = `design_os:${tenant_id}:${model_choice}:${prompt.replace(/\s+/g, "_")}`;
    const cached = await getCachedPrompt(cacheKey);
    if (cached) {
      return NextResponse.json({ html: cached, from_cache: true });
    }

    // ── Dynamic SDK Routing ─────────────────────────────────────────────
    let html: string;
    try {
      html = await routeByModel(model_choice, prompt, system_instructions);
    } catch (modelError) {
      console.error(`❌ Model ${model_choice} failed:`, modelError);
      return NextResponse.json(
        { error: `Model ${model_choice} generation failed: ${(modelError as Error).message}` },
        { status: 502 }
      );
    }

    // ── Cache the result (24h) ──────────────────────────────────────────
    await setCachedPrompt(cacheKey, html);

    return NextResponse.json({ html, from_cache: false }, { status: 200 });
  } catch (error: any) {
    console.error("❌ Design OS generate error:", error);
    return NextResponse.json(
      { error: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}

// ── Phase 3: Social Publish API ──────────────────────────────────────────
export async function PUT(request: NextRequest) {
  try {
    const { project_id, platforms = [] as string[] } = await request.json();

    if (!project_id || platforms.length === 0) {
      return NextResponse.json(
        { error: "project_id and at least one platform are required" },
        { status: 400 }
      );
    }

    // ── Fetch Design Project from Supabase ───────────────────────────────
    const { data: project, error: projError } = await supabase
      .from("empire_design_projects")
      .select("*")
      .eq("id", project_id)
      .single();

    if (projError || !project) {
      return NextResponse.json(
        { error: "Project not found", details: projError?.message },
        { status: 404 }
      );
    }

    // ── Extract Visual Assets ──────────────────────────────────────────
    const html = Array.isArray(project.html_content)
      ? project.html_content[0]?.content || ""
      : project.html_content || "";

    const extractFirstImage = (html: string) => {
      const match = html.match(/<img[^>]+src="([^"]+)"[^>]*>/i);
      return match ? match[1] : null;
    };

    const stripHTML = (html: string) =>
      html
        .replace(/<script[^>]*>.*?<\/script>/gi, "")
        .replace(/<style[^>]*>.*?<\/style>/gi, "")
        .replace(/<[^>]+>/g, "")
        .replace(/&nbsp;/g, " ")
        .trim();

    // ── Dispatch to Social Platforms via Potato API ──────────────────────
    const PLATFORM_ENDPOINTS = {
      instagram: "https://api.potato.io/v1/social/instagram/post",
      linkedin: "https://api.potato.io/v1/social/linkedin/post",
      x: "https://api.potato.io/v1/social/x/post",
      facebook: "https://api.potato.io/v1/social/facebook/post",
    };

    const dispatchResults = await Promise.allSettled(
      platforms.map(async (platform) => {
        const endpoint = PLATFORM_ENDPOINTS[platform];
        if (!endpoint) {
          return { platform, status: "failed" as const, error: "unknown platform" };
        }

        try {
          const potatoResponse = await fetch(endpoint, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${process.env.POTATO_API_KEY}`,
            },
            body: JSON.stringify({
              image: extractFirstImage(html),
              content: stripHTML(html).substring(0, 280),
              platform,
            }),
          });

          const result = await potatoResponse.json();
          return { platform, status: potatoResponse.ok ? "published" : "failed", result };
        } catch (err) {
          console.error(`❌ Potato API ${platform} error:`, err);
          return { platform, status: "failed" as const, error: (err as Error).message };
        }
      })
    );

    // ── Update empire_social_queue ──────────────────────────────────────
    const allPublished = dispatchResults.every(
      (r) => r.status === "fulfilled" && r.value.status === "published"
    );

    const queueUpdate = {
      project_id,
      platforms,
      status: allPublished ? "published" : "failed",
      api_response: {
        social_publish: dispatchResults.map((r) => ({
          platform: r.platform,
          status: r.status,
        })),
      },
      updated_at: new Date().toISOString(),
    };

    // Upsert queue entry
    const { error: queueError } = await supabase
      .from("empire_social_queue")
      .upsert({
        id: crypto.randomUUID(),
        project_id,
        platforms,
        status: allPublished ? "published" : "failed",
        api_response: queueUpdate.api_response,
        updated_at: new Date().toISOString(),
      })
      .select()
      .single();

    if (queueError) console.error("❌ Social queue upsert error:", queueError);

    return NextResponse.json({
      success: allPublished,
      results: dispatchResults.map((r) => ({
        platform: r.platform,
        status: r.value.status,
      })),
    });
  } catch (error: any) {
    console.error("❌ Design OS publish error:", error);
    return NextResponse.json(
      { error: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}