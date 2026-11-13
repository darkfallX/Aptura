import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aptura — Adaptive AI Strategy Supervisor | Historical Replay Lab",
  description:
    "Markets change. Your strategies should too. Aptura supervises algorithmic trading strategies on historical Solana pool data, detects regime deterioration, validates adaptations causally, and audits reasoning with OpenServ SERV and Reppo.",
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
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
