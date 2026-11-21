"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  Select,
  Textarea,
} from "@/design-system/components";
import { ApiError, NetworkError } from "@/lib/api/errors";
import {
  ENQUIRY_LIMITS,
  submitEnquiry,
  type EnquiryFormWire,
} from "@/lib/api/public-enquiry";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";

// Hosted enquiry page form (Phase 02-4, ADR-0024; template T18). Minimal
// personal data: a name, an email or a phone number, optionally a course and a
// message. Consent is mandatory and versioned: the version shown is the one
// sent, and a changed text is refused by the API (the page asks for a reload).
// The spam trap (`website`) is visually hidden (sr-only) inside an
// aria-hidden wrapper, so assistive technology ignores it, and not focusable; people never fill it in. Every accepted enquiry gets the
// same confirmation: the page never says whether the person is already known.
// Server messages are never shown; codes map to this page's own copy.

type Errors = Partial<
  Record<
    "full_name" | "email" | "mobile" | "course_id" | "message" | "consent",
    string
  >
>;

type Feedback = { tone: "error" | "warning"; title: string; body?: string };

const NOT_SURE = "not-sure";
const EMAIL_FORMAT = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_FORMAT = /^[0-9+\-() ]{6,32}$/;

const FIELD_COPY: Record<string, Record<string, string>> = {
  full_name: { default: "Enter your name." },
  email: {
    contact_required: "Enter an email address or a phone number.",
    default: "Enter a valid email address.",
  },
  mobile: { default: "Enter a valid phone number." },
  course_id: { default: "Choose a course from the list." },
  message: {
    default: `Keep the message under ${ENQUIRY_LIMITS.message} characters.`,
  },
  consent_accepted: { default: "Agree to the consent to send your enquiry." },
};

function copyFor(field: string, code: string): string {
  const copy = FIELD_COPY[field];
  return copy?.[code] ?? copy?.default ?? "Check this field.";
}

function validate(values: {
  name: string;
  email: string;
  mobile: string;
  message: string;
  consent: boolean;
}): Errors {
  const errors: Errors = {};
  if (!values.name.trim()) errors.full_name = "Enter your name.";
  const email = values.email.trim();
  const mobile = values.mobile.trim();
  if (!email && !mobile) {
    errors.email = "Enter an email address or a phone number.";
  } else {
    if (email && !EMAIL_FORMAT.test(email))
      errors.email = "Enter a valid email address.";
    const digits = mobile.replace(/\D/g, "").length;
    if (mobile && (!PHONE_FORMAT.test(mobile) || digits < 6 || digits > 15)) {
      errors.mobile = "Enter a valid phone number.";
    }
  }
  if (values.message.length > ENQUIRY_LIMITS.message) {
    errors.message = `Keep the message under ${ENQUIRY_LIMITS.message} characters.`;
  }
  if (!values.consent)
    errors.consent = "Agree to the consent to send your enquiry.";
  return errors;
}

function minutes(seconds: number | null): string {
  const count = Math.max(1, Math.ceil((seconds ?? 60) / 60));
  return count === 1 ? "a minute" : `${count} minutes`;
}

