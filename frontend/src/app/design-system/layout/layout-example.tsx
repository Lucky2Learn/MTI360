"use client";

import { useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  DataTable,
  FilterBar,
  Form,
  Input,
  Kpi,
  Pagination,
  Search,
  Select,
  Textarea,
  type DataTableColumn,
} from "@/design-system/components";
import { UsersIcon } from "@/design-system/icons";
import {
  ActionBar,
  Grid,
  GridItem,
  Inline,
  Section,
  SplitLayout,
  Stack,
} from "@/design-system/layout";
import {
  EXPERIENCE,
  ExperienceFrame,
  PageContainer,
  PageContent,
  PageHeader,
} from "@/shells";

// T00-09 in-shell page example (development/test only; see ../gate.ts).
// Generic layouts inside the real ApplicationShell — page header, dashboard,
// data, detail and form layouts — with deliberately long sample content to
// prove nothing overflows at 390/768/1024/1440. No business logic: nothing
// is fetched, filtered or submitted.

type Enrolment = {
  id: string;
  cadet: string;
  email: string;
  course: string;
  batch: string;
  fees: string;
  status: "Enrolled" | "Documents pending" | "Deferred";
};

const ROWS: Enrolment[] = [
  {
    id: "e1",
    cadet: "Arjun Menon",
    email: "arjun.menon@example.in",
    course: "DNS — Diploma in Nautical Science",
    batch: "DNS 2026-B",
    fees: "₹3,85,000",
    status: "Enrolled",
  },
  {
    id: "e2",
    cadet: "Venkataraghavan Subramaniam Iyer-Ramachandran",
    email:
      "venkataraghavan.subramaniam.iyer-ramachandran@seafarers-association.example",
    course:
      "B.Sc. Nautical Science (Pre-Sea, Three-Year Residential Programme with Training Berth Assurance)",
    batch: "BSc NS 2026-A",
    fees: "₹12,40,00,000",
    status: "Documents pending",
  },
  {
    id: "e3",
    cadet: "Fatima Sheikh",
    email: "fatima.sheikh@example.in",
    course: "GME — Graduate Marine Engineering",
    batch: "GME 2026-C",
    fees: "₹4,10,000",
    status: "Deferred",
  },
];

const statusTone = {
  Enrolled: "success",
  "Documents pending": "warning",
  Deferred: "neutral",
} as const;

const COLUMNS: DataTableColumn<Enrolment>[] = [
  {
    id: "cadet",
    header: "Cadet",
    cell: (row) => row.cadet,
    isRowHeader: true,
  },
  {
    id: "email",
    header: "Email",
    cell: (row) => row.email,
    visibleFrom: "desktop",
  },
  { id: "course", header: "Course", cell: (row) => row.course },
  {
    id: "batch",
    header: "Batch",
    cell: (row) => row.batch,
    visibleFrom: "tablet",
  },
  { id: "fees", header: "Fees (₹)", cell: (row) => row.fees, align: "end" },
  {
    id: "status",
    header: "Status",
    cell: (row) => <Badge tone={statusTone[row.status]}>{row.status}</Badge>,
  },
];

function ChartArea({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader title={title} description="Last 6 months" />
      <div
        role="img"
        aria-label={`${title}: chart placeholder (charts arrive with the analytics foundation)`}
        className="flex h-48 items-center justify-center rounded-md border border-dashed border-border-strong bg-surface-secondary px-4 text-center text-body-sm text-text-secondary"
      >
        Chart placeholder
      </div>
    </Card>
  );
}

function Fact({ term, children }: { term: string; children: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="text-caption text-text-muted">{term}</dt>
      <dd className="text-body-sm break-words text-text-primary">{children}</dd>
    </div>
  );
}

