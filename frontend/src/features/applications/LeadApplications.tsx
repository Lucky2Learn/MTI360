import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
} from "@/design-system/components";
import type { ApplicationListItemWire } from "@/lib/api/admissions";

import { RecordLink } from "../shared/RecordLink";

import { applicationPath, STATUS_LABEL, STATUS_TONE } from "./labels";

// The applications started from a lead (Phase 02-2; GROW-09 Lead 360 →
// ADM-06). Read on the server with application.read; only applications of the
// member's campuses are listed (the API's campus rule).

export function LeadApplications({
  applications,
}: {
  applications: ApplicationListItemWire[];
}) {
  return (
    <Card as="section">
      <CardHeader title="Applications" titleAs="h2" />
      <CardBody>
        {applications.length === 0 ? (
          <EmptyState
            title="No applications yet"
            description="Start an application when the enquirer is ready to apply."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {applications.map((application) => (
              <li key={application.id} className="flex flex-col gap-1">
                <RecordLink href={applicationPath(application.id)}>
                  {`${application.number} · ${application.course_code}`}
                </RecordLink>
                <span>
                  <Badge tone={STATUS_TONE[application.status]}>
                    {STATUS_LABEL[application.status]}
                  </Badge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
