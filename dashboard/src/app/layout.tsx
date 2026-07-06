import type { Metadata } from "next";

import { Sidebar } from "@/components/layout/sidebar";
import { LiveUpdates } from "@/components/layout/live-updates";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "LangOps",
  description: "Observability for LangGraph applications",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        <Providers>
          <LiveUpdates />
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-x-hidden p-8">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
