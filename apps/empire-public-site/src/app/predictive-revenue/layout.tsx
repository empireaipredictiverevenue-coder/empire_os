import type { Metadata } from "next";
import type { ReactNode } from "react";

// Exact route metadata. Parent layout's canonical "/" must not be inherited
// by these independently indexable first-party commercial landing pages.
const pageUrl = "https://empire-ai.co.uk/predictive-revenue";
const pageTitle = "Predictive Revenue AI Solutions for Business | Empire AI";
const pageDescription = "Explore Empire AI predictive revenue, governed AI operations and enterprise deployment options. Review business outcomes and request a founder-led discussion.";

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

export default function PredictiveRevenueLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}
