import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // Use the installed TypeScript 5 compiler API; sandbox child stdout capture
  // can be empty for the CLI --showConfig path. Type checking remains enabled.
  experimental: { useTypeScriptCli: false },
  images: { unoptimized: true },
};

export default nextConfig;