export function EnquiryForm({ form }: { form: EnquiryFormWire }) {
  const wrapper = useRef<HTMLDivElement>(null);
  const confirmation = useRef<HTMLDivElement>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [course, setCourse] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [trap, setTrap] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (sent) confirmation.current?.focus();
  }, [sent]);

  const options = [
    ...form.courses.map((item) => ({ id: item.id, label: item.name })),
    { id: NOT_SURE, label: "Not sure yet" },
  ];

  const reset = () => {
    setName("");
    setEmail("");
    setMobile("");
    setCourse(null);
    setMessage("");
    setConsent(false);
    setErrors({});
    setFeedback(null);
    setSent(false);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setFeedback(null);
    const found = validate({ name, email, mobile, message, consent });
    setErrors(found);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(wrapper.current);
      return;
    }
    setPending(true);
    try {
      await submitEnquiry({
        full_name: name.trim(),
        email: email.trim() || null,
        mobile: mobile.trim() || null,
        course_id: course && course !== NOT_SURE ? course : null,
        message: message.trim() || null,
        consent_accepted: consent,
        consent_version: form.consent.version,
        website: trap,
      });
      setSent(true);
    } catch (error) {
      const codes = fieldCodes(error);
      if (codes.consent_version) {
        setFeedback({
          tone: "warning",
          title: "The consent text has changed",
          body: "Reload the page to read the current text, then send your enquiry again.",
        });
      } else if (Object.keys(codes).length > 0) {
        const next: Errors = {};
        for (const [field, code] of Object.entries(codes)) {
          const key = field === "consent_accepted" ? "consent" : field;
          if (key in FIELD_COPY || key === "consent") {
            next[key as keyof Errors] = copyFor(field, code);
          }
        }
        setErrors(next);
        focusFirstInvalid(wrapper.current);
      } else if (error instanceof ApiError && error.status === 429) {
        setFeedback({
          tone: "warning",
          title: "Too many enquiries",
          body: `Please wait ${minutes(error.retryAfter)} and try again.`,
        });
      } else if (error instanceof ApiError && error.status === 404) {
        setFeedback({
          tone: "error",
          title: "This enquiry page is not available",
          body: "Contact the institute directly.",
        });
      } else if (error instanceof NetworkError) {
        setFeedback({
          tone: "error",
          title: "Your enquiry wasn't sent",
          body: "Check your connection and try again.",
        });
      } else {
        setFeedback({
          tone: "error",
          title: "Your enquiry wasn't sent",
          body: "Something went wrong on our side. Please try again in a few minutes.",
        });
      }
    } finally {
      setPending(false);
    }
  };

  if (sent) {
    return (
      <div
        ref={confirmation}
        tabIndex={-1}
        // a11y-focus: replaced content; receives programmatic focus only
        className="flex flex-col gap-4 outline-none"
      >
        <Alert tone="success" title="Thank you, we've received your enquiry">
          {form.institute_name} will contact you soon.
          {email.trim() ? " We've also sent a confirmation to your email." : ""}
        </Alert>
        <div>
          <Button variant="secondary" onPress={reset}>
            Send another enquiry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div ref={wrapper}>
      <Form
        aria-label={`Enquiry to ${form.institute_name}`}
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <p className="text-caption text-text-secondary">
          <span aria-hidden="true" className="text-error-text">
            *
          </span>{" "}
          Required field. Give an email address or a phone number, or both.
        </p>
        <Input
          label="Full name"
          name="full_name"
          autoComplete="name"
          maxLength={ENQUIRY_LIMITS.name}
          isRequired
          value={name}
          onChange={setName}
          isInvalid={Boolean(errors.full_name)}
          errorMessage={errors.full_name}
        />
        <div className="grid gap-4 tablet:grid-cols-2">
          <Input
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            autoCapitalize="none"
            spellCheck="false"
            maxLength={ENQUIRY_LIMITS.email}
            value={email}
            onChange={setEmail}
            isInvalid={Boolean(errors.email)}
            errorMessage={errors.email}
          />
          <Input
            label="Phone"
            name="mobile"
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            maxLength={ENQUIRY_LIMITS.mobile}
            value={mobile}
            onChange={setMobile}
            isInvalid={Boolean(errors.mobile)}
            errorMessage={errors.mobile}
          />
        </div>
        <Select
          label="Course"
          options={options}
          value={course}
          onChange={setCourse}
          placeholder="Choose a course"
          isInvalid={Boolean(errors.course_id)}
          errorMessage={errors.course_id}
        />
        <Textarea
          label="Message"
          name="message"
          rows={4}
          maxLength={ENQUIRY_LIMITS.message}
          showCount
          description="Optional. For example, the batch you are interested in or your questions."
          value={message}
          onChange={setMessage}
          isInvalid={Boolean(errors.message)}
          errorMessage={errors.message}
        />
        <div aria-hidden="true" className="sr-only">
          <label>
            Website (leave empty)
            <input
              type="text"
              name="website"
              tabIndex={-1}
              autoComplete="off"
              value={trap}
              onChange={(event) => setTrap(event.target.value)}
            />
          </label>
        </div>
        <Checkbox
          isSelected={consent}
          onChange={setConsent}
          isRequired
          isInvalid={Boolean(errors.consent)}
          errorMessage={errors.consent}
        >
          {form.consent.text}
        </Checkbox>
        <p className="text-caption text-text-secondary">
          {form.privacy_notice}
        </p>
        <Button type="submit" size="lg" isPending={pending}>
          {pending ? "Sending…" : "Send enquiry"}
        </Button>
      </Form>
    </div>
  );
}
