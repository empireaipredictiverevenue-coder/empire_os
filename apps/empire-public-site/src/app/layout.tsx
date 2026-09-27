import type { Metadata } from "next";
import "./globals.css";

const publicBaseUrl = "https://empire-ai.co.uk";
const publicDescription =
  "Empire AI discovers global opportunity, predicts economics and turns verified commercial signals into revenue.";

const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Empire AI",
  url: publicBaseUrl,
  logo: `${publicBaseUrl}/brand/empire-logo.svg`,
  description: publicDescription,
};

export const metadata: Metadata = {
  title: "Empire AI — Predictive Revenue",
  description: publicDescription,
  metadataBase: new URL(publicBaseUrl),
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
  },
  openGraph: {
    title: "Empire AI — Predictive Revenue",
    description:
      "Global opportunity intelligence, predictive revenue and governed AI execution.",
    url: publicBaseUrl,
    siteName: "Empire AI",
    type: "website",
    images: [
      {
        url: "/brand/empire-logo.svg",
        width: 560,
        height: 128,
        alt: "Empire AI Predictive Revenue",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Empire AI — Predictive Revenue",
    description:
      "Global opportunity intelligence, predictive revenue and governed AI execution.",
    images: ["/brand/empire-logo.svg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(organizationSchema),
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
