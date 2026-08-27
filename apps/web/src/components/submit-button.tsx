"use client";

import { useFormStatus } from "react-dom";

interface SubmitButtonProps {
  children: React.ReactNode;
  destructive?: boolean;
}

export function SubmitButton({ children, destructive = false }: SubmitButtonProps) {
  const { pending } = useFormStatus();
  return (
    <button className={destructive ? "button danger" : "button"} disabled={pending} type="submit">
      {pending ? "Working…" : children}
    </button>
  );
}

