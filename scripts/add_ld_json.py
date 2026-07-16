#!/usr/bin/env python3
"""Add JSON-LD structured data to all 36 AEO pages for rich snippets."""

import os, json, re
from pathlib import Path

AEO_ROOT = Path("/srv/aeo")

NICHE_META = {
    # Mass Torts
    "roundup": {"name":"Roundup Lawsuit","desc":"Roundup cancer lawsuit - non-Hodgkin lymphoma","type":"LegalService"},
    "camp_lejeune": {"name":"Camp Lejeune Water Contamination","desc":"Camp Lejeune lawsuit - water contamination claims","type":"LegalService"},
    "ozempic": {"name":"Ozempic Lawsuit","desc":"Ozempic gastroparesis lawsuit - GLP-1 side effects","type":"LegalService"},
    "zantac": {"name":"Zantac Cancer Lawsuit","desc":"Zantac ranitidine cancer lawsuit","type":"LegalService"},
    "afff": {"name":"AFFF Firefighting Foam Lawsuit","desc":"AFFF PFAS contamination lawsuit","type":"LegalService"},
    "3m_earplugs": {"name":"3M Combat Earplug Lawsuit","desc":"3M military earplug hearing loss lawsuit","type":"LegalService"},
    "hair_relaxers": {"name":"Hair Relaxer Cancer Lawsuit","desc":"Chemical hair straightener uterine cancer lawsuit","type":"LegalService"},
    "hernia_mesh": {"name":"Hernia Mesh Lawsuit","desc":"Hernia mesh complications lawsuit","type":"LegalService"},
    "nec_formula": {"name":"NEC Baby Formula Lawsuit","desc":"Necrotizing enterocolitis preterm formula lawsuit","type":"LegalService"},
    "philips_cpap": {"name":"Philips CPAP Recall Lawsuit","desc":"Philips CPAP cancer recall lawsuit","type":"LegalService"},
    "talcum_powder": {"name":"Talcum Powder Ovarian Cancer Lawsuit","desc":"Baby powder ovarian cancer lawsuit","type":"LegalService"},
    # Home Services
    "hvac": {"name":"HVAC Repair & Installation","desc":"Professional HVAC repair, AC installation, and heating services","type":"HVACBusiness"},
    "plumbing": {"name":"Plumbing Services","desc":"Emergency plumbing, drain cleaning, pipe repair","type":"PlumbingContractor"},
    "electrical": {"name":"Electrical Services","desc":"Residential and commercial electrical installation and repair","type":"Electrician"},
    "roofing": {"name":"Roofing Contractor","desc":"Roof repair, replacement, and installation","type":"RoofingContractor"},
    "pest_control": {"name":"Pest Control Services","desc":"Exterminator for termites, rodents, bed bugs, and more","type":"PestControl"},
    "landscaping": {"name":"Landscaping Services","desc":"Lawn care, landscape design, hardscaping, tree service","type":"Landscaping"},
    # Medical & Health
    "weight_loss": {"name":"Medical Weight Loss Programs","desc":"Doctor-supervised weight loss, GLP-1 medications, bariatric programs","type":"MedicalClinic"},
    "mental_health": {"name":"Mental Health Services","desc":"Therapy, counseling, psychiatric care, depression and anxiety treatment","type":"MentalHealthClinic"},
    "pain_management": {"name":"Pain Management Clinic","desc":"Chronic pain treatment, spinal injections, physical therapy","type":"MedicalClinic"},
    "physical_therapy": {"name":"Physical Therapy","desc":"Sports injury rehab, post-surgery PT, pain relief","type":"PhysicalTherapyClinic"},
    "dental": {"name":"Dental Services","desc":"General dentistry, cosmetic dentistry, implants, orthodontics","type":"Dentist"},
    "dermatology": {"name":"Dermatology Clinic","desc":"Skin care, acne treatment, mole removal, cosmetic dermatology","type":"DermatologyClinic"},
    # Business Services
    "business_consulting": {"name":"Business Consulting","desc":"Strategy consulting, management advisory, business optimization","type":"ConsultingBusiness"},
    "marketing": {"name":"Digital Marketing Agency","desc":"SEO, PPC, social media, content marketing for businesses","type":"MarketingAgency"},
    "staffing": {"name":"Staffing & Recruiting","desc":"Talent acquisition, temp staffing, executive recruiting","type":"EmploymentAgency"},
    "it_services": {"name":"IT Services & Support","desc":"Managed IT, cloud services, network security, tech support","type":"ITServices"},
    "accounting": {"name":"Accounting & Tax Services","desc":"CPA, tax preparation, bookkeeping, payroll services","type":"AccountingService"},
    "legal": {"name":"Legal Services","desc":"Business law, contract review, intellectual property, litigation","type":"LegalService"},
    # Financial
    "real_estate": {"name":"Real Estate Services","desc":"Property buying, selling, investment, commercial real estate","type":"RealEstateAgency"},
    "debt_relief": {"name":"Debt Relief & Settlement","desc":"Credit card debt relief, debt settlement, consolidation","type":"FinancialService"},
    "business_funding": {"name":"Business Funding & Loans","desc":"Small business loans, SBA financing, merchant cash advance","type":"FinancialService"},
    "tax_planning": {"name":"Tax Planning & Preparation","desc":"Tax strategy, corporate tax, individual tax planning","type":"AccountingService"},
    "insurance": {"name":"Insurance Agency","desc":"Auto, home, life, health, and business insurance","type":"InsuranceAgency"},
    "retirement": {"name":"Retirement Planning","desc":"401k, IRA, pension planning, retirement income strategies","type":"FinancialService"},
    # Technology
    "cybersecurity": {"name":"Cybersecurity Services","desc":"SOC2 compliance, penetration testing, managed security","type":"ITServices"},
    "ai_automation": {"name":"AI & Automation Services","desc":"AI agents, workflow automation, machine learning solutions","type":"Business"},
    "saas": {"name":"SaaS Development","desc":"Software as a Service development, cloud platforms","type":"SoftwareCompany"},
    "devops": {"name":"DevOps & Cloud Services","desc":"CI/CD, cloud migration, Kubernetes, infrastructure automation","type":"ITServices"},
    "blockchain": {"name":"Blockchain Development","desc":"Smart contracts, DeFi, NFT marketplace, crypto solutions","type":"SoftwareCompany"},
    "support": {"name":"Tech Support Services","desc":"Help desk, remote support, managed IT helpdesk","type":"ITServices"},
    "software_dev": {"name":"Software Development","desc":"Custom software, web apps, mobile apps, enterprise solutions","type":"SoftwareCompany"},
    "web_dev": {"name":"Web Development","desc":"Website design, e-commerce, CMS, responsive web development","type":"WebDesign"},
    "cloud": {"name":"Cloud Computing Services","desc":"Cloud migration, AWS/Azure/GCP, cloud infrastructure","type":"ITServices"},
    "data_analytics": {"name":"Data Analytics Services","desc":"Business intelligence, data science, analytics consulting","type":"DataAnalytics"},
    "managed_it": {"name":"Managed IT Services","desc":"IT support, network management, cybersecurity, helpdesk","type":"ITServices"},
    "consulting": {"name":"Business Consulting","desc":"Management consulting, strategy, operations, growth advisory","type":"ConsultingBusiness"},
    "legal_services": {"name":"Legal Services","desc":"Business law, contract review, litigation, corporate counsel","type":"LegalService"},
    "mortgage": {"name":"Mortgage Services","desc":"Home loans, refinancing, FHA, VA, conventional mortgages","type":"FinancialService"},
    "investing": {"name":"Investment Services","desc":"Wealth management, portfolio management, retirement investing","type":"FinancialService"},
    "tax_prep": {"name":"Tax Preparation Services","desc":"Tax filing, IRS representation, tax planning, corporate taxes","type":"AccountingService"},
    "addiction": {"name":"Addiction Treatment Center","desc":"Drug rehab, alcohol treatment, detox programs, recovery support","type":"MedicalClinic"},
    "hormone_therapy": {"name":"Hormone Therapy","desc":"HRT, testosterone therapy, thyroid treatment, bioidentical hormones","type":"MedicalClinic"},
    "vision": {"name":"Vision & Eye Care","desc":"Eye exams, glasses, contacts, LASIK, cataract surgery","type":"Optometrist"},
    "pt_rehab": {"name":"Physical Therapy & Rehab","desc":"Sports rehab, post-surgery PT, pain management","type":"PhysicalTherapyClinic"},
    "mass_torts": {"name":"Mass Tort & Class Action","desc":"Join class action lawsuits, mass tort claims, product liability","type":"LegalService"},
    "paraquat": {"name":"Paraquat Lawsuit","desc":"Paraquat herbicide Parkinson's disease lawsuit","type":"LegalService"},
}

