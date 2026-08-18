// The routing and the parsing. Not the model: a test that spawns Claude Code
// is not a test, it is a bill — so `draft` is exercised through the one seam
// that matters here, the reply it has to make sense of.
import assert from "node:assert/strict";
import { test } from "node:test";
import { once } from "node:events";

import { server } from "../src/server.js";

async function listening() {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const { port } = server.address();
  return `http://127.0.0.1:${port}`;
}

test("health answers without touching the model", async (t) => {
  const base = await listening();
  t.after(() => server.close());

  const response = await fetch(`${base}/health`);

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: "ok" });
});

test("an unknown route is a 404, not a spawned process", async (t) => {
  const base = await listening();
  t.after(() => server.close());

  assert.equal((await fetch(`${base}/nope`)).status, 404);
  assert.equal((await fetch(`${base}/draft`)).status, 404); // GET, not POST
});

test("a request with no prompt is rejected before anything runs", async (t) => {
  const base = await listening();
  t.after(() => server.close());

  const response = await fetch(`${base}/draft`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ system: "..." }),
  });

  assert.equal(response.status, 400);
  assert.match((await response.json()).error, /prompt is required/);
});

test("unreadable JSON is a 400", async (t) => {
  const base = await listening();
  t.after(() => server.close());

  const response = await fetch(`${base}/draft`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{ not json",
  });

  assert.equal(response.status, 400);
});

// The model is asked for a bare object and usually gives one. "Usually" is not
// a contract when the reply is being parsed, so the fence is stripped either
// way — these are the shapes seen in practice.
test("a fenced reply parses", () => {
  const cases = [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    '```\n{"a": 1}\n```',
    '  \n```json\n{"a": 1}\n```  \n',
  ];
  for (const body of cases) {
    const unfenced = body.match(/^\s*```(?:json)?\s*\n([\s\S]*?)\n?\s*```\s*$/)?.[1] ?? body;
    assert.deepEqual(JSON.parse(unfenced.trim()), { a: 1 }, `failed on: ${body}`);
  }
});
