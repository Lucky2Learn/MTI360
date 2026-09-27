"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import {
  Alert,
  Button,
  Card,
  Checkbox,
  Combobox,
  DatePicker,
  FileUpload,
  Form,
  Input,
  Select,
  Textarea,
  type AcceptedFileType,
  type Option,
} from "@/design-system/components";
import { AnchorIcon } from "@/design-system/icons";

// T00-07B form-component showcase (development/test only; see gate.ts).
// Nothing is submitted or uploaded anywhere; the "server validation" is local.

const COURSES: Option[] = [
  {
    id: "dns",
    label: "DNS — Diploma in Nautical Science",
    description: "Pre-sea · 1 year",
  },
  {
    id: "gme",
    label: "GME — Graduate Marine Engineering",
    description: "Pre-sea · 1 year",
  },
  {
    id: "bsc",
    label: "B.Sc. Nautical Science",
    description: "Pre-sea · 3 years",
  },
  { id: "stcw", label: "STCW Basic Safety", description: "Post-sea · 5 days" },
  {
    id: "eto",
    label: "ETO — Electro-Technical Officer",
    description: "Admissions closed",
    isDisabled: true,
  },
];

const CITIES: Option[] = [
  "Mumbai",
  "Chennai",
  "Kochi",
  "Kolkata",
  "Visakhapatnam",
  "Goa",
  "Pune",
  "Delhi",
  "Bengaluru",
  "Hyderabad",
  "Ahmedabad",
  "Lucknow",
  "Patna",
  "Chandigarh",
].map((city) => ({ id: city.toLowerCase(), label: city }));

const SHIPPING_COMPANIES = [
  "Anglo-Eastern Ship Management",
  "Great Eastern Shipping",
  "Synergy Marine Group",
  "Fleet Management Limited",
  "Wallem Shipmanagement",
  "Bernhard Schulte Shipmanagement",
  "V.Ships India",
  "Shipping Corporation of India",
].map((name) => ({
  id: name.toLowerCase().replace(/[^a-z]+/g, "-"),
  label: name,
}));

const DOCUMENTS: AcceptedFileType[] = [
  { label: "PDF", mimeTypes: ["application/pdf"], extensions: [".pdf"] },
  { label: "JPG", mimeTypes: ["image/jpeg"], extensions: [".jpg", ".jpeg"] },
  { label: "PNG", mimeTypes: ["image/png"], extensions: [".png"] },
];

const MB = 1024 * 1024;

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

const grid = "grid grid-cols-1 gap-6 desktop:grid-cols-2";

function AsyncCompanyCombobox() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Option[]>([]);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const search = (next: string) => {
    setText(next);
    window.clearTimeout(timer.current);
    if (!next) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    timer.current = window.setTimeout(() => {
      const query = next.toLowerCase();
      setResults(
        SHIPPING_COMPANIES.filter((c) => c.label.toLowerCase().includes(query)),
      );
      setLoading(false);
    }, 400);
  };

  return (
    <Combobox
      label="Sponsoring company (async)"
      filtering="manual"
      options={results}
      isLoading={loading}
      inputValue={text}
      onInputChange={search}
      placeholder="Type to search companies"
      emptyMessage={text ? "No companies match" : "Start typing to search"}
      description="Simulated server search (400 ms); the component never fetches."
    />
  );
}

function StudentEnquiryForm() {
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  return (
    <Card>
      <Form
        validationErrors={serverErrors}
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted(true);
        }}
        onReset={() => {
          setServerErrors({});
          setSubmitted(false);
        }}
      >
        <div className="flex flex-col gap-1">
          <h3 className="text-card-heading text-text-primary">
            Student enquiry
          </h3>
          <p className="text-caption text-text-secondary">
            <span aria-hidden="true" className="text-error-text">
              *
            </span>{" "}
            Required field
          </p>
        </div>
        {submitted && (
          <Alert tone="success" title="Enquiry saved (demo).">
            Nothing was sent — this form only demonstrates validation.
          </Alert>
        )}
        <div className={grid}>
          <Input
            label="Full name"
            name="fullName"
            isRequired
            autoComplete="name"
            errorMessage="Enter the student's full name."
          />
          <Input
            label="Email"
            name="email"
            type="email"
            isRequired
            autoComplete="email"
            errorMessage={(validation) =>
              validation.validationErrors[0] ??
              "Enter a valid email address, e.g. name@example.in."
            }
          />
          <Input
            label="Mobile"
            name="mobile"
            type="tel"
            isRequired
            inputMode="numeric"
            autoComplete="tel-national"
            pattern="[6-9][0-9]{9}"
            description="10-digit Indian mobile number."
            errorMessage={(validation) =>
              validation.validationErrors[0] ??
              "Enter a 10-digit mobile number starting with 6–9."
            }
          />
          <DatePicker
            label="Date of birth"
            name="dateOfBirth"
            isRequired
            maxValue="2010-12-31"
            errorMessage="Enter a date of birth on or before 31/12/2010."
          />
          <Select
            label="Course of interest"
            name="course"
            options={COURSES}
            isRequired
            errorMessage="Choose a course."
          />
          <Combobox
            label="City"
            name="city"
            options={CITIES}
            placeholder="Search city"
          />
        </div>
        <Textarea
          label="Message"
          name="message"
          maxLength={500}
          showCount
          placeholder="Tell us about your sea-career plans"
        />
        <Checkbox
          name="consent"
          value="yes"
          isRequired
          errorMessage="Consent is required to send the enquiry."
        >
          I agree to be contacted about admissions
        </Checkbox>
        <div className="flex flex-col-reverse gap-2 border-t border-border-subtle pt-4 tablet:flex-row tablet:justify-end">
          <Button type="reset" variant="secondary">
            Cancel
          </Button>
          <Button
            variant="ghost"
            onPress={() =>
              setServerErrors({
                email: "This email is already registered for DNS 2026-B.",
                mobile: "This mobile number is linked to another enquiry.",
              })
            }
          >
            Simulate server validation
          </Button>
          <Button type="submit">Submit enquiry</Button>
        </div>
      </Form>
    </Card>
  );
}

