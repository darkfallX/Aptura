import type { Metadata } from "next";
import "./globals.css";
import "./paper.css";
import { InkFilter } from "@/components/paper/Paper";

export const metadata: Metadata = {
  title: "Aptura — make your trading bot show receipts",
  description:
    "Before your trading bot rewrites its own rules, Aptura tests the change on past data, gets a Reppo review, and blocks what doesn't hold up. Paper trading only.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body><InkFilter />{children}</body>
    </html>
  );
}
