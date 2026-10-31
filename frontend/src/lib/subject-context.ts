/**
 * Helpers for persisting the selected subject across page navigation.
 * Stored in sessionStorage so it survives refreshes but not across browser
 * sessions (matching the token lifecycle).
 */

export const SUBJECT_STORAGE_KEY = "lakshya_selected_subject";

export function getStoredSubjectId(): string | null {
  if (typeof sessionStorage !== "undefined") {
    return sessionStorage.getItem(SUBJECT_STORAGE_KEY);
  }
  return null;
}

export function storeSubjectId(id: string): void {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.setItem(SUBJECT_STORAGE_KEY, id);
  }
}

export function clearStoredSubjectId(): void {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(SUBJECT_STORAGE_KEY);
  }
}

/** Clear the saved active quiz attempt so logout starts fresh. */
export function clearSavedAttempt(): void {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem("lakshya_active_attempt");
  }
}
