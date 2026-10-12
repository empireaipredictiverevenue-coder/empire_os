import type { Metadata } from "next";
import type { ReactNode } from "react";

// Exact route metadata. Parent layout's canonical "/" must not be inherited
// by these independently indexable first-party commercial landing pages.
const pageUrl = "https://empire-ai.co.uk/commercial";
const pageTitle = "AI Consultancy & Revenue Intelligence | Empire AI";
const pageDescription = "Explore founder-led AI consultancy, competitor search intelligence, digital workforce and predictive revenue solutions. Request a scoped business enquiry; no payment required.";

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
