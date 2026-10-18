"use client";

import type { AnchorHTMLAttributes } from "react";
import { useEffect, useState } from "react";
import { linkedCommercialHref } from "@/lib/organic-campaign-touch";

type Props = AnchorHTMLAttributes<HTMLAnchorElement>;

/** SSR stays usable; hydration enriches only the current owned-page link. */
export default function OrganicCommercialLink({ children, ...props }: Props) {
  const [href, setHref] = useState("/commercial");
  useEffect(() => {
    setHref(linkedCommercialHref(window.location.search, window.location.pathname));
  }, []);
  return <a {...props} href={href}>{children}</a>;
}
