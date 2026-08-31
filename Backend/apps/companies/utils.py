def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()

def validate_symbol(self, value):
    return normalize_symbol(value)