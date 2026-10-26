import type { Metadata } from "next";
import { notFound } from "next/navigation";
import IndustryIntelligencePage from "@/components/IndustryIntelligencePage";
import SolarIntelligenceExperience from "@/components/SolarIntelligenceExperience";
import { getIndustryPage, industryPages } from "@/lib/industry-pages";

export function generateStaticParams() {
  return industryPages.map((page) => ({ slug: page.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const page = getIndustryPage(slug);
  if (!page) return {};

  // Concise search-result wording should reflect the live, original B2B
  // buyer education rather than repeating a generic industry label.
  // This metadata is informational, NOT a claim of payable lead inventory.
  const buyerMetadata: Record<string, { title: string; description: string }> = {
    roofing: {
      title: "Roofing Demand & Call Qualification | Empire AI",
      description:
        "Explore roofing demand, eligible service areas, first-party enquiry quality and how buyers define payable calls. Evidence-first commercial intelligence.",
    },
    solar: {
      title: "Solar Market Intelligence & Installer Demand | Empire AI",
      description:
        "Explore solar market intelligence: territory demand, property and permit signals, installer coverage and buyer qualification for evidence-led commercial decisions.",
    },
  };
  const searchCopy = buyerMetadata[page.slug];
  const seoTitle = searchCopy?.title ?? `${page.eyebrow.replace(" INTELLIGENCE", "")} | Empire AI`;
  const seoDescription = searchCopy?.description ?? page.subtitle;

  return {
    title: seoTitle,
    description: seoDescription,
    alternates: {
      canonical: `/industries/${page.slug}`,
    },
    openGraph: {
      title: searchCopy?.title ?? page.title,
      description: searchCopy?.description ?? page.subtitle,
      url: `https://empire-ai.co.uk/industries/${page.slug}`,
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
  };
}

export default async function IndustryPageRoute({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const page = getIndustryPage(slug);
  if (!page) notFound();
  if (page.slug === "solar") return <SolarIntelligenceExperience page={page} />;
  return <IndustryIntelligencePage page={page} />;
}
