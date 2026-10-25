import { expect, test } from '@playwright/test';

for (const width of [320, 390, 768, 1440]) {
  test(`complete launch experience at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width < 500 ? 844 : 1000 });
    const errors: string[] = [];
    const forbiddenRequests: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.url().includes('/api/') || request.url().includes('supabase.co')) forbiddenRequests.push(request.url());
    });
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('networking.');
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`launch-${width}.png`), fullPage: true });

    const opener = page.getByRole('button', { name: 'Get early access' });
    await opener.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Applications are not being collected yet.');
    await dialog.getByLabel('Your email').fill('fictional@example.com');
    await dialog.getByLabel('Where do you want to go?', { exact: false }).fill('A first product design role.');
    await dialog.getByRole('checkbox').check();
    for (let index = 0; index < 8; index += 1) {
      await page.keyboard.press('Tab');
      expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
    }
    await dialog.getByRole('button', { name: 'Preview my application' }).click();
    await expect(dialog.getByRole('status')).toContainText('No signup, no email, no storage.');
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(opener).toBeFocused();

    await page.getByRole('button', { name: /Bring your experience in/ }).click();
    await page.getByRole('button', { name: 'Set permissions' }).click();
    await page.getByRole('checkbox', { name: /Use the sample resume/ }).uncheck();
    await expect(page.getByRole('button', { name: 'Make it personal' })).toBeDisabled();
    await page.getByRole('checkbox', { name: /Use the sample resume/ }).check();
    await page.getByRole('button', { name: 'Make it personal' }).click();
    await page.getByLabel('Sample email subject').fill('An introduction, in my own words');
    await page.getByRole('button', { name: 'Warm', exact: true }).click();
    await page.getByRole('button', { name: 'Sam', exact: true }).click();
    await expect(page.getByLabel('Sample email subject')).toHaveValue('Where thoughtful design meets engineering');
    await page.getByRole('button', { name: 'Jordan', exact: true }).click();
    await expect(page.getByLabel('Sample email subject')).toHaveValue('An introduction, in my own words');
    await page.locator('#workflow').scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`personalize-${width}.png`), fullPage: true });
    await page.getByRole('button', { name: 'Review messages' }).click();
    await expect(page.getByRole('button', { name: 'Simulate sending' })).toBeDisabled();
    await page.getByRole('button', { name: 'Sam Rivera' }).click();
    await page.getByRole('button', { name: 'Casey Chen' }).click();
    await page.getByLabel('I approve these sample messages for a simulated send.').check();
    await page.getByRole('button', { name: 'Simulate sending' }).click();
    await expect(page.getByText('Delivered', { exact: true })).toHaveCount(3, { timeout: 12000 });
    await page.getByRole('button', { name: 'Restart demo' }).click();
    await expect(page.getByRole('button', { name: 'Track', exact: true })).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(forbiddenRequests).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('reduced-motion demo and 200% equivalent layout', async ({ page }) => {
  await page.setViewportSize({ width: 720, height: 500 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.locator('html').evaluate(element => getComputedStyle(element).scrollBehavior)).toBe('auto');
  await page.getByRole('button', { name: /Bring your experience in/ }).click();
  await page.getByRole('button', { name: 'Set permissions' }).click();
  await page.getByRole('button', { name: 'Make it personal' }).click();
  await page.getByRole('button', { name: 'Review messages' }).click();
  await page.getByRole('button', { name: 'Sam Rivera' }).click();
  await page.getByRole('button', { name: 'Casey Chen' }).click();
  await page.getByRole('checkbox', { name: /I approve/ }).check();
  await page.getByRole('button', { name: 'Simulate sending' }).click();
  await expect(page.getByText('Delivered', { exact: true })).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'Pause simulation' })).toHaveCount(0);
});
