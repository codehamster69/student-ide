// Screenshots of every student-facing screen for the thesis, after entrance
// animations have settled. Same server setup as record.mjs.
//
//   BASE=http://127.0.0.1:8000 node frontend/e2e/screenshots.mjs <out-dir> [light|dark]

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
if (!OUT) throw new Error("usage: screenshots.mjs <out-dir> [light|dark]");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
const settle = () => page.waitForTimeout(1400);
const shot = async (name) => { await settle(); await page.screenshot({ path: `${OUT}/ui-${SCHEME}-${name}.png` }); };

await page.goto(BASE);
await page.waitForTimeout(3500); // let the typing demo get going
await shot("01-login");
await page.fill("input", `shot-${Date.now().toString(36)}`);
await page.click("button[type=submit]");
await page.waitForSelector("text=Before you start");
await page.check("input[type=checkbox]");
await shot("02-consent");
await page.click('button:text-is("Start")');
await page.waitForSelector("text=Choose a task");
await page.locator("button", { hasText: "Word frequency" }).hover();
await shot("03-tasks");
await page.click("text=Warm-up: FizzBuzz");
await page.waitForSelector(".cm-content");
await page.click(".cm-content");
await page.keyboard.press("Control+End");
await page.keyboard.type("for i in range(1, n + 1):\nif i % 15 == 0:\nprint(\"FizzBuzz\")", { delay: 5 });
await page.keyboard.press("Enter");
await page.keyboard.press("Backspace");
await page.keyboard.type("elif i % 3 == 0:\nprint(\"Fizz\")\n", { delay: 5 });
await page.keyboard.press("Backspace");
await page.keyboard.type("elif i % 5 == 0:\nprint(\"Buzz\")\n", { delay: 5 });
await page.keyboard.press("Backspace");
await page.keyboard.type("else:\nprint(i)", { delay: 5 });
await shot("04-editor");
await page.keyboard.press("Control+Enter");
await page.waitForFunction(() => !document.querySelector(".output")?.textContent?.startsWith("Running"));
await shot("05-run-output");
await page.keyboard.press("Control+A");
await page.keyboard.type("n = int(input())\nprint(10 / (n - 15))", { delay: 5 });
await page.keyboard.press("Control+Enter");
await page.waitForFunction(() => !document.querySelector(".output")?.textContent?.startsWith("Running"));
await shot("06-run-error");
await page.click('button:text-is("Finish")');
await shot("07-finish-dialog");
await page.click('[role=dialog] button:text-is("Finish session")');
await page.waitForSelector("text=Session saved");
await shot("08-saved");
await browser.close();
console.log(`screenshots written to ${OUT}`);
