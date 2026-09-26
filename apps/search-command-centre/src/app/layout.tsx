import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Empire AI · Search Command Centre",
  description: "Governed organic revenue intelligence for Empire AI.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
