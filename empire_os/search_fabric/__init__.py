"""Empire Search Fabric — canonical search/discovery layer."""
from .search import search, search_domains, search_domains_parallel, scrape_emails

__all__ = ["search", "search_domains", "search_domains_parallel", "scrape_emails"]
