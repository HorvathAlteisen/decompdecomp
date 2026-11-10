// The Agents tab's Stop and Stop all, run with the real code of agents.js: no server, no browser.
// With 70 helpers at work, the app answered a stop after one minute. The row did not change in that time. Also, a poll
// that drew the list again between the press and the release of a button cancelled the click.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const js = process.env.GUI_JS || path.join(__dirname, "..", "src", "decompnet", "app", "static", "js");
const source = fs.readFileSync(path.join(js, "agents.js"), "utf8").replace(/\r\n/g, "\n");
const start = source.indexOf("const LIVE = ["), end = source.lastIndexOf("/*", source.indexOf(" the launcher: "));
assert.ok(start >= 0 && end > start, "the Agents tab's code in agents.js");
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };

function setup() {
  const elements = new Map(), listeners = {}, timers = [], toasts = [], asked = [];
  let answer = null;
  const element = () => ({ hidden: false, disabled: false, textContent: "", innerHTML: "" });
  const get = (id) => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  const box = get("sessions");
  // the buttons the list has now, as the browser finds them in its HTML
  box.querySelectorAll = (selector) => {
    const attr = (selector.match(/^\[data-(\w+)\]$/) || [])[1];
    if (!attr) return [];
    return [...box.innerHTML.matchAll(new RegExp(`data-${attr}="([^"]*)"`, "g"))].map((m) => {
      const b = { dataset: { [attr]: m[1] }, disabled: false };
      (box.buttons ||= []).push(b);
      return b;
    });
  };
  const ctx = {
    $: get, S: { slug: "game", sessions: [], claims: [], stats: null, logFor: null },
    esc: (t) => String(t), setHtml: (el, html) => { el.innerHTML = html; }, plural: (n, w) => `${n} ${w}s`,
    money: String, clock: () => "12:00:00", fnLink: String, reading: () => "", rowTint: () => "", openFn() {},
    renderRoomAgents() {}, renderLog() {}, poll() {}, toast: (html) => toasts.push(html),
    addEventListener: (name, fn) => { (listeners[name] ||= []).push(fn); },
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    api(url, opts) {
      if (url.startsWith("/api/modelcosts")) return Promise.resolve([]);
      asked.push([url, opts && opts.body]);
      answer = {};
      answer.promise = new Promise((resolve, reject) => { answer.resolve = resolve; answer.reject = reject; });
      return answer.promise;
    },
  };
  vm.createContext(ctx);
  vm.runInContext(source.slice(start, end), ctx, { filename: "agents.js" });
  const helper = (id, state = "working", said = "") => ({ id, agent: id, label: id, state, kind_name: "Claude Code",
    model: "m", task: "", last_message: said });
  const button = (id) => box.buttons.filter((b) => b.dataset.stop === id).at(-1);
  const row = (id) => box.innerHTML.split('<div class="session').find((r) => r.includes(`title="${id}"`)) || "";
  const draw = (sessions) => { ctx.S.sessions = sessions; vm.runInContext("renderSessions(S.sessions)", ctx); };
  const release = () => { (listeners.pointerup || []).forEach((fn) => fn()); timers.splice(0).forEach((fn) => fn()); };
  return { ctx, get, box, toasts, asked, answer: () => answer, helper, button, row, draw, release };
}

async function main() {
  // Stop on one row: the row says "Stopping…" before the app answers
  {
    const t = setup();
    t.draw([t.helper("claude-1"), t.helper("claude-2")]);
    t.button("claude-1").onclick();
    assert.equal(JSON.stringify(t.asked), JSON.stringify([["/api/agents/stop", { id: "claude-1" }]]));  // (its objects come from the page's realm)
    assert.match(t.row("claude-1"), /Stopping…/, "the row of the stopped helper says Stopping… at once");
    assert.doesNotMatch(t.row("claude-1"), /data-stop=/, "its Stop button is not there to press again");
    assert.match(t.row("claude-2"), /data-stop="claude-2"/, "the other helper keeps its Stop");
    // a poll before the app answers: the helper is still at work there, and the row still says Stopping…
    t.draw([t.helper("claude-1", "working", "new words"), t.helper("claude-2")]);
    assert.match(t.row("claude-1"), /Stopping…/);
    t.answer().resolve({ ok: true });
    await flush();
    t.draw([Object.assign(t.helper("claude-1", "stopped"), { stopped_by: "you" }), t.helper("claude-2")]);
    assert.match(t.row("claude-1"), /Stopped by you/);
    assert.match(t.row("claude-1"), /data-again="claude-1"/);
  }
  // Stop that the app refuses: the row shows Stop again, and the error
  {
    const t = setup();
    t.draw([t.helper("claude-1"), t.helper("claude-2")]);
    t.button("claude-1").onclick();
    t.answer().reject(new Error("the app is busy"));
    await flush();
    assert.match(t.row("claude-1"), /data-stop="claude-1"/);
    assert.deepEqual(t.toasts, ["the app is busy"]);
  }
  // Stop all: it says so, and every row says "Stopping…", before the app answers
  {
    const t = setup();
    t.draw([t.helper("claude-1"), t.helper("claude-2"), t.helper("claude-3", "stopped")]);
    assert.equal(t.get("stopAll").hidden, false);
    t.get("stopAll").onclick();
    assert.equal(JSON.stringify(t.asked), JSON.stringify([["/api/agents/stop", { slug: "game" }]]));
    assert.deepEqual(t.toasts, ["Stopping every agent on this project."]);
    assert.match(t.row("claude-1"), /Stopping…/);
    assert.match(t.row("claude-2"), /Stopping…/);
    assert.equal(t.get("stopAll").hidden, true, "Stop all is not there to press again");
  }
  // a poll while a button of the list is pressed: the list stays as it is until the release, then it is drawn
  {
    const t = setup();
    t.draw([t.helper("claude-1", "working", "old words"), t.helper("claude-2")]);
    const before = t.box.innerHTML;
    t.box.onpointerdown();
    t.draw([t.helper("claude-1", "working", "new words"), t.helper("claude-2")]);
    assert.equal(t.box.innerHTML, before, "the button under the pointer stays the same button");
    t.release();
    assert.match(t.box.innerHTML, /new words/, "after the release, the list shows the new poll");
  }
}

main().then(() => console.log("ok"), (e) => { console.error(e && e.stack || e); process.exit(1); });
