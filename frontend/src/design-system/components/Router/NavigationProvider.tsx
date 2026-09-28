"use client";

import { RouterProvider } from "react-aria-components";

import type { ReactNode } from "react";

// NavigationProvider (T00-08): connects React Aria links — Button href,
// menu items with href, Link-rendering components — to the application's
// client-side router, so they navigate without a full page load. Framework
// neutral: the application shell passes Next.js' router.push. Without the
// provider, links fall back to normal browser navigation.

export type NavigationProviderProps = {
  /** Client-side navigation, e.g. (href) => router.push(href). */
  navigate: (href: string) => void;
  children: ReactNode;
};

export function NavigationProvider({
  navigate,
  children,
}: NavigationProviderProps) {
  return <RouterProvider navigate={navigate}>{children}</RouterProvider>;
}
