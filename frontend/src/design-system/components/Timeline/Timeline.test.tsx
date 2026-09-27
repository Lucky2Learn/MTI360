import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/design-system/testing/axe";

import { Timeline, type TimelineItem } from "./Timeline";

const ITEMS: TimelineItem[] = [
  {
    id: "1",
    title: "Application submitted",
    timestamp: "2026-09-12T10:42:00+05:30",
    timestampLabel: "12 Sep 2026, 10:42",
    actor: "Arjun Menon",
    tone: "info",
  },
  {
    id: "2",
    title: "Medical fitness certificate verified",
    timestamp: "2026-09-14T15:05:00+05:30",
    timestampLabel: "14 Sep 2026, 15:05",
    actor: "Admissions desk",
    tone: "success",
    description: "Valid until 13 Sep 2028.",
  },
  {
    id: "3",
    title: "Fee instalment overdue",
    timestamp: "2026-09-20T09:00:00+05:30",
    timestampLabel: "20 Sep 2026, 09:00",
    tone: "warning",
  },
];

describe("Timeline", () => {
  it("renders an ordered, labelled list of events", async () => {
    const { container } = render(
      <Timeline aria-label="Admission activity" items={ITEMS} />,
    );

    const list = screen.getByRole("list", { name: "Admission activity" });
    expect(list.tagName).toBe("OL");
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    await expectNoA11yViolations(container);
  });

  it("uses <time> with a machine-readable timestamp", () => {
    render(<Timeline aria-label="Activity" items={ITEMS} />);
    const time = screen.getByText("14 Sep 2026, 15:05");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("dateTime", "2026-09-14T15:05:00+05:30");
  });

  it("announces status in text, not only by icon colour", () => {
    render(<Timeline aria-label="Activity" items={ITEMS} />);
    expect(screen.getByText("Warning:", { exact: false })).toHaveClass(
      "sr-only",
    );
    expect(screen.getByText("Success:", { exact: false })).toHaveClass(
      "sr-only",
    );
  });

  it("shows actor and description", () => {
    render(<Timeline aria-label="Activity" items={ITEMS} />);
    expect(screen.getByText("Admissions desk")).toBeInTheDocument();
    expect(screen.getByText("Valid until 13 Sep 2028.")).toBeInTheDocument();
  });
});
