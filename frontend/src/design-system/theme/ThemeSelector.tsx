"use client";

import { useId } from "react";

import { useTheme } from "./ThemeProvider";

import type { ThemePreference } from "./theme";

// Appearance control (DESIGN-SYSTEM.md §15, CLAUDE.md §19). Native radio inputs
// in a fieldset: keyboard operable (Tab into the group, arrow keys to change),
// labelled by the legend, and the selection is shown by the radio mark, text
// weight and border — never by colour alone. T00-08 places it in the UserMenu.

const OPTIONS: { value: ThemePreference; label: string; glyph: string }[] = [
  { value: "light", label: "Light", glyph: "☀" },
  { value: "dark", label: "Dark", glyph: "☾" },
  { value: "system", label: "System", glyph: "◐" },
];

export function ThemeSelector() {
  const { preference, resolvedTheme, setPreference } = useTheme();
  const name = useId();
  const descriptionId = useId();

  return (
    <fieldset aria-describedby={descriptionId} className="flex flex-col gap-2">
      <legend className="text-body-sm font-semibold text-text-primary">
        Theme
      </legend>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className="inline-flex min-h-11 min-w-24 cursor-pointer items-center gap-2 rounded-md border border-border-default bg-surface-primary px-3 text-body-sm text-text-primary has-checked:border-accent-maritime has-checked:bg-surface-secondary has-checked:font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus-ring"
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={preference === option.value}
              onChange={() => setPreference(option.value)}
              className="size-4 accent-accent-maritime"
            />
            <span aria-hidden="true">{option.glyph}</span>
            {option.label}
          </label>
        ))}
      </div>
      <p id={descriptionId} className="text-caption text-text-muted">
        {preference === "system"
          ? `Follows your device setting (currently ${resolvedTheme === "dark" ? "Dark" : "Light"}).`
          : `Always ${preference === "dark" ? "Dark" : "Light"}, regardless of your device setting.`}
      </p>
    </fieldset>
  );
}
