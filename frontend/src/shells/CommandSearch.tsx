"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { Button, Dialog, IconButton, Search } from "@/design-system/components";
import { ForwardIcon, SearchIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

import { flattenNavigation, type Navigation } from "./navigation";

// CommandSearch (T00-08): shell entry point for future global search and
// commands. Today it only finds pages of the current experience's navigation
// (static configuration); there is no backend, database, tenant-wide or AI
// search. Opens a T00-07C Dialog from the header button or Ctrl+K / ⌘K;
// focus starts in the search field, Enter opens the first match, Escape
// closes, and focus returns to where it was. The result count is announced.

const MAX_RESULTS = 8;

const subscribeNothing = () => () => {};
const isApplePlatform = () =>
  /Mac|iPhone|iPad/.test(globalThis.navigator?.platform ?? "");

export type CommandSearchProps = {
  experienceLabel: string;
  navigation: Navigation;
};

export function CommandSearch({
  experienceLabel,
  navigation,
}: CommandSearchProps) {
  const router = useRouter();
  const [isOpen, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  // Server snapshot "Ctrl": the label switches to ⌘ after hydration on Apple devices.
  const apple = useSyncExternalStore(
    subscribeNothing,
    isApplePlatform,
    () => false,
  );
  const shortcut = apple ? "⌘ K" : "Ctrl K";

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key.toLowerCase() === "k" &&
        (event.metaKey || event.ctrlKey) &&
        !event.altKey
      ) {
        event.preventDefault();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const onOpenChange = (open: boolean) => {
    setOpen(open);
    if (!open) setQuery("");
  };

  const term = query.trim().toLowerCase();
  const results = flattenNavigation(navigation)
    .filter((item) => !term || item.label.toLowerCase().includes(term))
    .slice(0, MAX_RESULTS);

  return (
    <>
      <span className="hidden tablet:flex">
        <Button
          variant="secondary"
          iconStart={SearchIcon}
          aria-keyshortcuts="Control+K Meta+K"
          onPress={() => setOpen(true)}
        >
          Search
          <kbd
            aria-hidden="true"
            className="rounded-xs border border-border-default px-1 font-sans text-caption-sm text-text-muted"
          >
            {shortcut}
          </kbd>
        </Button>
      </span>
      <span className="flex tablet:hidden">
        <IconButton
          label="Search"
          icon={SearchIcon}
          aria-keyshortcuts="Control+K Meta+K"
          onPress={() => setOpen(true)}
        />
      </span>
      <Dialog
        isOpen={isOpen}
        onOpenChange={onOpenChange}
        size="md"
        title="Search"
        description={`Find pages in ${experienceLabel}.`}
        closeLabel="Close search"
      >
        {(close) => (
          <div className="flex flex-col gap-4">
            <Search
              label="Search pages"
              placeholder="Type a page name"
              value={query}
              onChange={setQuery}
              onSubmit={() => {
                const first = results[0];
                if (!first) return;
                close();
                router.push(first.href);
              }}
              // Opening search is an explicit user request to type (command
              // palette pattern), not DOM autofocus on page load.
              // eslint-disable-next-line jsx-a11y/no-autofocus
              autoFocus
            />
            <p role="status" className="text-caption text-text-muted">
              {results.length === 0
                ? `No pages match “${query.trim()}”.`
                : `${results.length} ${results.length === 1 ? "page" : "pages"}`}
            </p>
            {results.length > 0 && (
              <ul aria-label="Pages" className="flex flex-col gap-1">
                {results.map((item) => (
                  <li key={item.id}>
                    <Link
                      href={item.href}
                      onClick={close}
                      className={cx(
                        "flex min-h-control-lg items-center justify-between gap-3 rounded-md px-3 text-body-sm text-text-primary tablet:min-h-control-md",
                        "transition-colors hover:bg-surface-hover motion-reduce:transition-none",
                        focusRing,
                      )}
                    >
                      <span className="truncate">{item.label}</span>
                      <ForwardIcon
                        aria-hidden="true"
                        className="size-4 shrink-0 text-text-muted"
                      />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-caption text-text-muted">
              Searching records, people and documents arrives in a later phase.
            </p>
          </div>
        )}
      </Dialog>
    </>
  );
}
