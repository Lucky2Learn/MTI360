"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AlertDialog, Button, toast } from "@/design-system/components";
import { EditIcon } from "@/design-system/icons";
import type { CourseStatus, CourseWire } from "@/lib/api/admissions";
import { ApiError } from "@/lib/api/errors";
import { notifyActionError } from "@/lib/authz/action-feedback";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { COURSE_MANAGE, coursePath } from "./labels";

// ACA-02 course actions (Phase 02-1; blueprint §5, §21): edit, activate,
// archive (confirmed: leads keep the course) and reactivate — only with
// course.manage, and only the moves the course's status allows. The server
// re-checks the status move and the version; a conflict refreshes the page.

type Move = { to: CourseStatus; label: string; done: string };

const MOVES: Record<CourseStatus, Move[]> = {
  DRAFT: [
    { to: "ACTIVE", label: "Activate", done: "Course activated" },
    { to: "ARCHIVED", label: "Archive", done: "Course archived" },
  ],
  ACTIVE: [{ to: "ARCHIVED", label: "Archive", done: "Course archived" }],
  ARCHIVED: [{ to: "ACTIVE", label: "Reactivate", done: "Course reactivated" }],
};

export function CourseActions({ course }: { course: CourseWire }) {
  const router = useRouter();
  const { request } = useTenantSession();
  const [pending, setPending] = useState<CourseStatus | null>(null);
  const [confirming, setConfirming] = useState(false);

  const move = async ({ to, done }: Move) => {
    setPending(to);
    try {
      await request(`/courses/${course.id}/status`, {
        method: "POST",
        body: { status: to, version: course.version },
      });
      toast.success(done);
    } catch (error) {
      if (error instanceof ApiError && error.code === "CONFLICT") {
        toast.warning("This course changed — the latest version is shown.");
      } else {
        notifyActionError(error, `course-status:${course.id}`);
      }
    } finally {
      setPending(null);
      setConfirming(false);
      router.refresh();
    }
  };

  return (
    <PermissionGate permission={COURSE_MANAGE}>
      <Button
        variant="secondary"
        iconStart={EditIcon}
        href={`${coursePath(course.id)}/edit`}
      >
        Edit
      </Button>
      {MOVES[course.status].map((item) =>
        item.to === "ARCHIVED" ? (
          <Button
            key={item.to}
            variant="secondary"
            onPress={() => setConfirming(true)}
            isPending={pending === item.to}
          >
            {item.label}
          </Button>
        ) : (
          <Button
            key={item.to}
            onPress={() => void move(item)}
            isPending={pending === item.to}
          >
            {item.label}
          </Button>
        ),
      )}
      <AlertDialog
        isOpen={confirming}
        onOpenChange={setConfirming}
        title={`Archive ${course.name}?`}
        description="Leads and applications keep this course, but it can't be chosen for new ones. You can reactivate it later."
        confirmLabel="Archive course"
        isPending={pending === "ARCHIVED"}
        onConfirm={() =>
          void move({
            to: "ARCHIVED",
            label: "Archive",
            done: "Course archived",
          })
        }
      />
    </PermissionGate>
  );
}
