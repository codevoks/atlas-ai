import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, Inter } from "next/font/google";

import { authMode } from "@/lib/config";

import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const serif = Fraunces({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
  axes: ["opsz", "SOFT", "WONK"],
  style: ["normal", "italic"],
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Atlas AI",
  description: "A calm, evidence-grounded workspace for enterprise knowledge and research.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const document = (
    <html className={`${sans.variable} ${serif.variable} ${mono.variable}`} lang="en">
      <body>{children}</body>
    </html>
  );
  return authMode === "oidc" ? <ClerkProvider>{document}</ClerkProvider> : document;
}