export function LayoutExample() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  return (
    <ExperienceFrame experience={EXPERIENCE.TENANT}>
      <PageContainer width="wide">
        <PageHeader
          breadcrumbs={[
            { label: "Design system", href: "/design-system" },
            { label: "Layout foundation", href: "/design-system#breakpoints" },
            { label: "Operations overview for a very long institute name" },
          ]}
          title="Pre-Sea Training Operations Overview — Anglo-Eastern Maritime Training Centre, Navi Mumbai"
          status={<Badge tone="info">Layout example</Badge>}
          description="Generic page layout inside the application shell: header, dashboard, data, detail and form layouts with long sample content. Nothing here is live data."
          actions={
            <>
              <Button variant="secondary">Export report</Button>
              <Button variant="secondary">Share</Button>
              <Button>Schedule batch</Button>
            </>
          }
        />
        <PageContent>
          <Alert title="Development example">
            Sample content only. This page exists in development and test
            environments and returns 404 in production.
          </Alert>

          <Section
            title="Dashboard layout"
            description="KPIs: 1 column on mobile, 2 on tablet and desktop (the sidebar takes 256px), 4 from large. Charts: stacked below desktop."
          >
            <Grid
              as="ul"
              columns={{ base: 1, tablet: 2, large: 4 }}
              aria-label="Key figures"
            >
              <li>
                <Kpi
                  label="Active cadets"
                  value="1,284"
                  icon={UsersIcon}
                  trend={{
                    direction: "up",
                    value: "8.4%",
                    sentiment: "positive",
                  }}
                  comparison="vs last month"
                />
              </li>
              <li>
                <Kpi
                  label="Batches in session"
                  value="26"
                  comparison="across 3 campuses"
                />
              </li>
              <li>
                <Kpi
                  label="Fees collected this year"
                  value="₹12,40,00,000"
                  trend={{
                    direction: "down",
                    value: "2.1%",
                    sentiment: "negative",
                  }}
                  comparison="vs last year"
                />
              </li>
              <li>
                <Kpi label="Documents awaiting verification" value="73" />
              </li>
            </Grid>
            <Grid columns={{ base: 1, desktop: 2 }}>
              <ChartArea title="Enquiries by course" />
              <ChartArea title="Batch occupancy" />
            </Grid>
          </Section>

          <Section
            title="Data layout"
            description="Filters above the table; table actions in the section header. The table scrolls inside its own region — never the page."
            actions={<Button variant="secondary">Export CSV</Button>}
          >
            <FilterBar
              label="Enrolment filters"
              search={
                <Search
                  label="Search cadets"
                  isLabelHidden
                  value={query}
                  onChange={setQuery}
                  placeholder="Search cadets"
                />
              }
              filters={
                <div className="w-full tablet:w-56">
                  <Select
                    label="Status"
                    options={[
                      { id: "enrolled", label: "Enrolled" },
                      { id: "pending", label: "Documents pending" },
                      { id: "deferred", label: "Deferred" },
                    ]}
                    value={status}
                    onChange={setStatus}
                  />
                </div>
              }
              activeFilterCount={status ? 1 : 0}
              resultCount={`${ROWS.length} results`}
              onClear={() => setStatus(null)}
            />
            <DataTable
              label="Enrolments (sample)"
              columns={COLUMNS}
              rows={ROWS}
              getRowId={(row) => row.id}
              getRowLabel={(row) => row.cadet}
              footer={
                <Pagination
                  page={page}
                  pageSize={10}
                  totalItems={128}
                  onPageChange={setPage}
                  itemLabel="enrolments"
                  label="Enrolment pages"
                />
              }
            />
          </Section>

          <Section
            title="Detail layout"
            description="Summary and primary content with secondary information beside it from desktop, below it on smaller screens."
          >
            <SplitLayout
              primary={
                <Card as="section" aria-labelledby="detail-primary">
                  <CardHeader
                    title="Primary content"
                    titleAs="h3"
                    titleId="detail-primary"
                    description="Record details — facts reflow from 1 to 3 columns."
                  />
                  <Grid
                    as="dl"
                    columns={{ base: 1, tablet: 2, desktop: 3 }}
                    gap="md"
                  >
                    <Fact term="Cadet">
                      Venkataraghavan Subramaniam Iyer-Ramachandran
                    </Fact>
                    <Fact term="Email">
                      venkataraghavan.subramaniam.iyer-ramachandran@seafarers-association.example
                    </Fact>
                    <Fact term="Course">B.Sc. Nautical Science</Fact>
                    <Fact term="Batch">BSc NS 2026-A</Fact>
                    <Fact term="INDoS">19ZL1234</Fact>
                    <Fact term="Training berth">Awaiting allocation</Fact>
                  </Grid>
                </Card>
              }
              secondary={
                <Card as="section" aria-labelledby="detail-secondary">
                  <CardHeader
                    title="Secondary content"
                    titleAs="h3"
                    titleId="detail-secondary"
                  />
                  <CardBody>
                    <Inline gap="xs">
                      <Badge tone="warning">Documents pending</Badge>
                      <Badge tone="info">Pre-Sea Training</Badge>
                    </Inline>
                    <p>Related information, status and next steps.</p>
                  </CardBody>
                  <ActionBar>
                    <Button variant="secondary">Message cadet</Button>
                    <Button>Verify documents</Button>
                  </ActionBar>
                </Card>
              }
            />
          </Section>

          <Section
            title="Form layout"
            description="Two columns from desktop, one on mobile and tablet; long fields span both columns; actions stack on mobile with the primary on top."
          >
            <Card>
              <Form onSubmit={(event) => event.preventDefault()}>
                <Stack gap="lg">
                  <Grid columns={{ base: 1, desktop: 2 }}>
                    <Input label="Full name" autoComplete="name" isRequired />
                    <Input label="Email" type="email" autoComplete="email" />
                    <Input
                      label="Institute"
                      defaultValue="Anglo-Eastern Maritime Training Centre for Advanced Seafarer Competency Development"
                    />
                    <Select
                      label="Course of interest"
                      options={[
                        {
                          id: "dns",
                          label: "DNS — Diploma in Nautical Science",
                        },
                        {
                          id: "gme",
                          label: "GME — Graduate Marine Engineering",
                        },
                      ]}
                    />
                    <GridItem span="full">
                      <Textarea
                        label="Notes"
                        placeholder="Sea-career plans, questions"
                      />
                    </GridItem>
                  </Grid>
                  <ActionBar divider aria-label="Form actions">
                    <Button variant="tertiary">Cancel</Button>
                    <Button variant="secondary">Save draft</Button>
                    <Button type="submit">Submit enquiry</Button>
                  </ActionBar>
                </Stack>
              </Form>
            </Card>
          </Section>
        </PageContent>
      </PageContainer>
    </ExperienceFrame>
  );
}
