import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.describe("Landing page", () => {
  test("renders the nav and hero section", async ({ page }) => {
    await page.goto("/");

    // Nav brand name
    await expect(page.locator("nav", { hasText: "Stellantis AI" })).toBeVisible();

    // "Bypass Protocol" CTA button (dev/auth-disabled access)
    await expect(
      page.getByRole("button", { name: /bypass protocol/i }),
    ).toBeVisible();
  });

  test("Bypass Protocol navigates to workspace", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/");

    const bypass = page.getByRole("button", { name: /bypass protocol/i });
    await bypass.click();

    // Should redirect to /workspace
    await page.waitForURL("**/workspace**");
    await expect(page).toHaveURL(/\/workspace/);
  });
});
