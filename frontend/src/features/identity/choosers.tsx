"use client";

import { useState } from "react";

import { Button, RadioGroup, Search } from "@/design-system/components";
import type { Campus, Institute } from "@/lib/session/session";

// Chooser bodies shared by AUTH-07 / AUTH-08 and the in-shell switch dialogs
// (T01-04 UI contract §8.5, §8.6, §8.8). The options are EXACTLY what the
// server session returned — no free text, nothing cached from earlier
// sessions, nothing from the URL or storage. The chosen value is only a
// selector: the API decides whether it is allowed (S1).

const SEARCH_THRESHOLD = 8;
const collator = new Intl.Collator(undefined, { sensitivity: "base" });

export type InstituteChooserProps = {
  institutes: Institute[];
  value: string | null;
  onChange: (id: string) => void;
  isDisabled?: boolean;
  isInvalid?: boolean;
};

/** Institutes as a radio group, with a search above it when there are more than 8. */
export function InstituteChooser({
  institutes,
  value,
  onChange,
  isDisabled = false,
  isInvalid = false,
}: InstituteChooserProps) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLocaleLowerCase();
  const visible = needle
    ? institutes.filter((institute) =>
        institute.name.toLocaleLowerCase().includes(needle),
      )
    : institutes;

  return (
    <div className="flex flex-col gap-4">
      {institutes.length > SEARCH_THRESHOLD && (
        <Search
          label="Find an institute"
          placeholder="Search institutes"
          value={query}
          onChange={setQuery}
        />
      )}
      {visible.length === 0 ? (
        <div className="flex flex-col items-start gap-2">
          <p className="text-body-sm text-text-secondary">
            {`No institutes match '${query.trim()}'.`}
          </p>
          <Button variant="tertiary" onPress={() => setQuery("")}>
            Clear search
          </Button>
        </div>
      ) : (
        <RadioGroup
          label="Institutes"
          isLabelHidden
          isRequired
          isDisabled={isDisabled}
          isInvalid={isInvalid || undefined}
          errorMessage="Choose an institute to continue."
          value={value}
          onChange={onChange}
          options={visible.map((institute) => ({
            value: institute.id,
            label: institute.name,
            description: institute.isTrial ? "Trial" : undefined,
          }))}
        />
      )}
    </div>
  );
}

/** Value of the "All campuses" option (sent to the API as null). */
export const ALL_CAMPUSES = "all-campuses";

export type CampusChooserProps = {
  campuses: Campus[];
  value: string | null;
  onChange: (value: string) => void;
  /** Offer "All campuses" first — only when the server allows it (D04). */
  allCampuses?: { instituteName: string } | null;
  isDisabled?: boolean;
  isInvalid?: boolean;
};

export function CampusChooser({
  campuses,
  value,
  onChange,
  allCampuses = null,
  isDisabled = false,
  isInvalid = false,
}: CampusChooserProps) {
  const options = [
    ...(allCampuses
      ? [
          {
            value: ALL_CAMPUSES,
            label: "All campuses",
            description: `Every campus of ${allCampuses.instituteName}`,
          },
        ]
      : []),
    ...[...campuses]
      .sort((a, b) => collator.compare(a.name, b.name))
      .map((campus) => ({
        value: campus.id,
        label: campus.name,
        description: campus.code,
      })),
  ];
  return (
    <RadioGroup
      label="Campuses"
      isLabelHidden
      isRequired
      isDisabled={isDisabled}
      isInvalid={isInvalid || undefined}
      errorMessage="Choose a campus to continue."
      value={value}
      onChange={onChange}
      options={options}
    />
  );
}
