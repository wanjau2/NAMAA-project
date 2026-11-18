import type { Metadata } from "next";
import {
  IBM_Plex_Sans_Arabic,
  Inter,
  JetBrains_Mono,
  Plus_Jakarta_Sans,
} from "next/font/google";
import "./globals.css";
import { DemoSessionProvider } from "@/lib/demo-session";
import { CaseStoreProvider } from "@/lib/case-store";
import { MainNav } from "@/components/main-nav";
import { SimulationBar } from "@/components/simulation-bar";

/**
 * Fonts are self-hosted by next/font (D002 §6) rather than the @import in
 * globals.css that the theme document originally specified: the import is a
 * render-blocking serial request and causes layout shift, both of which work
 * against the release gate requirement that a fresh browser enters the demo
 * cleanly.
 */

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  weight: ["600", "700"],
  display: "swap",
});

const plexArabic = IBM_Plex_Sans_Arabic({
  variable: "--font-plex-arabic",
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Namaa — Synthetic Demo",
  description:
    "Precision prevention and care-coordination prototype. Synthetic demonstration data only — not for clinical use.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // lang/dir are rendered for the default locale and kept in sync by
    // DemoSessionProvider when the language toggle changes.
    <html
      lang="en"
      dir="ltr"
      className={`${inter.variable} ${jakarta.variable} ${plexArabic.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <DemoSessionProvider>
          <CaseStoreProvider>
            <SimulationBar />
            <MainNav />
            <main className="flex-1">{children}</main>
          </CaseStoreProvider>
        </DemoSessionProvider>
      </body>
    </html>
  );
}
