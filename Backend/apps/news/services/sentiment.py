

from __future__ import annotations

import html
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_OK = "ok"
STATUS_INSUFFICIENT_CONTENT = "insufficient_content"
STATUS_UNSUPPORTED_LANGUAGE = "unsupported_language"
STATUS_NO_LEXICON_MATCH = "no_lexicon_match"
STATUS_ERROR = "error"
STATUS_PENDING = "pending"

SUCCESS_STATUSES = frozenset({STATUS_OK, STATUS_NO_LEXICON_MATCH})

LABEL_POSITIVE = "positive"
LABEL_NEGATIVE = "negative"
LABEL_NEUTRAL = "neutral"

#: Identifier stored alongside every score so a later model swap is visible.
METHOD_LEXICON = "FINANCIAL_LEXICON_V1"

#: Label boundaries. Documented above; changing these changes every label.
POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05

#: Below this many word characters an article cannot be scored honestly.
#: A three-word stub gives one lexicon hit total, which would swing the
#: score to an extreme purely as an artefact of the text being short.
MIN_CONTENT_CHARS = 40

#: The headline is the most tone-bearing part of a news article, so its
#: lexicon hits count for more than body hits.
HEADLINE_WEIGHT = 2.0
BODY_WEIGHT = 1.0

#: Tokens within this distance after a negator get their polarity flipped.
NEGATION_WINDOW = 3

#: How far AFTER a term to look for a trailing intensifier.
INTENSIFIER_WINDOW = 2


# ---------------------------------------------------------------------------
# Lexicons
# ---------------------------------------------------------------------------
# Finance-oriented word lists. Weights are in [-1.0, +1.0] and represent
# how strongly a term signals tone in a market-news context, NOT how
# strongly it predicts price. Terms are stored normalised (casefolded,
# punctuation stripped) so they match the normaliser below.

_EN_POSITIVE = {
    "surge": 0.8, "surges": 0.8, "surged": 0.8, "soar": 0.9, "soars": 0.9,
    "soared": 0.9, "rally": 0.7, "rallied": 0.7, "jump": 0.6, "jumped": 0.6,
    "gain": 0.6, "gains": 0.6, "gained": 0.6, "rise": 0.5, "rises": 0.5,
    "rose": 0.5, "rising": 0.5, "climb": 0.5, "climbed": 0.5, "up": 0.3,
    "upward": 0.5, "higher": 0.5, "high": 0.3, "record": 0.5, "peak": 0.5,
    "profit": 0.7, "profits": 0.7, "profitable": 0.7, "growth": 0.7,
    "grew": 0.6, "grow": 0.5, "growing": 0.5, "expansion": 0.6,
    "expand": 0.5, "expanded": 0.5, "strong": 0.6, "stronger": 0.6,
    "strength": 0.6, "robust": 0.6, "outperform": 0.8, "outperformed": 0.8,
    "beat": 0.6, "beats": 0.6, "exceed": 0.6, "exceeded": 0.6,
    "bullish": 0.8, "optimistic": 0.7, "optimism": 0.7, "confidence": 0.5,
    "dividend": 0.5, "dividends": 0.5, "bonus": 0.6, "payout": 0.4,
    "approve": 0.5, "approved": 0.5, "approval": 0.5, "upgrade": 0.7,
    "upgraded": 0.7, "boost": 0.6, "boosted": 0.6, "recovery": 0.6,
    "recover": 0.5, "recovered": 0.5, "rebound": 0.7, "rebounded": 0.7,
    "success": 0.6, "successful": 0.6, "positive": 0.6, "improve": 0.6,
    "improved": 0.6, "improvement": 0.6, "benefit": 0.5, "favourable": 0.6,
    "favorable": 0.6, "opportunity": 0.4, "milestone": 0.5, "launch": 0.3,
    "launched": 0.3, "partnership": 0.4, "agreement": 0.3, "deal": 0.3,
    "invest": 0.3, "investment": 0.3, "stable": 0.3, "stability": 0.4,
}

