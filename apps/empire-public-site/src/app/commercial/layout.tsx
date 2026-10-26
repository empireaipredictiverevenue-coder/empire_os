import type { Metadata } from "next";
import type { ReactNode } from "react";

// Exact first-party commercial page. TAM buyer-readiness explanation, real
// assessment scope, no promise of indexed rankings, closed deals or payment.
const pageUrl = "https://empire-ai.co.uk/commercial";
const pageTitle = "Buyer Readiness & Revenue Intelligence | Empire AI";
const pageDescription = "Learn how to evaluate buyer readiness across your total addressable market, trace revenue leaks and request a scoped Empire AI business assessment. No payment required.";

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

export default function CommercialLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}
