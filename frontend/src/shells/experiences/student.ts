import {
  AttendanceIcon,
  CertificateIcon,
  CourseIcon,
  ExamIcon,
  FeeIcon,
  FileIcon,
  HomeIcon,
  NotificationIcon,
  ProfileIcon,
  ScheduleIcon,
} from "@/design-system/icons";

import { EXPERIENCE, type ApplicationExperience } from "./types";

// Student Portal (/student): mobile-first and task-oriented (CLAUDE.md §4.3,
// §15). A simpler shell than the staff experiences: a fixed desktop sidebar
// (the navigation drawer on mobile and tablet), no command search, standard
// content width. A separate realm from staff users (ADR-0005). Navigation
// placeholders only; the portal is built in Phase 13.

const page = (
  id: string,
  label: string,
  path: string,
  icon: typeof HomeIcon,
) => ({ id, label, href: `/student${path}`, icon });

export const studentExperience: ApplicationExperience = {
  id: EXPERIENCE.STUDENT,
  label: "Student Portal",
  basePath: "/student",
  navigationLabel: "Student navigation",
  layout: "application",
  sidebar: "fixed",
  search: false,
  notifications: true,
  pageWidth: "standard",
  navigation: [
    {
      id: "student",
      items: [
        page("home", "Home", "", HomeIcon),
        page("course", "My Course", "/course", CourseIcon),
        page("schedule", "Schedule", "/schedule", ScheduleIcon),
        page("attendance", "Attendance", "/attendance", AttendanceIcon),
        page("exams", "Exams", "/exams", ExamIcon),
        page("certificates", "Certificates", "/certificates", CertificateIcon),
        page("fees", "Fees", "/fees", FeeIcon),
        page("documents", "Documents", "/documents", FileIcon),
        page(
          "notifications",
          "Notifications",
          "/notifications",
          NotificationIcon,
        ),
        page("profile", "Profile", "/profile", ProfileIcon),
      ],
    },
  ],
  demo: {
    account: {
      name: "Student",
      detail: "Demo account · Student Portal",
      initials: "ST",
    },
    notifications: [
      {
        id: "student-n1",
        title: "Fee instalment due on 5 October",
        description: "Second instalment for Pre-Sea Training.",
        timestamp: "2026-09-28T08:00:00+05:30",
        timeLabel: "2 hours ago",
        read: false,
      },
      {
        id: "student-n2",
        title: "Timetable updated",
        description: "Seamanship practical moved to Thursday.",
        timestamp: "2026-09-27T15:20:00+05:30",
        timeLabel: "Yesterday",
        read: true,
      },
    ],
  },
};
