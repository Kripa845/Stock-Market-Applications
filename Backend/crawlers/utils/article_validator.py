MIN_BODY_LENGTH = 150


def is_valid_article(item):

    if not item.get("headline"):
        return False

    if not item.get("body"):
        return False

    if len(item["body"].strip()) < MIN_BODY_LENGTH:
        return False

    if not item.get("published_at"):
        return False

    return True