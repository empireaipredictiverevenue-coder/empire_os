"""Original decorative skyline backdrop for the privately staged Chicago research page.

No photography, external asset fetch, user-tracking or live website dependency.
Not evidence of roofing market activity, Chicago permit jurisdiction or demand.
"""
from __future__ import annotations
from base64 import b64encode
from hashlib import sha256
from pathlib import Path
import os

CHICAGO_PHOTO_SHA256 = "e7b587241803e033576f5fc6f8df5c81993ec89b37b0644699ac7215e2ed8a24"
CHICAGO_PHOTO_CREDIT_URL = "https://unsplash.com/photos/a-river-running-through-a-city-at-night-IRMWK1Hv0_8"
CHICAGO_PHOTO_LICENSE_URL = "https://unsplash.com/license"

CHICAGO_WORKER_PHOTO_SHA256 = "b7fa5187e2bb329dd31308533a795dbb0dfcf1b52fcaf0aae94934c62ff05a2d"
CHICAGO_WORKER_PHOTO_SOURCE = "https://unsplash.com/photos/a-man-standing-on-the-roof-of-a-house--1l0iZaM8ms"
CHICAGO_4K_PHOTO_SHA256 = "94ab7dd8ef0b83a0ff6f3089a7a913ad723c1a0f541062e8d9e7a16d556c4f10"


def _source_photo(name: str, digest: str, limit: int) -> str | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    p = Path(raw)
    if not p.is_file() or p.is_symlink():
        raise ValueError(f"{name}: owner-staged regular file required")
    data = p.read_bytes()
    if not 20_000 <= len(data) <= limit or data[:4] != b"RIFF" or data[8:12] != b"WEBP" or sha256(data).hexdigest() != digest:
        raise ValueError(f"{name}: exact source digest/format required")
    return "data:image/webp;base64," + b64encode(data).decode("ascii")


def chicago_worker_research_photo_data_uri() -> str | None:
    """Unaltered-source licensed illustrative Texas worksite; never claim Chicago."""
    return _source_photo("EMPIRE_MICROSITE_CHICAGO_RESEARCH_WORKER_PHOTO", CHICAGO_WORKER_PHOTO_SHA256, 135000)


def chicago_4k_photo_asset_validated() -> bool:
    """Read-only proof for an existing staged 3840x2160 brand hero asset."""
    return _source_photo("EMPIRE_MICROSITE_CHICAGO_NATIVE_4K_PHOTO", CHICAGO_4K_PHOTO_SHA256, 2000000) is not None




def chicago_owner_photo_data_uri() -> str | None:
    """One private, licensed original-source photograph; no network at render time.

    The first-party release owner must make its own asset/credit decision.
    No repo-scoped photo file or unchecked CDN URL is silently published.
    """
    path = os.getenv("EMPIRE_MICROSITE_CHICAGO_HERO_PHOTO")
    if not path:
        return None
    item = Path(path)
    if item.is_symlink() or not item.is_file():
        raise ValueError("Chicago photo must be owner-staged regular file")
    data = item.read_bytes()
    if (not 10_000 <= len(data) <= 700_000
            or data[:4] != b"RIFF" or data[8:12] != b"WEBP"
            or sha256(data).hexdigest() != CHICAGO_PHOTO_SHA256):
        raise ValueError("Chicago photo source rights/hash validation failed")
    return "data:image/webp;base64," + b64encode(data).decode("ascii")


