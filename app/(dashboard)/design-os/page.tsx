"use client";

import { useState, useEffect, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectItem, SelectTrigger, SelectContent, SelectViewport, SelectOption } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/card";
import { useToast } from "@/hooks/use-toast";

// Empire OS design tokens
const DESIGN_TOKENS = {
  colors: {
    background: "#0a0a0f",
    card: "#12121a",
    border: "#1e1e2a",
    foreground: "#e8e8f0",
    muted: "#6b6b80",
    accent: "#00d4aa",
    error: "#ff4757",
  },
  fonts: {
    family: "'Inter', sans-serif",
    size: { base: "14px", lg: "16px" },
  },
  spacing: { xs: "4px", sm: "8px", md: "16px", lg: "32px" },
};

// ── Types ──────────────────────────────────────────────────────────────

type ModelChoice = "claude-3-5-sonnet" | "gpt-4o" | "gemini-1.5-pro";

interface DesignOSState {
  prompt: string;
  model: ModelChoice;
  generatedHTML: string | null;
  loading: boolean;
  platforms: Set<string>;
  canvasRef: React.RefObject<HTMLDivElement>;
}

interface PlatformOption {
  value: string;
  label: string;
  icon: React.ElementType;
}

// ── Component ──────────────────────────────────────────────────────────