export function FormsShowcase() {
  const [joining, setJoining] = useState<string | null>("2026-10-05");
  const [course, setCourse] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);

  return (
    <>
      <Section
        id="inputs"
        title="Input"
        description="Label, description, required, error, success, disabled and read-only states."
      >
        <div className={grid}>
          <Input
            label="Full name"
            placeholder="As printed on the CDC"
            description="Used on certificates."
            isRequired
          />
          <Input label="Home port" icon={AnchorIcon} defaultValue="Mumbai" />
          <Input
            label="Passport number"
            defaultValue="Z1234567"
            isInvalid
            errorMessage="This passport number is already registered."
          />
          <Input
            label="Email"
            type="email"
            defaultValue="arjun.menon@example.in"
            successMessage="Email verified."
          />
          <Input
            label="Institute code"
            defaultValue="MTI-MUM-01"
            isReadOnly
            description="Read-only."
          />
          <Input label="Campus" defaultValue="Mumbai" isDisabled />
        </div>
      </Section>

      <Section
        id="textareas"
        title="Textarea"
        description="Multi-line text with an optional character count."
      >
        <div className={grid}>
          <Textarea
            label="Counselling notes"
            maxLength={300}
            showCount
            defaultValue="Interested in DNS; sea time pending."
          />
          <Textarea
            label="Reason for deferral"
            isInvalid
            errorMessage="Enter a reason of at least 20 characters."
          />
        </div>
      </Section>

      <Section
        id="checkboxes"
        title="Checkbox"
        description="Selected, indeterminate, error and disabled states."
      >
        <div className="flex flex-col gap-2">
          <Checkbox
            defaultSelected
            description="Batch updates are sent on WhatsApp."
          >
            Send WhatsApp updates
          </Checkbox>
          <Checkbox isIndeterminate>Select all cadets in DNS 2026-B</Checkbox>
          <Checkbox
            isInvalid
            errorMessage="Accept the hostel rules to continue."
          >
            I accept the hostel rules
          </Checkbox>
          <Checkbox isDisabled>Scholarship applied (closed)</Checkbox>
        </div>
      </Section>

      <Section
        id="selects"
        title="Select"
        description="Keyboard, type-ahead, disabled options; popover on every screen size."
      >
        <div className={grid}>
          <div className="flex flex-col gap-2">
            <Select
              label="Course"
              options={COURSES}
              value={course}
              onChange={setCourse}
            />
            <output className="text-caption text-text-muted">
              Selected id: {course ?? "none"}
            </output>
          </div>
          <Select
            label="Course (error)"
            options={COURSES}
            isInvalid
            errorMessage="Choose a course."
          />
        </div>
      </Section>

      <Section
        id="comboboxes"
        title="Combobox"
        description="Built-in filtering, or manual (async-ready) filtering with a loading state."
      >
        <div className={grid}>
          <Combobox
            label="City"
            options={CITIES}
            placeholder="Search city"
            description="14 cities; type to filter."
          />
          <AsyncCompanyCombobox />
        </div>
      </Section>

      <Section
        id="date-pickers"
        title="DatePicker"
        description="en-IN (DD/MM/YYYY), ISO values, Monday-first by MTI 360 default; min/max and unavailable dates."
      >
        <div className={grid}>
          <div className="flex flex-col gap-2">
            <DatePicker
              label="Joining date"
              value={joining}
              onChange={setJoining}
            />
            <output id="joining-iso" className="text-caption text-text-muted">
              ISO value: {joining ?? "empty"}
            </output>
          </div>
          <DatePicker
            label="Counselling slot"
            minValue="2026-09-28"
            maxValue="2026-12-31"
            isDateUnavailable={(iso) =>
              new Date(`${iso}T00:00:00`).getDay() === 0
            }
            description="28/09/2026 – 31/12/2026; Sundays unavailable."
          />
          <DatePicker
            label="Sunday-first (explicit override)"
            firstDayOfWeek="sun"
            defaultValue="2026-09-27"
          />
          <DatePicker label="Exam date" defaultValue="2026-11-15" isDisabled />
        </div>
      </Section>

      <Section
        id="file-uploads"
        title="FileUpload"
        description="Client-side checks for UX only — the server validates authoritatively. No previews."
      >
        <div className={grid}>
          <FileUpload
            label="Continuous Discharge Certificate (CDC)"
            accept={DOCUMENTS}
            maxSize={5 * MB}
            isRequired
            value={files}
            onChange={setFiles}
          />
          <FileUpload
            label="Supporting documents"
            accept={DOCUMENTS}
            maxSize={2 * MB}
            maxFiles={3}
            description="Passport, medical fitness certificate, photo."
          />
        </div>
      </Section>

      <Section
        id="enquiry-form"
        title="Student enquiry form"
        description="Two columns from desktop, stacked on mobile (DESIGN-SYSTEM.md §28); actions per §84; simulated server errors."
      >
        <StudentEnquiryForm />
      </Section>
    </>
  );
}
