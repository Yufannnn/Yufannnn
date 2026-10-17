// Use the same aggregate commit snapshot as the cards, including private work.
// The upstream renderer accepts a GitHub Enterprise base URL. A loopback-only
// adapter supplies its calendar schema without sending a token or private data.
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { generateSnakeAnimation } from "generate-snake-animation";

const root = new URL("../", import.meta.url);
const activity = JSON.parse(await readFile(new URL("assets/github-pulse/activity.json", root), "utf8"));
const dayMs = 86_400_000;
const end = new Date(`${activity.updated_at.slice(0, 10)}T00:00:00Z`);
const start = new Date(end.getTime() - 364 * dayMs);
const calendarStart = new Date(start.getTime() - start.getUTCDay() * dayMs);
const positive = Object.values(activity.daily_commits).filter(n => n > 0).sort((a, b) => a - b);
const thresholds = [.25, .5, .75].map(q => positive[Math.floor((positive.length - 1) * q)] ?? 0);
const levels = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"];
const weeks = [];
let sum = 0;
let activeDays = 0;
for (let time = calendarStart.getTime(); time <= end.getTime(); time += dayMs) {
  const date = new Date(time);
  const key = date.toISOString().slice(0, 10);
  const count = time < start.getTime() ? 0 : activity.daily_commits[key] ?? 0;
  const level = count ? 1 + thresholds.filter(threshold => count > threshold).length : 0;
  const week = Math.floor((time - calendarStart.getTime()) / (7 * dayMs));
  weeks[week] ??= { contributionDays: [] };
  weeks[week].contributionDays.push({ date: key, weekday: date.getUTCDay(), contributionCount: count, contributionLevel: levels[level] });
  sum += count;
  activeDays += count > 0;
}
if (sum !== activity.commits) throw new Error("Snake calendar and profile card totals differ");
const payload = JSON.stringify({ data: { user: { contributionsCollection: { contributionCalendar: { weeks } } } } });
const server = createServer((req, res) => {
  if (req.method !== "POST" || req.url !== "/api/graphql") {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(payload);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));

const common = { sizeCell: 16, sizeDot: 11, sizeDotBorderRadius: 2 };
const palettes = [
  { ...common, colorEmpty: "#ebedf0", colorDotBorder: "#ffffff", colorSnake: "#0969da", colorDots: { 1: "#9be9a8", 2: "#40c463", 3: "#30a14e", 4: "#216e39" } },
  { ...common, colorEmpty: "#161b22", colorDotBorder: "#0d1117", colorSnake: "#58a6ff", colorDots: { 1: "#0e4429", 2: "#006d32", 3: "#26a641", 4: "#39d353" } },
];
try {
  const outputs = await generateSnakeAnimation({
    platform: "github", username: "Yufannnn", githubToken: "local-aggregate-snapshot",
    baseUrl: `http://127.0.0.1:${server.address().port}`,
  }, palettes.map(drawOptions => ({ format: "svg", drawOptions, animationOptions: { stepDurationMs: 90 } })));
  const out = new URL("dist/", root);
  await mkdir(out, { recursive: true });
  for (const [index, name] of ["commit-snake.svg", "commit-snake-dark.svg"].entries()) {
    const description = `${sum.toLocaleString("en-US")} authored commits across ${activeDays} active days. Includes public and private repositories; same snapshot as the profile cards, updated ${activity.updated_at.slice(0, 10)}.`;
    let svg = outputs[index].replace("<svg ", `<svg role="img" aria-labelledby="snake-title snake-desc" data-total-commits="${sum}" data-active-days="${activeDays}" `);
    svg = svg.replace(/<desc>[\s\S]*?<\/desc>/, `<title id="snake-title">Commit activity, in motion</title><desc id="snake-desc">${description} Animation generated with https://github.com/Platane/snk.</desc>`);
    // Give the full calendar a moment to be read before the snake starts eating.
    svg = svg.replace("</style>", "*{animation-delay:4s!important}@media(prefers-reduced-motion:reduce){*{animation:none!important}}</style>");
    await writeFile(new URL(name, out), svg);
  }
  console.log(`Rendered both snake themes from ${sum.toLocaleString("en-US")} commits across ${activeDays} active days in ${fileURLToPath(out)}`);
} finally {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
