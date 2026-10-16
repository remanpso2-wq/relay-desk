import { test, expect } from "@playwright/test";
async function login(page: any, email = "admin@example.test") {
  await page.goto("/");
  await page.getByLabel("メールアドレス").fill(email);
  await page.getByLabel("パスワード").fill("e2e-only-password-2026");
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "問い合わせ", exact: true }),
  ).toBeVisible();
}
test("根拠確認・生成・人による承認・再読み込み後の保存", async ({ page }) => {
  await login(page);
  await page
    .getByRole("button")
    .filter({
      has: page.getByRole("heading", {
        name: "注文後に配送先住所を変更したい",
      }),
    })
    .click();
  await page.getByRole("button", { name: "送信内容・参照資料を確認" }).click();
  await page.getByLabel("内容と送信先を確認しました").check();
  await page.getByRole("button", { name: "下書きを生成", exact: true }).click();
  await expect(page.getByLabel("返信案", { exact: true })).toHaveValue(/配送/);
  await page
    .getByLabel("返信案", { exact: true })
    .fill(
      "ご連絡ありがとうございます。出荷前であることを確認して対応いたします。",
    );
  await page.getByLabel("確認メモ").fill("適用条件を確認しました");
  await page.getByLabel("根拠資料と返信内容を確認しました").check();
  await page.getByRole("button", { name: "承認する", exact: true }).click();
  await expect(
    page.getByText("返信案を承認しました。お客様への送信は行っていません。"),
  ).toBeVisible();
  await page.reload();
  await page
    .getByRole("button")
    .filter({
      has: page.getByRole("heading", {
        name: "注文後に配送先住所を変更したい",
      }),
    })
    .click();
  await expect(page.getByLabel("返信案", { exact: true })).toHaveValue(
    /出荷前/,
  );
});
test("担当者は資料編集と承認ができずスマホ幅でも操作可能", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "agent@example.test");
  await expect(
    page.getByRole("button", { name: "操作履歴", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "ナレッジ", exact: true }).click();
  await expect(page.getByRole("button", { name: "資料を追加" })).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "ログアウト", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "ワークスペースにログイン" }),
  ).toBeVisible();
});
