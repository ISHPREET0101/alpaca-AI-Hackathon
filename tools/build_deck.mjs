import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const artifactToolPath = path.join(
  process.env.RUNTIME_NODE_MODULES,
  "@oai/artifact-tool/dist/artifact_tool.mjs",
);
const { Presentation, PresentationFile } = await import(pathToFileURL(artifactToolPath).href);

const OUT = path.resolve("artifacts/submission");
const COVER = path.join(OUT, "aegis-alpha-cover.png");
const W = 1280;
const H = 720;
const C = {
  ink: "#070B10",
  muted: "#606873",
  panel: "#EDF1F4",
  rule: "#BCC4CC",
  cyan: "#27C4F4",
  blue: "#3D8DFF",
  pale: "#DDF5FC",
  white: "#FFFFFF",
  green: "#0E8F64",
  red: "#CE3E54",
};

function addText(slide, text, x, y, w, h, size = 24, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: opts.name,
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: size,
    typeface: "Arial",
    color: opts.color ?? C.ink,
    bold: opts.bold ?? false,
    alignment: opts.align ?? "left",
    verticalAlignment: opts.valign ?? "top",
    autoFit: "shrinkText",
  };
  return shape;
}

function addBox(slide, x, y, w, h, fill = C.panel, opts = {}) {
  return slide.shapes.add({
    geometry: opts.geometry ?? "rect",
    name: opts.name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: {
      style: "solid",
      fill: opts.line ?? fill,
      width: opts.lineWidth ?? 0,
    },
  });
}

function addRule(slide, x, y, w, color = C.rule, width = 2) {
  return slide.shapes.add({
    geometry: "straightConnector1",
    position: { left: x, top: y, width: w, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width },
  });
}

function header(slide, title, kicker, number) {
  addText(slide, kicker.toUpperCase(), 52, 34, 360, 24, 13, {
    color: C.blue,
    bold: true,
  });
  addText(slide, title, 52, 66, 1150, 74, 42, { bold: true });
  addRule(slide, 52, 143, 1176, C.ink, 1);
  addText(slide, String(number).padStart(2, "0"), 1180, 674, 48, 20, 12, {
    color: C.muted,
    align: "right",
  });
}

function note(slide, lines, sources) {
  const body = [...lines, "", "[Sources]", ...sources.map((s) => `- ${s}`), "[/Sources]"];
  slide.speakerNotes.textFrame.setText(body.join("\n"));
}

function node(slide, x, y, w, label, accent = C.panel) {
  addBox(slide, x, y, w, 76, accent, { line: C.rule, lineWidth: 1 });
  addText(slide, label, x + 14, y + 15, w - 28, 46, 19, {
    bold: true,
    align: "center",
    valign: "middle",
  });
}

