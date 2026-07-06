import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LangOps",
  description: "Observability for LangGraph applications",
};

// Phase 5 (tasks.md): app shell — sidebar, topbar, TanStack Query provider.
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        {children}
      </body>
    </html>
  );
}
