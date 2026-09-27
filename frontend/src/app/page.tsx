import { ThemeSelector } from "@/design-system/theme/ThemeSelector";

// Neutral foundation page (T00-02, token-styled since T00-06). This is not a
// product screen; it is replaced when the application shells and experience
// routes are built (T00-08 onwards). It shows the theme control so Light, Dark
// and System can be verified.
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-3xl flex-col justify-center gap-8 px-4 py-12 tablet:px-8">
      <div className="flex flex-col gap-3">
        <h1 className="text-page-title text-text-primary">MTI 360</h1>
        <p className="text-body text-text-secondary">
          Application foundation. Product experiences are not implemented yet.
        </p>
      </div>
      <section
        aria-label="Appearance"
        className="rounded-xl border border-border-subtle bg-surface-primary p-6 shadow-sm"
      >
        <ThemeSelector />
      </section>
    </main>
  );
}
