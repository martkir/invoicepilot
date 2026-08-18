// Runs Claude Code and returns the JSON it produced. That is the whole service.
//
// It exists because of an authentication boundary, not a design preference.
// The api service drafts a template for an issuer no template covers, and the
// credential available on this deployment is the OAuth token Claude Code holds
// for itself. That token authenticates against the public Messages API — it
// resolves to an organization — but the API declines to serve it to a
// third-party client, returning a 429 carrying none of the rate-limit headers a
// real quota response has. Claude Code itself is served, so the way to use the
// credential is to be Claude Code.
//
// Nothing here knows what an invoice is. It takes a prompt and a system prompt,
// runs them, and hands back parsed JSON; every rule about what a template looks
// like stays in the api service, in one place. That also means this is only a
// transport, and swapping it for a direct API call is a change of one class in
// invoicepilot/learn.py.
//
// No framework and no build step: it is one route, and Node has an HTTP server.
// Callers are sequential by construction — the scan teaches one issuer at a
// time — so there is no queue here, and each request spawns its own process.

import http from "node:http";
import { query } from "@anthropic-ai/claude-agent-sdk";

const PORT = Number(process.env.PORT || 8100);
const HOST = process.env.HOST || "0.0.0.0";

// A draft is a few hundred tokens, but the model reasons first and the process
// has to start. Generous, because the caller's alternative to waiting is
// failing to teach an issuer at all.
const TIMEOUT_MS = Number(process.env.DRAFT_TIMEOUT_MS || 180_000);

// Enough turns for a reply plus the harness's own bookkeeping. One is not:
// the run ends in error_max_turns before any text arrives.
const MAX_TURNS = 4;

const MAX_BODY_BYTES = 1_000_000;

// The model is asked for a bare object and usually gives one, but "usually" is
// not a contract when the reply is parsed.
const FENCE = /^\s*```(?:json)?\s*\n([\s\S]*?)\n?\s*```\s*$/;

function parseJson(text) {
  const unfenced = text.match(FENCE)?.[1] ?? text;
  return JSON.parse(unfenced.trim());
}

async function draft(prompt, system) {
  const abortController = new AbortController();
  const timer = setTimeout(() => abortController.abort(), TIMEOUT_MS);
  let text = "";
  try {
    for await (const message of query({
      prompt,
      options: {
        abortController,
        maxTurns: MAX_TURNS,
        // A pure text task. Without this the harness offers a filesystem it has
        // no reason to touch, and a turn spent reaching for one is a turn not
        // spent answering.
        allowedTools: [],
        systemPrompt: system,
      },
    })) {
      if (message.type === "assistant") {
        for (const block of message.message?.content ?? []) {
          if (block.type === "text") text += block.text;
        }
      }
      if (message.type === "result" && message.is_error) {
        // A `success` subtype with is_error set is a turn that ended on an API
        // error, and the reason is in `result` — reporting the subtype instead
        // produces the useless "claude code failed: success".
        throw new Error(`claude code failed: ${message.result || message.subtype}`);
      }
    }
  } finally {
    clearTimeout(timer);
  }
  if (!text.trim()) throw new Error("claude code returned no text");
  return parseJson(text);
}

function send(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(payload),
  });
  response.end(payload);
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error("request body too large"));
        request.destroy();
        return;
      }
      chunks.push(chunk);
    });
    request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    request.on("error", reject);
  });
}

export const server = http.createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    return send(response, 200, { status: "ok" });
  }
  if (request.method !== "POST" || request.url !== "/draft") {
    return send(response, 404, { error: "not found" });
  }

  let prompt;
  let system;
  try {
    ({ prompt, system } = JSON.parse(await readBody(request)));
  } catch (error) {
    return send(response, 400, { error: `unreadable request: ${error.message}` });
  }
  if (typeof prompt !== "string" || !prompt.trim()) {
    return send(response, 400, { error: "prompt is required" });
  }

  try {
    return send(response, 200, { draft: await draft(prompt, system) });
  } catch (error) {
    // 502 rather than 500: the failure is upstream, and the caller treats it as
    // "could not draft this one" — which leaves the issuer to be tried again
    // rather than recorded as impossible.
    console.error(`draft failed: ${error.message}`);
    return send(response, 502, { error: error.message });
  }
});

if (import.meta.url === `file://${process.argv[1]}`) {
  server.listen(PORT, HOST, () => console.log(`drafter listening on ${HOST}:${PORT}`));
}
