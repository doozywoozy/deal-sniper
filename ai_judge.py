# ai_judge.py
import aiohttp
import json
from config import OLLAMA_MODEL, OLLAMA_BASE_URL

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
    1. FIRST check current prices of similar items on Blocket RIGHT NOW
    2. Compare against recently sold prices for identical/similar items
    3. Consider the specific category context
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

    [COMPONENT VALUATION GUIDE]
    - RTX 3080: 4000-5500kr (depending on model and condition)
    - RTX 3080 Ti: 4500-6000kr
    - i7/i9 CPUs: 1500-3000kr (depending on generation)
    - 16GB RAM: 400-600kr
    - 1TB SSD: 400-600kr
    - Complete gaming PC: Sum of components - 20% for being used

    [EXAMPLES]
    - RTX 3080 bought for 4000kr, sells for 6000kr = 🔥 HOT DEAL (1500kr profit after costs)
    - Gaming PC bought for 8000kr, sells for 10000kr = ✅ GOOD DEAL (1500kr profit after costs)
    - RTX 3080 bought for 5500kr, sells for 6000kr = ❌ BAD DEAL (only 300kr profit after costs)

    [CATEGORY-SPECIFIC RULES]
    - For "All Stationary Computers" category: be EXTRA conservative (most are fairly priced)
    - For specific searches: can be slightly more aggressive but still strict
    - Always check multiple comparable listings before deciding

    [RESPONSE FORMAT]
    Return ONLY JSON with this structure:
    {{
      "verdict": "HOT", "GOOD", "FAIR", or "BAD",
      "reason": "Brief explanation of market comparison and profit potential",
      "estimated_market_value": estimated selling price in SEK,
      "estimated_profit": estimated profit in SEK after costs,
      "profit_percentage": estimated profit percentage,
      "comparison_count": number of similar listings considered
    }}

    Be EXTREMELY conservative. Most deals are NOT profitable. When in doubt, say BAD.
    """

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,  # More deterministic, less creative
                    "top_p": 0.9
                }
            }
            async with session.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload) as resp:
                result = await resp.json()
                response_text = result.get('response', '{"verdict": "BAD", "reason": "AI failed to respond", "estimated_market_value": 0, "estimated_profit": 0, "profit_percentage": 0, "comparison_count": 0}')
                
                # Clean the response
                response_text = response_text.strip()
                if '```json' in response_text:
                    response_text = response_text.split('```json')[1].split('```')[0]
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0]
                
                # Parse JSON response
                decision = json.loads(response_text)
                
                # Validate the response has required fields
                required_fields = ["verdict", "reason", "estimated_market_value", "estimated_profit", "profit_percentage", "comparison_count"]
                for field in required_fields:
                    if field not in decision:
                        decision[field] = 0 if field != "reason" else "Missing field in AI response"
                
                return decision
                
    except json.JSONDecodeError as e:
        print(f"AI JSON decode error: {e}")
        return {
            "verdict": "BAD", 
            "reason": "AI returned invalid JSON format", 
            "estimated_market_value": 0, 
            "estimated_profit": 0, 
            "profit_percentage": 0,
            "comparison_count": 0
        }
    except Exception as e:
        print(f"AI analysis error: {e}")
        return {
            "verdict": "BAD", 
            "reason": "Error during analysis", 
            "estimated_market_value": 0, 
            "estimated_profit": 0, 
            "profit_percentage": 0,
            "comparison_count": 0
        }