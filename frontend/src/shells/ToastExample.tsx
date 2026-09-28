"use client";

import { Button, toast } from "@/design-system/components";

// Development affordance on experience home pages (T00-08): shows a toast
// through the shell's global ToastRegion. Removed when the home pages are
// replaced by their dashboards.

export function ToastExample() {
  return (
    <Button
      variant="secondary"
      onPress={() =>
        toast.success("Example notification", {
          description: "Messages from any page appear in this region.",
        })
      }
    >
      Show example notification
    </Button>
  );
}
