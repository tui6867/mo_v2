import { test, expect } from '@playwright/test';

test('real UI workflow with synthetic transport only', async ({ page }, testInfo) => {
  const problems: string[] = [];
  page.on('pageerror', error => problems.push(error.message));
  await page.goto('/tests/visual.html');
  await page.getByLabel('Upload contact CSV').setInputFiles({ name: 'contacts.csv', mimeType: 'text/csv', buffer: Buffer.from('email,name\nana@example.com,Ana María Lee\nbob@example.com,Bob de la Cruz') });
  await expect(page.getByRole('textbox', { name: 'Name for ana@example.com' })).toHaveValue('Ana María Lee');
  const noOverflow = async () => expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await noOverflow();
  await page.screenshot({ path: testInfo.outputPath('import.png'), fullPage: true });
  await page.getByRole('button', { name: /^Connect your account/ }).click();
  await expect(page.getByRole('heading', { name: 'Connected to Gmail' })).toBeVisible();
  await page.getByRole('button', { name: /^Write messages$/ }).click();
  await page.getByLabel('Starting subject').fill('Hello {{first_name}}');
  await page.getByLabel('Starting message').fill('Hi {{name}},\n\nI wanted to introduce myself.\n\nThank you.');
  await page.getByRole('button', { name: /Apply to selected/ }).click();
  await noOverflow(); await page.screenshot({ path: testInfo.outputPath('compose.png'), fullPage: true });
  await page.getByRole('button', { name: /Review exact batch/ }).click();
  await expect(page.getByRole('button', { name: /Send 2 real emails/ })).toBeDisabled();
  await page.getByRole('button', { name: /Bob de la Cruz/ }).click();
  await page.getByRole('checkbox', { name: /I am permitted/ }).check();
  await page.getByRole('checkbox', { name: /I approve these exact/ }).check();
  await expect(page.getByText('Hello Bob', { exact: true })).toBeVisible();
  await noOverflow(); await page.screenshot({ path: testInfo.outputPath('review.png'), fullPage: true });
  await page.getByRole('button', { name: /Send 2 real emails/ }).click(); // Synthetic local fixture, never the live app.
  await expect(page.locator('.delivery-status').filter({ hasText: 'SMTP accepted' })).toHaveCount(2);
  await noOverflow(); await page.screenshot({ path: testInfo.outputPath('status.png'), fullPage: true });
  await page.getByRole('button', { name: 'Manage access' }).click();
  await expect(page.getByText('applicant@example.com', { exact: true })).toBeVisible();
  await noOverflow(); await page.screenshot({ path: testInfo.outputPath('admin.png'), fullPage: true });
  await page.getByRole('button', { name: 'Remove debug screen' }).click();
  await expect(page.getByRole('button', { name: 'Debug', exact: true })).toHaveCount(0);
  expect(problems).toEqual([]);
});
