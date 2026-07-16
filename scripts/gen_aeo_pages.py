#!/usr/bin/env python3
"""Generate AEO content pages for all 36 sub-niches across 6 categories."""

import os
from pathlib import Path

CATEGORY_PAGES = {
    "mass_torts": {
        "label": "Mass Torts & Personal Injury",
        "subs": {
            "camp_lejeune": {"title": "Camp Lejeune Water Contamination Lawsuit - Free Case Evaluation | Toxic Water at Marine Corps Base, ",
                             "h1": "Camp Lejeune Water Contamination Lawsuit", 
                             "intro": "Thousands of veterans and their families were exposed to toxic drinking water at Camp Lejeune Marine Corps Base from 1953–1987. If you or a loved one served at Camp Lejeune and developed cancer, Parkinson's disease, or other serious health conditions, you may qualify for compensation."},
            "roundup": {"title": "Roundup Weed Killer Cancer Lawsuit - Non-Hodgkin Lymphoma Claims | Glyphosate, Monsanto ",
                        "h1": "Roundup Cancer Lawsuit", 
                        "intro": "Roundup's active ingredient glyphosate has been linked to non-Hodgkin lymphoma and other cancers. If you used Roundup regularly on your farm, lawn, or property and were later diagnosed with cancer, you may be entitled to significant compensation."},
            "paraquat": {"title": "Paraquat Herbicide Parkinson's Lawsuit - Free Case Review | Gramoxone Exposure ",
                         "h1": "Paraquat Parkinson's Lawsuit", 
                         "intro": "Paraquat is one of the most toxic herbicides on the market, linked to Parkinson's disease development in agricultural workers and residents near treated areas. Find out if you qualify for compensation today."},
            "afff": {"title": "AFFF Firefighting Foam Cancer Lawsuit - PFAS Water Contamination | Free Case Review ",
                     "h1": "AFFF Firefighting Foam Lawsuit", 
                     "intro": "Aqueous Film Forming Foam (AFFF) used at military bases and airports contains PFAS chemicals linked to kidney cancer, testicular cancer, and other serious illnesses. Firefighters and military personnel are at highest risk."},
            "zantac": {"title": "Zantac Cancer Lawsuit - Ranitidine NDMA Contamination | Free Claim Review ",
                       "h1": "Zantac Cancer Lawsuit", 
                       "intro": "Zantac (ranitidine) was found to contain NDMA, a known carcinogen, at unsafe levels. If you took Zantac for heartburn and were later diagnosed with cancer, you may have a legal claim."},
            "ozempic": {"title": "Ozempic Lawsuit - Stomach Paralysis, Gallbladder Injury | GLP-1 Side Effects ",
                        "h1": "Ozempic & GLP-1 Lawsuit", 
                        "intro": "Ozempic, Mounjaro, Wegovy, and other GLP-1 drugs have been linked to gastroparesis (stomach paralysis), gallbladder disease, and other serious injuries. If you suffered complications from these weight loss drugs, you may qualify for compensation."},
        }
    },
    "home_services": {
        "label": "Home Services",
        "subs": {
            "electrical": {"title": "Licensed Electrician Near You - Residential & Commercial Electrical Services",
                           "h1": "Professional Electrical Services", 
                           "intro": "From emergency electrical repairs to complete home rewiring, our network of licensed electricians handles it all. Panel upgrades, outlet installation, surge protection, and more."},
            "hvac": {"title": "HVAC Repair & Installation - Heating and Cooling Services | Free Quote",
                     "h1": "Heating & Air Conditioning Services",
                     "intro": "Stay comfortable year-round with professional HVAC services. AC repair, furnace installation, heat pump maintenance, and indoor air quality solutions from certified technicians."},
            "plumbing": {"title": "Emergency Plumber Near You - Plumbing Repair & Installation | 24/7 Service",
                         "h1": "Expert Plumbing Services",
                         "intro": "Burst pipes, clogged drains, water heater failure — our plumbing professionals handle emergencies and routine maintenance. Fast response, quality workmanship."},
            "roofing": {"title": "Roof Repair & Replacement - Licensed Roofing Contractors | Free Inspection",
                        "h1": "Professional Roofing Services",
                        "intro": "Protect your home with quality roofing services. Shingle replacement, leak repair, gutter installation, and full roof replacements from experienced contractors."},
            "pest_control": {"title": "Pest Control Near You - Termite, Rodent & Bed Bug Extermination",
                             "h1": "Professional Pest Control Services",
                             "intro": "Don't let pests take over your home. Our exterminators handle termites, bed bugs, rodents, cockroaches, and more with proven treatment methods and prevention plans."},
            "landscaping": {"title": "Landscaping Services - Lawn Care, Design & Hardscaping | Free Quote",
                            "h1": "Professional Landscaping & Lawn Care",
                            "intro": "Transform your outdoor space with professional landscaping. Lawn maintenance, garden design, hardscaping, irrigation systems, and tree services from top-rated landscapers."},
        }
    },
    "medical_health": {
        "label": "Medical & Health",
        "subs": {
            "weight_loss": {"title": "Medical Weight Loss Programs - Semaglutide, Tirzepatide & GLP-1 Treatments",
                            "h1": "Medical Weight Loss Programs",
                            "intro": "Achieve your weight loss goals with medically supervised programs including GLP-1 medications like semaglutide and tirzepatide. Personalized plans from licensed healthcare providers."},
            "hormone_therapy": {"title": "Hormone Replacement Therapy - Testosterone, HRT for Men & Women",
                                "h1": "Hormone Replacement Therapy",
                                "intro": "Restore your vitality with hormone replacement therapy. Testosterone therapy for men, bioidentical HRT for women, and thyroid optimization from hormone specialists."},
            "dental": {"title": "Dental Services - Implants, Whitening, Orthodontics | Top-Rated Dentists",
                       "h1": "Comprehensive Dental Services",
                       "intro": "From routine cleanings to full mouth reconstruction, find top-rated dentists for implants, Invisalign, teeth whitening, crowns, and emergency dental care."},
            "vision": {"title": "Eye Care & Vision Services - LASIK, Eye Exams, Cataract Surgery",
                       "h1": "Vision Care & Eye Health",
                       "intro": "Protect your vision with comprehensive eye exams, LASIK surgery, cataract treatment, and contact lens fittings from experienced optometrists and ophthalmologists."},
            "pt_rehab": {"title": "Physical Therapy & Rehabilitation - Sports Medicine, Injury Recovery",
                         "h1": "Physical Therapy & Rehabilitation",
                         "intro": "Recover from injury, surgery, or chronic pain with professional physical therapy. Sports medicine, occupational therapy, chiropractic care, and personalized rehab programs."},
            "addiction": {"title": "Addiction Treatment & Rehab Centers - Detox & Recovery Programs",
                          "h1": "Addiction Treatment & Recovery",
                          "intro": "Find hope and healing at accredited addiction treatment centers. Medical detox, inpatient rehab, outpatient programs, and sober living support for substance abuse and alcoholism."},
        }
    },
    "business_services": {
        "label": "Business Services",
        "subs": {
            "marketing": {"title": "Digital Marketing Agency - SEO, PPC, Social Media | Grow Your Business",
                          "h1": "Digital Marketing Services",
                          "intro": "Scale your business with data-driven digital marketing. SEO, paid advertising, social media management, content marketing, and conversion optimization from experienced agencies."},
            "web_dev": {"title": "Web Development & Design - Custom Websites, Ecommerce, Apps",
                        "h1": "Web Development & Design Services",
                        "intro": "Build your online presence with professional web development. Custom websites, ecommerce stores, web applications, and mobile apps built with modern technologies."},
            "accounting": {"title": "Small Business Accounting - Bookkeeping, Tax Prep, CPA Services",
                           "h1": "Accounting & Bookkeeping Services",
                           "intro": "Keep your finances in order with professional accounting services. Bookkeeping, tax preparation, payroll, and CPA services for small businesses and startups."},
            "consulting": {"title": "Business Consulting - Strategy, Operations, Growth Consulting",
                           "h1": "Business Consulting Services",
                           "intro": "Accelerate your business growth with expert consulting. Strategy development, operations optimization, market analysis, and growth planning from seasoned consultants."},
            "staffing": {"title": "Staffing Agency - Temp, Permanent & Executive Recruitment",
                         "h1": "Staffing & Recruitment Services",
                         "intro": "Find the right talent with professional staffing services. Temporary staffing, permanent placement, executive recruiting, and specialized industry recruitment."},
            "legal_services": {"title": "Business Attorney - Contract Law, Estate Planning, Business Formation",
                               "h1": "Business Legal Services",
                               "intro": "Protect your business with experienced legal counsel. Contract review, business formation, estate planning, intellectual property, and corporate law services."},
        }
    },
    "financial": {
        "label": "Financial Services",
        "subs": {
            "real_estate": {"title": "Real Estate Agents Near You - Home Buyers & Sellers",
                            "h1": "Real Estate Services",
                            "intro": "Buying or selling a home? Connect with top-rated real estate agents who know your local market. Expert guidance for first-time buyers, sellers, and investors."},
            "mortgage": {"title": "Mortgage Lenders - Home Loans, Refinancing & Pre-Approval",
                         "h1": "Mortgage & Home Loan Services",
                         "intro": "Get the best mortgage rates for your home purchase or refinance. FHA, conventional, VA loans, and jumbo mortgages from trusted lenders."},
            "insurance": {"title": "Insurance Agents - Auto, Home, Life & Business Insurance Quotes",
                          "h1": "Insurance Services",
                          "intro": "Protect what matters most with comprehensive insurance coverage. Auto, home, life, health, and business insurance from licensed agents."},
            "investing": {"title": "Financial Advisors - Wealth Management, Retirement Planning",
                          "h1": "Financial Planning & Investment Services",
                          "intro": "Build and protect your wealth with professional financial advice. Retirement planning, investment management, estate planning, and wealth preservation strategies."},
            "debt_relief": {"title": "Debt Relief Solutions - Credit Card Debt, Settlement, Consolidation",
                            "h1": "Debt Relief & Credit Repair",
                            "intro": "Take control of your finances with debt relief solutions. Debt settlement, credit card consolidation, bankruptcy alternatives, and credit repair services."},
            "tax_prep": {"title": "Tax Preparation Services - IRS Help, Business & Personal Tax Filing",
                         "h1": "Tax Preparation & Planning",
                         "intro": "File with confidence. Professional tax preparation for individuals and businesses, IRS representation, tax planning strategies, and year-round support."},
        }
    },
    "technology": {
        "label": "Technology & Software",
        "subs": {
            "managed_it": {"title": "Managed IT Services - IT Support, Network Management, Helpdesk",
                           "h1": "Managed IT Services",
                           "intro": "Keep your business running with reliable managed IT services. 24/7 network monitoring, helpdesk support, cloud management, and cybersecurity from experienced MSPs."},
            "cybersecurity": {"title": "Cybersecurity Services - Penetration Testing, Compliance, Security Audits",
                              "h1": "Cybersecurity & Information Security",
                              "intro": "Protect your business from cyber threats. Penetration testing, vulnerability assessments, compliance audits, SOC services, and ransomware protection."},
            "software_dev": {"title": "Software Development Company - Custom Apps, SaaS, APIs",
                             "h1": "Custom Software Development",
                             "intro": "Turn your idea into reality with custom software development. Web applications, mobile apps, SaaS platforms, API development, and enterprise software solutions."},
            "cloud": {"title": "Cloud Services - Migration, AWS, Azure, Google Cloud Consulting",
                      "h1": "Cloud Computing Services",
                      "intro": "Transform your infrastructure with cloud solutions. Cloud migration, AWS/Azure/GCP architecture, DevOps, containerization, and cloud cost optimization."},
            "ai_automation": {"title": "AI & Automation Consulting - Machine Learning, RPA, Chatbots",
                              "h1": "AI & Business Automation",
                              "intro": "Leverage artificial intelligence and automation to transform your business. Machine learning, RPA, AI chatbots, process automation, and intelligent workflow solutions."},
            "data_analytics": {"title": "Data Analytics & BI - Power BI, Tableau, Data Science Consulting",
                               "h1": "Data Analytics & Business Intelligence",
                               "intro": "Turn your data into actionable insights. Business intelligence dashboards, data engineering, analytics consulting, and data science from experienced professionals."},
        }
    },
}


