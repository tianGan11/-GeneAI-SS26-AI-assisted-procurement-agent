# Legal Compliance Report — Data Sourcing & Web Scraping

**Project:** Fuyao Procurement Cloud — AI-assisted Procurement Agent
**Course:** GenAI SS26, TUM
**Document type:** Compliance statement for academic submission

> This report explains the legal risks of web scraping for supplier data in the EU and documents
> the concrete measures our project adopted to avoid them. It demonstrates a *compliance-by-design*
> approach rather than after-the-fact justification.
>
> ⚠️ **Disclaimer:** This is a technical compliance analysis for academic purposes, **not formal
> legal advice.**

---

## 1. Scope & Context

Our system sources two kinds of data: (a) supplier master data and (b) standard-product quotes,
covering the glass / automotive-glass supply chain in Europe. Candidate sources include B2B
directories (wlw.de, Europages, Kompass), public company registries, and company websites.
Because both targets and users are in the **EU/Germany**, and the data may include **personal data
of contact persons**, the work falls under **GDPR and EU/German law**.

---

## 2. Applicable Legal Framework

Four layers constrain web scraping in the EU. "Publicly visible" does **not** mean "free to take
and reuse."

| # | Layer | Key rule |
|---|---|---|
| 1 | **Terms of Service (contract)** | Per *Ryanair v PR Aviation* (CJEU C‑30/14), a site may contractually restrict use even of data **not** protected by copyright or database right. |
| 2 | **robots.txt & anti-scraping** | robots.txt is not law, but ignoring it is evidence of bad faith. **Bypassing logins, CAPTCHAs, or paywalls** may breach **German Criminal Code §202a (data espionage)**. |
| 3 | **EU Sui Generis Database Right** (Dir. 96/9/EC) | Protects databases built with "substantial investment." Extracting a **substantial part**, or **repeated systematic** extraction (Art. 7(5)), infringes. B2B directories likely qualify. |
| 4 | **GDPR** (Reg. EU 2016/679) | Contact-person data is personal data even in B2B. Requires a legal basis, minimization, transparency, and deletion rights. |

Additional: copyright protects original descriptions and images (not bare facts); the German
**UWG** (unfair competition) may apply to systematic free-riding.

---

## 3. Risk Assessment of Our Data Sources

| Source | Risk | Rationale |
|---|---|---|
| Company websites | Low–Medium | Public pages; obey robots.txt and rate-limit. |
| Public registries (Handelsregister, **OpenCorporates API**, EU VIES) | **Low** | Official/public, often API-based — **preferred**. |
| Europages / Kompass / wlw.de | **High** | Protected databases plus restrictive Terms of Service. |
| Login / paywalled data | **Very High** | Bypassing protection may be criminal (§202a). |

---

## 4. Compliance Measures We Adopted ★

This is the core of our compliance position: for each legal risk we made a deliberate design or
process choice to avoid it.

| Legal risk | Measure we took | Status |
|---|---|---|
| **Database right** — bulk extraction of B2B directories | We did **not** mass-scrape commercial directories. The prototype uses a **small, curated seed dataset (24 suppliers + 36 quotes)** and public registries. | ✅ Implemented |
| **§202a / anti-scraping** — bypassing protection | We never bypass logins, CAPTCHAs, paywalls, or IP blocks; only publicly accessible pages. | ✅ Implemented |
| **robots.txt / ToS** | The scraper component honors robots.txt and applies **rate limiting + an identifying User-Agent**. | ✅ In scraper |
| **Database right** — source-first strategy | Data sourcing is **pluggable, API-first**: official API / data licensing → public registries → scraping only as a fallback. | ✅ Architecture |
| **Copyright** — copying expression | We store **factual fields** (name, address, VAT, contact); descriptive prose is summarized, not copied verbatim. | ✅ Data model |
| **GDPR** — minimization | We collect only fields needed for procurement decisions; no indiscriminate harvesting of personal data. | ✅ Implemented |
| **GDPR** — right to erasure | The product implements per-record and bulk **deletion** of stored user data (conversation memory), demonstrating an erasure capability. | ✅ Implemented |
| **GDPR** — provenance & retention | The data schema records `source` + `fetched_at` per record to support audit and deletion; retention limits enforced server-side. | 🟡 Designed |
| **GDPR** — legal basis & transparency | For production, processing relies on a documented **Legitimate Interest Assessment (LIA)**, a **Record of Processing (ROPA)**, and an Art. 14 information notice. | 🟡 For production |

---

## 5. GDPR-Specific Position

Business contact data (a named person, a personal email such as `markus.bauer@…`) is personal data
under GDPR even in a B2B context. Our position:

- **Legal basis:** legitimate interest (Art. 6(1)(f)) with a balancing test before any production use.
- **Minimization & retention (Art. 5):** store only what procurement needs; define retention periods.
- **Transparency (Art. 14):** inform data subjects when data is not collected directly from them.
- **Data-subject rights (Art. 15–21):** support access, rectification, **erasure**, and objection.
- **Penalties:** up to €20M or 4% of global turnover — hence we keep the prototype to seed/public data.

---

## 6. Conclusion

Our project treats legal compliance as a design constraint, not an afterthought. By (1) limiting the
prototype to a curated seed dataset and public registries, (2) never bypassing technical protections,
(3) refusing systematic bulk extraction of protected B2B directories, (4) storing only minimal
factual data with provenance, and (5) building erasure into the product, we have **materially
avoided** the principal legal risks (EU database right, §202a, copyright, GDPR). Remaining
production-readiness items (LIA, ROPA, Art. 14 notice, data licensing) are explicitly identified and
scheduled before any commercial deployment.

---

## 7. References

- **GDPR** — Regulation (EU) 2016/679 (esp. Art. 5, 6, 14, 17, 21)
- **BDSG** — German Federal Data Protection Act
- **Database Directive 96/9/EC** — EU sui generis database right (Art. 7)
- **§202a StGB** — German Criminal Code, data espionage
- **UWG** — German Act Against Unfair Competition
- **ePrivacy Directive 2002/58/EC** — electronic marketing
- Case law: *CJEU C‑30/14 Ryanair v PR Aviation*; (US, reference only) *hiQ v LinkedIn*

---

*Compliance statement for academic submission — not legal advice.*