_EN_NEGATIVE = {
    "plunge": -0.9, "plunged": -0.9, "plunges": -0.9, "crash": -0.9,
    "crashed": -0.9, "slump": -0.8, "slumped": -0.8, "tumble": -0.8,
    "tumbled": -0.8, "plummet": -0.9, "plummeted": -0.9, "sink": -0.7,
    "sank": -0.7, "drop": -0.6, "dropped": -0.6, "drops": -0.6,
    "fall": -0.6, "fell": -0.6, "falls": -0.6, "falling": -0.6,
    "decline": -0.6, "declined": -0.6, "declines": -0.6, "down": -0.3,
    "downward": -0.5, "lower": -0.5, "loss": -0.7, "losses": -0.7,
    "lost": -0.6, "deficit": -0.6, "weak": -0.6, "weaker": -0.6,
    "weakness": -0.6, "poor": -0.6, "negative": -0.6, "bearish": -0.8,
    "pessimistic": -0.7, "concern": -0.4, "concerns": -0.4,
    "worry": -0.5, "worries": -0.5, "fear": -0.6, "fears": -0.6,
    "risk": -0.3, "risks": -0.3, "risky": -0.5, "warning": -0.6,
    "warn": -0.5, "warned": -0.5, "crisis": -0.8, "collapse": -0.9,
    "collapsed": -0.9, "bankrupt": -0.9, "bankruptcy": -0.9,
    "default": -0.8, "defaulted": -0.8, "fraud": -0.9, "scam": -0.9,
    "scandal": -0.8, "investigation": -0.5, "probe": -0.5, "fine": -0.4,
    "fined": -0.6, "penalty": -0.6, "penalised": -0.6, "penalized": -0.6,
    "sanction": -0.6, "suspend": -0.7, "suspended": -0.7,
    "suspension": -0.7, "halt": -0.6, "halted": -0.6, "delist": -0.8,
    "delisted": -0.8, "downgrade": -0.7, "downgraded": -0.7,
    "cut": -0.4, "cuts": -0.4, "reduce": -0.4, "reduced": -0.4,
    "layoff": -0.7, "layoffs": -0.7, "resign": -0.5, "resigned": -0.5,
    "dispute": -0.5, "lawsuit": -0.7, "litigation": -0.6, "delay": -0.4,
    "delayed": -0.4, "shortage": -0.5, "inflation": -0.4,
    "recession": -0.8, "slowdown": -0.6, "struggle": -0.6,
    "struggling": -0.6, "underperform": -0.7, "miss": -0.5,
    "missed": -0.5, "disappointing": -0.7, "disappointed": -0.6,
}

# Nepali (Devanagari) financial terms. ShareSansar and Arthakhabar both
# publish in Nepali, so an English-only lexicon would leave a large share
# of the corpus permanently unscored.
_NE_POSITIVE = {
    "बढ्यो": 0.7, "बढ्दो": 0.6, "बृद्धि": 0.7, "वृद्धि": 0.7,
    "नाफा": 0.8, "मुनाफा": 0.8, "बढी": 0.4, "उच्च": 0.5,
    "सकारात्मक": 0.7, "सुधार": 0.6, "प्रगति": 0.6, "लाभ": 0.7,
    "लाभांश": 0.5, "बोनस": 0.6, "सफल": 0.6, "सफलता": 0.6,
    "स्वीकृत": 0.5, "स्वीकृति": 0.5, "बलियो": 0.6, "तेजी": 0.8,
    "उकालो": 0.6, "सुधारिएको": 0.6, "विस्तार": 0.5, "लगानी": 0.3,
}

_NE_NEGATIVE = {
    "घट्यो": -0.7, "घट्दो": -0.6, "घटी": -0.4, "गिरावट": -0.8,
    "घाटा": -0.8, "नोक्सान": -0.8, "कमजोर": -0.6, "नकारात्मक": -0.7,
    "संकट": -0.8, "मन्दी": -0.8, "ठगी": -0.9, "जालसाजी": -0.9,
    "अनियमितता": -0.7, "छानबिन": -0.5, "कारबाही": -0.6,
    "निलम्बन": -0.7, "निलम्बित": -0.7, "जरिवाना": -0.6,
    "रोक": -0.5, "रोकिएको": -0.5, "ओरालो": -0.6, "चिन्ता": -0.4,
    "जोखिम": -0.3, "विवाद": -0.5, "ढिलाइ": -0.4, "असफल": -0.6,
}

_EN_NEGATORS = frozenset({
    "not", "no", "never", "none", "nor", "neither", "without",
    "cannot", "cant", "wont", "dont", "doesnt", "didnt", "isnt",
    "arent", "wasnt", "werent", "hasnt", "havent", "hadnt", "fails",
    "failed", "fail", "unable", "lack", "lacks", "lacking",
})

_NE_NEGATORS = frozenset({"छैन", "भएन", "नभएको", "बिना", "हुन"})

_INTENSIFIERS = {
    "very": 1.4, "highly": 1.4, "significantly": 1.4, "sharply": 1.5,
    "substantially": 1.4, "massively": 1.6, "extremely": 1.6,
    "hugely": 1.5, "strongly": 1.3, "considerably": 1.3, "greatly": 1.4,
    "slightly": 0.6, "marginally": 0.6, "somewhat": 0.7, "modestly": 0.7,
    "निकै": 1.4, "धेरै": 1.4, "अत्यधिक": 1.5, "थोरै": 0.6,
}

