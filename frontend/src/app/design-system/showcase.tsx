"use client";

import { useState, type ReactNode } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardFooter,
  CardHeader,
  EmptyState,
  ErrorState,
  IconButton,
  Kpi,
  LoadingRegion,
  SkeletonCard,
  SkeletonTableRows,
  SkeletonText,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  Timeline,
  type ButtonVariant,
  type TimelineItem,
} from "@/design-system/components";
import {
  AddIcon,
  AnchorIcon,
  CloseIcon,
  CompassIcon,
  DownloadIcon,
  ForwardIcon,
  SettingsIcon,
} from "@/design-system/icons";
import { ThemeSelector } from "@/design-system/theme/ThemeSelector";

import { FormsShowcase } from "./showcase-forms";
import { OverlaysShowcase } from "./showcase-overlays";

// Component showcase for T00-07A, T00-07B and T00-07C (development/test only; see gate.ts).
// Realistic maritime sample data (CLAUDE.md §61); nothing is fetched.

const VARIANTS: ButtonVariant[] = [
  "primary",
  "secondary",
  "tertiary",
  "ghost",
  "destructive",
  "success",
];

const TIMELINE: TimelineItem[] = [
  {
    id: "t1",
    title: "Application submitted for DNS 2026-B",
    timestamp: "2026-09-12T10:42:00+05:30",
    timestampLabel: "12 Sep 2026, 10:42",
    actor: "Arjun Menon",
    tone: "info",
  },
  {
    id: "t2",
    title: "Medical fitness certificate verified",
    timestamp: "2026-09-14T15:05:00+05:30",
    timestampLabel: "14 Sep 2026, 15:05",
    actor: "Admissions desk",
    tone: "success",
    description: "Valid until 13 Sep 2028.",
  },
  {
    id: "t3",
    title: "First fee instalment overdue",
    timestamp: "2026-09-20T09:00:00+05:30",
    timestampLabel: "20 Sep 2026, 09:00",
    actor: "Finance",
    tone: "warning",
  },
  {
    id: "t4",
    title: "AI suggested a counselling call",
    timestamp: "2026-09-21T11:15:00+05:30",
    timestampLabel: "21 Sep 2026, 11:15",
    tone: "ai",
    description: "Based on course interest in B.Sc. Nautical Science.",
  },
];

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

