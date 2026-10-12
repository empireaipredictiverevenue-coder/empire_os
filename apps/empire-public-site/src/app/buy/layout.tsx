import type { Metadata } from "next";
import type { ReactNode } from "react";

// Exact route metadata. Parent layout's canonical "/" must not be inherited
// by these independently indexable first-party commercial landing pages.
const pageUrl = "https://empire-ai.co.uk/buy";
const pageTitle = "AI Intelligence Products & Pricing | Empire AI";
const pageDescription = "Explore Empire AI intelligence products and verified catalogue pricing. Ask about competitor search, market signals and revenue opportunities. Payment and orders remain subject to approval.";

export const metadata: Metadata = {
  title: pageTitle,
  description: pageDescription,
  alternates: { canonical: pageUrl },
  openGraph: {
    title: pageTitle,
    description: pageDescription,
    url: pageUrl,
    siteName: "Empire AI",
    type: "website",
    images: [
      { url: "/brand/empire-logo.svg", width: 560, height: 128, alt: "Empire AI" },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: pageTitle,
    description: pageDescription,
    images: ["/brand/empire-logo.svg"],
  },
};

export default function BuyLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}
