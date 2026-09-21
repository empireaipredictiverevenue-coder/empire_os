import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Empire AI — Predictive Revenue",
  description:
    "Empire AI discovers global opportunity, predicts economics and turns verified commercial signals into revenue.",
  metadataBase: new URL("https://empire-ai.co.uk"),
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
  },
  openGraph: {
    title: "Empire AI — Predictive Revenue",
    description:
      "Global opportunity intelligence, predictive revenue and governed AI execution.",
    url: "https://empire-ai.co.uk",
    siteName: "Empire AI",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
