"use client";

import { useRef, useState } from "react";

import { CheckIcon, CopyIcon } from "@/components/icons";

interface CopyButtonProps {
  /**
   * The text to copy, already computed by the caller. This must be a plain
   * string rather than a getter function: several callers render inside
   * async Server Components, and a closure prop cannot cross the Server ->
   * Client Component boundary (only serializable values and Server Actions
   * can), so a `getText: () => string` prop would throw at render time for
   * those callers.
   */
  text: string;
  label: string;
  copiedLabel?: string;
  variant?: "ghost" | "secondary";
}

type CopyState = "idle" | "copied" | "error";

/** Falls back to a hidden-textarea + execCommand copy when the async
 * Clipboard API is unavailable (non-secure context, older browser, or a
 * browser that denies programmatic clipboard access) instead of failing
 * silently. */
function legacyCopy(text: string): boolean {
  if (typeof document === "undefined") return false;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let succeeded = false;
  try {
    succeeded = document.execCommand("copy");
  } catch {
    succeeded = false;
  }
  document.body.removeChild(textarea);
  return succeeded;
}

export function CopyButton({ text, label, copiedLabel = "Copied", variant = "ghost" }: CopyButtonProps) {
  const [state, setState] = useState<CopyState>("idle");
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function handleCopy() {
    let succeeded = false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        succeeded = true;
      } else {
        succeeded = legacyCopy(text);
      }
    } catch {
      succeeded = legacyCopy(text);
    }
    setState(succeeded ? "copied" : "error");
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setState("idle"), 2000);
  }

  const displayLabel = state === "copied" ? copiedLabel : state === "error" ? "Copy failed" : label;

  return (
    <button
      aria-live="polite"
      className={`button ${variant} small`}
      onClick={handleCopy}
      type="button"
    >
      {state === "copied" ? <CheckIcon /> : <CopyIcon />}
      {displayLabel}
    </button>
  );
}
