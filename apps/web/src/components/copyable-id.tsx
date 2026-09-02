"use client";

import { useState } from "react";

import { CheckIcon, CopyIcon } from "@/components/icons";

interface CopyableIdProps {
  value: string;
  label?: string;
}

export function CopyableId({ value, label }: CopyableIdProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard access denied — the id remains selectable as plain text.
    }
  }

  return (
    <button
      className={`id-chip${copied ? " copied" : ""}`}
      onClick={handleCopy}
      title="Copy to clipboard"
      type="button"
    >
      {label ? `${label} ` : ""}
      {value}
      {copied ? <CheckIcon /> : <CopyIcon />}
    </button>
  );
}