export default function DesignOSDashboard() {
  const [state, setState] = useState<DesignOSState>({
    prompt: "",
    model: "claude-3-5-sonnet",
    generatedHTML: null,
    loading: false,
    platforms: new Set(),
    canvasRef: useRef<HTMLDivElement>(null),
  });

  const { toast } = useToast();

  // ── Generate on prompt change ────────────────────────────────────────
  const handleGenerate = async (e: React.Event) => {
    e.preventDefault();
    const { prompt, model } = state;
    if (!prompt.trim()) return;

    setState({ ...state, loading: true });

    try {
      const res = await fetch("/api/design-os/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, model_choice: model, tenant_id: "temp_tenant" }),
      });

      const data = await res.json();
      if (res.ok) {
        setState({ ...state, generatedHTML: data.html, loading: false });
      } else {
        toast({
          title: "Generation Failed",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
        setState({ ...state, loading: false });
      }
    } catch (err) {
      toast({
        title: "Network Error",
        description: "Could not reach design OS generator",
        variant: "destructive",
      });
      setState({ ...state, loading: false });
    }
  };

  // ── Publish ──────────────────────────────────────────────────────────
  const handlePublish = async () => {
    if (state.platforms.size === 0) {
      toast({ title: "No Platforms Selected", description: "Select at least one platform to publish to.", variant: "destructive" });
      return;
    }
    if (!state.generatedHTML) {
      toast({ title: "No Content", description: "Generate design content first.", variant: "destructive" });
      return;
    }

    setState({ ...state, loading: true });

    try {
      const res = await fetch("/api/design-os/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "temp_project",
          platforms: Array.from(state.platforms),
        }),
      });

      const data = await res.json();
      if (res.ok) {
        toast({ title: "Publishing Complete", description: `${data.results.filter((r: any) => r.status === "published").length}/${data.results.length} platforms published successfully` });
        setState({ ...state, platforms: new Set(), loading: false });
      } else {
        toast({
          title: "Publish Failed",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
        setState({ ...state, loading: false });
      }
    } catch (err) {
      toast({
        title: "Network Error",
        description: "Could not reach social distribution service",
        variant: "destructive",
      });
      setState({ ...state, loading: false });
    }
  };

  // ── Render ──────────────────────────────────────────────────────────

  return (
    <Card className="bg-[var(--color-background)] border-b-[var(--color-border)]">
      <CardHeader>
        <CardTitle>Design OS — Empire OS</CardTitle>
      </CardHeader>

      <CardContent className="p-4 space-y-6">

        {/* Left Panel: Prompt + Model Selector */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--color-foreground)] mb-2">
              Prompt
            </label>
            <Input
              value={state.prompt}
              onChange={(e) => setState({ ...state, prompt: e.target.value }) }
              placeholder="Enter design prompt..."
              disabled={state.loading}
            />
          </div>

          <Select disabled={state.loading} defaultOpen>
            <SelectTrigger>
              <SelectValue className="justify-start">
                <span className="font-medium">{state.model}</span>
              </SelectValue>
              <SelectContent>
                <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
                <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                <SelectItem value="gemini-1.5-pro">Gemini 1.5 Pro</SelectItem>
              </SelectContent>
            </SelectTrigger>
          </Select>
        </div>

        {/* Right Panel: Visual Canvas + Preview */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">

          {/* Canvas Preview */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-foreground)] mb-2">
              Preview
            </label>
            <Card className="bg-[var(--color-card)] border-[var(--color-border)] h-[300px] overflow-hidden">
              <div
                ref={state.canvasRef}
                className="p-4 flex flex-col items-center justify-center min-h-full"
              >
                {state.generatedHTML
                  ? (
                      <div dangerouslySetInnerHTML={{ __html: state.generatedHTML }} />
                    )
                  : (
                    <div className="text-[var(--color-muted)] text-sm center-align">
                      No design generated yet
                    </div>
                  )}
              </div>
            </Card>

            <Button
              onClick={handleGenerate}
              disabled={state.loading}
              className="w-full py-2 bg-[var(--color-accent)] text-[var(--color-background)] font-medium hover:opacity-90 transition-opacity"
            >
              {state.loading ? "Generating..." : "Generate Design"}
            </Button>
          </div>

          {/* Publishing Panel */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-foreground)] mb-2">
              Publish To
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="checkbox"
                checked={state.platforms.has("instagram")}
                onChange={(e) => setState(s => ({ ...s, platforms: e.target.checked ? new Set([...s.platforms, "instagram"]) : new Set(s.platforms.filter(v => v !== "instagram")) }))}
                className="w-4 h-4 rounded border-[var(--color-border)] bg-[var(--color-card)] cursor-pointer"
              />
              <span className="text-[var(--color-foreground)]">Instagram</span>

              <button
                type="checkbox"
                checked={state.platforms.has("linkedin")}
                onChange={(e) => setState(s => ({ ...s, platforms: e.target.checked ? new Set([...s.platforms, "linkedin"]) : new Set(s.platforms.filter(v => v !== "linkedin")) }))}
                className="w-4 h-4 rounded border-[var(--color-border)] bg-[var(--color-card)] cursor-pointer"
              />
              <span className="text-[var(--color-foreground)]">LinkedIn</span>

              <button
                type="checkbox"
                checked={state.platforms.has("x")}
                onChange={(e) => setState(s => ({ ...s, platforms: e.target.checked ? new Set([...s.platforms, "x"]) : new Set(s.platforms.filter(v => v !== "x")) }))}
                className="w-4 h-4 rounded border-[var(--color-border)] bg-[var(--color-card)] cursor-pointer"
              />
              <span className="text-[var(--color-foreground)]">X</span>

              <button
                type="checkbox"
                checked={state.platforms.has("facebook")}
                onChange={(e) => setState(s => ({ ...s, platforms: e.target.checked ? new Set([...s.platforms, "facebook"]) : new Set(s.platforms.filter(v => v !== "facebook")) }))}
                className="w-4 h-4 rounded border-[var(--color-border)] bg-[var(--color-card)] cursor-pointer"
              />
              <span className="text-[var(--color-foreground)]">Facebook</span>
            </div>

            <Button
              onClick={handlePublish}
              disabled={state.loading || state.generatedHTML == null || state.platforms.size === 0}
              className="w-full py-2 bg-[var(--color-accent)] text-[var(--color-background)] font-medium hover:opacity-90 transition-opacity mt-3"
            >
              {state.loading ? "Publishing..." : "Publish Design"}
            </Button>
          </div>
        </div>

      </CardContent>
    </Card>
  );
}