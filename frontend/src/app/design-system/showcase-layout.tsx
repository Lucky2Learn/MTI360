"use client";

import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
} from "@/design-system/components";
import {
  ActionBar,
  Container,
  Grid,
  GridItem,
  Inline,
  Section as LayoutSection,
  Show,
  SplitLayout,
  Stack,
  type ContentWidth,
  type Gap,
} from "@/design-system/layout";

import type { ReactNode } from "react";

// T00-09 layout showcase (development/test only; see gate.ts). Generic
// layout demonstrations with sample maritime labels; no business logic.
// The in-shell page example lives at /design-system/layout.

const LONG_INSTITUTE =
  "Anglo-Eastern Maritime Training Centre for Advanced Seafarer Competency Development, Navi Mumbai";
const LONG_EMAIL =
  "admissions.coordinator.pre-sea-training@angloeasternmaritimetrainingcentre.example";

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="flex flex-col gap-4 border-t border-border-subtle pt-8"
    >
      <div className="flex flex-col gap-1">
        <h2 id={`${id}-title`} className="text-section text-text-primary">
          {title}
        </h2>
        <p className="text-body-sm text-text-secondary">{description}</p>
      </div>
      {children}
    </section>
  );
}

/** A neutral block that makes layout boxes visible. */
function Tile({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-12 items-center rounded-md border border-dashed border-border-strong bg-surface-secondary px-3 py-2 text-body-sm break-words text-text-primary">
      {children}
    </div>
  );
}

function Caption({ children }: { children: ReactNode }) {
  return <p className="text-caption text-text-muted">{children}</p>;
}

const WIDTHS: { width: ContentWidth; label: string }[] = [
  { width: "narrow", label: "narrow · 48rem · focused forms, settings" },
  { width: "standard", label: "standard · 72rem · most pages, detail pages" },
  { width: "wide", label: "wide · 80rem · dashboards, lists, tables" },
  { width: "full", label: "full · no cap · workspaces" },
];

const GAPS: Gap[] = ["2xs", "xs", "sm", "md", "lg", "xl", "2xl"];

