import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";

import { authMode } from "@/lib/config";

import "./globals.css";

export const metadata: Metadata = {
  title: "Atlas AI",
  description: "Secure enterprise knowledge and grounded research.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const document = (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
  return authMode === "oidc" ? <ClerkProvider>{document}</ClerkProvider> : document;
}
