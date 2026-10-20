import type { Metadata } from "next";
import "./globals.css";
import "./brand-polish.css";
import SiteChrome from "@/components/SiteChrome";

const publicBaseUrl = "https://empire-ai.co.uk";
const publicDescription =
  "Explore Empire AI’s Predictive Revenue Infrastructure: company intelligence, governed AI workflows, search and content. Discuss capability fit and a scoped engagement.";

const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Empire AI",
  url: publicBaseUrl,
  logo: `${publicBaseUrl}/brand/empire-ai-founder-reference-orbital-a-transparent.webp`,
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
    icon: "/icon.svg?brand=orbital-a-live-20261017-v2",
    shortcut: "/icon.svg?brand=orbital-a-live-20261017-v2",
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
        url: "/art/empire-atrium.webp",
        width: 1672,
        height: 941,
        alt: "Illustration of Empire AI Predictive Revenue Infrastructure",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Empire AI — Predictive Revenue",
    description:
      "Global opportunity intelligence, predictive revenue and governed AI execution.",
    images: ["/art/empire-atrium.webp"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <meta name="empire-flagship-source-fingerprint" content={process.env.EMPIRE_FLAGSHIP_SOURCE_FINGERPRINT ?? "UNATTESTED"} />
        {[400, 500, 700].map(weight => <link key={weight} rel="preload" href={`/fonts/satoshi-${weight}.woff2`} as="font" type="font/woff2" crossOrigin="anonymous" />)}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(organizationSchema),
          }}
        />
      </head>
      <body><SiteChrome>{children}</SiteChrome></body>
    </html>
  );
}
