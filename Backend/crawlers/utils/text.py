import re


def clean_text(value):
    if not value:
        return ""

    value = re.sub(r"\s+", " ", value)

    return value.strip()