import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { PotatoAPI } from "@potato-inc/potato-sdk";

// ── Initialize Supabase ──────────────────────────────────────────────────
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Potato API client
const potato = new PotatoAPI({ apiKey: process.env.POTATO_API_KEY });

// ── Platform Endpoints ──────────────────────────────────────────────────
const PLATFORM_ENDPOINTS = {
  instagram: "https://api.potato.io/v1/social/instagram/post",
  linkedin: "https://api.potato.io/v1/social/linkedin/post",
  x: "https://api.potato.io/v1/social/x/post",
  facebook: "https://api.potato.io/v1/social/facebook/post",
} as const;

// ── Helper: Extract first image from HTML ───────────────────────────────
const extractFirstImage = (html: string) => {
  const match = html.match(/<img[^>]+src="([^"]+)"[^>]*>/i);
  return match ? match[1] : null;
};

// ── Helper: Strip HTML for social platform text ─────────────────────────
const stripHTML = (html: string) =>
  html
    .replace(/<script[^>]*>.*?<\/script>/gi, "")
    .replace(/<style[^>]*>.*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .trim();

// ── Phase 3: Social Publish API ──────────────────────────────────────────
export async function POST(request: NextRequest) {
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

    // ── Dispatch to Social Platforms ────────────────────────────────────
    const dispatchResults = await Promise.allSettled(
      platforms.map(async (platform) => {
        const endpoint = PLATFORM_ENDPOINTS[platform];
        if (!endpoint) {
          return { platform, status: "failed" as const, error: "unknown platform" };
        }

        try {
          const result = await fetch(endpoint, {
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

          const data = await result.json();
          return { platform, status: result.ok ? "published" : "failed", data };
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