def categorize_article(article):

    candidates = find_company_candidates(article)

    results = []

    for candidate in candidates:

        confidence = calculate_confidence(
            article,
            candidate,
        )

        if confidence >= 0.45:
            results.append(
                {
                    "company": candidate["company"],
                    "confidence": confidence,
                    "method": "keyword_weighted",
                    "evidence": candidate["evidence"],
                }
            )

    save_tags(article, results)

    return results