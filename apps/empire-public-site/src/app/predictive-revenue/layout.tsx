import type { Metadata } from "next";
import type { ReactNode } from "react";

// Exact route metadata. Parent layout's canonical "/" must not be inherited
// by these independently indexable first-party commercial landing pages.
const pageUrl = "https://empire-ai.co.uk/predictive-revenue";
const pageTitle = "Predictive Revenue AI for B2B Pipeline Decisions | Empire AI";
const pageDescription = "Learn how to evaluate B2B opportunity signals, forecast pipeline outcomes and reconcile predictions with verified sales and payments. Request a scoped Empire AI assessment.";

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