def inject_ld_json(html: str, niche_key: str, meta: dict) -> str:
    """Inject JSON-LD script before closing </head>."""
    ld = {
        "@context": "https://schema.org",
        "@type": meta["type"],
        "name": meta["name"],
        "description": meta["desc"],
        "url": f"https://302ai.net/aeo/{niche_key}/",
        "areaServed": "US",
        "potentialAction": {
            "@type": "ContactAction",
            "target": f"https://302ai.net/aeo/{niche_key}/#contact"
        }
    }
    script = f'\n<script type="application/ld+json">\n{json.dumps(ld, indent=2)}\n</script>\n'
    return html.replace("</head>", script + "</head>", 1)

count = 0
for niche_dir in sorted(AEO_ROOT.iterdir()):
    if not niche_dir.is_dir():
        continue
    index = niche_dir / "index.html"
    if not index.exists():
        continue
    meta = NICHE_META.get(niche_dir.name)
    if not meta:
        continue
    html = index.read_text()
    if 'application/ld+json' in html:
        continue  # already has LD JSON
    new_html = inject_ld_json(html, niche_dir.name, meta)
    index.write_text(new_html)
    count += 1
    print(f"  {niche_dir.name}: {meta['type']}")

print(f"\nInjected JSON-LD into {count} pages")
