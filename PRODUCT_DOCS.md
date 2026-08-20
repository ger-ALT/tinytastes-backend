# TinyTastes AI — Product, Market & Business Documentation

> Living document. Update as the product evolves.
> Last updated: May 2026

---

## Table of Contents
1. [Product Overview](#1-product-overview)
2. [The Problem We Solve](#2-the-problem-we-solve)
3. [Market Research — India](#3-market-research--india)
4. [Target Users](#4-target-users)
5. [Product Features](#5-product-features)
6. [Revenue Model](#6-revenue-model)
7. [Cost Structure](#7-cost-structure)
8. [Path to Profitability](#8-path-to-profitability)
9. [Competitive Landscape](#9-competitive-landscape)
10. [Regional Strategy (India)](#10-regional-strategy-india)
11. [Tech Stack](#11-tech-stack)
12. [Go-to-Market Plan](#12-go-to-market-plan)
13. [Legal & Compliance](#13-legal--compliance)
14. [6-Month Roadmap](#14-6-month-roadmap)

---

## 1. Product Overview

**TinyTastes AI** is an LLM-powered baby food recipe engine built specifically for Indian parents introducing solid foods to infants aged 6–24 months.

The app takes a parent's available ingredients and baby's profile (age, region, allergens) and returns a safe, age-appropriate recipe — instantly from a deterministic database for common combinations, or AI-generated for edge cases.

**Core differentiator:** Region-aware recipes that understand Indian kitchens — ragi in Karnataka, dalia in Punjab, coconut in Kerala — not Western ingredient assumptions.

**Business model:** Free tier with affiliate commerce revenue + ₹99/month premium subscription.

---

## 2. The Problem We Solve

### The feeding window is high-stakes and underserved
- WHO recommends exclusive breastfeeding for 6 months, then introducing complementary foods
- The 6–24 month window is nutritionally critical — it shapes growth, immunity, and eating habits for life
- Most Indian parents navigate this alone — through Google searches, WhatsApp forwards, and advice from relatives

### The information available is wrong for India
- Most baby food content online is US/UK-centric (avocado toast, butternut squash)
- Indian parents need guidance around ragi, khichuri, dalia, sattu, drumstick leaves
- Regional diversity is massive — what's available in a Chennai kitchen is fundamentally different from a Ludhiana kitchen
- No existing app addresses this

### The pediatrician gap
- India has 1 pediatrician per ~11,000 children (WHO recommends 1 per 1,000)
- A typical pediatric consultation is 7–10 minutes — feeding guidance gets 90 seconds
- Parents leave clinics with no structured plan for what to feed their baby this week

### The consequence of bad information
- India has one of the world's highest rates of child malnutrition: 35% of children under 5 are stunted (NFHS-5, 2021)
- Early complementary feeding done wrong contributes directly to this
- TinyTastes is not just an app — it's public health infrastructure

---

## 3. Market Research — India

### Market size
| Metric | Number | Source |
|---|---|---|
| Annual births in India | ~25 million | Census/SRS 2024 |
| Babies in 6–24 month window at any time | ~37–40 million | Derived |
| Smartphone-owning parents (urban+semi-urban) | ~180 million households | IAMAI 2024 |
| Parents who searched "baby food" online (monthly) | ~15 million queries | Google Trends estimate |
| Existing dedicated baby food apps (India) | 0 with AI | Our research |

### Adjacent market validation
- **Happa Foods** (Indian baby food brand) raised ₹7 crore in seed funding in 2021 — demand for quality Indian baby food is proven
- **Slurrp Farm** grew to ₹100 crore revenue in 5 years selling packaged baby cereals
- These are product companies, not software. No one owns the guidance/recipe layer.

### Quick commerce tailwind (affiliate revenue)
- Blinkit, Zepto, Swiggy Instamart combined GMV: ~₹40,000 crore in FY2024
- Growing 60% YoY
- Average basket size for grocery: ₹400–600
- Parents are already buying ingredients online — we insert at the point of need

### Willingness to pay research
- Indian parents spend ₹2,000–5,000/month on premium baby food (Happa, Slurrp Farm, Munchkin)
- Digital spending on parenting apps is lower, but growing — BabyChakra has 30M+ users and monetizes via brand partnerships and e-commerce
- ₹99/month is at the "don't have to think about it" price point for urban parents

---

## 4. Target Users

### Primary: Urban/semi-urban first-time mothers, 24–35 years
- Smartphone-first, comfortable with apps
- Anxious about doing complementary feeding "correctly"
- Has access to a supermarket or quick-commerce delivery
- Speaks English or Hindi
- Lives in Tier 1 or Tier 2 city

### Secondary: Pediatric clinic nurses and counsellors
- Recommends the app to parents post-consultation
- B2B channel — clinic pays ₹2,000–5,000/month for white-label access
- Gives the app medical credibility

### Tertiary: Anganwadi workers (government ICDS program)
- Reaches low-income, rural mothers
- Government partnership opportunity (long sales cycle, high impact)
- Could be grant-funded, not commercially driven

### User persona: Priya, 28, Bengaluru
- First-time mother, baby Arjun is 8 months old
- Works in IT, on maternity leave
- Panicked when Arjun started refusing purees at 7 months
- Googled "8 month baby food ideas India" — got 10 contradictory articles
- Would pay ₹99/month for something that tells her exactly what to make with what's in her fridge

---

## 5. Product Features

### MVP (launch)
- [ ] Phone OTP login (Indian mobile number)
- [ ] Baby profile (name, DOB, state/region, known allergens)
- [ ] Ingredient selector → AI/DB recipe generation
- [ ] Recipe card with preparation steps + allergen badges
- [ ] Affiliate "Buy on Blinkit" links for missing ingredients
- [ ] Save recipe + "Tried it" tracking
- [ ] Recipe history per baby

### Phase 2 (month 3–6)
- [ ] Hindi language support
- [ ] Meal planner (7-day view)
- [ ] Multiple baby profiles (for subsequent children)
- [ ] PDF weekly cookbook export (₹29 one-off or premium)
- [ ] WhatsApp recipe delivery bot
- [ ] Pediatric clinic B2B portal

### Phase 3 (month 6–12)
- [ ] Tamil + Telugu language support
- [ ] Milestone notifications ("Arjun turns 9 months in 3 days — here's what to introduce")
- [ ] Community (parent forums by region/age group)
- [ ] Dietitian video consultation booking (marketplace)
- [ ] Packaged product recommendations (Slurrp Farm, Happa Foods affiliate)

---

## 6. Revenue Model

### Stream 1: Quick Commerce Affiliate (primary, cash-flow from day 1)
Every recipe card shows "Buy missing ingredients on Blinkit/BigBasket."
- Apply to: Blinkit Affiliate Program, BigBasket Partner API, Swiggy Instamart
- Commission: 2–5% of cart value
- Avg cart value for a recipe's missing items: ₹150–300
- Commission per click-through: ₹8–15
- **Projection at 10,000 recipe views/day, 20% CTR:** ₹500–1,500/day = ₹15,000–45,000/month

### Stream 2: Freemium Subscription (₹99/month)
| Free | Premium (₹99/mo) |
|---|---|
| 20 DB recipes | Unlimited AI recipes |
| 1 baby profile | Multiple baby profiles |
| Generic ingredient set | State-level regional ingredients |
| — | 7-day meal planner |
| — | PDF export |
| — | WhatsApp daily recipe |

- Target: 2–5% conversion of MAU
- At 20,000 MAU → 400–1,000 paying users → **₹39,600–99,000/month**

### Stream 3: B2B Clinic Licensing (₹3,000–5,000/month per clinic)
- White-label app branded for a clinic (e.g., "Dr. Sharma's Baby Nutrition Guide")
- Doctor recommends to patients as QR code in prescription
- Doubles as distribution and credibility
- Target: 20 clinics by month 12 → **₹60,000–1,00,000/month**

### Stream 4: PDF Cookbook Export (₹29 one-off)
- "My Baby's First Year Cookbook" — generates a personalized PDF of all tried recipes
- Single Stripe Checkout transaction, no subscription
- Emotional product — parents want a keepsake

### Stream 5 (future): Brand Partnerships
- Slurrp Farm, Happa Foods, Nestle NAN pay for sponsored recipe cards
- Only after 100K+ MAU — don't pollute trust early

---

## 7. Cost Structure

### Monthly costs at MVP stage (~₹1,500/month)
| Service | Purpose | Cost |
|---|---|---|
| Railway (Starter) | FastAPI backend | ₹415/month ($5) |
| Framer (Mini) | Landing page | ₹415/month ($5) |
| Domain tinytastes.in | BigRock/GoDaddy | ₹58/month (₹700/yr) |
| Claude Haiku API | AI recipe generation | ~₹500/month (100 calls/day) |
| MSG91 | SMS OTP for auth | ~₹75/month (500 OTPs) |
| Vercel (Hobby) | Next.js frontend | Free |
| Supabase (Free) | Database + Auth | Free |
| GitHub | Code hosting | Free |
| Zoho Mail | hello@tinytastes.in | Free |
| **Total** | | **~₹1,463/month** |

### At 1,000 DAU (~₹6,500/month)
| Service | Cost |
|---|---|
| Railway (Pro) | ₹1,660/month ($20) |
| Supabase (Pro) | ₹2,075/month ($25) |
| Claude Haiku API (400 calls/day) | ₹2,000/month |
| Framer + domain | ₹475/month |
| SMS OTP | ₹300/month |
| **Total** | **~₹6,510/month** |

### At 10,000 DAU (~₹25,000/month)
- Need to evaluate moving backend to AWS Mumbai (ap-south-1) for latency
- Supabase Team plan: $599/month = ₹49,700 — at this point, consider self-hosted Postgres on AWS
- Claude Haiku (4,000 calls/day): ~₹20,000/month
- BUT: affiliate revenue at this scale covers costs 3–5x over

---

## 8. Path to Profitability

### Unit economics
- **CAC (Customer Acquisition Cost):** ₹0 at launch (organic — Reddit, WhatsApp groups)
- **LTV (Lifetime Value) of free user:** ₹15–50 (affiliate click-throughs over lifetime)
- **LTV of paid user:** ₹99 × avg 8 months retention = ₹792
- **LTV:CAC ratio target:** >3:1 before spending on ads

### Break-even milestones
| Milestone | Revenue | Cost | Status |
|---|---|---|---|
| 15 paying users | ₹1,485/month | ₹1,463/month | Breaks even on fixed costs |
| 500 daily recipe views (affiliate) | ~₹1,500/month | — | Covers variable costs |
| 200 paying users + affiliate | ~₹25,000/month | ~₹3,000/month | First real profit |
| 10 B2B clinic contracts | ₹40,000/month | ~₹0 incremental | High-margin revenue |

### 12-month P&L projection (realistic)
| Month | MAU | Paying Users | Affiliate Rev | Subscription Rev | B2B Rev | Total Rev | Cost | Profit |
|---|---|---|---|---|---|---|---|---|
| 1–2 | 500 | 0 | ₹5,000 | ₹0 | ₹0 | ₹5,000 | ₹1,500 | +₹3,500 |
| 3–4 | 2,000 | 40 | ₹15,000 | ₹3,960 | ₹0 | ₹18,960 | ₹3,000 | +₹15,960 |
| 5–6 | 8,000 | 200 | ₹40,000 | ₹19,800 | ₹10,000 | ₹69,800 | ₹7,000 | +₹62,800 |
| 9–10 | 25,000 | 750 | ₹80,000 | ₹74,250 | ₹30,000 | ₹1,84,250 | ₹20,000 | +₹1,64,250 |
| 12 | 50,000 | 1,500 | ₹1,50,000 | ₹1,48,500 | ₹50,000 | ₹3,48,500 | ₹30,000 | +₹3,18,500 |

> Note: These are targets, not guarantees. Affiliate CTR and subscription conversion are the key variables to validate in months 1–3.

---

## 9. Competitive Landscape

### Direct competitors (India)
| Product | What they do | Gap |
|---|---|---|
| BabyChakra | Parenting community + doctor Q&A | No recipe engine, no regional food |
| Tinystep | Parenting articles | Content only, no personalization |
| Happa Foods | Packaged baby food products | Product, not guidance |
| Slurrp Farm | Packaged baby cereals | Product, not guidance |

### Indirect competitors
| Product | Geography | Gap |
|---|---|---|
| Solid Starts | US | US-centric ingredients, no India |
| Baby Led Weaning (Gill Rapley) | UK | Book, not an app |
| Yumi | US | Meal delivery, not guidance |

### Our moat
1. **Regional Indian recipe database** — takes 6–12 months to build properly; first-mover advantage
2. **Deterministic fast-path** — 80% of requests served in <5ms at zero AI cost; unit economics better than pure LLM apps
3. **B2B clinic channel** — once 10+ clinics are onboarded, competitor switching cost is high (doctors don't change tools easily)
4. **Data flywheel** — every "Tried it" rating improves the DB; network effect on recipe quality

---

## 10. Regional Strategy (India)

Priority order based on population density + smartphone penetration:

### Tier 1 regions (launch with these)
| Region | Key ingredients to support | Population |
|---|---|---|
| North India (UP, Delhi, Punjab, Haryana) | Dalia, makki, ghee, sattu | ~400M |
| South India — Karnataka, Tamil Nadu | Ragi, rice, coconut, drumstick | ~130M |
| Maharashtra + Gujarat | Jowar, bajra, peanuts, jaggery | ~180M |

### Tier 2 regions (month 4–6)
- Bengal: Khichuri, mustard oil, posto (poppy seeds)
- Kerala: Nendran banana, coconut milk, kodampuli
- Rajasthan: Bajra, ker sangri, buttermilk

### Language rollout
1. English (launch)
2. Hindi (month 3–4) — covers 40%+ of target market
3. Tamil (month 6) — large urban tech-savvy base
4. Telugu (month 8)
5. Kannada, Marathi (month 10–12)

### Region codes used in API
```
IN-UP  Uttar Pradesh
IN-DL  Delhi
IN-PB  Punjab
IN-HR  Haryana
IN-MH  Maharashtra
IN-GJ  Gujarat
IN-KA  Karnataka
IN-TN  Tamil Nadu
IN-KL  Kerala
IN-WB  West Bengal
IN-RJ  Rajasthan
IN-TS  Telangana
IN-AP  Andhra Pradesh
```

---

## 11. Tech Stack

### Backend (built)
```
FastAPI (Python)        REST API
SQLite → PostgreSQL     Recipe DB + user data
Claude Haiku API        AI recipe generation (replaces Ollama for production)
reportlab               PDF cookbook export
```

### Frontend (to build)
```
Next.js 14 (App Router) React framework
Tailwind CSS            Styling
shadcn/ui               Component library
Supabase JS             Auth + DB client
```

### Infrastructure
```
Railway                 Backend hosting (Mumbai region)
Vercel                  Frontend hosting (global CDN)
Supabase                Postgres DB + Auth (Mumbai region)
Framer                  Landing page
MSG91                   SMS OTP for Indian phone numbers
```

### API integrations (planned)
```
Blinkit Affiliate       Grocery affiliate links
BigBasket Partner API   Grocery affiliate links
Anthropic API           Claude Haiku (AI recipes)
Stripe                  Payments (subscription + one-off PDF)
```

---

## 12. Go-to-Market Plan

### Month 1–3: Organic, zero-spend
**Channels:**
- Reddit: r/IndiaMothers, r/IndianParenting, r/beyondthebump_india
- Facebook Groups: "Indian Baby-led Weaning", "First Foods India", state-specific parenting groups
- Instagram Reels: 30-second screen recordings showing the app generating a recipe ("I told it I had ragi and banana — look what it made for my 9-month-old")
- Product Hunt launch (global visibility, Indian developer community is active here)

**Clinic outreach:**
- Cold email/WhatsApp 50 pediatric clinics in your city
- Offer 3-month free trial of B2B portal
- Goal: 5 clinics using it and recommending to patients

**Metrics to validate:**
- D7 retention > 20% (users come back after 1 week)
- Affiliate CTR > 15% (people click "Buy on Blinkit")
- If both are green → scale; if not → fix product before spending on acquisition

### Month 3–6: Low-spend amplification
- Partner with 3–5 Indian pediatric dietitians on Instagram (5K–50K followers)
- Offer them free premium access + ₹10 affiliate commission per signup they drive
- WhatsApp channel for "Daily Baby Recipe" (use WhatsApp Business API)

### Month 6–12: Paid acquisition (only after retention is proven)
- Google Ads: "6 month baby food ideas india", "baby first food recipes india"
- CPC on these terms is low (₹8–15) vs. Western markets
- Facebook/Instagram ads targeted to: mothers, age 22–35, metro + Tier 2 cities, with infants

---

## 13. Legal & Compliance

### Medical disclaimer (mandatory on every recipe output)
> "TinyTastes AI provides general recipe suggestions for informational purposes only. It is not a substitute for professional medical advice. Always consult your pediatrician before introducing new foods, especially if your baby has allergies or health conditions."

### Data privacy
- Collect only: phone number, baby name, DOB, region, allergens
- Do not share with third parties (except Blinkit/BigBasket for affiliate redirect — this is standard)
- Privacy Policy must comply with India's DPDP Act 2023 (Digital Personal Data Protection Act)
- Add a "Delete my data" option before launch

### FSSAI (food safety)
- TinyTastes provides recipes, not food products — no FSSAI license needed
- Do not make claims like "prevents malnutrition" or "clinically tested" — describe, don't prescribe

### Allergen liability
- The `allergen_flags` field is a legal surface
- Add disclaimer: "Allergen flags are AI-generated and may be incomplete. Always verify with a healthcare professional for allergy-related concerns."

### Terms of service
- Use a standard SaaS ToS template (Docracy or Termly) customized for India
- Key clause: no liability for medical outcomes from recipe suggestions

---

## 14. 6-Month Roadmap

```
Month 1   ─── Backend: Claude API swap, baby profiles, saved recipes
              Frontend: Next.js scaffold, all 5 screens
              Data: 100 Indian regional recipes in DB
              Infra: Railway + Vercel + Supabase deployed

Month 2   ─── Soft launch: 3 WhatsApp parenting groups + Reddit
              Affiliate links: Blinkit + BigBasket live
              Goal: 500 MAU, measure D7 retention

Month 3   ─── Iterate on retention gaps
              B2B: 5 clinic pilots live
              Analytics: PostHog (free, self-host) for funnel visibility

Month 4   ─── Hindi UI (covers 40% of market you're missing)
              Subscription billing: Stripe (₹99/month tier)
              WhatsApp bot: daily recipe for subscribed users

Month 5   ─── Meal planner feature
              PDF export (Stripe one-off ₹29)
              Goal: 5,000 MAU, 100 paying users

Month 6   ─── Review metrics, decide: double down organically or raise seed
              Fundraise target: ₹50L at ₹2–3Cr valuation if metrics are good
              Use capital for: Hindi content, regional recipe expansion, ads
```

---

*Document owner: TinyTastes founding team*
*Next review: when MAU crosses 1,000*
