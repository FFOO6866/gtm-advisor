# Data Source Alternatives: Paid vs Free/Scraping

## Quick Reference: What to Scrape Instead of Paying

| Paid Service | Cost | FREE Alternative | How to Scrape |
|--------------|------|------------------|---------------|
| **Clearbit** ($0.10/record) | Company enrichment | Company website + ACRA | Scrape about page, team page, meta tags |
| **ZoomInfo** ($15K/yr) | Contacts + companies | LinkedIn + Google | Google: `site:linkedin.com/in "company"` |
| **Apollo.io** (paid tiers) | Lead data | LinkedIn + job boards | Google search + company careers pages |
| **BuiltWith** ($295/mo) | Tech stack | HTML analysis | Scan page source for React, Vue, etc. |
| **Cognism** (enterprise) | Phone numbers | Company websites | Scrape contact pages (limited) |
| **Crunchbase Pro** ($99/mo) | Funding data | News + press releases | Google: `"company" "series A" OR "raised"` |
| **Bombora** (enterprise) | Intent data | Job postings + news | Monitor careers pages, news mentions |
| **6sense** (enterprise) | Buying signals | G2 + news + jobs | Scrape review sites, news, job boards |
| **PitchBook** ($$$) | Detailed financials | EODHD + news | Use EODHD for public cos, news for private |
| **Lusha** ($70/mo) | Contact emails | Hunter.io free + pattern | Free tier + email pattern guessing |
| **SimilarWeb** ($200/mo) | Traffic estimates | Not scrapable | No good free alternative |

---

## Detailed Scraping Strategies

### 1. Company Enrichment (Replace Clearbit)

**Target**: Company websites
**Data extracted**:
- Company name (title tag)
- Description (meta description)
- Employee count (about page text)
- Founded year (about page text)
- Tech stack (HTML source analysis)
- Social links (footer/header links)
- Leadership team (team page)
- Job postings (careers page)

```python
# Scrape targets
ABOUT_PATHS = ['/about', '/about-us', '/company', '/our-story']
TEAM_PATHS = ['/team', '/about/team', '/leadership', '/people']
CAREERS_PATHS = ['/careers', '/jobs', '/join-us', '/open-positions']

# Tech detection patterns
TECH_PATTERNS = {
    'react': [r'react', r'_react', r'__next'],
    'vue': [r'vue\.js', r'v-bind'],
    'angular': [r'ng-app', r'angular'],
    'hubspot': [r'hubspot', r'hs-scripts'],
    'salesforce': [r'salesforce'],
    'google_analytics': [r'gtag', r'ga\.js'],
    'intercom': [r'intercom'],
    'zendesk': [r'zendesk'],
}
```

### 2. Contact Discovery (Replace ZoomInfo/Apollo)

**Strategy**: Google dorking + LinkedIn public pages

```python
# Find employees at a company
GOOGLE_QUERIES = [
    f'site:linkedin.com/in "{company}" "{title}"',
    f'site:linkedin.com/in "{company}" CEO OR founder',
    f'site:linkedin.com/in "{company}" "VP" OR "Director"',
]

# Email pattern guessing (after finding name)
EMAIL_PATTERNS = [
    '{first}@{domain}',
    '{first}.{last}@{domain}',
    '{first}{last}@{domain}',
    '{f}{last}@{domain}',
    '{first}_{last}@{domain}',
]
```

### 3. Funding Data (Replace Crunchbase Pro)

**Strategy**: News search + press releases

```python
FUNDING_QUERIES = [
    f'"{company}" "series A" OR "series B" OR "seed round"',
    f'"{company}" "raised" "$" "million"',
    f'"{company}" "funding" "led by"',
    f'site:prnewswire.com "{company}" funding',
    f'site:businesswire.com "{company}" investment',
]

# Singapore-specific
SG_FUNDING_SOURCES = [
    'dealstreetasia.com',
    'techinasia.com',
    'e27.co',
    'businesstimes.com.sg',
]
```

