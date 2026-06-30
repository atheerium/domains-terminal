# Providers

Providers are the data ingestion layer. Each one fetches domain names from an external source and returns `List[Domain]`.

## Contract

```python
class SomeProvider:
    def __init__(self, storage: Storage | None = None):
        ...

    def fetch(self, *, persist: bool = True, **kwargs) -> list[Domain]:
        ...
```

- `fetch()` is the main entry point
- When `persist=True`, domains are inserted into storage automatically
- No base class required — duck-typed

## DropCatch (`providers/dropcatch.py`)

**Source**: `https://api.dropcatch.com`  
**Auth**: OAuth2 (client ID + client secret) → bearer token  
**Endpoints used**:
- `/Authorize` — get token
- `/v2/auctions` — live auction search
- `/v2/backorders` — active backorders
- `/v2/downloads/auctions/{type}` — bulk data (bulk download)

**Env vars**: `DROPCATCH_CLIENT_ID`, `DROPCATCH_CLIENT_SECRET`  
**Token cache**: `~/.config/domains-terminal/token.json`

```python
provider = DropCatchProvider()
provider.auth()  # manual auth
domains = provider.get_auctions(tlds=["com", "io"], high_bid_min=10.0)
```

## ExpiredDomains (`providers/expireddomains.py`)

**Source**: `https://www.expireddomains.net`  
**Method**: BeautifulSoup HTML scraper  
**Auth**: Optional (free account for some sections)

**Env vars**: `EXPIREDDOMAINS_USERNAME`, `EXPIREDDOMAINS_PASSWORD`

```python
provider = ExpiredDomainsProvider()
domains = provider.get_expiring(tld="com", days=7)
```

## NameBio (`providers/namebio.py`)

**Source**: `https://api.namebio.com` + `https://namebio.com`  
**Method**: API (primary), BeautifulSoup scrape (fallback)  
**Auth**: Optional API key

**Env vars**: `NAMEBIO_API_KEY`

```python
provider = NameBioProvider()
sales = provider.search_sales("startup", limit=20)
comps = provider.get_comps("example.com")
```

## Adding a New Provider

See `docs/architecture.md` → Extension Patterns.
