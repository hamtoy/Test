import { expect, test } from "@playwright/test";

test.describe("Smoke", () => {
    test.skip(
        !process.env.E2E_BASE_URL,
        "E2E_BASE_URL가 설정되지 않아 e2e를 건너뜁니다.",
    );

    test("QA 페이지 로드", async ({ page }) => {
        await page.goto("/qa");
        await expect(page.locator("body")).toBeVisible();
        await expect(page.locator("#generate-btn")).toBeVisible();
    });
});
