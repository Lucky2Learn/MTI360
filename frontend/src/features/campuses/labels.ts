// Tenant Campuses copy and helpers (02-C; ADMIN-03/04 over the T01-08 API).
// Display only: the API authorizes every read and change again, and lists
// only the caller's own campuses (D-B1). Client checks mirror the API's
// rules (backend institute/service.py); the API validates again.

export const CAMPUSES_PATH = "/app/administration/campuses";
export const campusPath = (id: string) => `${CAMPUSES_PATH}/${id}`;

export const CAMPUS_CREATE = "campus.create";
export const CAMPUS_UPDATE = "campus.update";

export const NAME_MAX = 200;
export const CODE_MAX = 32;
const CODE_FORMAT = /^[A-Z0-9][A-Z0-9-]*$/;

export const NAME_MESSAGE = "Enter a campus name of up to 200 characters.";
export const CODE_MESSAGE =
  "Use up to 32 letters, digits or hyphens, starting with a letter or digit.";
export const CODE_TAKEN = "Another campus already uses this code.";

/** The code as the API stores it: trimmed and uppercase. */
export const normalizeCode = (code: string) => code.trim().toUpperCase();

export function nameError(name: string): string | undefined {
  const cleaned = name.split(/\s+/).filter(Boolean).join(" ");
  return !cleaned || cleaned.length > NAME_MAX ? NAME_MESSAGE : undefined;
}

export function codeError(code: string): string | undefined {
  const cleaned = normalizeCode(code);
  return cleaned.length > CODE_MAX || !CODE_FORMAT.test(cleaned)
    ? CODE_MESSAGE
    : undefined;
}