### 4. Intent Signals (Replace Bombora/6sense)

**Strategy**: Monitor job postings + news + reviews

| Signal Type | Where to Find | What It Means |
|-------------|---------------|---------------|
| Hiring SDRs/AEs | Careers page, LinkedIn Jobs | Scaling sales = budget |
| Hiring Engineers | Careers page | Building = growth mode |
| New VP Sales | LinkedIn, news | New leader = new tools |
| Negative reviews | G2, Glassdoor | May be looking to switch |
| Funding news | News sites | Money to spend |
| Expansion news | News, job locations | Growing = buying |

```python
INTENT_SIGNALS = {
    'sales_hiring': ['sdr', 'bdr', 'account executive', 'sales rep'],
    'tech_hiring': ['engineer', 'developer', 'architect'],
    'expansion': ['opening office', 'expanding to', 'hiring in'],
    'pain_indicators': ['struggling with', 'looking for', 'need help'],
}
```

### 5. Competitor Tech Stack (Replace BuiltWith)

**Strategy**: Analyze HTML and headers

```python
# Technologies detectable from HTML
DETECTABLE_TECH = {
    # Frontend frameworks
    'react': ['react', '__NEXT_DATA__', 'data-reactroot'],
    'vue': ['__VUE__', 'v-bind', 'v-model'],
    'angular': ['ng-app', 'ng-controller', 'angular'],

    # Analytics
    'google_analytics': ['google-analytics.com', 'gtag(', 'ga.js'],
    'segment': ['segment.com/analytics.js', 'analytics.identify'],
    'mixpanel': ['mixpanel.com', 'mixpanel.track'],
    'amplitude': ['amplitude.com', 'amplitude.getInstance'],

    # Marketing
    'hubspot': ['js.hs-scripts.com', 'hubspot.com'],
    'marketo': ['marketo.net', 'munchkin'],
    'pardot': ['pardot.com', 'piAId'],
    'mailchimp': ['mailchimp.com'],

    # Chat/Support
    'intercom': ['intercom.io', 'Intercom('],
    'zendesk': ['zdassets.com', 'zendesk.com'],
    'drift': ['drift.com', 'driftt.com'],
    'freshchat': ['freshchat.com'],

    # CRM signals
    'salesforce': ['force.com', 'salesforce.com'],
    'pipedrive': ['pipedrive.com'],

    # E-commerce
    'shopify': ['cdn.shopify.com', 'Shopify.'],
    'woocommerce': ['woocommerce'],
    'magento': ['Magento', 'mage/'],

    # Payments
    'stripe': ['js.stripe.com', 'Stripe('],
    'paypal': ['paypal.com/sdk'],

    # Infrastructure
    'cloudflare': ['cloudflare'],
    'aws': ['amazonaws.com'],
    'vercel': ['vercel.app', '_vercel'],
}

# HTTP Headers to check
HEADER_SIGNALS = {
    'x-powered-by': 'Server technology',
    'server': 'Web server',
    'x-vercel-id': 'Vercel hosting',
    'cf-ray': 'Cloudflare',
}
```

---

## Singapore-Specific Free Sources

### Government Data (100% Free)

| Source | URL | Data |
|--------|-----|------|
| **ACRA** | data.gov.sg | 588K registered companies |
| **MAS** | mas.gov.sg | Licensed financial entities |
| **GeBIZ** | gebiz.gov.sg | Government tenders |
| **MyCareersFuture** | mycareersfuture.gov.sg | Job postings |
| **SGX** | sgx.com | Listed companies |
| **IRAS** | iras.gov.sg | GST-registered businesses |

### Singapore News RSS (Free)

