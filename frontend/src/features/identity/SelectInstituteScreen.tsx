"use client";

import { useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  EmptyState,
  ErrorState,
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
import { destinationFor, sessionEndedUrl } from "@/lib/session/routes";
import { toSession, type Session } from "@/lib/session/session";

import { InstituteChooser } from "./choosers";
import { FeedbackRegion } from "./components";
import { commonFeedback, type Feedback } from "./feedback";

// AUTH-07 Choose institute (T01-04 UI contract §8.5). Also the landing page
// when a membership is suspended or revoked (T01-08; T01-05 §10 rows D-F):
// the API answers 401, the re-read session has no institute, and this screen
// offers what remains — or "No institute available".

export const NO_INSTITUTE = {
  title: "No institute available",
  description:
    "Your account isn't active in any institute right now. Contact your institute administrator.",
} as const;

export type SelectInstituteScreenProps = {
  session: SessionWire;
  /** Validated `next` (or null). */
  next: string | null;
};

export function SelectInstituteScreen({
  session: initial,
  next,
}: SelectInstituteScreenProps) {
  const [session, setSession] = useState<Session>(() => toSession(initial));
  const [selected, setSelected] = useState<string | null>(
    session.activeInstitute?.id ?? null,
  );
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const reload = async () => {
    setLoading(true);
    setLoadFailed(false);
    try {
      const fresh = await readSession();
      if (!fresh) {
        assignLocation(sessionEndedUrl());
        return;
      }
      setSession(fresh);
      setSelected((current) =>
        fresh.institutes.some((institute) => institute.id === current)
          ? current
          : null,
      );
    } catch {
      setLoadFailed(true);
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
      const fresh = await selectInSession(
        "tenant",
        { tenant_id: selected },
        session.csrfToken,
      );
      // The session was rotated: continue with a full document navigation.
      assignLocation(destinationFor(fresh.status, next));
    } catch (error) {
      setPending(false);
      if (error instanceof ApiError && error.status === 401) {
        assignLocation(sessionEndedUrl());
        return;
      }
      if (
        error instanceof ApiError &&
        (error.code === "NOT_FOUND" || error.code === "CONFLICT")
      ) {
        setFeedback({
          tone: "warning",
          title: "That institute is no longer available to you.",
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

  if (loadFailed) {
    return (
      <AuthenticationTemplate footer={signOutButton}>
        <ErrorState
          titleAs="h1"
          title="We couldn't load your institutes"
          description="Something went wrong while loading your institutes. Try again in a moment."
          onRetry={() => void reload()}
        />
      </AuthenticationTemplate>
    );
  }

  if (!loading && session.institutes.length === 0) {
    return (
      <AuthenticationTemplate>
        {feedback && <Alert tone={feedback.tone} title={feedback.title} />}
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
      title="Choose an institute"
      description="You have access to more than one institute. You can switch later from the top bar."
      footer={
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="text-body-sm break-all text-text-secondary">
            {`Signed in as ${session.user.email}`}
          </p>
          {signOutButton}
        </div>
      }
    >
      <FeedbackRegion feedback={feedback} />
      {loading ? (
        <LoadingRegion label="Loading your institutes">
          <div className="flex flex-col gap-2">
            <Skeleton height="control" />
            <Skeleton height="control" />
            <Skeleton height="control" />
          </div>
        </LoadingRegion>
      ) : (
        <Form aria-label="Choose an institute" onSubmit={(e) => void submit(e)}>
          <InstituteChooser
            institutes={session.institutes}
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