def generate_html(cat_key: str, sub_key: str, info: dict) -> str:
    title = info["title"]
    h1 = info["h1"]
    intro = info["intro"]
    cat_label = CATEGORY_PAGES[cat_key]["label"]
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{intro[:155]}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://empireos.io/aeo/{sub_key}/">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; }}
        header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 60px 0; }}
        header h1 {{ font-size: 2.5em; margin-bottom: 20px; }}
        header p {{ font-size: 1.2em; opacity: 0.9; max-width: 800px; }}
        .cta {{ display: inline-block; background: #e94560; color: white; padding: 15px 40px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1.1em; margin-top: 25px; transition: background 0.3s; }}
        .cta:hover {{ background: #d63851; }}
        section {{ padding: 40px 0; }}
        section:nth-child(even) {{ background: #f8f9fa; }}
        h2 {{ font-size: 1.8em; margin-bottom: 20px; color: #1a1a2e; }}
        ul {{ margin-left: 20px; }}
        li {{ margin-bottom: 10px; }}
        .benefits {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 30px; }}
        .benefit-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .benefit-card h3 {{ color: #e94560; margin-bottom: 10px; }}
        footer {{ background: #1a1a2e; color: white; text-align: center; padding: 20px; font-size: 0.9em; opacity: 0.8; }}
        @media (max-width: 768px) {{ header h1 {{ font-size: 1.8em; }} }}
    </style>
</head>
<body>
<header>
    <div class="container">
        <p style="text-transform:uppercase;letter-spacing:2px;opacity:0.7;margin-bottom:10px;">{cat_label}</p>
        <h1>{h1}</h1>
        <p>{intro}</p>
        <a href="#" class="cta" onclick="document.getElementById('contact').scrollIntoView({{behavior:'smooth'}});return false;">Free Consultation →</a>
    </div>
</header>

<section id="about">
    <div class="container">
        <h2>How We Can Help</h2>
        <p>We connect you with pre-vetted, top-rated professionals in the {cat_label.lower()} industry. Our network spans the entire country, ensuring you get quality service wherever you are.</p>
        <p>Every professional in our network undergoes a rigorous vetting process including license verification, background checks, and client satisfaction reviews.</p>
    </div>
</section>

<section id="benefits">
    <div class="container">
        <h2>Why Choose Our Network</h2>
        <div class="benefits">
            <div class="benefit-card">
                <h3>✓ Verified Professionals</h3>
                <p>Every provider is licensed, insured, and vetted for quality. We don't just list anyone — we verify.</p>
            </div>
            <div class="benefit-card">
                <h3>✓ Free Matching Service</h3>
                <p>Tell us what you need and we'll match you with the right professional. No cost, no obligation.</p>
            </div>
            <div class="benefit-card">
                <h3>✓ Nationwide Coverage</h3>
                <p>Access our network of providers across all 50 states. Wherever you are, we have you covered.</p>
            </div>
        </div>
    </div>
</section>

<section id="contact">
    <div class="container" style="text-align:center;">
        <h2>Get Your Free Consultation</h2>
        <p style="margin-bottom:25px;font-size:1.1em;">Fill out the form below and we'll connect you with the right professional within 24 hours.</p>
        <div style="max-width:500px;margin:0 auto;background:white;padding:30px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
            <form action="#" method="post">
                <input type="text" placeholder="Full Name" style="width:100%;padding:12px;margin-bottom:15px;border:1px solid #ddd;border-radius:6px;" required>
                <input type="email" placeholder="Email Address" style="width:100%;padding:12px;margin-bottom:15px;border:1px solid #ddd;border-radius:6px;" required>
                <input type="tel" placeholder="Phone Number" style="width:100%;padding:12px;margin-bottom:15px;border:1px solid #ddd;border-radius:6px;" required>
                <select style="width:100%;padding:12px;margin-bottom:15px;border:1px solid #ddd;border-radius:6px;">
                    <option value="">Select State</option>
                    <option>AL</option><option>AK</option><option>AZ</option><option>AR</option><option>CA</option><option>CO</option><option>CT</option><option>DE</option><option>FL</option><option>GA</option>
                </select>
                <textarea placeholder="Briefly describe what you need" rows="4" style="width:100%;padding:12px;margin-bottom:15px;border:1px solid #ddd;border-radius:6px;"></textarea>
                <button type="submit" style="width:100%;background:#e94560;color:white;padding:15px;border:none;border-radius:6px;font-size:1.1em;font-weight:bold;cursor:pointer;">Get Connected →</button>
            </form>
        </div>
    </div>
</section>

<footer>
    <div class="container">
        <p>&copy; 2026 Empire OS. All rights reserved. | <a href="/privacy" style="color:white;">Privacy Policy</a></p>
    </div>
</footer>
</body>
</html>"""


def main():
    surface_root = Path("/srv/aeo")
    
    total = 0
    for cat_key, cat_info in CATEGORY_PAGES.items():
        for sub_key, sub_info in cat_info["subs"].items():
            page_dir = surface_root / sub_key
            page_dir.mkdir(parents=True, exist_ok=True)
            
            html = generate_html(cat_key, sub_key, sub_info)
            (page_dir / "index.html").write_text(html, encoding="utf-8")
            total += 1
            print(f"  [OK] {cat_key}/{sub_key}")

    print(f"\nDone: {total} AEO pages generated at {surface_root}")


if __name__ == "__main__":
    main()
