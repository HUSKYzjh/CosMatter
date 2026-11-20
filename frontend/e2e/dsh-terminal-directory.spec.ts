import { expect, test } from "@playwright/test";

const terminals = [
  { mode: "windows-venv", root: "D:\\Materials\\O’Brien's lab", executable: "& 'D:\\Materials\\O’’Brien''s lab\\.venv\\Scripts\\cosmatter.exe'" },
  { mode: "posix-venv", root: "/home/lab/O'Brien group/", executable: "'/home/lab/O'\\''Brien group/.venv/bin/cosmatter'" },
];

for (const terminal of terminals) {
  test("copies the chosen repository executable from " + terminal.mode, async ({ page, context, baseURL }) => {
    await page.setViewportSize({ width: 320, height: 650 });
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(baseURL!).origin });
    const requests: string[] = [];
    await page.route("**/api/**", route => {
      requests.push(route.request().url() + (route.request().postData() ?? ""));
      return route.fulfill({ status: 503, json: {} });
    });
    await page.goto("/?api=local");
    const opener = page.getByRole("button", { name: "DSH 插件", exact: true });
    await expect(opener).toHaveAccessibleDescription("连接待检查");
    await opener.press("Enter");
    const panel = page.getByRole("tabpanel", { name: "DSH 会话" });
    const mode = panel.getByRole("combobox", { name: "命令运行环境" });
    await mode.selectOption(terminal.mode);
    const location = panel.locator(".dsh-repository-location");
    await location.locator("summary").press("Enter");
    const root = location.getByLabel("CosMatter 仓库目录");
    const command = panel.getByRole("region", { name: "启动本机工作台" }).locator("code");
    const defaultCommand = await command.innerText();
    await root.fill("relative/path");
    await root.press("Enter");
    await expect(root).toHaveAttribute("aria-invalid", "true");
    await expect(command).toHaveText(defaultCommand);
    await root.fill(terminal.root);
    await root.press("Enter");
    await expect(root).toHaveAttribute("aria-invalid", "false");
    const expected = terminal.executable + " preview-ui --solid --api --port 0";
    await expect(command).toHaveText(expected);
    await panel.getByRole("button", { name: "复制本机工作台命令" }).press("Enter");
    await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(expected);
    expect(await panel.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.keyboard.press("Escape");
    await expect(opener).toBeFocused();
    await opener.press("Enter");
    await expect(command).toHaveText(expected);
    await mode.selectOption("path");
    await expect(command).toHaveText("cosmatter preview-ui --solid --api --port 0");
    expect(requests.join("\n")).not.toContain("Brien");
  });
}