```python
SG_NEWS_FEEDS = {
    'business_times': 'https://www.businesstimes.com.sg/rss/singapore',
    'straits_times_business': 'https://www.straitstimes.com/news/business/rss.xml',
    'channel_news_asia': 'https://www.channelnewsasia.com/rss/business',
    'tech_in_asia': 'https://www.techinasia.com/feed',
    'e27': 'https://e27.co/feed/',
    'dealstreetasia': 'https://www.dealstreetasia.com/feed/', # Partial
}
```

### Job Boards to Scrape

| Site | What to Extract | Hiring Signal |
|------|-----------------|---------------|
| LinkedIn Jobs | Open positions | Company growth |
| MyCareersFuture | SG jobs (required by law for EPs) | Local hiring |
| Indeed SG | Job count + titles | Team expansion |
| Glassdoor | Jobs + reviews | Employee sentiment |
| Company /careers | Direct positions | Accurate count |

---

## Scraping Best Practices

### Rate Limiting
```python
# Respect the site
RATE_LIMITS = {
    'default': 1.0,        # 1 request/second
    'linkedin': 5.0,       # 1 request/5 seconds (aggressive blocking)
    'google': 2.0,         # 1 request/2 seconds
    'news_sites': 0.5,     # 2 requests/second
}
```

### User Agent Rotation
```python
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
]
```

### Caching
```python
# Cache scraped data to avoid re-scraping
CACHE_DURATIONS = {
    'company_about': 7 * 24 * 3600,    # 7 days
    'company_team': 7 * 24 * 3600,     # 7 days
    'company_jobs': 1 * 24 * 3600,     # 1 day (changes frequently)
    'news_articles': 30 * 24 * 3600,   # 30 days (doesn't change)
    'linkedin_profile': 14 * 24 * 3600, # 14 days
}
```

### Fallback Strategy
```python
# If scraping fails, try alternatives
FALLBACK_CHAIN = {
    'company_info': [
        'company_website',
        'linkedin_company',
        'crunchbase_free',
        'google_search',
    ],
    'contact_info': [
        'company_team_page',
        'linkedin_google_search',
        'email_pattern_guess',
    ],
    'funding_info': [
        'crunchbase_free',
        'news_search',
        'press_releases',
    ],
}
```

---

## Legal Considerations

### Generally Safe to Scrape
- ✅ Public company websites
- ✅ Public news articles
- ✅ Government data (data.gov.sg)
- ✅ Public RSS feeds
- ✅ Public job postings
- ✅ Public review sites (read-only)

### Proceed with Caution
- ⚠️ LinkedIn (aggressive ToS enforcement)
- ⚠️ Facebook/Meta properties
- ⚠️ Rate-limited APIs without key
- ⚠️ Sites with explicit robots.txt deny

### Avoid
- ❌ Logged-in content without permission
- ❌ CAPTCHA bypassing
- ❌ Paid content scraping
- ❌ Personal data without consent (PDPA)

---

## When to Pay

| Scenario | Recommendation |
|----------|----------------|
| < 100 leads/month | Scraping is fine |
| 100-500 leads/month | Free tiers + scraping |
| 500-2000 leads/month | Consider Apollo/Hunter paid |
| 2000+ leads/month | Full paid stack worth it |
| Enterprise compliance needs | Must use official APIs |
| Real-time data critical | Paid APIs more reliable |

---

## Implementation Priority

### Week 1-2: Core Scraping (FREE)
1. Company website scraper
2. ACRA data integration
3. Google News/RSS aggregator
4. Tech stack detector

### Week 3-4: Enhanced Scraping (FREE)
1. LinkedIn via Google dorking
2. Job board scrapers
3. Review site scrapers
4. Email pattern guessing

### Week 5+: Freemium APIs
1. Apollo.io free tier (50 credits)
2. Hunter.io free tier (25 searches)
3. Crunchbase free tier
4. EODHD free tier (you have this)

### Later: Paid (when needed)
1. Apollo.io Basic ($49/mo)
2. Proxycurl for LinkedIn ($50/mo)
3. BuiltWith for tech stack ($295/mo)