LEXICONS: Dict[str, Dict[str, float]] = {
    "en": {**_EN_POSITIVE, **_EN_NEGATIVE},
    "ne": {**_NE_POSITIVE, **_NE_NEGATIVE},
}

NEGATORS: Dict[str, frozenset] = {
    "en": _EN_NEGATORS,
    "ne": _NE_NEGATORS,
}

SUPPORTED_LANGUAGES = frozenset(LEXICONS.keys())


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class SentimentResult:
    """Outcome of one sentiment attempt. Always returned; never raised."""

    score: Optional[float] = None
    label: str = ""
    status: str = STATUS_PENDING
    language: str = "unknown"
    method: str = METHOD_LEXICON
    error: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        """True when the frontend may display a score."""
        return self.status in SUCCESS_STATUSES and self.score is not None


# ---------------------------------------------------------------------------
# Step 1: clean text
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WS_RE = re.compile(r"\s+")


def clean_text(raw: Any) -> str:
    """
    Normalise article text for analysis.

    The crawled ``headline``/``body`` fields on ``NewsArticle`` are never
    modified: this returns a derived copy, so the raw crawl output stays
    authoritative and re-processing always starts from the original.
    """
    if raw is None:
        return ""

    text = str(raw)
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = _WS_RE.sub(" ", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Step 2: detect language
# ---------------------------------------------------------------------------

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    """
    Script-based language detection: "ne", "en", or "unknown".

    Deliberately script-based rather than a statistical detector. The
    corpus is Nepali market news, which is reliably Devanagari or Latin,
    and a script check has no model to download, no per-call cost, and no
    non-determinism. A short headline is exactly where statistical
    detectors are least reliable and a script check is most reliable.

    Mixed-script text is assigned to whichever script carries more
    characters, since Nepali market articles routinely embed Latin ticker
    symbols and English financial terms.
    """
    if not text:
        return "unknown"

    devanagari = len(_DEVANAGARI_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))

    if devanagari == 0 and latin == 0:
        return "unknown"

    return "ne" if devanagari > latin else "en"


# ---------------------------------------------------------------------------
# Step 3: sentiment processing
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[\w\u0900-\u097F]+", flags=re.UNICODE)


def tokenize(text: str) -> List[str]:
    """Casefolded word tokens, punctuation discarded."""
    return [token.casefold() for token in _TOKEN_RE.findall(text or "")]


def _score_tokens(tokens: List[str], language: str) -> Dict[str, Any]:
    """
    Sum lexicon weights across a token list, applying negation and
    intensifier modifiers.

    Negation flips polarity within ``NEGATION_WINDOW`` tokens, so
    "profit did not rise" does not read as positive. Intensifiers scale
    the following term, so "sharply fell" outweighs "fell".
    """
    lexicon = LEXICONS.get(language, {})
    negators = NEGATORS.get(language, frozenset())

    total = 0.0
    hits: List[Dict[str, Any]] = []

    for index, token in enumerate(tokens):
        weight = lexicon.get(token)

        if weight is None:
            continue

        multiplier = 1.0
        negated = False

        # Negators only ever precede the term they negate
        # ("did not rise"), so look backwards for those.
        window_start = max(0, index - NEGATION_WINDOW)
        for previous in tokens[window_start:index]:
            if previous in negators:
                negated = True
            if previous in _INTENSIFIERS:
                multiplier *= _INTENSIFIERS[previous]

        # Intensifiers, unlike negators, routinely FOLLOW the term in
        # financial writing: "rose sharply", "fell significantly". Looking
        # only backwards would miss the most common phrasing in this
        # corpus, so scan a short forward window too.
        forward_end = min(len(tokens), index + 1 + INTENSIFIER_WINDOW)
        for following in tokens[index + 1:forward_end]:
            if following in _INTENSIFIERS:
                multiplier *= _INTENSIFIERS[following]
            # Stop at the next tone-bearing term so an intensifier is not
            # double-counted against two different words.
            if following in lexicon:
                break

        value = weight * multiplier
        if negated:
            value = -value

        total += value
        hits.append({
            "token": token,
            "weight": weight,
            "negated": negated,
            "multiplier": round(multiplier, 2),
            "contribution": round(value, 4),
        })

    return {"total": total, "hits": hits}