def chicago_night_skyline_data_uri() -> str:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 720" role="presentation">
<defs>
  <linearGradient id="sky" x1="0" y1="0" x2=".7" y2="1">
    <stop stop-color="#01122b"/><stop offset=".42" stop-color="#06317a"/>
    <stop offset=".73" stop-color="#04204a"/><stop offset="1" stop-color="#01091c"/>
  </linearGradient>
  <radialGradient id="light" cx=".7" cy=".22" r=".67">
    <stop stop-color="#0869de" stop-opacity=".83"/>
    <stop offset=".56" stop-color="#0759bd" stop-opacity=".22"/>
    <stop offset="1" stop-color="#01091c" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="tower" x1="0" y1="0" x2="1" y2="0">
    <stop stop-color="#031328"/><stop offset=".5" stop-color="#112d4e"/>
    <stop offset="1" stop-color="#021023"/>
  </linearGradient>
  <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
    <stop stop-color="#034b89" stop-opacity=".75"/>
    <stop offset=".3" stop-color="#031e4a" stop-opacity=".55"/>
    <stop offset="1" stop-color="#01091c" stop-opacity="0"/>
  </linearGradient>
  <pattern id="windows" width="17" height="23" patternUnits="userSpaceOnUse">
    <path d="M5 7h3v9H5z" fill="#2c98dd" opacity=".65"/>
    <path d="M12 7h2v5h-2z" fill="#dc9d51" opacity=".63"/>
  </pattern>
  <filter id="glow"><feGaussianBlur stdDeviation="11"/></filter>
</defs>
<rect width="1440" height="720" fill="url(#sky)"/>
<rect width="1440" height="720" fill="url(#light)"/>
<g fill="none" stroke="#13bfff" opacity=".22"><circle cx="1106" cy="-20" r="450"/><circle cx="1110" cy="-20" r="457" stroke-width=".4"/></g>
<g transform="translate(0 40)">
<path d="M490 470V360h40v-48h78v45h55v113zm155 0V318h52v-92h88v244zm120 0V350h54v-76h61v196zm95 0V258h58V92h30v-55h5v55h9v166h62v212zm163 0V320h55v-92h62v242zm130 0V354h54v-51h75v167zm130 0V365h42v-135h54v240z" fill="#021127" stroke="#15508a" stroke-width="2"/>
<path d="M490 470V360h40v-48h78v45h55v113zm155 0V318h52v-92h88v244zm120 0V350h54v-76h61v196zm95 0V258h58V92h30v-55h5v55h9v166h62v212zm163 0V320h55v-92h62v242zm130 0V354h54v-51h75v167zm130 0V365h42v-135h54v240z" fill="url(#windows)" opacity=".86"/>
<path d="M915 260V89h30V40h5v52h9v168" fill="url(#tower)"/>
<g fill="none" stroke="#06aaf9" opacity=".48" stroke-width="2"><path d="M955 40V-16M944 40v-55"/><path d="M920 240v70m98 0V240"/></g>
<g fill="#89ccf4" opacity=".53"><rect x="906" y="274" width="45" height="2"/><rect x="682" y="319" width="81" height="2"/></g>
<path d="M450 471h940" stroke="#07c7fe" opacity=".8"/>
<path d="M460 476h980v210H460z" fill="url(#water)"/>
<g filter="url(#glow)" stroke="#17aafd" opacity=".62">
  <path d="M820 494h140m-92 26h184m-145 21h140m-174 46h80m-100 26h110M650 505h90m-40 34h115m-97 38h110"/>
</g>
<g fill="#83ccfa" opacity=".42">
<rect x="861" y="490" width="67" height="2"/><rect x="902" y="516" width="94" height="1"/>
<rect x="836" y="561" width="128" height="1"/><rect x="775" y="602" width="69" height="1"/>
</g>
</g>
<rect width="1440" height="720" fill="#01091c" opacity=".08"/>
</svg>"""
    return "data:image/svg+xml;base64," + b64encode(svg.encode("utf-8")).decode("ascii")


def chicago_premium_css() -> str:
    """Self-contained private-page styling, no external fonts or JS."""
    return """
