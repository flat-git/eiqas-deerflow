import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

const styles = readFileSync(
  new URL("../../src/styles/eiqas.css", import.meta.url),
  "utf8",
);

for (const width of [980, 1366, 1440]) {
  for (const reader of [false, true]) {
    test(`${reader ? "reader" : "workbench"} has independent scroll regions at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 800 });
      const paragraphs = Array.from(
        { length: 100 },
        (_, index) =>
          `<p>实际布局回归 ${index}：长内容应留在自己的滚动区域。</p>`,
      ).join("");
      const chat = `<aside class="eiqas-chat-pane"><div class="eiqas-chat"><header>研究对话</header><div class="eiqas-chat-messages"><div role="log" style="height:100%;overflow:auto">${paragraphs}</div></div><form><input type="file" class="hidden"/><textarea aria-label="研究输入"></textarea><button>发送</button></form></div></aside>`;
      const body = reader
        ? `<div class="eiqas-reader with-chat"><header class="eiqas-reader-bar">研究成果</header><div class="eiqas-reader-body"><main>${paragraphs}</main>${chat}</div></div>`
        : `<div class="eiqas-layout"><aside class="eiqas-sidebar">研究记录</aside><div class="eiqas-workspace"><header class="eiqas-topbar">研究工作台</header><div class="eiqas-work-area with-chat"><main class="eiqas-main">${paragraphs}</main>${chat}</div></div></div>`;
      await page.setContent(
        `<style>body{margin:0}.hidden{display:none}${styles}</style><div class="eiqas">${body}</div>`,
      );
      await expect(page.locator('input[type="file"]')).toBeHidden();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      const main = page.locator("main");
      const bounds = await main.evaluate((node) => ({
        client: node.clientHeight,
        content: node.scrollHeight,
      }));
      expect(bounds.client).toBeLessThan(800);
      expect(bounds.content).toBeGreaterThan(bounds.client);
      const header = page.locator(
        reader ? ".eiqas-reader-bar" : ".eiqas-topbar",
      );
      const headerTop = (await header.boundingBox())!.y;
      await main.hover();
      await page.mouse.wheel(0, 600);
      await expect
        .poll(() => main.evaluate((node) => node.scrollTop))
        .toBeGreaterThan(100);
      const mainTop = await main.evaluate((node) => node.scrollTop);
      const log = page.getByRole("log");
      expect(await log.evaluate((node) => node.scrollTop)).toBe(0);
      await log.hover();
      await page.mouse.wheel(0, 500);
      await expect
        .poll(() => log.evaluate((node) => node.scrollTop))
        .toBeGreaterThan(100);
      expect(await main.evaluate((node) => node.scrollTop)).toBe(mainTop);
      expect((await header.boundingBox())!.y).toBe(headerTop);
      await expect(page.getByLabel("研究输入")).toBeInViewport();
      expect(
        await page.evaluate(() => document.documentElement.scrollHeight),
      ).toBe(800);
    });
  }
}
