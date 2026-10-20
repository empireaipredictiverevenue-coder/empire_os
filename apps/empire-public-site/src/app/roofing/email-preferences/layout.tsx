import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Homeowner Email Preferences | Empire AI",
  description: "Manage an optional Empire AI homeowner email subscription.",
  robots: { index: false, follow: false },
};

export default function PreferenceLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return children;
}
