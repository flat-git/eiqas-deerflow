import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

const styles = readFileSync(
  new URL("../../src/styles/eiqas.css", import.meta.url),
  "utf8",
);
const options = [
  "先修复环境（沙箱卷挂载改为绝对路径、抓取白名单恢复），修好后按已确认的方案自动继续，并逐项保留原件与计算记录。",
  "改由我手动下载并上传四份官方年度报告，保留原文页码和单位，上传后继续分析并明确记录取得方式。",
  "先交付可判断部分，并在成果首页列出尚未取得的资料、无法判断的指标以及这些缺口对结论的影响。",
];

for (const width of [300, 332, 368]) {
  test(`long clarification options remain contained and separate in a ${width}px chat`, async ({
    page,
  }) => {
    await page.setContent(
      `<style>body{margin:0}.h-9{height:36px}.min-h-11{min-height:44px}.grid{display:grid;gap:8px}.choice{width:100%;white-space:normal;text-align:left;line-height:20px}.label{min-width:0;white-space:pre-wrap;overflow-wrap:anywhere}${styles}</style><div class="eiqas" style="width:${width}px"><section data-testid="human-input-card" style="padding:16px"><p>需要你的决定</p><div class="grid">${options.map((text) => `<button class="h-9 min-h-11 choice"><span class="label">${text}</span></button>`).join("")}</div></section></div>`,
    );
    const boxes = await page.getByRole("button").evaluateAll((buttons) =>
      buttons.map((button) => {
        const box = button.getBoundingClientRect();
        const label = button.querySelector("span")!.getBoundingClientRect();
        return {
          top: box.top,
          bottom: box.bottom,
          height: box.height,
          labelTop: label.top,
          labelBottom: label.bottom,
        };
      }),
    );
    for (let index = 0; index < boxes.length; index++) {
      const box = boxes[index]!;
      expect(box.labelTop).toBeGreaterThanOrEqual(box.top);
      expect(box.labelBottom).toBeLessThanOrEqual(box.bottom);
      expect(box.height).toBeGreaterThan(44);
      if (index) expect(box.top).toBeGreaterThan(boxes[index - 1]!.bottom);
    }
  });
}
