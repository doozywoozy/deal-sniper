# ai_judge.py
import aiohttp
import json
from logger import logger
from config import AI_MODEL, OLLAMA_BASE_URL

async def analyze_listing(listing):
    """Analyzes listings for profit potential with market comparison - VERY strict."""
    prompt = f"""
    [ROLE]
    You are a professional PC flipper in Sweden. Your ONLY goal is to identify deals where you can make significant profit after all costs.

    [LISTING DATA]
    TITLE: {listing['title']}
    PRICE: {listing['price']} SEK
    SITE: {listing['site']}
    CATEGORY: {listing['query']}

    [MARKET ANALYSIS REQUIREMENTS]
    1. Check current prices of similar items on Blocket RIGHT NOW (as of September 14, 2025, 12:32 PM CEST)
    2. Compare against recently sold prices for identical/similar items
    3. Consider the specific category context from {listing['query']}
    4. Account for market trends - prices are falling for older hardware
    5. Research component-level values for PCs (CPU, GPU, RAM, SSD separately)

    [PROFIT ANALYSIS CRITERIA]
    1. ESTIMATE MARKET VALUE: Current selling prices for identical items
    2. CALCULATE POTENTIAL PROFIT: (Market Value - Listing Price - 200kr costs)
    3. PROFIT MARGIN: (Profit / Listing Price) * 100
    4. ABSOLUTE PROFIT: Must meet minimum thresholds
    5. DEMAND FACTOR: High-demand items get priority

    [PROFIT THRESHOLDS - VERY STRICT]
    - 🔥 HOT DEAL: 50%+ profit margin AND 1000kr+ absolute profit
    - ✅ GOOD DEAL: 25-50% profit margin AND 500kr+ absolute profit  
    - ⚠️ FAIR DEAL: 10-25% profit margin (not worth flipping)
    - ❌ BAD DEAL: <10% profit or loss

    [STRICT RULES]
    1. MUST have minimum 500kr absolute profit for GOOD deals
    2. MUST have minimum 1000kr absolute profit for HOT deals
    3. Subtract 200kr for transaction costs, time, and risk
    4. Be EXTREMELY conservative - assume you'll sell at lower end of market range
    5. Only recommend deals with clear, undeniable profit potential
    6. For category scans, be 2x more strict (most items are fairly priced)
    7. Compare to at least 5 similar listings/sold items

    [COMPONENT VALUATION GUIDE - REFERENCE ONLY, VERIFY WITH CURRENT DATA]
    - RTX 3080: Check current Blocket, typically 3000-5000kr for used
    - Xeon CPUs: Verify market, usually 2000-4000kr depending on gen
    - Adjust for condition, age, specs

    [RESPONSE FORMAT]
    Return ONLY JSON with this structure:
    {{
      "verdict": "HOT DEAL", "GOOD DEAL", "FAIR DEAL", or "BAD DEAL",
      "reason": "Brief explanation of market comparison and profit potential",
      "estimated_market_value": estimated resale price in SEK,
      "estimated_profit": estimated profit in SEK after costs,
      "profit_percentage": estimated profit percentage,
      "comparison_count": number of similar listings considered
    }}

    Be EXTREMELY conservative. Most deals are NOT profitable. When in doubt, say BAD DEAL.
    """

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": AI_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,  # More deterministic
                    "top_p": 0.9
                }
            }
            async with session.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload) as resp:
                result = await resp.json()
                response_text = result.get('response', '{"verdict": "BAD DEAL", "reason": "AI failed to respond", "estimated_market_value": 0, "estimated_profit": 0, "profit_percentage": 0, "comparison_count": 0}')
                
                # Clean response
                response_text = response_text.strip()
                if '```json' in response_text:
                    response_text = response_text.split('```json
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0].strip()
                
                # Parse JSON
                decision = json.loads(response_text)
                
                # Validate fields
                required_fields = ["verdict", "reason", "estimated_market_value", "estimated_profit", "profit_percentage", "comparison_count"]
                for field in required_fields:
                    if field not in decision:
                        decision[field] = 0 if field != "reason" else "Missing field in AI response"
                
                return decision
                
    except json.JSONDecodeError as e:
        logger.error(f"AI JSON decode error: {e}")
        return {
            "verdict": "BAD DEAL", 
            "reason": "AI returned invalid JSON format", 
            "estimated_market_value": 0, 
            "estimated_profit": 0, 
            "profit_percentage": 0,
            "comparison_count": 0
        }
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return {
            "verdict": "BAD DEAL", 
            "reason": "Error during analysis", 
            "estimated_market_value": 0, 
            "estimated_profit": 0, 
            "profit_percentage": 0,
            "comparison_count": 0
        }
