#!/usr/bin/env python3
"""Resolve sector and GICS industry focus presets for the sector report workflow."""

from __future__ import annotations

import argparse
import re
import sys


def normalize_token(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


SECTOR_FOCUS_OPTIONS: dict[str, dict[str, object]] = {
    "communication_services": {
        "label": "Communication Services",
        "balanced_instruction": (
            "For the communication services report, keep the analysis balanced across diversified telecom, "
            "wireless, media, entertainment, and interactive platforms so the output remains a true sector-level report."
        ),
        "industries": {
            "diversified_telecommunication_services": {
                "label": "Diversified Telecommunication Services",
                "focus": "wireline networks, fiber, wholesale transport, enterprise connectivity, and cash-flow durability in scaled telecom infrastructure",
            },
            "wireless_telecommunication_services": {
                "label": "Wireless Telecommunication Services",
                "focus": "mobile networks, spectrum economics, subscriber monetization, customer service automation, and AI-enabled network operations",
            },
            "media": {
                "label": "Media",
                "focus": "advertising economics, publishing workflows, rights management, audience targeting, and content production support tools",
            },
            "entertainment": {
                "label": "Entertainment",
                "focus": "streaming, gaming, studios, experiential content, and the tension between lower production cost and franchise value protection",
            },
            "interactive_media_and_services": {
                "label": "Interactive Media & Services",
                "focus": "digital platforms, search, social, user engagement loops, ad targeting, creator ecosystems, and distribution power",
            },
        },
    },
    "consumer_discretionary": {
        "label": "Consumer Discretionary",
        "balanced_instruction": (
            "For the consumer discretionary report, keep the analysis balanced across autos, retail, travel, leisure, services, and household durables rather than collapsing into a single consumer niche."
        ),
        "industries": {
            "automobile_components": {
                "label": "Automobile Components",
                "focus": "supplier engineering, design complexity, procurement, warranty support, and how AI may alter content value within the auto stack",
            },
            "automobiles": {
                "label": "Automobiles",
                "focus": "vehicle design, manufacturing efficiency, pricing, digital sales, software content, and competitive separation in auto platforms",
            },
            "household_durables": {
                "label": "Household Durables",
                "focus": "appliances, furnishings, home products, product design cycles, channel management, and service economics",
            },
            "leisure_products": {
                "label": "Leisure Products",
                "focus": "recreation equipment, product innovation, enthusiast demand, channel inventory, and branded merchandising efficiency",
            },
            "distributors": {
                "label": "Distributors",
                "focus": "catalog intelligence, procurement productivity, sales enablement, fulfillment accuracy, and working-capital turns",
            },
            "diversified_consumer_services": {
                "label": "Diversified Consumer Services",
                "focus": "education, training, staffing, and consumer service workflows where AI may compress labor intensity or reshape service delivery",
            },
            "hotels_restaurants_and_leisure": {
                "label": "Hotels, Restaurants & Leisure",
                "focus": "guest service, labor scheduling, pricing, demand forecasting, marketing efficiency, and unit-level margin leverage",
            },
            "broadline_retail": {
                "label": "Broadline Retail",
                "focus": "large-scale merchandising, search and recommendation, fulfillment economics, advertising monetization, and vendor power",
            },
            "specialty_retail": {
                "label": "Specialty Retail",
                "focus": "category expertise, conversion optimization, inventory planning, service automation, and omnichannel execution",
            },
            "textiles_apparel_and_luxury_goods": {
                "label": "Textiles, Apparel & Luxury Goods",
                "focus": "design and merchandising speed, brand control, pricing power, customer acquisition efficiency, and premium positioning risk",
            },
        },
    },
    "consumer_staples": {
        "label": "Consumer Staples",
        "balanced_instruction": (
            "For the consumer staples report, keep the analysis balanced across staple retail, food, beverage, household, personal care, and tobacco so the report stays sector-wide."
        ),
        "industries": {
            "consumer_staples_distribution_and_retail": {
                "label": "Consumer Staples Distribution & Retail",
                "focus": "high-frequency retail operations, demand forecasting, merchandising, shrink reduction, labor efficiency, and private-label execution",
            },
            "beverages": {
                "label": "Beverages",
                "focus": "brand investment efficiency, route-to-market execution, demand sensing, pricing, and promotional optimization",
            },
            "food_products": {
                "label": "Food Products",
                "focus": "formulation, procurement, plant planning, demand forecasting, and margin defense in a brand-heavy but cost-sensitive category",
            },
            "tobacco": {
                "label": "Tobacco",
                "focus": "regulatory sensitivity, brand retention, channel execution, and efficiency gains in mature cash-generative business models",
            },
            "household_products": {
                "label": "Household Products",
                "focus": "brand management, supply chain planning, product support, promotional ROI, and category shelf competition",
            },
            "personal_care_products": {
                "label": "Personal Care Products",
                "focus": "consumer marketing, formulation and product design, social commerce, pricing, and customer lifetime value",
            },
        },
    },
    "energy": {
        "label": "Energy",
        "balanced_instruction": (
            "For the energy report, keep the analysis balanced across energy equipment and services plus oil, gas, and consumable fuels rather than focusing only on one side of the value chain."
        ),
        "industries": {
            "energy_equipment_and_services": {
                "label": "Energy Equipment & Services",
                "focus": "service intensity, field productivity, maintenance workflows, reservoir and drilling support, and cyclicality in capital spending",
            },
            "oil_gas_and_consumable_fuels": {
                "label": "Oil, Gas & Consumable Fuels",
                "focus": "upstream and downstream operations, trading and logistics, maintenance planning, and the limits of AI versus commodity-cycle exposure",
            },
        },
    },
    "financials": {
        "label": "Financials",
        "balanced_instruction": (
            "For the financials report, keep the analysis balanced across banks, payments and financial services, capital markets, mortgage REITs, consumer finance, and insurance."
        ),
        "industries": {
            "banks": {
                "label": "Banks",
                "focus": "servicing, onboarding, relationship management, credit workflows, compliance cost, and deposit-franchise economics",
            },
            "financial_services": {
                "label": "Financial Services",
                "focus": "payments, financial infrastructure, transaction processing, embedded finance workflows, and service-economics automation",
            },
            "capital_markets": {
                "label": "Capital Markets",
                "focus": "advisory workflows, research, trading operations, market infrastructure, distribution advantage, and data monetization",
            },
            "mortgage_real_estate_investment_trusts_reits": {
                "label": "Mortgage Real Estate Investment Trusts (REITs)",
                "focus": "portfolio surveillance, underwriting support, servicing efficiency, and risk management in spread-driven business models",
            },
            "consumer_finance": {
                "label": "Consumer Finance",
                "focus": "origination, underwriting, collections, fraud mitigation, customer acquisition efficiency, and regulatory conduct risk",
            },
            "insurance": {
                "label": "Insurance",
                "focus": "claims handling, underwriting support, distribution productivity, policy servicing, and loss-ratio implications",
            },
        },
    },
    "healthcare": {
        "label": "Healthcare",
        "balanced_instruction": (
            "For the healthcare report, keep the analysis balanced across providers and services, equipment, healthcare technology, pharmaceuticals, biotechnology, and life sciences tools rather than narrowing to a single healthcare workflow."
        ),
        "industries": {
            "healthcare_equipment_and_supplies": {
                "label": "Healthcare Equipment & Supplies",
                "focus": "devices, instruments, procedure support, diagnostics-enabling equipment, and how AI changes product capability or clinical workflow value",
            },
            "healthcare_providers_and_services": {
                "label": "Healthcare Providers & Services",
                "focus": "care delivery, payer-provider administration, revenue cycle, utilization management, staffing pressure, and workflow economics",
            },
            "healthcare_technology": {
                "label": "Healthcare Technology",
                "focus": "clinical software, data platforms, workflow systems, interoperability, trusted distribution, and software ROI in care settings",
            },
            "biotechnology": {
                "label": "Biotechnology",
                "focus": "target discovery, molecule design, biomarker work, trial design, R&D productivity, and probability-of-success debates",
            },
            "pharmaceuticals": {
                "label": "Pharmaceuticals",
                "focus": "pipeline economics, lifecycle management, commercial operations, medical affairs, and scale advantages in drug development",
            },
            "life_sciences_tools_and_services": {
                "label": "Life Sciences Tools & Services",
                "focus": "research tools, CRO workflows, lab productivity, data assets, scientific software, and enabling infrastructure for discovery and trials",
            },
        },
    },
    "industrials": {
        "label": "Industrials",
        "balanced_instruction": (
            "For the industrials report, keep the analysis balanced across capital goods, services, transportation, and distribution instead of reducing the sector to factory automation alone."
        ),
        "industries": {
            "aerospace_and_defense": {
                "label": "Aerospace & Defense",
                "focus": "engineering workflows, sustainment, procurement complexity, mission-critical support, and regulatory constraints on autonomy",
            },
            "building_products": {
                "label": "Building Products",
                "focus": "specification-driven selling, channel support, manufacturing efficiency, and service differentiation in installed-base markets",
            },
            "construction_and_engineering": {
                "label": "Construction & Engineering",
                "focus": "bid and design workflows, project execution, field productivity, documentation burden, and margin risk control",
            },
            "electrical_equipment": {
                "label": "Electrical Equipment",
                "focus": "component design, project support, installed-base service, demand planning, and exposure to electrification and infrastructure themes",
            },
            "industrial_conglomerates": {
                "label": "Industrial Conglomerates",
                "focus": "portfolio management, shared services productivity, engineering leverage, and capital allocation across diverse industrial assets",
            },
            "machinery": {
                "label": "Machinery",
                "focus": "engineering speed, aftermarket service, predictive maintenance support, sales configuration, and installed-base monetization",
            },
            "trading_companies_and_distributors": {
                "label": "Trading Companies & Distributors",
                "focus": "catalog intelligence, pricing, procurement, sales productivity, and working-capital efficiency",
            },
            "commercial_services_and_supplies": {
                "label": "Commercial Services & Supplies",
                "focus": "route density, service workflows, dispatching, document-heavy operations, and labor cost leverage",
            },
            "professional_services": {
                "label": "Professional Services",
                "focus": "staffing, consulting, information services, workflow automation, and pricing pressure on labor-intensive knowledge work",
            },
            "air_freight_and_logistics": {
                "label": "Air Freight & Logistics",
                "focus": "network planning, customs and documentation workflows, customer service, and yield management",
            },
            "passenger_airlines": {
                "label": "Passenger Airlines",
                "focus": "revenue management, crew and maintenance planning, customer service, and operational resilience",
            },
            "marine_transportation": {
                "label": "Marine Transportation",
                "focus": "fleet deployment, routing, documentation, port coordination, and cyclicality versus AI-enabled efficiency",
            },
            "ground_transportation": {
                "label": "Ground Transportation",
                "focus": "routing, dispatch, labor productivity, service quality, pricing, and network utilization",
            },
            "transportation_infrastructure": {
                "label": "Transportation Infrastructure",
                "focus": "traffic management, asset monitoring, pricing systems, throughput optimization, and concession economics",
            },
        },
    },
    "information_technology": {
        "label": "Information Technology",
        "balanced_instruction": (
            "For the information technology report, keep the analysis balanced across IT services, software, communications equipment, hardware, electronic components, and semiconductors as a full GICS sector view."
        ),
        "industries": {
            "it_services": {
                "label": "IT Services",
                "focus": "consulting, outsourcing, managed services, implementation work, labor leverage, and client workflow transformation",
            },
            "software": {
                "label": "Software",
                "focus": "application and infrastructure software, workflow copilots, pricing power, feature monetization, and platform defensibility",
            },
            "communications_equipment": {
                "label": "Communications Equipment",
                "focus": "network gear, data traffic growth, service support, edge infrastructure, and AI-driven demand for connectivity hardware",
            },
            "technology_hardware_storage_and_peripherals": {
                "label": "Technology Hardware, Storage & Peripherals",
                "focus": "devices, systems, enterprise hardware refresh, edge compute, storage demand, and channel economics",
            },
            "electronic_equipment_instruments_and_components": {
                "label": "Electronic Equipment, Instruments & Components",
                "industry_group": "Technology Hardware & Equipment",
                "industry": "Electronic Equipment, Instruments & Components",
                "sub_industry": "Electronic Equipment & Instruments",
                "focus": "sensors, test equipment, components, design complexity, industrial end-market exposure, and embedded intelligence value capture",
            },
            "semiconductors_and_semiconductor_equipment": {
                "label": "Semiconductors & Semiconductor Equipment",
                "focus": "accelerated computing demand, memory and networking exposure, EDA productivity, equipment intensity, and cyclicality beyond AI headlines",
            },
        },
    },
    "materials": {
        "label": "Materials",
        "balanced_instruction": (
            "For the materials report, keep the analysis balanced across chemicals, construction materials, packaging, metals and mining, and paper and forest products."
        ),
        "industries": {
            "chemicals": {
                "label": "Chemicals",
                "focus": "process optimization, formulation support, customer technical service, pricing discipline, and plant productivity",
            },
            "construction_materials": {
                "label": "Construction Materials",
                "focus": "plant operations, logistics, project demand visibility, channel support, and margin management in bulky-product markets",
            },
            "containers_and_packaging": {
                "label": "Containers & Packaging",
                "focus": "design workflows, procurement, plant scheduling, customer service, and efficiency in high-volume manufacturing",
            },
            "metals_and_mining": {
                "label": "Metals & Mining",
                "focus": "ore-body modeling, maintenance planning, safety workflows, trading and logistics support, and capital intensity limits",
            },
            "paper_and_forest_products": {
                "label": "Paper & Forest Products",
                "focus": "forestry planning, mill operations, logistics, customer service, and cost control in mature commodity-linked businesses",
            },
        },
    },
    "real_estate": {
        "label": "Real Estate",
        "balanced_instruction": (
            "For the real estate report, keep the analysis balanced across equity REITs and real estate management and development so the report stays at the sector level."
        ),
        "industries": {
            "equity_real_estate_investment_trusts_reits": {
                "label": "Equity Real Estate Investment Trusts (REITs)",
                "focus": "property operations, leasing, tenant service, maintenance workflows, occupancy management, and asset-level NOI implications",
            },
            "real_estate_management_and_development": {
                "label": "Real Estate Management & Development",
                "focus": "broker workflows, marketing, development planning, underwriting support, and project execution productivity",
            },
        },
    },
    "utilities": {
        "label": "Utilities",
        "balanced_instruction": (
            "For the utilities report, keep the analysis balanced across electric, gas, water, multi-utility, and independent power and renewable operators."
        ),
        "industries": {
            "electric_utilities": {
                "label": "Electric Utilities",
                "focus": "grid operations, outage response, customer service, planning, maintenance workflows, and regulated return frameworks",
            },
            "gas_utilities": {
                "label": "Gas Utilities",
                "focus": "network integrity, field service, demand planning, customer service, and compliance-heavy operating models",
            },
            "multi_utilities": {
                "label": "Multi-Utilities",
                "focus": "shared-service productivity, cross-network operations, customer workflows, and capital allocation across regulated assets",
            },
            "water_utilities": {
                "label": "Water Utilities",
                "focus": "asset monitoring, service response, billing support, infrastructure planning, and reliability in regulated local systems",
            },
            "independent_power_and_renewable_electricity_producers": {
                "label": "Independent Power and Renewable Electricity Producers",
                "focus": "generation dispatch, power marketing, asset monitoring, maintenance planning, and AI-linked electricity-demand narratives",
            },
        },
    },
}


def build_focus_instruction(
    sector_key: str,
    industry_key: str,
    report_mode: str = "investment_implications",
) -> str:
    sector_config = SECTOR_FOCUS_OPTIONS[sector_key]

    if industry_key == "balanced":
        return str(sector_config["balanced_instruction"])

    industries = sector_config["industries"]
    industry_config = industries[industry_key]
    if report_mode == "frontier_possibilities":
        return (
            f"For the {sector_config['label']} report, place extra emphasis on the {industry_config['label']} industry, "
            f"especially {industry_config['focus']}, while still covering adjacent workflows, the broader sector context, "
            "and realistic operational constraints that shape what could become possible."
        )
    return (
        f"For the {sector_config['label']} report, place extra emphasis on the {industry_config['label']} industry, "
        f"especially {industry_config['focus']}, while still covering the full sector, adjacent industries, and the main sector-level value-capture question."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve the workflow's sector-level industry focus preset into concrete instructions."
    )
    parser.add_argument(
        "--sector",
        required=True,
        help="Selected sector slug.",
    )
    parser.add_argument(
        "--industry-focus",
        required=True,
        help="Selected industry focus slug or balanced.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sector_key = normalize_token(args.sector)
    industry_key = normalize_token(args.industry_focus)

    if sector_key not in SECTOR_FOCUS_OPTIONS:
        available_sectors = ", ".join(sorted(SECTOR_FOCUS_OPTIONS))
        print(
            f"Unsupported sector '{args.sector}'. Available sectors: {available_sectors}",
            file=sys.stderr,
        )
        return 1

    if industry_key == "balanced":
        print(build_focus_instruction(sector_key, industry_key))
        return 0

    industries = SECTOR_FOCUS_OPTIONS[sector_key]["industries"]
    if industry_key not in industries:
        available_focuses = ", ".join(["balanced", *sorted(industries)])
        print(
            f"Industry focus '{args.industry_focus}' is not valid for sector '{args.sector}'. "
            f"Allowed values: {available_focuses}",
            file=sys.stderr,
        )
        return 1

    print(build_focus_instruction(sector_key, industry_key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
