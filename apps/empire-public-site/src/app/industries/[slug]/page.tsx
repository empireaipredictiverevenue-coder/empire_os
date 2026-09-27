import type { Metadata } from "next";
import { notFound } from "next/navigation";
import IndustryIntelligencePage from "@/components/IndustryIntelligencePage";
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

  return {
    title: `${page.eyebrow.replace(" INTELLIGENCE", "")} | Empire AI`,
    description: page.subtitle,
    alternates: {
      canonical: `/industries/${page.slug}`,
    },
    openGraph: {
      title: page.title,
      description: page.subtitle,
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
  return <IndustryIntelligencePage page={page} />;
}
