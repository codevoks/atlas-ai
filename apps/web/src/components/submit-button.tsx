"use client";

import { useFormStatus } from "react-dom";

interface SubmitButtonProps {
  children: React.ReactNode;
  destructive?: boolean;
  disabled?: boolean;
}

export function SubmitButton({ children, destructive = false, disabled = false }: SubmitButtonProps) {
  const { pending } = useFormStatus();
  return (
    <button
      className={destructive ? "button danger" : "button"}
      disabled={pending || disabled}
      type="submit"
    >
      {pending ? "Working…" : children}
    </button>
  );
}