async function imageBytes(filePath) {
  const b = await fs.readFile(filePath);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

async function main() {
  await fs.mkdir(path.join(OUT, "deck-render"), { recursive: true });
  const deck = Presentation.create({ slideSize: { width: W, height: H } });

  // 1 — cover
  {
    const s = deck.slides.add();
    s.background.fill = C.ink;
    s.images.add({
      blob: await imageBytes(COVER),
      contentType: "image/png",
      alt: "A glowing shield made from option payoff curves over market data",
      fit: "cover",
      position: { left: 0, top: 0, width: W, height: H },
    });
    addBox(s, 0, 0, 610, H, "#020407");
    addText(s, "ALPACA AI TRADING AGENTS", 58, 54, 480, 24, 14, {
      color: C.cyan,
      bold: true,
    });
    addText(s, "Aegis Alpha", 58, 173, 500, 90, 64, {
      color: C.white,
      bold: true,
    });
    addText(s, "An autonomous, explainable options agent with deterministic risk control", 58, 279, 470, 112, 27, {
      color: "#DAE3EA",
    });
    addRule(s, 58, 431, 300, C.cyan, 4);
    addText(s, "SPY / QQQ defined-risk debit spreads\nPaper trading only", 58, 457, 420, 74, 20, {
      color: C.white,
    });
    addText(s, "Hackathon submission • September 2026", 58, 650, 450, 22, 14, {
      color: "#8D9AA7",
    });
    note(s, ["Open with the tension: autonomy is useful only when it cannot evade risk limits."], [
      "User-supplied hackathon brief and roadmap",
      "https://docs.alpaca.markets/us/docs/getting-started-with-trading-api",
    ]);
  }

  // 2 — problem / answer
  {
    const s = deck.slides.add();
    s.background.fill = C.white;
    header(s, "Autonomy needs a hard boundary", "The problem", 2);
    addText(s, "THE FAILURE MODE", 62, 191, 420, 26, 14, { color: C.red, bold: true });
    addText(s, "AI can produce a persuasive thesis while market data is stale, liquidity is poor, or portfolio risk is already exhausted.", 62, 226, 450, 220, 31, { bold: true });
    addBox(s, 609, 182, 2, 410, C.ink);
    addText(s, "THE DESIGN RESPONSE", 660, 191, 430, 26, 14, { color: C.green, bold: true });
    addText(s, "Reasoning may rank valid opportunities. Deterministic Python alone decides whether an order is permitted.", 660, 226, 505, 150, 30, { bold: true });
    addText(s, "• Missing data → NO_TRADE\n• Contradiction → NO_TRADE\n• Reconciliation mismatch → HALT\n• Live endpoint → REJECT", 660, 412, 480, 170, 22, { color: C.muted });
    note(s, ["Make the safety boundary the original idea—not merely a feature list."], [
      "D:/Hacathon/Alpaca AI Hackathon/docs/ARCHITECTURE.md",
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/risk.py",
    ]);
  }

  // 3 — architecture
  {
    const s = deck.slides.add();
    s.background.fill = C.white;
    header(s, "Every cycle narrows freedom before execution", "Architecture", 3);
    const labels = ["Market\nData", "Regime", "Candidates", "Critic", "Risk\nGuard", "Executor", "Monitor"];
    const xs = [42, 215, 388, 561, 734, 907, 1080];
    labels.forEach((l, i) => node(s, xs[i], 226, 150, l, i === 4 ? C.pale : C.panel));
    for (let i = 0; i < xs.length - 1; i++) {
      addRule(s, xs[i] + 150, 264, 23, i === 3 ? C.blue : C.ink, i === 3 ? 4 : 2);
    }
    addText(s, "AI reasoning zone", 230, 352, 480, 35, 21, { color: C.muted, align: "center" });
    addRule(s, 215, 396, 496, C.rule, 2);
    addText(s, "Deterministic safety + execution zone", 746, 352, 462, 35, 21, { color: C.blue, bold: true, align: "center" });
    addRule(s, 734, 396, 496, C.blue, 3);
    addText(s, "Independent CLI reconciliation runs around the execution boundary. MCP remains inspection-only for the demo.", 216, 475, 814, 88, 25, { bold: true, align: "center" });
    note(s, ["Walk left to right. Stress that the highlighted boundary cannot be bypassed by the ranker."], [
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/orchestrator.py",
      "https://alpaca.markets/learn/building-a-multi-agent-ai-trading-system-on-alpaca",
    ]);
  }

  // 4 — strategy
  {
    const s = deck.slides.add();
    s.background.fill = C.white;
    header(s, "The search space is deliberately small and testable", "Strategy", 4);
    addText(s, "SIGNAL", 54, 183, 180, 24, 14, { color: C.blue, bold: true });
    addText(s, "Five-minute EMA trend, VWAP, RSI and realized volatility classify the regime as bullish, bearish or neutral.", 54, 216, 340, 224, 26, { bold: true });
    addRule(s, 420, 180, 0, C.rule, 1);
    addText(s, "CONTRACTS", 457, 183, 180, 24, 14, { color: C.blue, bold: true });
    addText(s, "Only same-expiry SPY/QQQ bull-call or bear-put debit spreads, 7–21 DTE, with long delta near 0.35–0.55.", 457, 216, 340, 224, 26, { bold: true });
    addText(s, "ORDER", 860, 183, 180, 24, 14, { color: C.blue, bold: true });
    addText(s, "One atomic two-leg limit order with an idempotent client_order_id. Neutral regimes produce no candidate.", 860, 216, 340, 224, 26, { bold: true });
    addBox(s, 54, 493, 1146, 92, C.ink);
    addText(s, "Selection is optimized. Constraints are fixed.", 84, 518, 1086, 44, 28, { color: C.white, bold: true, align: "center" });
    note(s, ["Explain that fixed structure makes behavior auditable and keeps the demo honest."], [
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/indicators.py",
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/strategy.py",
      "https://github.com/alpacahq/alpaca-py",
    ]);
  }

  // 5 — risk gates
  {
    const s = deck.slides.add();
    s.background.fill = C.white;
    header(s, "Nine deterministic gates must all agree", "Risk controls", 5);
    const risks = [
      ["≤ $500", "planned loss per trade"],
      ["≤ $1,500", "aggregate open risk"],
      ["≤ 3", "simultaneous positions"],
      ["1 / day", "new trade per underlying"],
      ["30 min", "post-order cooldown"],
      ["≤ 60 sec", "quote freshness"],
      ["≤ 15%", "quote-width ratio"],
      ["−1.5%", "daily drawdown halt"],
      ["15:45 ET", "forced risk exit"],
    ];
    risks.forEach(([stat, body], i) => {
      const col = i % 3;
      const row = Math.floor(i / 3);
      const x = 55 + col * 402;
      const y = 176 + row * 145;
      addText(s, stat, x, y, 180, 48, 32, { bold: true, color: i === 8 ? C.red : C.blue });
      addText(s, body, x + 180, y + 5, 190, 52, 18, { color: C.muted, valign: "middle" });
      addRule(s, x, y + 75, 352, C.rule, 1);
    });
    addText(s, "Exit logic: +40% profit • −30% loss • invalidated signal • end-of-day cutoff", 55, 623, 1100, 38, 22, { bold: true });
    note(s, ["These numbers are frozen configuration, each covered by unit tests."], [
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/config.py",
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/risk.py",
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/monitor.py",
    ]);
  }

  // 6 — execution / audit
  {
    const s = deck.slides.add();
    s.background.fill = C.white;
    header(s, "A second control plane checks the first", "Execution assurance", 6);
    addText(s, "SDK PATH", 60, 181, 250, 26, 14, { color: C.blue, bold: true });
    addText(s, "alpaca-py retrieves account, clock, data, option chain and positions—then submits a typed multi-leg limit order.", 60, 219, 475, 165, 27, { bold: true });
    addText(s, "CLI PATH", 742, 181, 250, 26, 14, { color: C.blue, bold: true });
    addText(s, "Pinned Alpaca CLI independently reads account, open orders and positions through isolated JSON parsing.", 742, 219, 475, 165, 27, { bold: true });
    addRule(s, 565, 282, 147, C.ink, 2);
    addBox(s, 566, 244, 145, 78, C.pale, { line: C.blue, lineWidth: 2 });
    addText(s, "COMPARE", 578, 264, 121, 35, 17, { bold: true, color: C.blue, align: "center" });
    addBox(s, 182, 460, 916, 101, C.ink);
    addText(s, "Mismatch → log full evidence → activate execution halt → allow no new order", 211, 489, 858, 44, 27, { color: C.white, bold: true, align: "center" });
    addText(s, "MCP is a judge-facing inspection surface—not a backdoor around the risk engine.", 181, 601, 918, 34, 21, { align: "center", color: C.muted });
    note(s, ["Show both the SDK and CLI adapters. The comparison is material, not decorative."], [
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/broker/alpaca_gateway.py",
      "D:/Hacathon/Alpaca AI Hackathon/src/aegis_alpha/broker/cli_adapter.py",
      "https://docs.alpaca.markets/us/docs/alpacas-cli",
      "https://docs.alpaca.markets/us/docs/alpaca-mcp-server",
    ]);
  }

  // 7 — verified evidence
  {
    const s = deck.slides.add();
    s.background.fill = C.white;
    header(s, "Offline verified; broker proof is still pending", "Evidence", 7);
    addText(s, "28", 57, 196, 240, 90, 64, { bold: true, color: C.blue });
    addText(s, "tests passed", 57, 282, 260, 42, 24, { bold: true });
    addText(s, "5", 430, 196, 240, 90, 64, { bold: true, color: C.blue });
    addText(s, "replay regimes passed", 430, 282, 300, 42, 24, { bold: true });
    addText(s, "72%", 810, 196, 260, 90, 64, { bold: true, color: C.blue });
    addText(s, "measured code coverage", 810, 282, 340, 42, 24, { bold: true });
    addRule(s, 57, 365, 1090, C.rule, 1);
    addText(s, "Verified locally", 57, 402, 260, 34, 18, { color: C.green, bold: true });
    addText(s, "Signals • filtering • risk gates • idempotency • malformed AI • replay • sanitized export • forced exits", 57, 447, 490, 124, 23, { bold: true });
    addText(s, "Credential-gated next", 690, 402, 300, 34, 18, { color: C.red, bold: true });
    addText(s, "Real paper account • option-chain integration • filled multi-leg lifecycle • CLI reconciliation • paper P&L", 690, 447, 490, 124, 23, { bold: true });
    addText(s, "One credential-gated integration test is skipped by design.", 57, 625, 1090, 26, 17, { color: C.muted });
    note(s, ["Be precise: these are local results, not a live Alpaca session or profitability claim."], [
      "D:/Hacathon/Alpaca AI Hackathon/tests",
      "D:/Hacathon/Alpaca AI Hackathon/fixtures/replay_scenarios.json",
    ]);
  }

  // 8 — close / demo
  {
    const s = deck.slides.add();
    s.background.fill = C.ink;
    addText(s, "THE DEMO PROMISE", 58, 48, 350, 22, 14, { color: C.cyan, bold: true });
    addText(s, "Explain every decision.\nBound every loss.\nFail closed.", 58, 119, 760, 266, 54, { color: C.white, bold: true });
    addRule(s, 58, 431, 1110, C.cyan, 4);
    const steps = [
      ["01", "Run one cycle", "Regime → spread → critic → gates"],
      ["02", "Inspect execution", "API request, order intent and audit log"],
      ["03", "Reconcile", "SDK vs CLI account, orders and positions"],
      ["04", "Show limits", "Dashboard, MCP inspection and honest caveats"],
    ];
    steps.forEach(([n, t, d], i) => {
      const x = 58 + i * 292;
      addText(s, n, x, 470, 55, 28, 18, { color: C.cyan, bold: true });
      addText(s, t, x, 509, 250, 35, 24, { color: C.white, bold: true });
      addText(s, d, x, 553, 250, 74, 17, { color: "#AAB6C1" });
    });
    addText(s, "Paper trading only • No claim of real-world profitability", 58, 665, 620, 20, 14, { color: "#8D9AA7" });
    note(s, ["Resolve the opening: safe autonomy is achieved by separating judgment from authority."], [
      "D:/Hacathon/Alpaca AI Hackathon/README.md",
      "D:/Hacathon/Alpaca AI Hackathon/docs/VIDEO_SCRIPT.md",
    ]);
  }

  for (const [i, slide] of deck.slides.items.entries()) {
    const stem = `slide-${String(i + 1).padStart(2, "0")}`;
    const png = await deck.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(OUT, "deck-render", `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(OUT, "deck-render", `${stem}.layout.json`), await layout.text());
  }
  const montage = await deck.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(path.join(OUT, "aegis-alpha-deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(path.join(OUT, "Aegis_Alpha_Hackathon_Deck.pptx"));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
