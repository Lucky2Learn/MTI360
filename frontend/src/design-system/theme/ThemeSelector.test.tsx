import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  blockLocalStorage,
  installColorScheme,
  removeColorScheme,
  resetDocumentTheme,
} from "./test-helpers";
import { THEME_STORAGE_KEY } from "./theme";
import { ThemeProvider, useTheme } from "./ThemeProvider";
import { ThemeSelector } from "./ThemeSelector";

const root = document.documentElement;

function renderSelector() {
  return render(
    <ThemeProvider>
      <ThemeSelector />
    </ThemeProvider>,
  );
}

afterEach(() => {
  window.localStorage.clear();
  removeColorScheme();
  resetDocumentTheme();
});

describe("ThemeSelector accessibility", () => {
  it("is a labelled group of three native radio options", () => {
    installColorScheme(false);
    renderSelector();

    const group = screen.getByRole("group", { name: "Theme" });
    const radios = screen.getAllByRole("radio");
    expect(group).toContainElement(radios[0]!);
    expect(radios.map((radio) => radio.getAttribute("value"))).toEqual([
      "light",
      "dark",
      "system",
    ]);
    for (const name of ["Light", "Dark", "System"]) {
      expect(screen.getByRole("radio", { name })).toBeInstanceOf(
        HTMLInputElement,
      );
    }
    // One radio group (shared name) → Tab enters the group, arrow keys move.
    expect(
      new Set(radios.map((radio) => radio.getAttribute("name"))).size,
    ).toBe(1);
    for (const radio of radios)
      expect(radio).not.toHaveAttribute("tabindex", "-1");
  });

  it("describes the current behaviour in text, not only colour", () => {
    installColorScheme(true);
    renderSelector();

    expect(
      screen.getByRole("group", { name: "Theme" }),
    ).toHaveAccessibleDescription(
      "Follows your device setting (currently Dark).",
    );
  });
});

describe("ThemeSelector behaviour", () => {
  it("defaults to System and resolves it against the OS", () => {
    installColorScheme(true);
    renderSelector();

    expect(screen.getByRole("radio", { name: "System" })).toBeChecked();
    expect(root.dataset.theme).toBe("dark");
  });

  it("applies and persists an explicit choice", () => {
    installColorScheme(true);
    renderSelector();

    fireEvent.click(screen.getByRole("radio", { name: "Light" }));

    expect(screen.getByRole("radio", { name: "Light" })).toBeChecked();
    expect(root.dataset.theme).toBe("light");
    expect(root.style.colorScheme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("restores the stored preference", () => {
    installColorScheme(false);
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    renderSelector();

    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
    expect(root.dataset.theme).toBe("dark");
  });

  it("follows live OS changes only in System mode", () => {
    const scheme = installColorScheme(false);
    renderSelector();
    expect(root.dataset.theme).toBe("light");

    act(() => scheme.setDark(true));
    expect(root.dataset.theme).toBe("dark");

    fireEvent.click(screen.getByRole("radio", { name: "Light" }));
    act(() => scheme.setDark(false));
    act(() => scheme.setDark(true));
    expect(root.dataset.theme).toBe("light");
  });

  it("synchronises a change made in another tab", () => {
    installColorScheme(false);
    renderSelector();

    act(() => {
      window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
      window.dispatchEvent(
        new StorageEvent("storage", { key: THEME_STORAGE_KEY }),
      );
    });

    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
    expect(root.dataset.theme).toBe("dark");
  });

  it("still switches theme when storage is unavailable", () => {
    installColorScheme(false);
    const restore = blockLocalStorage();
    try {
      renderSelector();
      fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
      expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
      expect(root.dataset.theme).toBe("dark");
    } finally {
      restore();
    }
  });

  it("removes its OS listener on unmount", () => {
    const scheme = installColorScheme(false);
    const { unmount } = renderSelector();
    expect(scheme.listenerCount()).toBeGreaterThan(0);
    unmount();
    expect(scheme.listenerCount()).toBe(0);
  });
});

describe("useTheme", () => {
  it("requires a ThemeProvider", () => {
    function Consumer() {
      useTheme();
      return null;
    }
    expect(() => render(<Consumer />)).toThrow(/ThemeProvider/);
  });
});
