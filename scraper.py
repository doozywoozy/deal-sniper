# scraper.py (partial update for fallback_extract_listings)
def fallback_extract_listings(content: str, search: Dict) -> List[Dict]:
    """Extract listings using flexible BS4 selectors based on visible content."""
    listings = []
    try:
        soup = BeautifulSoup(content, 'html.parser')

        # Target listing containers based on Blocket's structure
        potential_listings = soup.select('div.styled__Wrapper-sc-1kpvi4z-0.iQpUlz')

        logger.debug(f"Found {len(potential_listings)} potential listing containers.")

        for item in potential_listings:
            try:
                # Title and URL
                title_link = item.select_one('h2 a.Link-sc-6wulv7-0')
                if not title_link:
                    continue
                title = title_link.select_one('span.styled__SubjectContainer-sc-1kpvi4z-9').get_text(strip=True)
                url = f"https://www.blocket.se{title_link['href']}"

                # Price
                price_tag = item.select_one('div.Price__StyledPrice-sc-1v2maoc-1')
                price_text = price_tag.get_text(strip=True) if price_tag else "0"
                price = int(re.sub(r'[^\d]', '', price_text.replace(' ', ''))) if price_text and price_text.strip() else 0
                if price == 0:
                    logger.warning(f"Invalid or missing price for listing: {title}")
                    continue

                # Location
                location_tag = item.select_one('p.styled__TopInfoWrapper-sc-1kpvi4z-22 a:nth-child(3)')
                location = location_tag.get_text(strip=True) if location_tag else "No location"

                # ID from URL
                listing_id_match = re.search(r"ad/(\d+)", url)
                listing_id = listing_id_match.group(1) if listing_id_match else None

                if listing_id and not database.is_listing_seen(listing_id) and price <= search.get('price_end', float('inf')):
                    listing = {
                        "id": listing_id,
                        "title": title,
                        "price": price,
                        "url": url,
                        "location": location,
                        "source": "blocket",
                        "query": search["name"],
                    }
                    listings.append(listing)
                    database.mark_listing_seen(
                        listing["id"],
                        listing["title"],
                        listing["price"],
                        listing["url"],
                        listing["source"],
                    )

            except Exception as e:
                logger.error(f"Listing extraction error: {e}")
                continue

        logger.info(f"Extracted {len(listings)} listings via BS4.")

    except Exception as e:
        logger.error(f"BS4 extraction failed: {e}")

    return listings
