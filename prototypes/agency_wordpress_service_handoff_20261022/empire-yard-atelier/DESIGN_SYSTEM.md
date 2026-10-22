# Atelier Motors — fictional demo design system (Claude Design-inspired Step 0)
Version 0.1 | Internal capability theme, **not customer-approved branding**

## Product truth
Atelier Motors is a clearly fictional premium dealership concept used to demonstrate Empire AI's reusable WordPress Delivery Engine. Audience: a potential dealership buyer evaluating digital stock presentation, visual quality and a future workshop solution. This mockup does not advertise real vehicles, offers, prices, testimonials or public booking.

## Source of truth
The design tokens below were extracted from this child theme's existing Tailwind utility classes and screenshots; they are a descriptive reference, **not another stylesheet or handwritten CSS**. Existing code: src/main.jsx, src/ShowroomScene.jsx, parts/header.html and templates/front-page.html. Screenshots: docs/commercial/car_yard_react_browser_evidence_v2.

## Visual vocabulary
- Personality: cinematic, precise, spacious, restrained, editorial. Avoid generic AI SaaS gradients, nested cards and exaggerated animations.
- Primary deep navy: #091923. Supporting charcoal/blue: #102832, #102630. Product foreground: #0b1e28.
- Warm metallic accent: #dfbd82 and #dcbc85. Use for selected actions/kickers, not as a decorative spray.
- Off-white surface: #f5f2eb. Light text: #fffdf7. Secondary text: #bacbd2.
- Display hierarchy: locally available system serif through Tailwind font-serif; body through Tailwind font-sans. Do not pull remote fonts without rights/performance review.
- Layout: max width about 1320px for hero and 1240px for product sections; desktop 1440px and mobile 390px already browser-tested. Avoid horizontal overflow.
- Motion: React Motion for reveal, 3D pointer movement only where supported. Respect prefers-reduced-motion and provide non-WebGL fallback.
- Forms: native WordPress admin only for synthetic appointments; clear denial/success states. Any real public submission requires a separate privacy/consent release.

## Content rules
Show an explicit fictitious/demo notice, no invented social proof, safety endorsements, availability, pricing or business contact information. Client brands, images and real stock require written approval and applicable rights. Keep copyrighted third-party logos/models out of the demo.

## Reusability boundary
This document describes **this** child theme, not the Empire AI corporate visual identity. For another agency client, generate a separate approved brand context and plan rather than silently reusing Atelier Motors colours, copy or mockup assets.
