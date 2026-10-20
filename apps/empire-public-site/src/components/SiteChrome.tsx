"use client";
import BrandLockup from "./BrandLockup";
import { usePathname } from "next/navigation";
import { useState, useRef, useEffect } from "react";
const headerLinks = [
  ["/predictive-revenue", "Predictive Revenue"],
  ["/buy", "Intelligence"],
  ["/industries", "Industries"],
  ["/about", "About"],
] as const;
const footerExploreLinks = [
  ["/#capabilities", "Capabilities"],
  ...headerLinks.slice(0, 3),
  ["/insights/revenue-opportunity-assessment", "ROI assessment"],
] as const;
const footerCompanyLinks = [
  ["/about", "About"],
  ["/trust", "Trust"],
  ["https://empire-ai.co.uk/privacy", "Privacy"],
  ["https://empire-ai.co.uk/terms", "Terms"],
  ["/commercial", "Request a proposal"],
] as const;
export default function SiteChrome({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); toggle.current?.focus(); } };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);
  if (path === "/roofing" || path === "/uk/roofing") return <>{children}</>;
  return <>
    <a className="skip-link" href="#site-content">Skip to content</a>
    <header className={path === "/" ? "site-header immersive-header" : "site-header"} onKeyDown={e => { if (e.key === "Escape") { setOpen(false); toggle.current?.focus(); } }}>
      <a href="/" aria-label="Empire AI home" className="site-brand"><BrandLockup /></a>
      <button ref={toggle} className="menu-toggle" aria-expanded={open} aria-controls="site-nav" onClick={() => setOpen(!open)}>{open ? "Close" : "Menu"}</button>
      <nav id="site-nav" aria-label="Main navigation" className={open ? "site-nav is-open" : "site-nav"}>
        {headerLinks.map(([href, label]) => <a key={href} href={href} aria-current={path === href || path.startsWith(href + "/") ? "page" : undefined} onClick={() => setOpen(false)}>{label}</a>)}
      </nav>
      <a href="/commercial" className="site-proposal" aria-current={path === "/commercial" ? "page" : undefined} onClick={() => setOpen(false)}>Discuss your business <span aria-hidden="true">↗</span></a>
    </header>
    <div id="site-content" tabIndex={-1}>{children}</div>
    <footer className="site-footer">
      <div className="site-footer-brand">
        <BrandLockup />
        <p>Predictive Revenue Infrastructure.<br />Company intelligence. Governed AI. Measured outcomes.</p>
      </div>
      <nav className="site-footer-links" aria-label="Explore Empire AI">
        <h2>Explore</h2>
        {footerExploreLinks.map(([href, label]) => <a key={href} href={href}>{label}</a>)}
      </nav>
      <nav className="site-footer-links" aria-label="Company and legal">
        <h2>Company</h2>
        {footerCompanyLinks.map(([href, label]) => <a key={href} href={href}>{label}</a>)}
      </nav>
      <p className="footer-note">© {new Date().getFullYear()} Empire AI. Proposals are non-binding. Scope, delivery and terms are agreed before a commercial commitment.</p>
    </footer>
  </>;
}
