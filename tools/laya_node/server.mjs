import http from "node:http";
import process from "node:process";
import { Laya } from "@receptron/laya";

const host = process.env.LAYA_HOST || "127.0.0.1";
const port = Number(process.env.LAYA_PORT || "8769");
const cacheDir = process.env.LAYA_CACHE || "/srv/empire_os/runtime/laya/cache";
const apiKey = process.env.LAYA_API_KEY || "";
const threads = Math.max(1, Number(process.env.LAYA_THREADS || "4"));
const maxBodyBytes = 256 * 1024;

const model = await Laya.load({
  cacheDir,
  executionProviders: ["cpu"],
  sessionOptions: { intraOpNumThreads: threads },
});

let queue = Promise.resolve();

function send(res, status, body) {
  const payload = Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": String(payload.length),
    "cache-control": "no-store",
  });
  res.end(payload);
}

function authorized(req) {
  if (!apiKey) return true;
  return req.headers.authorization === `Bearer ${apiKey}`;
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > maxBodyBytes) {
        reject(new Error("request_body_too_large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      try {
        const value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
        resolve(value);
      } catch {
        reject(new Error("invalid_json"));
      }
    });
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    send(res, 200, {
      ok: true,
      service: "empire-laya-shadow",
      model: "convaiinnovations/laya",
      shadow_only: true,
      execution_authority: "none",
    });
    return;
  }

  if (req.method !== "POST" || req.url !== "/v1/systemone") {
    send(res, 404, { error: "not_found" });
    return;
  }
  if (!authorized(req)) {
    send(res, 401, { error: "unauthorized" });
    return;
  }

  try {
    const body = await readJson(req);
    if (
      !body ||
      typeof body !== "object" ||
      !body.state ||
      typeof body.state !== "object" ||
      !body.questions ||
      typeof body.questions !== "object"
    ) {
      send(res, 400, { error: "state_and_questions_required" });
      return;
    }

    const task = async () => model.systemOne(body.state, body.questions);
    const pending = queue.then(task, task);
    queue = pending.then(() => undefined, () => undefined);
    const result = await pending;
    send(res, 200, result);
  } catch (error) {
    send(res, 400, {
      error: "decision_failed",
      detail: String(error?.message || error).slice(0, 200),
    });
  }
});

server.listen(port, host, () => {
  console.log(JSON.stringify({
    event: "laya_shadow_ready",
    host,
    port,
    cacheDir,
    shadow_only: true,
    execution_authority: "none",
  }));
});

async function shutdown() {
  server.close(async () => {
    try {
      await model.close();
    } finally {
      process.exit(0);
    }
  });
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
