#!/usr/bin/env python3
"""
Create sample project input files in DOCX format for testing.
These are mock-up documents representing typical project details.
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path


def create_sample_1():
    """Sample 1: Smart Traffic Light System"""
    doc = Document()

    # Title
    title = doc.add_heading('Smart Traffic Light Management System for Orchard Road', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Project Summary
    doc.add_heading('PROJECT SUMMARY', 1)
    doc.add_paragraph(
        'The Land Transport Authority (LTA) proposes to implement an AI-powered adaptive traffic light '
        'control system along Orchard Road to reduce congestion and improve traffic flow. The system will '
        'use real-time traffic data from cameras and sensors to dynamically adjust signal timings.'
    )

    # Background
    doc.add_heading('BACKGROUND', 1)
    doc.add_paragraph(
        'Orchard Road experiences severe congestion during peak hours (8-10am, 6-8pm), with average wait '
        'times of 90 seconds per intersection. This leads to increased CO2 emissions, delayed emergency '
        'vehicle response, and poor commuter experience.'
    )

    # Objectives
    doc.add_heading('PROJECT OBJECTIVES', 1)
    objectives = [
        'Reduce average vehicle wait time by 30% (from 90s to 60s)',
        'Decrease CO2 emissions by 15% through smoother traffic flow',
        'Improve emergency vehicle response time by 20%',
        'Enhance overall road network efficiency'
    ]
    for obj in objectives:
        doc.add_paragraph(obj, style='List Number')

    # Budget & Costs
    doc.add_heading('BUDGET & COSTS', 1)
    doc.add_paragraph('Development Cost: S$12 million').bold = True
    costs = [
        'Hardware (cameras, sensors, traffic lights): S$8 million',
        'Software development (AI algorithms, integration): S$3 million',
        'Professional fees (consultants, project management): S$1 million'
    ]
    for cost in costs:
        doc.add_paragraph(cost, style='List Bullet')

    doc.add_paragraph('\nAnnual Recurrent Cost: S$800,000').bold = True
    recurrent = [
        'Maintenance: S$500,000',
        'Operations (electricity, monitoring): S$300,000'
    ]
    for r in recurrent:
        doc.add_paragraph(r, style='List Bullet')

    # Timeline
    doc.add_heading('TIMELINE', 1)
    timeline = [
        'Design Phase: 6 months (Q1-Q2 2026)',
        'Procurement: 3 months (Q3 2026)',
        'Implementation: 9 months (Q4 2026 - Q2 2027)',
        'Testing & Commissioning: 3 months (Q3 2027)',
        'Total Project Duration: 18 months from approval'
    ]
    for item in timeline:
        doc.add_paragraph(item, style='List Bullet')

    # Expected Benefits
    doc.add_heading('EXPECTED BENEFITS', 1)
    doc.add_paragraph('Quantifiable:').bold = True
    benefits = [
        'Time savings: 30 seconds per vehicle x 50,000 vehicles/day = 416 hours/day saved',
        'Fuel savings: 15% reduction = S$2.5M annually',
        'Emission reduction: 15% = 450 tonnes CO2/year'
    ]
    for b in benefits:
        doc.add_paragraph(b, style='List Bullet')

    doc.add_paragraph('\nIntangible:').bold = True
    intangible = [
        'Improved commuter experience',
        "Enhanced Singapore's Smart Nation reputation",
        'Better emergency response capabilities'
    ]
    for i in intangible:
        doc.add_paragraph(i, style='List Bullet')

    # KPIs
    doc.add_heading('KEY PERFORMANCE INDICATORS', 1)
    kpis = [
        'Average wait time at Orchard Road intersections (Target: <60 seconds)',
        'Traffic flow rate (Target: +25% vehicles/hour)',
        'CO2 emissions (Target: -15% from baseline)',
        'Emergency vehicle response time (Target: -20% from baseline)',
        'System uptime (Target: 99.5%)'
    ]
    for kpi in kpis:
        doc.add_paragraph(kpi, style='List Number')

    # Stakeholders
    doc.add_heading('STAKEHOLDERS', 1)
    stakeholders = [
        'Land Transport Authority (LTA) - Project Owner',
        'Ministry of Transport (MOT) - Approving Authority',
        'Traffic Police - Operations Partner',
        'Singapore Civil Defence Force (SCDF) - Emergency Services',
        'Orchard Road Business Association - Community Stakeholder'
    ]
    for s in stakeholders:
        doc.add_paragraph(s, style='List Bullet')

    # Risks
    doc.add_heading('RISKS', 1)
    risks = [
        'Technical: AI system accuracy in adverse weather',
        'Budget: Hardware cost escalation',
        'Schedule: Procurement delays',
        'Operational: Public acceptance and behavioral change'
    ]
    for risk in risks:
        doc.add_paragraph(risk, style='List Number')

    # Alignment
    doc.add_heading('ALIGNMENT WITH NATIONAL GOALS', 1)
    alignment = [
        'Smart Nation initiative (Digital Government Blueprint)',
        'Singapore Green Plan 2030 (reduced emissions)',
        'Land Transport Master Plan 2040 (sustainable mobility)'
    ]
    for a in alignment:
        doc.add_paragraph(a, style='List Bullet')

    # Economic Lifespan
    doc.add_heading('ECONOMIC LIFESPAN', 1)
    doc.add_paragraph('15 years')

    # Alternative Approaches
    doc.add_heading('ALTERNATIVE APPROACHES CONSIDERED', 1)
    approaches = [
        'Full AI system (proposed)',
        'Phased implementation (pilot first, then scale)',
        'Manual optimization with data analytics (lower cost, lower benefit)'
    ]
    for approach in approaches:
        doc.add_paragraph(approach, style='List Number')

    return doc


def create_sample_2():
    """Sample 2: SingPass 3.0"""
    doc = Document()

    # Title
    title = doc.add_heading('National Digital Identity System Upgrade (SingPass 3.0)', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Project Summary
    doc.add_heading('PROJECT SUMMARY', 1)
    doc.add_paragraph(
        'GovTech proposes to upgrade the national digital identity infrastructure (SingPass) to enhance '
        'security, user experience, and enable new digital services. The upgrade will implement biometric '
        'authentication, blockchain-based credential verification, and seamless cross-agency integration.'
    )

    # Background
    doc.add_heading('BACKGROUND', 1)
    doc.add_paragraph(
        'Current SingPass system serves 4.5 million users but faces limitations:'
    )
    limitations = [
        'Limited biometric authentication (only mobile app)',
        'No cross-border identity verification',
        'Manual document verification processes',
        'Increasing cybersecurity threats',
        'User complaints about complex authentication flows'
    ]
    for lim in limitations:
        doc.add_paragraph(lim, style='List Bullet')

    # Objectives
    doc.add_heading('PROJECT OBJECTIVES', 1)
    objectives = [
        'Implement multi-factor biometric authentication (face, fingerprint, voice)',
        'Enable cross-border digital identity verification with 5 countries',
        'Reduce authentication time by 70% (from 45 seconds to 15 seconds)',
        'Achieve 99.99% system availability',
        'Support 10 million transactions per day (up from current 3 million)'
    ]
    for obj in objectives:
        doc.add_paragraph(obj, style='List Number')

    # Budget & Costs
    doc.add_heading('BUDGET & COSTS', 1)
    doc.add_paragraph('Total Development Cost: S$85 million').bold = True
    doc.add_paragraph()

    doc.add_paragraph('Development Cost Breakdown by Works:').bold = True
    doc.add_paragraph('Software Development: S$35 million', style='List Bullet')
    doc.add_paragraph('  • Core platform upgrade: S$20 million', style='List Bullet')
    doc.add_paragraph('  • Biometric engine: S$10 million', style='List Bullet')
    doc.add_paragraph('  • API gateway & integration: S$5 million', style='List Bullet')

    doc.add_paragraph('Hardware & Infrastructure: S$25 million', style='List Bullet')
    doc.add_paragraph('  • Cloud infrastructure (5-year contract): S$15 million', style='List Bullet')
    doc.add_paragraph('  • Biometric devices: S$7 million', style='List Bullet')
    doc.add_paragraph('  • Network security appliances: S$3 million', style='List Bullet')

    doc.add_paragraph('Professional Services: S$15 million', style='List Bullet')
    doc.add_paragraph('  • System integrator fees: S$8 million', style='List Bullet')
    doc.add_paragraph('  • Security audit & penetration testing: S$3 million', style='List Bullet')
    doc.add_paragraph('  • Change management & training: S$2 million', style='List Bullet')
    doc.add_paragraph('  • Project management: S$2 million', style='List Bullet')

    doc.add_paragraph('Contingency (5%): S$4 million', style='List Bullet')
    doc.add_paragraph('GST (9%): S$6 million', style='List Bullet')

    doc.add_paragraph()
    doc.add_paragraph('Land Cost: Not applicable (using existing Government cloud)').bold = True

    doc.add_paragraph()
    doc.add_paragraph('Annual Recurrent Cost: S$12 million').bold = True
    recurrent = [
        'Cloud hosting & infrastructure: S$5 million',
        'Cybersecurity monitoring: S$2 million',
        'Maintenance & support: S$3 million',
        'Staff operations (15 FTE): S$2 million'
    ]
    for r in recurrent:
        doc.add_paragraph(r, style='List Bullet')

    # Timeline
    doc.add_heading('TIMELINE', 1)
    timeline = [
        'Requirements & Design: 6 months (Jan - Jun 2026)',
        'Vendor Selection: 3 months (Jul - Sep 2026)',
        'Development Phase 1 (Core Platform): 12 months (Oct 2026 - Sep 2027)',
        'Development Phase 2 (Biometrics): 6 months (Oct 2027 - Mar 2028)',
        'Integration & Testing: 4 months (Apr - Jul 2028)',
        'Pilot Rollout (100,000 users): 2 months (Aug - Sep 2028)',
        'Full Production Launch: Oct 2028',
        'Total Duration: 33 months'
    ]
    for item in timeline:
        doc.add_paragraph(item, style='List Bullet')

    # Expected Benefits
    doc.add_heading('EXPECTED BENEFITS', 1)
    doc.add_paragraph('Quantifiable Benefits (Annual):').bold = True
    benefits = [
        'Time savings: 30 seconds x 1.1 billion transactions = 9.2 million hours saved',
        '  • Monetized value: S$230 million (at S$25/hour)',
        'Fraud prevention: S$15 million annual losses avoided',
        'Operational cost savings: S$20 million (reduced manual verification)',
        'Total Annual Benefits: S$265 million'
    ]
    for b in benefits:
        doc.add_paragraph(b, style='List Bullet')

    doc.add_paragraph('\nIntangible Benefits:').bold = True
    intangible = [
        'Enhanced cybersecurity posture',
        'Improved citizen satisfaction (target NPS: +40)',
        'International recognition for digital government',
        'Enabler for future digital services (smart city, e-health)',
        'Economic competitiveness'
    ]
    for i in intangible:
        doc.add_paragraph(i, style='List Bullet')

    # KPIs
    doc.add_heading('KEY PERFORMANCE INDICATORS (KPIs)', 1)
    kpis = [
        'Authentication Success Rate (Target: 99.95%)',
        'Average Authentication Time (Target: <15 seconds, Current: 45 seconds)',
        'System Availability (Target: 99.99%)',
        'Cybersecurity Incidents (Target: 0 critical breaches)',
        'User Satisfaction Score (Target: 8.5/10, Current: 6.8/10)',
        'Cross-border Verification Success Rate (Target: 95%)'
    ]
    for kpi in kpis:
        doc.add_paragraph(kpi, style='List Number')

    doc.add_paragraph()
    doc.add_paragraph('Monitoring: Monthly dashboard reviews, quarterly steering committee, annual independent audit')

    # Stakeholders
    doc.add_heading('STAKEHOLDERS', 1)
    doc.add_paragraph('Primary:').bold = True
    primary = [
        'Government Technology Agency (GovTech) - Project Owner',
        'Smart Nation and Digital Government Office (SNDGO) - Policy Owner',
        'Cyber Security Agency (CSA) - Security Oversight'
    ]
    for s in primary:
        doc.add_paragraph(s, style='List Bullet')

    doc.add_paragraph('\nSecondary:').bold = True
    secondary = [
        'All government agencies (using SingPass)',
        'Citizens and residents (4.5 million users)',
        'Businesses (relying parties)'
    ]
    for s in secondary:
        doc.add_paragraph(s, style='List Bullet')

    # Risks
    doc.add_heading('RISKS & MITIGATION', 1)
    risks = [
        'Cybersecurity Risk (HIGH): Multi-layer security, regular audits, bug bounty program',
        'Data Privacy Risk (HIGH): Privacy-by-design, PDPA compliance, data minimization',
        'Vendor Lock-in Risk (MEDIUM): Open standards, modular architecture, multi-vendor strategy',
        'Budget Overrun Risk (MEDIUM): Fixed-price contracts, 5% contingency, phased payments',
        'User Adoption Risk (MEDIUM): Extensive user testing, training, phased rollout'
    ]
    for risk in risks:
        doc.add_paragraph(risk, style='List Number')

    # Alignment
    doc.add_heading('ALIGNMENT WITH GOVERNMENT PRIORITIES', 1)
    alignment = [
        'Digital Government Blueprint (Pillar 1: Digital to the Core)',
        'Smart Nation Strategy (Key Initiative: National Digital Identity)',
        'Cybersecurity Strategy (Critical Infrastructure Protection)',
        'Public Sector Transformation (Citizen-Centric Services)'
    ]
    for a in alignment:
        doc.add_paragraph(a, style='List Bullet')

    # Economic Lifespan
    doc.add_heading('ECONOMIC LIFESPAN', 1)
    doc.add_paragraph('10 years')

    # Feasible Approaches
    doc.add_heading('FEASIBLE APPROACHES', 1)

    doc.add_paragraph('Approach 1 (Proposed): Full upgrade with biometrics').bold = True
    doc.add_paragraph('Pros: Comprehensive solution, future-ready, high security')
    doc.add_paragraph('Cons: Higher cost, longer timeline, complexity')
    doc.add_paragraph()

    doc.add_paragraph('Approach 2 (Alternative): Incremental upgrade without biometrics').bold = True
    doc.add_paragraph('Development Cost: S$45 million (47% lower)')
    doc.add_paragraph('Annual Recurrent: S$8 million')
    doc.add_paragraph('Benefits: S$150 million annually (43% lower)')
    doc.add_paragraph('Pros: Lower risk, faster deployment, lower cost')
    doc.add_paragraph('Cons: Limited future capability, competitive disadvantage, security gaps')
    doc.add_paragraph()

    doc.add_paragraph('Benefit-Cost Ratio (BCR):').bold = True
    doc.add_paragraph('  • Approach 1: 2.8 (Benefits S$265M / Cost S$95M)')
    doc.add_paragraph('  • Approach 2: 2.5 (Benefits S$150M / Cost S$60M)')
    doc.add_paragraph()
    doc.add_paragraph('Recommendation: Approach 1 (Higher BCR, strategic alignment, future-ready)')

    return doc


def create_sample_3():
    """Sample 3: Community Health Hub"""
    doc = Document()

    # Title
    title = doc.add_heading('Integrated Community Health Hub (Queenstown)', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Summary
    doc.add_heading('PROJECT SUMMARY', 1)
    doc.add_paragraph(
        'The Ministry of Health (MOH) proposes to develop an Integrated Community Health Hub in Queenstown '
        'to provide holistic healthcare services for the aging population. The hub will combine primary care, '
        'chronic disease management, eldercare, mental health services, and wellness programs under one roof.'
    )

    # Background
    doc.add_heading('BACKGROUND', 1)
    doc.add_paragraph(
        'Queenstown has 90,000 residents with 28% aged 65+, significantly higher than national average (18%). '
        'Current healthcare facilities are fragmented with long waiting times and poor care coordination.'
    )
    doc.add_paragraph()
    doc.add_paragraph('Current Challenges:').bold = True
    challenges = [
        'Average polyclinic wait time: 2.5 hours',
        'Elderly patients visit average 4.2 different facilities per month',
        '15% hospital readmission rate for chronic conditions',
        'Limited preventive care and health screening participation (45%)'
    ]
    for c in challenges:
        doc.add_paragraph(c, style='List Bullet')

    # Objectives
    doc.add_heading('PROJECT OBJECTIVES', 1)
    objectives = [
        'Establish one-stop integrated health hub serving 50,000 residents',
        'Reduce polyclinic waiting time by 50% (from 2.5 hours to 1.25 hours)',
        'Reduce hospital readmission rate by 30% (from 15% to 10.5%)',
        'Increase preventive health screening participation to 75%',
        'Improve patient satisfaction score from 6.5/10 to 8.5/10'
    ]
    for obj in objectives:
        doc.add_paragraph(obj, style='List Number')

    # Budget
    doc.add_heading('BUDGET & COSTS', 1)
    doc.add_paragraph('Total Project Cost: S$150 million (Development + Land)').bold = True
    doc.add_paragraph()

    doc.add_paragraph('Development Cost: S$120 million').bold = True
    doc.add_paragraph('Building Construction (5,000 sqm): S$65 million')
    doc.add_paragraph('Medical Equipment & Furniture: S$25 million')
    doc.add_paragraph('Professional Fees: S$15 million')
    doc.add_paragraph('Site Preparation: S$5 million')
    doc.add_paragraph('Contingency (5%): S$6 million')
    doc.add_paragraph('GST (9%): S$4 million')
    doc.add_paragraph()

    doc.add_paragraph('Land Cost: S$30 million (acquisition of adjacent private plot)').bold = True
    doc.add_paragraph()

    doc.add_paragraph('Annual Recurrent Cost: S$18 million').bold = True
    recurrent = [
        'Staff salaries (120 FTE): S$10 million',
        'Facility operations: S$4 million',
        'Medical supplies & consumables: S$3 million',
        'IT & systems support: S$1 million'
    ]
    for r in recurrent:
        doc.add_paragraph(r, style='List Bullet')

    # Timeline
    doc.add_heading('TIMELINE', 1)
    timeline = [
        'Phase 1 - Planning (12 months): Jan - Dec 2026',
        'Phase 2 - Construction (24 months): Jan 2027 - Dec 2028',
        'Phase 3 - Commissioning (6 months): Jan - Jun 2029',
        'Phase 4 - Full Operations: Jul 2029',
        '',
        'Total Project Duration: 42 months (3.5 years)',
        'Expected Commencement: January 2026',
        'Expected Physical Completion: June 2029',
        'Expected Operational Start: July 2029'
    ]
    for item in timeline:
        if item:
            doc.add_paragraph(item, style='List Bullet')
        else:
            doc.add_paragraph()

    # Benefits
    doc.add_heading('EXPECTED BENEFITS', 1)
    doc.add_paragraph('Quantifiable Benefits (Annual after steady state):').bold = True
    benefits = [
        'Healthcare Cost Savings: S$25 million',
        '  • Reduced hospital readmissions: S$12 million',
        '  • Preventive care: S$8 million',
        '  • Operational efficiency: S$5 million',
        'Time Savings for Patients: S$10.5 million',
        'Productivity Gains: S$3 million',
        '',
        'Total Annual Benefits: S$38.5 million'
    ]
    for b in benefits:
        if b:
            doc.add_paragraph(b, style='List Bullet')
        else:
            doc.add_paragraph()

    # KPIs
    doc.add_heading('KEY PERFORMANCE INDICATORS (KPIs)', 1)
    kpis = [
        'Patient Wait Time (Target: <75 minutes, Current: 150 minutes)',
        'Hospital Readmission Rate (Target: <10.5%, Current: 15%)',
        'Patient Satisfaction Score (Target: >8.5/10, Current: 6.5/10)',
        'Health Screening Participation (Target: >75%, Current: 45%)',
        'Chronic Disease Control Rate (Target: >80%, Current: 65%)'
    ]
    for kpi in kpis:
        doc.add_paragraph(kpi, style='List Number')

    # Stakeholders
    doc.add_heading('STAKEHOLDERS', 1)
    stakeholders = [
        'Ministry of Health (MOH) - Project Owner & Funder',
        'National Healthcare Group (NHG) - Operating Partner',
        'Health Promotion Board (HPB) - Wellness Programs Partner',
        'Agency for Integrated Care (AIC) - Eldercare Coordinator',
        'Queenstown Residents\' Committee - Community Engagement'
    ]
    for s in stakeholders:
        doc.add_paragraph(s, style='List Bullet')

    # Risks
    doc.add_heading('RISKS & MITIGATION', 1)
    risks = [
        'Construction Delay Risk (HIGH): Experienced contractor, buffer in timeline',
        'Budget Overrun Risk (MEDIUM): Fixed-price contract, 5% contingency',
        'Staff Recruitment Risk (MEDIUM): Early recruitment, competitive packages',
        'Demand Risk (LOW): Community engagement, phased opening',
        'Clinical Quality Risk (LOW): Robust protocols, accreditation'
    ]
    for risk in risks:
        doc.add_paragraph(risk, style='List Number')

    # Alignment
    doc.add_heading('ALIGNMENT WITH NATIONAL STRATEGIES', 1)
    alignment = [
        'Healthier SG Strategy (Preventive Care, Community Health)',
        'Action Plan for Successful Ageing (Aging-in-Place)',
        'War on Diabetes (Chronic Disease Management)',
        'Healthcare 2020 Masterplan (Right-siting of Care)'
    ]
    for a in alignment:
        doc.add_paragraph(a, style='List Bullet')

    # Economic Lifespan
    doc.add_heading('ECONOMIC LIFESPAN', 1)
    doc.add_paragraph('30 years (building design life)')

    # Asset Write-off
    doc.add_heading('ASSET WRITE-OFF', 1)
    doc.add_paragraph('Existing Queenstown Polyclinic Branch A (built 1985):')
    doc.add_paragraph('  • Original Cost: S$8 million')
    doc.add_paragraph('  • Net Book Value: S$1.2 million')
    doc.add_paragraph('  • Write-off upon completion of new hub')
    doc.add_paragraph('  • Repurposing Plan: Convert to Senior Activity Centre')

    # Feasible Approaches
    doc.add_heading('FEASIBLE APPROACHES', 1)

    doc.add_paragraph('Approach 1 (Proposed): New Purpose-Built Integrated Hub').bold = True
    doc.add_paragraph('NPV (30 years, 4% discount): S$450 million | BCR: 2.5')
    doc.add_paragraph('Pros: Purpose-designed, full integration, scalable')
    doc.add_paragraph('Cons: Higher upfront cost, longer timeline')
    doc.add_paragraph()

    doc.add_paragraph('Approach 2 (Alternative): Refurbishment of Existing Facilities').bold = True
    doc.add_paragraph('Development: S$50 million | NPV: S$290 million | BCR: 2.1')
    doc.add_paragraph('Pros: Lower cost, faster implementation')
    doc.add_paragraph('Cons: Limited integration, aging buildings, suboptimal experience')
    doc.add_paragraph()

    doc.add_paragraph('Approach 3 (Alternative): Public-Private Partnership (PPP)').bold = True
    doc.add_paragraph('Government: S$60 million | NPV: S$320 million | BCR: 1.9')
    doc.add_paragraph('Pros: Reduced upfront expenditure, risk transfer')
    doc.add_paragraph('Cons: Higher long-term cost, less control')
    doc.add_paragraph()

    doc.add_paragraph('RECOMMENDED: Approach 1 (Highest BCR, best alignment, long-term value)').bold = True

    # Contact Persons
    doc.add_heading('CONTACT PERSONS', 1)
    doc.add_paragraph('Drafted by:')
    doc.add_paragraph('Mr. Tan Wei Ming, Director, Healthcare Infrastructure Planning Division')
    doc.add_paragraph('Ministry of Health | Tel: 6325 9220 | Email: tan_wei_ming@moh.gov.sg')
    doc.add_paragraph()
    doc.add_paragraph('Vetted by:')
    doc.add_paragraph('Dr. Sarah Lim, Deputy Director, Policy & Planning Group')
    doc.add_paragraph('Ministry of Health | Tel: 6325 9180 | Email: sarah_lim@moh.gov.sg')
    doc.add_paragraph()
    doc.add_paragraph('Cleared by:')
    doc.add_paragraph('Mr. Kenneth Chen, Chief Financial Officer')
    doc.add_paragraph('Ministry of Health | Tel: 6325 9100 | Email: kenneth_chen@moh.gov.sg')

    return doc


def main():
    """Create all 3 sample DOCX files"""
    output_dir = Path(__file__).parent.parent / 'test_inputs'
    output_dir.mkdir(exist_ok=True)

    print("Creating sample project input files (DOCX format)...")

    # Sample 1
    print("\n[1/3] Creating Sample 1: Smart Traffic Light System...")
    doc1 = create_sample_1()
    path1 = output_dir / 'sample_project_1.docx'
    doc1.save(path1)
    print(f"✓ Saved: {path1}")

    # Sample 2
    print("\n[2/3] Creating Sample 2: SingPass 3.0...")
    doc2 = create_sample_2()
    path2 = output_dir / 'sample_project_2.docx'
    doc2.save(path2)
    print(f"✓ Saved: {path2}")

    # Sample 3
    print("\n[3/3] Creating Sample 3: Community Health Hub...")
    doc3 = create_sample_3()
    path3 = output_dir / 'sample_project_3.docx'
    doc3.save(path3)
    print(f"✓ Saved: {path3}")

    print("\n" + "="*70)
    print("✅ All 3 sample DOCX files created successfully!")
    print("="*70)
    print(f"\nLocation: {output_dir}/")
    print("\nFiles created:")
    print("  1. sample_project_1.docx - Smart Traffic Light System")
    print("  2. sample_project_2.docx - SingPass 3.0 Upgrade")
    print("  3. sample_project_3.docx - Community Health Hub")
    print("\nThese mock-up documents can be used as test inputs for the system.")


if __name__ == '__main__':
    main()