export function LayoutShowcase() {
  return (
    <>
      <Section
        id="breakpoints"
        title="Breakpoints"
        description="Approved tiers (DESIGN-SYSTEM.md §21): mobile 390–767 (base), tablet 768, desktop 1024, large 1440. Resize the window: exactly one tier is shown."
      >
        <Inline gap="xs" aria-label="Current breakpoint">
          <Show below="tablet">
            <Badge tone="info">Current tier: Mobile (below 768px)</Badge>
          </Show>
          <Show from="tablet" below="desktop">
            <Badge tone="info">Current tier: Tablet (768–1023px)</Badge>
          </Show>
          <Show from="desktop" below="large">
            <Badge tone="info">Current tier: Desktop (1024–1439px)</Badge>
          </Show>
          <Show from="large">
            <Badge tone="info">Current tier: Large (1440px and wider)</Badge>
          </Show>
        </Inline>
        <Caption>
          In-shell page example (sidebar, page header, dashboard, table and form
          layouts):{" "}
          <a
            href="/design-system/layout"
            className="text-link underline underline-offset-4"
          >
            /design-system/layout
          </a>
        </Caption>
      </Section>

      <Section
        id="container"
        title="Container"
        description="Centres content, caps the reading width and applies the page gutter (16 → 24 → 32px). The width is chosen by content type."
      >
        <Stack gap="xs">
          {WIDTHS.map(({ width, label }) => (
            <div
              key={width}
              className="rounded-md border border-border-subtle bg-background-secondary py-2"
            >
              <Container width={width}>
                <Tile>{label}</Tile>
              </Container>
            </div>
          ))}
        </Stack>
        <Caption>
          Inside this showcase (itself capped at 72rem) standard, wide and full
          look alike; the caps apply to the page column.
        </Caption>
      </Section>

      <Section
        id="stack"
        title="Stack"
        description="Vertical flow with a spacing token. xl and 2xl are section spacing: compact on mobile, larger from tablet."
      >
        <Grid columns={{ base: 1, tablet: 2, desktop: 4 }} gap="md">
          {GAPS.map((gap) => (
            <Stack key={gap} gap="xs">
              <p className="text-caption font-semibold text-text-secondary">
                gap=&quot;{gap}&quot;
              </p>
              <Stack gap={gap}>
                <Tile>Item</Tile>
                <Tile>Item</Tile>
              </Stack>
            </Stack>
          ))}
        </Grid>
      </Section>

      <Section
        id="inline"
        title="Inline"
        description="Horizontal flow that wraps instead of overflowing, or stacks full width below a breakpoint."
      >
        <Stack gap="lg">
          <Stack gap="xs">
            <Caption>Badges and metadata wrap:</Caption>
            <Inline gap="xs">
              <Badge tone="success">Documents verified</Badge>
              <Badge tone="warning">Fee instalment overdue</Badge>
              <Badge tone="info">Pre-Sea Training</Badge>
              <Badge tone="neutral">DNS 2026-B</Badge>
              <Badge tone="ai">AI suggestion available</Badge>
              <span className="text-body-sm break-all text-text-secondary">
                {LONG_EMAIL}
              </span>
            </Inline>
          </Stack>
          <Stack gap="xs">
            <Caption>
              stackBelow=&quot;tablet&quot; — full-width buttons on mobile, a
              row from tablet:
            </Caption>
            <Inline stackBelow="tablet" justify="end" gap="xs">
              <Button variant="secondary">Export roster</Button>
              <Button variant="secondary">Print attendance</Button>
              <Button>Add cadet</Button>
            </Inline>
          </Stack>
          <Stack gap="xs">
            <Caption>
              ActionBar — form and panel actions; primary last in the DOM, on
              top on mobile:
            </Caption>
            <ActionBar divider aria-label="Example actions">
              <Button variant="tertiary">Cancel</Button>
              <Button variant="secondary">Save draft</Button>
              <Button>Submit application</Button>
            </ActionBar>
          </Stack>
        </Stack>
      </Section>

      <Section
        id="grid"
        title="Grid"
        description="Equal columns with a count per breakpoint; items span columns. Cells shrink below their content, so long values wrap."
      >
        <Stack gap="lg">
          <Stack gap="xs">
            <Caption>
              columns = base 1 · tablet 2 · desktop 4 (long content in the last
              cell)
            </Caption>
            <Grid columns={{ base: 1, tablet: 2, desktop: 4 }}>
              <Tile>Cell 1</Tile>
              <Tile>Cell 2</Tile>
              <Tile>Cell 3</Tile>
              <Tile>{LONG_INSTITUTE}</Tile>
            </Grid>
          </Stack>
          <Stack gap="xs">
            <Caption>
              12-column grid: spans 8 + 4 from desktop, full below
            </Caption>
            <Grid columns={{ base: 1, desktop: 12 }}>
              <GridItem span={{ base: "full", desktop: 8 }}>
                <Tile>Primary · span 8</Tile>
              </GridItem>
              <GridItem span={{ base: "full", desktop: 4 }}>
                <Tile>Secondary · span 4</Tile>
              </GridItem>
            </Grid>
          </Stack>
        </Stack>
      </Section>

      <Section
        id="layout-section"
        title="Section"
        description="A titled block of page content, named by its heading; actions stack under the title on mobile."
      >
        <Card>
          <LayoutSection
            titleAs="h3"
            title="Upcoming batches"
            description="Batches starting in the next 30 days."
            actions={
              <>
                <Button variant="secondary">View calendar</Button>
                <Button>Schedule batch</Button>
              </>
            }
          >
            <Inline gap="xs">
              <Badge tone="info">DNS 2026-B · 5 Oct</Badge>
              <Badge tone="info">GME 2026-C · 12 Oct</Badge>
              <Badge tone="neutral">STCW Basic Safety · 19 Oct</Badge>
            </Inline>
          </LayoutSection>
        </Card>
      </Section>

      <Section
        id="split-layout"
        title="Two-column layout"
        description="SplitLayout: primary and secondary side by side from desktop (2:1), stacked below. The DOM order is the stacked order."
      >
        <SplitLayout
          primary={
            <Card>
              <CardHeader title="Primary content" />
              <CardBody>
                <p>
                  Record details, forms or the main list. Takes two thirds of
                  the width from desktop.
                </p>
              </CardBody>
            </Card>
          }
          secondary={
            <Card>
              <CardHeader title="Secondary content" />
              <CardBody>
                <p>Summary, status, related information or next steps.</p>
              </CardBody>
            </Card>
          }
        />
        <Caption>
          secondaryPosition=&quot;start&quot;, ratio 1:1 from tablet:
        </Caption>
        <SplitLayout
          ratio="1:1"
          stackBelow="tablet"
          secondaryPosition="start"
          primary={<Tile>Primary (second in the DOM)</Tile>}
          secondary={<Tile>Secondary (first in the DOM)</Tile>}
        />
      </Section>

      <Section
        id="responsive-visibility"
        title="Responsive visibility"
        description="Show renders alternative presentations per width with CSS only (no viewport detection). Every width keeps the same information."
      >
        <Card>
          <Show below="desktop">
            <p className="text-body-sm text-text-primary">
              Compact summary (below desktop): 3 documents pending ·{" "}
              <a href="#responsive-visibility" className="text-link underline">
                Review
              </a>
            </p>
          </Show>
          <Show from="desktop">
            <Stack gap="xs">
              <p className="text-body-sm font-semibold text-text-primary">
                Documents pending (desktop and wider)
              </p>
              <Inline gap="xs" as="ul">
                <li>
                  <Badge tone="warning">INDoS number</Badge>
                </li>
                <li>
                  <Badge tone="warning">Medical fitness certificate</Badge>
                </li>
                <li>
                  <Badge tone="warning">Passport copy</Badge>
                </li>
              </Inline>
            </Stack>
          </Show>
        </Card>
      </Section>
    </>
  );
}
