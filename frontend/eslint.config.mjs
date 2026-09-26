import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import jsxA11y from "eslint-plugin-jsx-a11y";
import tseslint from "typescript-eslint";

// Lint scope: frontend/ only. The root marketing website (index.html, app.js,
// styles.css) is intentionally never linted.
export default defineConfig([
  ...nextVitals,
  ...nextTs,

  // Type-aware TypeScript rules. The @typescript-eslint plugin and parser are
  // already registered by eslint-config-next, so only rules are added here.
  {
    files: ["**/*.{ts,tsx,mts}"],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      ...Object.assign(
        {},
        ...tseslint.configs.recommendedTypeCheckedOnly.map((c) => c.rules),
      ),
    },
  },

  // Full jsx-a11y recommended rule set (WCAG 2.2 AA target, CLAUDE.md §38).
  // The plugin itself is registered by eslint-config-next.
  {
    files: ["**/*.{jsx,tsx}"],
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
    },
  },

  // Import ordering (plugin registered by eslint-config-next).
  {
    rules: {
      "import/order": [
        "error",
        {
          groups: [
            "builtin",
            "external",
            "internal",
            "parent",
            "sibling",
            "index",
            "type",
          ],
          pathGroups: [{ pattern: "@/**", group: "internal" }],
          "newlines-between": "always",
          alphabetize: { order: "asc", caseInsensitive: true },
        },
      ],
    },
  },

  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "coverage/**",
    "next-env.d.ts",
  ]),
]);
