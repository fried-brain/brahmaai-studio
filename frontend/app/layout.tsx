import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BrahmaAI Studio — Imagine Beyond Boundaries",
  description: "An intelligent architectural creation studio.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
