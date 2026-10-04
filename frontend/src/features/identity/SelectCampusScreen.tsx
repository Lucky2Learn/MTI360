"use client";

import { useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  EmptyState,
  Form,
  LoadingRegion,
  Skeleton,
} from "@/design-system/components";
import { InstituteIcon } from "@/design-system/icons";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import { ApiError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";
import { readSession, selectInSession, signOut } from "@/lib/session/client";
import { assignLocation } from "@/lib/session/document";
import {
  AUTH_ROUTES,
  authUrl,
  resolveNext,
  sessionEndedUrl,
} from "@/lib/session/routes";
import { toSession, type Session } from "@/lib/session/session";

import { CampusChooser } from "./choosers";
import { FeedbackRegion } from "./components";
import { commonFeedback, type Feedback } from "./feedback";
import { NO_INSTITUTE } from "./SelectInstituteScreen";

// AUTH-08 Choose campus (T01-04 UI contract §8.6; D04). Reached only when the
// server says `campus_selection_required` (SELECTED scope with two or more
// permitted campuses and none chosen, or the active campus was withdrawn).
// The options are exactly `campus_options`; there is no "All campuses" here.
// The active campus is a view filter, not an authorization boundary (D-B1).

export type SelectCampusScreenProps = {
  session: SessionWire;
  next: string | null;
  /** The previous campus was withdrawn (shows the notice). */
  campusWithdrawn: boolean;
};

export function SelectCampusScreen({
  session: initial,
  next,
  campusWithdrawn,
}: SelectCampusScreenProps) {
  const [session, setSession] = useState<Session>(() => toSession(initial));
  const [selected, setSelected] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const reload = async () => {
    setLoading(true);
    try {
      const fresh = await readSession();
      if (!fresh) {
        assignLocation(sessionEndedUrl());
        return;
      }
      setSession(fresh);
      setSelected(null);
    } catch (error) {
      setFeedback(commonFeedback(error));
    } finally {
      setLoading(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending || !selected) return;
    setPending(true);
    setFeedback(null);
    try {
      await selectInSession(
        "campus",
        { campus_id: selected },
        session.csrfToken,
      );
      assignLocation(resolveNext(next));
    } catch (error) {
      setPending(false);
      if (error instanceof ApiError && error.status === 401) {
        assignLocation(sessionEndedUrl());
        return;
      }
      if (error instanceof ApiError && error.code === "NOT_FOUND") {
        setFeedback({
          tone: "warning",
          title: "That campus is no longer available to you.",
        });
        await reload();
        return;
      }
      setFeedback(commonFeedback(error));
    }
  };

  const signOutButton = (
    <Button variant="tertiary" onPress={() => void signOut()}>
      Sign out
    </Button>
  );

  // Defensive: a usable membership always has a permitted campus.
  if (!loading && session.campusOptions.length === 0) {
    return (
      <AuthenticationTemplate>
        <EmptyState
          titleAs="h1"
          icon={InstituteIcon}
          title={NO_INSTITUTE.title}
          description={NO_INSTITUTE.description}
          primaryAction={
            <Button onPress={() => void signOut()}>Sign out</Button>
          }
        />
      </AuthenticationTemplate>
    );
  }

  return (
    <AuthenticationTemplate
      title="Choose a campus"
      description={`${session.activeInstitute?.name ?? ""}. You can change campus later from the top bar.`}
      notice={
        campusWithdrawn ? (
          <Alert
            tone="info"
            title="The campus you were using is no longer available to you. Choose another to continue."
          />
        ) : undefined
      }
      footer={
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {session.institutes.length > 1 && (
            <Button
              variant="tertiary"
              href={authUrl(AUTH_ROUTES.selectInstitute, { next })}
            >
              Choose a different institute
            </Button>
          )}
          {signOutButton}
        </div>
      }
    >
      <FeedbackRegion feedback={feedback} />
      {loading ? (
        <LoadingRegion label="Loading your campuses">
          <div className="flex flex-col gap-2">
            <Skeleton height="control" />
            <Skeleton height="control" />
            <Skeleton height="control" />
          </div>
        </LoadingRegion>
      ) : (
        <Form aria-label="Choose a campus" onSubmit={(e) => void submit(e)}>
          <CampusChooser
            campuses={session.campusOptions}
            value={selected}
            onChange={setSelected}
            isDisabled={pending}
          />
          <Button type="submit" size="lg" fullWidth isPending={pending}>
            {pending ? "Opening…" : "Continue"}
          </Button>
        </Form>
      )}
    </AuthenticationTemplate>
  );
}
