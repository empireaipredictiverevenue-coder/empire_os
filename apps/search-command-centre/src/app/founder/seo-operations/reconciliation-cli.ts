import { filesystemReader, probe, PROTECTED_ROUTES, reconcile, SEO_ROUTE } from "./reconciliation-preflight";

async function main() {
  const args = process.argv.slice(2);
  if (!args[0] || args.slice(1).some(a => a !== "--probe-live") || args.length > 2) throw new Error("usage");
  const observations = [];
  if (args.includes("--probe-live")) for (const route of [...PROTECTED_ROUTES, SEO_ROUTE]) observations.push(await probe(route));
  const result = reconcile(filesystemReader(args[0]), observations);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  process.exitCode = result.candidateVerification === "PASS" ? 0 : 2;
}
main().catch(() => {
  process.stdout.write(JSON.stringify({ candidateVerification: "HOLD", productionRelease: "HOLD", error: "invalid_input_or_usage", usage: "reconciliation-cli.js CANDIDATE_APP_ROOT [--probe-live]", writes: false }) + "\n");
  process.exitCode = 2;
});
