# pricing.py — a small, realistic pricing engine (example project under test).
# Applies a percentage discount, then tax, and rounds to cents.

def final_price(base, discount_pct, tax_pct):
    discounted = base * (1 - discount_pct / 100)
    taxed = discounted * (1 + tax_pct / 100)
    return round(taxed, 2)