export function Showcase() {
  const [presses, setPresses] = useState(0);
  const [retrying, setRetrying] = useState(false);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-4 py-12 tablet:px-8">
      <header className="flex flex-col gap-6 desktop:flex-row desktop:items-end desktop:justify-between">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-semibold tracking-wide text-text-muted uppercase">
            MTI 360 · T00-07A · T00-07B · T00-07C
          </p>
          <h1 className="text-page-title text-text-primary">Design system</h1>
          <p className="max-w-2xl text-body text-text-secondary">
            Core components on the semantic token foundation, in Light, Dark and
            System themes. Development and test environments only.
          </p>
        </div>
        <Card padding="md">
          <ThemeSelector />
        </Card>
      </header>

      <Section
        id="buttons"
        title="Button"
        description="Six variants, three sizes, icons, pending, disabled and link buttons."
      >
        <div className="flex flex-wrap items-center gap-3">
          {VARIANTS.map((variant) => (
            <Button key={variant} variant={variant}>
              {variant[0]!.toUpperCase() + variant.slice(1)}
            </Button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" variant="secondary">
            Small
          </Button>
          <Button size="md" variant="secondary">
            Medium
          </Button>
          <Button size="lg" variant="secondary">
            Large
          </Button>
          <Button iconStart={AddIcon}>Add batch</Button>
          <Button variant="secondary" iconEnd={DownloadIcon}>
            Export roster
          </Button>
          <Button isPending>Saving</Button>
          <Button isDisabled>Approve</Button>
          <Button href="#tabs" variant="tertiary" iconEnd={ForwardIcon}>
            Jump to tabs
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button onPress={() => setPresses((count) => count + 1)}>
            Save batch
          </Button>
          <output
            aria-live="polite"
            className="text-body-sm text-text-secondary"
          >
            Saved {presses} {presses === 1 ? "time" : "times"}
          </output>
        </div>
      </Section>

      <Section
        id="icon-buttons"
        title="IconButton"
        description="Icon-only actions always carry an accessible label."
      >
        <div className="flex flex-wrap items-center gap-3">
          <IconButton label="Batch settings" icon={SettingsIcon} />
          <IconButton
            label="Close panel"
            icon={CloseIcon}
            variant="secondary"
          />
          <IconButton label="Add cadet" icon={AddIcon} variant="primary" />
          <IconButton
            label="Remove access"
            icon={CloseIcon}
            variant="destructive"
          />
          <IconButton
            label="Download certificate"
            icon={DownloadIcon}
            size="lg"
          />
          <IconButton label="Refreshing" icon={SettingsIcon} isPending />
        </div>
      </Section>

      <Section
        id="badges"
        title="Badge"
        description="Status is always text + icon + colour."
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge>Draft</Badge>
          <Badge tone="info">Pending</Badge>
          <Badge tone="success">Approved</Badge>
          <Badge tone="warning">Overdue</Badge>
          <Badge tone="error">Rejected</Badge>
          <Badge tone="ai">AI suggested</Badge>
          <Badge icon={AnchorIcon}>Deck Cadet</Badge>
        </div>
      </Section>

      <Section
        id="kpis"
        title="KPI"
        description="Label, value, trend, comparison and context; trend in words, not colour."
      >
        <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2 large:grid-cols-4">
          <Kpi
            label="Active Students"
            value="1,284"
            trend={{ direction: "up", value: "8.4%", sentiment: "positive" }}
            comparison="vs last month"
            icon={AnchorIcon}
          />
          <Kpi
            label="Admissions this month"
            value="96"
            trend={{ direction: "up", value: "12", sentiment: "positive" }}
            comparison="vs August"
          />
          <Kpi
            label="Fee collection"
            value="₹48,20,000"
            trend={{ direction: "down", value: "3.1%", sentiment: "negative" }}
            comparison="vs last month"
          />
          <Kpi
            label="Training berths allocated"
            value="36 / 40"
            trend={{ direction: "flat", value: "0" }}
            comparison="vs last week"
            context="Across 3 partner shipping companies"
          />
        </div>
      </Section>

      <Section
        id="cards"
        title="Card"
        description="Groups related content; header actions wrap on small screens."
      >
        <div className="grid grid-cols-1 gap-4 desktop:grid-cols-2">
          <Card as="article" aria-labelledby="card-batch">
            <CardHeader
              title="DNS Batch 2026-B"
              titleId="card-batch"
              description="Diploma in Nautical Science · 40 cadets · Mumbai campus"
              actions={<Badge tone="success">Active</Badge>}
            />
            <CardBody>
              <p className="text-text-secondary">
                Pre-sea training started on 1 September. Training berth
                allocation is pending for 4 cadets.
              </p>
            </CardBody>
            <CardFooter>
              <Button variant="secondary" size="sm">
                View roster
              </Button>
              <Button size="sm">Allocate berths</Button>
            </CardFooter>
          </Card>
          <Card elevation="none">
            <CardHeader
              title="STCW Basic Safety"
              description="Post-sea course · 5 days"
            />
            <CardBody>
              <p className="text-text-secondary">
                Next batch opens 14 October. 18 of 24 seats booked.
              </p>
            </CardBody>
          </Card>
        </div>
      </Section>

      <Section
        id="tabs"
        title="Tabs"
        description="Arrow keys, Home and End; horizontal scroll on mobile."
      >
        <Card>
          <Tabs defaultSelectedKey="profile">
            <TabList aria-label="Student record">
              <Tab id="profile">Profile</Tab>
              <Tab id="documents">Documents</Tab>
              <Tab id="fees">Fees</Tab>
              <Tab id="training">Training</Tab>
              <Tab id="certificates">Certificates</Tab>
              <Tab id="placement" isDisabled>
                Placement
              </Tab>
            </TabList>
            <TabPanel id="profile">
              Arjun Menon · Deck Cadet · DNS 2026-B · Mumbai campus
            </TabPanel>
            <TabPanel id="documents">
              CDC, passport and medical fitness certificate verified.
            </TabPanel>
            <TabPanel id="fees">
              Instalment 2 of 3 due on 20 October 2026.
            </TabPanel>
            <TabPanel id="training">
              Pre-sea training: 6 of 24 weeks completed.
            </TabPanel>
            <TabPanel id="certificates">
              STCW Basic Safety — issued 5 Sep 2026.
            </TabPanel>
            <TabPanel id="placement">Placement opens after sea time.</TabPanel>
          </Tabs>
        </Card>
      </Section>

      <Section
        id="timeline"
        title="Timeline"
        description="Ordered events with machine-readable time and status in text."
      >
        <Card>
          <Timeline
            aria-label="Admission activity for Arjun Menon"
            items={TIMELINE}
          />
        </Card>
      </Section>

      <Section
        id="alerts"
        title="Alert"
        description="Concise, actionable, accessible; errors are announced assertively."
      >
        <div className="flex flex-col gap-3">
          <Alert tone="info" title="New RPSL circular published">
            Review the updated documentation checklist for placement.
          </Alert>
          <Alert
            tone="success"
            title="Payment recorded successfully."
            action={
              <Button variant="tertiary" size="sm">
                View receipt
              </Button>
            }
          >
            Receipt MTI-2026-0412 was sent to the cadet.
          </Alert>
          <Alert tone="warning" title="Medical certificate expires in 14 days">
            3 cadets in DNS 2026-B need renewed medical fitness certificates.
          </Alert>
          <Alert tone="error" title="Certificate generation failed">
            Nothing was issued. Check the signatory settings and try again.
          </Alert>
        </div>
      </Section>

      <Section
        id="skeletons"
        title="Skeleton"
        description="Layout-stable loading placeholders; one polite announcement."
      >
        <LoadingRegion label="Loading batch overview">
          <div className="grid grid-cols-1 gap-4 desktop:grid-cols-2">
            <SkeletonCard />
            <div className="flex flex-col gap-4 rounded-xl border border-border-subtle bg-surface-primary p-4 tablet:p-6">
              <SkeletonText lines={2} />
              <SkeletonTableRows rows={3} columns={4} />
            </div>
          </div>
        </LoadingRegion>
      </Section>

      <Section
        id="empty-states"
        title="EmptyState"
        description="What is empty, why, and what to do next."
      >
        <Card>
          <EmptyState
            title="No leads yet"
            description="Enquiries from your website, campaigns and walk-ins will appear here."
            icon={CompassIcon}
            primaryAction={<Button iconStart={AddIcon}>Add lead</Button>}
            secondaryAction={<Button variant="secondary">Import leads</Button>}
          />
        </Card>
      </Section>

      <Section
        id="error-states"
        title="ErrorState"
        description="What happened, what was saved, what to do; permission-restricted variant."
      >
        <div className="grid grid-cols-1 gap-4 desktop:grid-cols-2">
          <Card>
            <ErrorState
              titleAs="h3"
              title="We couldn't load the fee schedule"
              description="The finance service did not respond. Try again in a moment."
              savedState="Your changes to the instalment plan were saved."
              onRetry={() => {
                setRetrying(true);
                window.setTimeout(() => setRetrying(false), 1200);
              }}
              isRetrying={retrying}
              backHref="#top"
              supportHref="#top"
              reference="req-7f3a9c"
            />
          </Card>
          <Card>
            <ErrorState
              titleAs="h3"
              kind="permission"
              title="You don't have permission to approve this application."
              description="Ask your Admissions Manager for approval access."
              backHref="#top"
            />
          </Card>
        </div>
      </Section>

      <FormsShowcase />
      <OverlaysShowcase />
    </main>
  );
}
