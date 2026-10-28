import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { expect, test } from "@playwright/test";

// Explicit live acceptance prerequisite: generate the labelled synthetic
// exports and replay receipt using scripts/acceptance/offline_delivery.py.
const receiptPath = path.resolve(
  process.env.EIQAS_OFFLINE_RECEIPT ??
    "../.eiqas/acceptance/offline-v2/receipt.json",
);
const receipt = JSON.parse(readFileSync(receiptPath, "utf8")) as {
  synthetic: boolean;
  status: string;
  exports: { html: string };
};

for (const width of [1366, 1440]) {
  test(`standalone HTML works offline at ${width}px`, async ({
    page,
  }, testInfo) => {
    expect(receipt.synthetic).toBe(true);
    expect(receipt.status).toBe("passed");
    const requests: string[] = [];
    const errors: string[] = [];
    page.on("request", (request) => {
      if (/^https?:/.test(request.url())) requests.push(request.url());
    });
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.goto(pathToFileURL(receipt.exports.html).href);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("合成");
    await expect(
      page.getByRole("heading", { name: "合成输入口径与依据" }),
    ).toBeVisible();
    await expect(page.locator(".status")).toContainText("读者待复核");
    await expect(page.locator("#row-count")).toHaveText("2 / 2 行");
    const canvases = page.locator(".chart canvas");
    expect(await canvases.count()).toBeGreaterThan(0);
    await expect
      .poll(() =>
        canvases
          .first()
          .evaluate((node: HTMLCanvasElement) => node.toDataURL().length),
      )
      .toBeGreaterThan(5000);
    await page.getByLabel("区域甲").uncheck();
    await expect(page.locator("#row-count")).toHaveText("1 / 2 行");
    await expect(page.locator("#table tbody tr")).toHaveCount(1);
    await page
      .locator("#table")
      .getByRole("button", { name: "查看依据" })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.locator("#provenance-content")).toContainText("区域乙");
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "下载当前筛选 CSV" }).click();
    const download = await downloadPromise;
    const csv = readFileSync(await download.path(), "utf8");
    expect(csv).toContain("区域乙");
    expect(csv).not.toContain("区域甲");
    expect(requests).toEqual([]);
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("offline-report.png") });
  });
}

test("ZIP HTML references existing package originals using relative paths", async ({
  page,
}) => {
  const unpacked = path.join(path.dirname(receiptPath), "unpacked");
  const html = path.join(unpacked, "index.html");
  expect(existsSync(html)).toBe(true);
  await page.goto(pathToFileURL(html).href);
  const sources = await page
    .locator('a[href^="sources/"]')
    .evaluateAll((links) => links.map((link) => link.getAttribute("href")!));
  expect(sources.length).toBeGreaterThan(0);
  for (const relative of sources) {
    const original = path.resolve(unpacked, relative.split("#")[0]!);
    expect(original.startsWith(unpacked + path.sep)).toBe(true);
    expect(existsSync(original)).toBe(true);
  }
});