def _normalise(total: float, hit_count: int) -> float:
    """
    Squash an unbounded weight sum into [-1, +1].

    Uses the VADER-style ``x / sqrt(x^2 + alpha)`` curve so that adding
    more of the same evidence keeps moving the score but with diminishing
    returns, and no article can saturate at exactly +/-1.0. Alpha grows
    with hit count so a long article needs proportionally more evidence
    to reach the same score as a short one.
    """
    if hit_count == 0:
        return 0.0

    alpha = 4.0 + (hit_count * 0.5)
    normalised = total / ((total * total + alpha) ** 0.5)

    return round(max(-1.0, min(1.0, normalised)), 4)


def score_to_label(score: Optional[float]) -> str:
    """Apply the documented label thresholds."""
    if score is None:
        return ""
    if score >= POSITIVE_THRESHOLD:
        return LABEL_POSITIVE
    if score <= NEGATIVE_THRESHOLD:
        return LABEL_NEGATIVE
    return LABEL_NEUTRAL


def analyze_text(headline: Any, body: Any = "") -> SentimentResult:
    """
    Run the full pipeline on raw headline/body text.

    clean -> detect language -> score -> label.

    Never raises. Every failure mode returns a ``SentimentResult`` with a
    status explaining why no score is available, because one unparseable
    article must not be able to abort a batch of a thousand.
    """
    try:
        clean_headline = clean_text(headline)
        clean_body = clean_text(body)
        combined = f"{clean_headline} {clean_body}".strip()

        if len(combined) < MIN_CONTENT_CHARS:
            return SentimentResult(
                status=STATUS_INSUFFICIENT_CONTENT,
                language=detect_language(combined),
                details={
                    "content_length": len(combined),
                    "minimum_required": MIN_CONTENT_CHARS,
                },
            )

        language = detect_language(combined)

        if language not in SUPPORTED_LANGUAGES:
            return SentimentResult(
                status=STATUS_UNSUPPORTED_LANGUAGE,
                language=language,
                details={"supported_languages": sorted(SUPPORTED_LANGUAGES)},
            )

        headline_scored = _score_tokens(tokenize(clean_headline), language)
        body_scored = _score_tokens(tokenize(clean_body), language)

        total = (
            headline_scored["total"] * HEADLINE_WEIGHT
            + body_scored["total"] * BODY_WEIGHT
        )
        hit_count = len(headline_scored["hits"]) + len(body_scored["hits"])

        details = {
            "headline_hits": headline_scored["hits"],
            "body_hits": body_scored["hits"],
            "hit_count": hit_count,
            "raw_total": round(total, 4),
            "headline_weight": HEADLINE_WEIGHT,
            "body_weight": BODY_WEIGHT,
            "content_length": len(combined),
        }

        if hit_count == 0:
            # Supported language, but no tone-bearing vocabulary. This is
            # a neutral reading backed by zero evidence, which is worth
            # distinguishing from a neutral reading backed by balanced
            # evidence.
            return SentimentResult(
                score=0.0,
                label=LABEL_NEUTRAL,
                status=STATUS_NO_LEXICON_MATCH,
                language=language,
                details=details,
            )

        score = _normalise(total, hit_count)

        return SentimentResult(
            score=score,
            label=score_to_label(score),
            status=STATUS_OK,
            language=language,
            details=details,
        )

    except Exception as exc:  # noqa: BLE001 - analyser must never propagate
        logger.exception("Sentiment analysis failed: %s", exc)
        return SentimentResult(
            status=STATUS_ERROR,
            error=f"{type(exc).__name__}: {exc}",
        )


def analyze_article(article) -> SentimentResult:
    """Convenience wrapper: score a ``NewsArticle`` without saving it."""
    return analyze_text(
        getattr(article, "headline", ""),
        getattr(article, "body", ""),
    )


# ---------------------------------------------------------------------------
# Step 4: persist
# ---------------------------------------------------------------------------

def apply_sentiment(article, result: Optional[SentimentResult] = None,
                    save: bool = True) -> SentimentResult:
    """
    Write a ``SentimentResult`` onto a ``NewsArticle``.

    Idempotent: the score is a pure function of the stored headline/body,
    so re-running over an already-processed article recomputes the same
    values and rewrites the same row. It never appends, never duplicates
    and never mutates the crawled text.
    """
    if result is None:
        result = analyze_article(article)

    article.sentiment = result.score
    article.sentiment_label = result.label
    article.sentiment_status = result.status
    article.sentiment_method = result.method
    article.sentiment_error = result.error or ""
    article.sentiment_language = result.language

    if save:
        from django.utils import timezone

        article.sentiment_processed_at = timezone.now()
        article.save(update_fields=[
            "sentiment",
            "sentiment_label",
            "sentiment_status",
            "sentiment_method",
            "sentiment_error",
            "sentiment_language",
            "sentiment_processed_at",
            "updated_at",
        ])

    return result
