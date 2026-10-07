import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CopyButton } from "@/design-system/components/CopyButton";
import { expectNoA11yViolations } from "@/design-system/testing/axe";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";

import { CodeList, groupCharacters, SecretValue } from "./SecretValue";

import type { ReactNode } from "react";

// SecretValue, CodeList and CopyButton (T01-09B design-system extension).

const frame = (node: ReactNode, theme: "light" | "dark" = "light") => {
  document.documentElement.dataset.theme = theme;
  return render(<ThemeProvider>{node}</ThemeProvider>);
};

afterEach(() => {
  Reflect.deleteProperty(navigator, "clipboard");
});

describe("SecretValue", () => {
  it("groups characters for reading, labelled and monospaced", async () => {
    expect(groupCharacters("JBSWY3DPEHPK3PXP")).toBe("JBSW Y3DP EHPK 3PXP");
    expect(groupCharacters("ab cd e", 2)).toBe("ab cd e");
    const { container } = frame(
      <SecretValue label="Setup key" value="JBSWY3DPEHPK3PXP" />,
      "dark",
    );
    const value = screen.getByLabelText("Setup key");
    expect(value).toHaveTextContent("JBSW Y3DP EHPK 3PXP");
    expect(value.className).toContain("font-mono");
    expect(value.className).toContain("break-all");
    await expectNoA11yViolations(container);
  });
});

describe("CodeList", () => {
  it("is a named ordered list of the codes", async () => {
    const { container } = frame(
      <CodeList
        label="Recovery codes"
        codes={["abcde-fghij", "klmno-pqrst"]}
      />,
    );
    const list = screen.getByRole("list", { name: "Recovery codes" });
    expect(list.tagName).toBe("OL");
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    await expectNoA11yViolations(container);
  });
});

describe("CopyButton", () => {
  it("copies only when pressed and announces the result without the value", async () => {
    // After setup(): user-event installs its own clipboard stub.
    const user = userEvent.setup();
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const { container } = frame(
      <CopyButton value="secret-value-123" label="Copy key" />,
    );
    expect(writeText).not.toHaveBeenCalled();
    const status = screen.getByRole("status");
    expect(status).toBeEmptyDOMElement();
    await user.click(screen.getByRole("button", { name: "Copy key" }));
    expect(writeText).toHaveBeenCalledWith("secret-value-123");
    await waitFor(() =>
      expect(status).toHaveTextContent("Copied to the clipboard."),
    );
    expect(container.textContent).not.toContain("secret-value-123");
    await expectNoA11yViolations(container);
  });

  it("explains the fallback when the clipboard is unavailable", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    frame(<CopyButton value="x" label="Copy codes" />);
    await user.click(screen.getByRole("button", { name: "Copy codes" }));
    expect(
      await screen.findByText(
        "Couldn't copy. Select the text and copy it instead.",
      ),
    ).toBeInTheDocument();
  });
});
