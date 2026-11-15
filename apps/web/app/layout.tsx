import type { Metadata } from "next";
import "./globals.css";
import "./app.css";
import "./layout.css";

export const metadata: Metadata = {
  title: "Aptura · Supervision for self-tuning trading bots",
  description:
    "Before your trading bot rewrites its own rules, Aptura tests the change on past data, gets a Reppo review, and blocks what doesn't hold up. Paper trading only.",
};

const themeInit = `try{var t=localStorage.getItem('aptura-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