/* Cinematic Chicago pilot: original vector scene, canonical palette, no external assets */
body {overflow-x:clip;background:var(--brand-navy,#01091c)}
body::before {opacity:.37;height:1050px;z-index:0}
.site-art {position:absolute;z-index:0;inset:0 0 auto;height:775px;pointer-events:none;
  background-position:center 23%;background-size:cover;background-repeat:no-repeat;opacity:.98}
.site-art::after {content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,#01091cf4 0%,#01091cd4 24%,#01091c55 58%,#01091c55 100%),
  linear-gradient(0deg,#01091c 1%,transparent 32%),
  radial-gradient(ellipse at 63% 11%,#005aff2e,transparent 70%)}
header,main,footer {z-index:1}
.wrap {max-width:1320px;padding-inline:clamp(20px,4.6vw,58px)}
nav {min-height:96px}
.preview {border-color:#4e7abb;color:#d3e8f9;background:#071b3a9c;
  font-size:.72rem;backdrop-filter:blur(10px)}
.hero {max-width:unset;min-height:615px;padding-top:82px;padding-bottom:86px}
.hero-layout {grid-template-columns:minmax(0,1.32fr) minmax(270px,.78fr);gap:clamp(24px,4vw,70px)}
.hero-content {max-width:760px}
h1 {font-size:clamp(2.9rem,5.3vw,5.35rem);letter-spacing:-.054em;max-width:810px}
.hero-title-base {display:block;color:#f4f9ff}
.hero-title-accent {display:block;color:#02c7fe;
  background:linear-gradient(125deg,#8bdfff 0%,#02c7fe 65%,#338cff 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.lede {color:#e9f4ff;font-size:clamp(1.08rem,1.65vw,1.32rem);max-width:660px}
.desc {color:#a4b8d2;font-size:.95rem;max-width:610px}
.action {background:linear-gradient(120deg,#02c7fe,#86e3ff);box-shadow:0 0 27px #02c7fe42;
  border:1px solid #88e4ff;color:#021126;min-height:50px;padding:12px 22px}
.action:hover {box-shadow:0 0 33px #02c7fe7a;filter:brightness(1.06)}
.signal-panel {backdrop-filter:blur(22px);border:1px solid #198ee8;
  background:linear-gradient(145deg,#09244de6,#071936dc 70%,#041128e4);
  box-shadow:0 0 32px #005aff3e,inset 0 1px #73caff2c,0 26px 70px #0007;
  padding:27px;border-radius:19px;align-self:center}
.signal-head {font-size:.69rem;color:#05d2fc}
.signal-value {font-size:1.025rem;color:#ebf6ff}
.signal-rule {border-top-color:#2b4c77}
main>.wrap:not(:first-child) {position:relative}
main>.wrap:not(:first-child)::before {content:"";position:absolute;pointer-events:none;
  inset:0 0 auto;height:1px;background:linear-gradient(90deg,transparent,#02c7fe50,transparent)}
section {padding-block:52px}
.tag,.micro {color:#38ceff}
h2 {font-size:clamp(1.75rem,2.6vw,2.7rem);letter-spacing:-.035em}
.grid {grid-template-columns:repeat(5,minmax(0,1fr));gap:13px}
.fact {min-width:0;min-height:340px;padding:20px;border:1px solid #166eb0;border-radius:17px;
  background:linear-gradient(148deg,#0d2750dc,#08172ee5);
  box-shadow:inset 0 1px #68baff1f,0 15px 40px #0003;backdrop-filter:blur(8px);
  display:flex;flex-direction:column}
.fact .micro {font-size:.65rem;letter-spacing:.12em}
.fact .micro:before {content:"◈";display:block;width:47px;height:45px;
  margin-bottom:18px;border:1px solid #058bda;border-radius:13px;
  padding:8px;text-align:center;line-height:26px;font-size:24px;color:#03c7fa;
  background:linear-gradient(145deg,#093d76,#041c3d)}
.fact p {font-size:.93rem;line-height:1.55}
.fact .source {margin-top:auto;padding-top:17px;border-top:1px solid #26456d;
  color:#91aacb;font-size:.73rem!important}
.official-link {font-size:.87rem;color:#48d3ff;text-decoration-color:#48d3ff;text-decoration-thickness:1px}
.decision-list {list-style:none;padding-left:0;max-width:unset;
  display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:13px;counter-reset:step}
.decision-list li {margin:0;min-width:0;position:relative;padding:68px 19px 24px;
  border:1px solid #1469b0;background:linear-gradient(150deg,#0e2b57d8,#06152be6);
  border-radius:17px;box-shadow:inset 0 1px #8de2ff15}
.decision-list li::before {content:counter(step);counter-increment:step;
  position:absolute;left:19px;top:17px;min-width:31px;height:31px;line-height:29px;
  border:1px solid #02c7fe;border-radius:50%;font-weight:800;
  text-align:center;color:#02c7fe;background:#063058}
.decision-list li::marker {content:""}
.hint {border:1px solid #c88e39;border-radius:14px;
  background:linear-gradient(100deg,#28212bd9,#0a1b38cc);
  box-shadow:0 0 19px #f8a72b2b;max-width:100%}
footer {border-top:1px solid #164c83;background:linear-gradient(180deg,transparent,#071c38)}
@media(max-width:1150px) {
  .grid {grid-template-columns:repeat(3,minmax(0,1fr))}
  .decision-list {grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media(max-width:760px) {
  .site-art {height:630px;background-position:64% 15%;opacity:.65}
  .site-art::after {background:linear-gradient(90deg,#01091cdd,#01091c94),
    linear-gradient(0deg,#01091c 0%,transparent 55%)}
  nav {min-height:79px}
  .hero-layout {grid-template-columns:1fr}
  .hero {padding:45px 0 43px;min-height:0}
  .hero-content {max-width:100%}
  h1 {font-size:clamp(2.55rem,8.5vw,4.5rem)}
  .signal-panel {width:100%;max-width:600px;margin-top:10px}
  .grid,.decision-list {grid-template-columns:repeat(2,minmax(0,1fr))}
  .fact {min-height:290px}
}
@media(max-width:540px) {
  .wrap {padding-inline:20px}
  nav {align-items:flex-start;gap:9px;flex-direction:column;justify-content:center;padding:17px 0}
  .wordmark {width:174px}
  .hero {padding:44px 0 37px}
  .grid,.decision-list {grid-template-columns:1fr;gap:12px}
  .fact {min-height:0}
  .decision-list li {padding:24px 21px 24px 64px}
  .decision-list li::before {left:16px;top:23px}
  .site-art {background-position:70% top;height:630px}
  .hero-title-accent {font-size:.96em}
}
"""


def chicago_4k_visual_refinement_css() -> str:
    """V9: LinkedIn-derived sharp visual hierarchy, never fake locality data."""
    return """
/* LinkedIn visual study: picture-led hierarchy and meaningful, readable evidence */
body {font-feature-settings:"kern" 1;text-rendering:optimizeLegibility;
  -webkit-font-smoothing:antialiased}
.site-art {height:clamp(720px,61vw,1100px);opacity:1;background-position:center 40%}
.site-art::after {background:
  linear-gradient(90deg,#01091cf9 0%,#01091ce6 25%,#01091c99 54%,#01091c5b 100%),
  linear-gradient(0deg,#01091c 0%,#01091c9c 16%,transparent 62%),
  radial-gradient(circle at 65% 23%,#005aff16,transparent 65%)}
.hero {min-height:685px;padding-top:105px}
.hero-content h1 {font-weight:860;text-shadow:0 5px 22px #0008;max-width:860px}
.hero-title-base {letter-spacing:-.062em}
.hero-title-accent {letter-spacing:-.062em;line-height:1.03}
.hero .tag {font-size:.87rem;letter-spacing:.16em}
.signal-panel {box-shadow:0 0 38px #005aff45,inset 0 1px #8de7ff32,0 26px 70px #0009}
.hero .lede {font-size:clamp(1.18rem,1.55vw,1.42rem);font-weight:550}
#research-method {padding-top:65px}
.research-intro {display:flex;gap:18px;align-items:flex-end;
  justify-content:space-between;max-width:1100px;padding-bottom:22px}
.research-intro p {max-width:400px;line-height:1.65;color:#a6c2dd}
.research-intro h2 {margin:9px 0 0;max-width:770px}
.research-visual-grid {display:grid;grid-template-columns:1.26fr 1fr;
  gap:19px;margin:25px 0 45px}
.research-visual-hero {min-width:0;min-height:360px;position:relative;
  overflow:hidden;border-radius:22px;border:1px solid #2383ca;
  background:#071833;isolation:isolate;box-shadow:0 20px 55px #0009,inset 0 1px #d6efff32}
.research-visual-hero::before {content:"";position:absolute;inset:0;
  background-image:var(--feature-image);background-position:center 47%;background-size:cover;
  transform:scale(1.002);z-index:-2}
.research-visual-hero::after {content:"";position:absolute;inset:0;
  background:linear-gradient(0deg,#01091cf8 0%,#03112fa5 33%,transparent 70%),
    linear-gradient(90deg,#01091c69,transparent);z-index:-1}
.research-visual-content {position:absolute;bottom:0;left:0;right:0;padding:27px}
.research-visual-content .tag {font-size:.77rem}
.research-visual-content h3 {font-size:clamp(1.7rem,2.6vw,2.7rem);
  line-height:1.08;letter-spacing:-.04em;max-width:530px;margin:9px 0}
.research-visual-content p {font-size:.9rem;line-height:1.55;
  max-width:510px;color:#d6e6f4;margin:0 0 13px}
.research-visual-content a {display:inline-flex;align-items:center;min-height:44px;
  color:#41d6ff;font-size:.9rem;text-decoration-thickness:1px;text-underline-offset:5px;
  font-weight:750}
.research-visual-hero.photo-field::before {background-position:center 37%}
.research-visual-hero.photo-city::before {background-position:center 40%}
.research-visual-hero .visual-caption {position:absolute;right:17px;top:14px;
  border:1px solid #92caff70;background:#051128ac;backdrop-filter:blur(12px);
  padding:5px 10px;border-radius:999px;font-size:.65rem;color:#d3edff;letter-spacing:.02em}
.evidence-path {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
  gap:13px;margin:0 0 29px}
.evidence-path-item {display:flex;align-items:center;gap:12px;
  border:1px solid #20527b;border-radius:11px;padding:16px 17px;
  background:linear-gradient(100deg,#0e2c59b8,#06162cbb)}
.evidence-path-num {flex:0 0 auto;font-size:.9rem;border:1px solid #02c7fe;
  color:#02c7fe;width:35px;height:35px;line-height:33px;
  text-align:center;border-radius:50%;font-weight:850}
.evidence-path-label {font-size:.88rem;color:#deefff;font-weight:700;line-height:1.3}
.evidence-path-detail {display:block;color:#8fb4d1;font-weight:450;font-size:.75rem;margin-top:3px}
.grid {grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}
.fact {min-height:0;padding:27px;border-color:#246ca8;background:
  linear-gradient(140deg,#0d2b52dd,#071a35eb);border-radius:18px}
.fact p {font-size:clamp(.94rem,1.05vw,1.08rem);line-height:1.68}
.fact .source {font-size:.81rem!important}
.fact .micro {font-size:.73rem}
.fact .micro:before {font-size:25px}
.fact:nth-child(1),.fact:nth-child(2) {grid-column:span 1}
.official-link {font-size:.92rem}
.decision-list {grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.decision-list li {line-height:1.65;font-size:1rem}
#utility-title {max-width:900px}
#utility-title::after {content:"";display:block;width:74px;height:3px;margin-top:22px;
  background:linear-gradient(90deg,#02c7fe,#005aff)}
@media(min-width:2000px) {
  .wrap {max-width:1820px}
  .hero {min-height:780px}
  .hero-layout {grid-template-columns:1.18fr .7fr}
  .research-visual-hero {min-height:480px}
  .research-visual-content {padding:39px}
  .grid {grid-template-columns:repeat(3,minmax(0,1fr))}
  .fact {padding:37px}
  .fact p {font-size:1.13rem}
  .decision-list li {font-size:1.09rem;padding:70px 31px 31px}
}
@media(max-width:980px) {
  .research-visual-grid {grid-template-columns:1fr 1fr}
  .research-visual-hero {min-height:320px}
  .research-intro {display:block}
  .grid {grid-template-columns:repeat(2,minmax(0,1fr))}
  .evidence-path {gap:7px}
}
@media(max-width:640px) {
  .hero {min-height:0;padding-top:35px}
  .site-art {height:800px;background-position:58% top}
  .site-art::after {background:linear-gradient(90deg,#01091ce3,#01091c99),
    linear-gradient(0deg,#01091c 0%,transparent 80%)}
  .research-visual-grid {grid-template-columns:1fr;gap:13px}
  .research-visual-hero {min-height:310px}
  .research-visual-content {padding:22px}
  .research-visual-content h3 {font-size:clamp(1.7rem,6.5vw,2.4rem)}
  .evidence-path {grid-template-columns:1fr;gap:8px}
  .grid,.decision-list {grid-template-columns:1fr}
  .fact {padding:23px}
  .fact p {font-size:1rem}
  .research-intro p {font-size:.95rem}
}
"""


def chicago_native_4k_layout_css() -> str:
    """Scale actual interface density for ultra-wide 4K screens, not just photos."""
    return """
@media(min-width:2560px) {
  .wrap {max-width:3060px;padding-inline:72px}
  nav {min-height:134px}
  .wordmark {max-width:310px;width:310px}
  .preview {font-size:1.12rem;padding:12px 24px}
  .hero {min-height:1020px;padding-top:165px;padding-bottom:124px}
  .hero-layout {grid-template-columns:minmax(0,1.25fr) minmax(680px,.72fr);gap:100px}
  .hero-content {max-width:1580px}
  .hero-content h1 {font-size:clamp(5.5rem,4.25vw,10rem);max-width:1560px;
    line-height:1.05;margin:22px 0 42px}
  .hero .tag {font-size:1.33rem;letter-spacing:.2em}
  .hero .lede {font-size:2rem;max-width:1300px}
  .hero .desc {font-size:1.38rem;max-width:1260px}
  .hero .action {font-size:1.42rem;min-height:75px;padding:18px 35px;border-radius:15px}
  .signal-panel {padding:54px;border-radius:28px}
  .signal-head {font-size:1.15rem}
  .signal-value {font-size:1.48rem}
  .signal-rule {margin:26px 0}
  #research-method {padding-top:105px}
  section {padding-block:90px}
  h2, .research-intro h2 {font-size:clamp(3rem,2.45vw,5.7rem)}
  .research-intro {max-width:2250px;gap:95px}
  .research-intro p {max-width:610px;font-size:1.28rem}
  .research-visual-grid {gap:32px;margin-top:45px;margin-bottom:55px}
  .research-visual-hero {min-height:620px;border-radius:34px}
  .research-visual-content {padding:55px}
  .research-visual-content h3 {font-size:clamp(3rem,2.25vw,5rem);max-width:950px}
  .research-visual-content p {font-size:1.53rem;max-width:930px}
  .research-visual-content a {font-size:1.4rem;min-height:64px}
  .research-visual-hero .visual-caption {font-size:1rem;padding:11px 17px}
  .evidence-path {gap:24px;margin-bottom:60px}
  .evidence-path-item {padding:28px 35px;gap:24px}
  .evidence-path-num {width:58px;height:58px;line-height:56px;font-size:1.3rem}
  .evidence-path-label {font-size:1.36rem}
  .evidence-path-detail {font-size:1.08rem}
  .grid {grid-template-columns:repeat(3,minmax(0,1fr));gap:28px}
  .fact {padding:45px;border-radius:26px}
  .fact p {font-size:1.55rem;line-height:1.6}
  .fact .micro {font-size:1rem}
  .fact .source {font-size:1.06rem!important}
  .fact .official-link {font-size:1.3rem}
  .decision-list {gap:28px}
  .decision-list li {font-size:1.5rem;padding:110px 45px 45px}
  .decision-list li::before {left:45px;top:33px;width:50px;height:50px;line-height:48px;font-size:1.4rem}
  .hint {font-size:1.45rem;padding:35px 42px}
  footer {font-size:1.25rem}
}
"""
