import process from "node:process";
import { Laya } from "@receptron/laya";

const cacheDir = process.env.LAYA_CACHE || "/srv/empire_os/runtime/laya/cache";
const threads = Math.max(1, Number(process.env.LAYA_THREADS || "4"));

const model = await Laya.load({
  cacheDir,
  executionProviders: ["cpu"],
  sessionOptions: { intraOpNumThreads: threads },
});

const result = await model.systemOne(
  { body: "Yes, send the one-page example." },
  {
    reply_classification: {
      type: "choice",
      instructions: "Classify buyer reply intent.",
      criteria: {
        positive: "explicit interest or request to continue",
        negative: "declines",
        unsubscribe: "asks to stop contact"
      }
    }
  }
);

console.log(JSON.stringify({
  ok: true,
  model: "convaiinnovations/laya",
  answer: result.answers?.reply_classification || null,
  shadow_only: true,
  execution_authority: "none"
}));
await model.close();
