"""Rules for turning raw Online Retail descriptions into storefront-ready products.

The UCI dataset only has an upper-case description per stock code, so we derive a
readable title and a coarse category from keywords. Rules are ordered: the first
matching category wins.
"""

from __future__ import annotations

import re

FALLBACK_CATEGORY = "Gifts & Novelties"

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Christmas & Seasonal",
        (
            "CHRISTMAS", "XMAS", "ADVENT", "SANTA", "REINDEER", "BAUBLE", "SNOWFLAKE", "NATIVITY",
            "TREE DECORATION", "SLEIGH", "NOEL", "EASTER",
        ),
    ),
    (
        "Candles & Lighting",
        (
            "CANDLE", "CANDLEHOLDER", "CHOCOLATECANDLE", "T-LIGHT", "TLIGHT", "TEA LIGHT", "LANTERN",
            "LIGHT", "LAMP", "MATCHES",
        ),
    ),
    (
        "Bags",
        ("BAG", "SHOPPER", "PURSE", "RUCKSACK", "BACKPACK", "TOTE"),
    ),
    (
        "Kitchen & Dining",
        (
            "MUG", "CUP", "PLATE", "BOWL", "TEACUP", "TEAPOT", "TEA SET", "CAKE", "CAKESTAND", "BAKING",
            "NAPKIN", "CUTLERY", "LUNCH BOX", "JUG", "TRAY", "APRON", "OVEN GLOVE", "OVEN MITT",
            "COASTER", "SPOON", "KITCHEN", "RECIPE", "JAM", "BOTTLE", "GLASS", "SAUCER", "BEAKER",
            "STRAW", "TUMBLER", "PANTRY", "COLANDER", "CHOPSTICK", "EGG", "DOILY", "DOILIES",
            "COOKIE CUTTER", "BISCUIT", "BREAD BIN", "TEA TOWEL", "BUTTER DISH", "SUGAR", "STRAINER",
            "TONGS", "PLACEMAT", "WASHING UP GLOVE", "FOOD COVER", "SALT", "POPCORN", "DISPENSER",
            "FOOD CONTAINER",
        ),
    ),
    (
        "Stationery & Gift Wrap",
        (
            "CARD", "WRAP", "PAPER", "NOTEBOOK", "NOTE BOOK", "EXERCISE BOOK", "ADDRESS BOOK", "PENCIL",
            "PEN", "STICKER", "TAPE", "ENVELOPE", "SKETCHBOOK", "ERASER", "RIBBON", "GIFT TAG", "TAG",
            "NOTEPAD", "JOURNAL", "DIARY", "CALENDAR", "STAMP", "CRAYON", "CHALK STICK", "RULER",
            "STATIONERY", "WRITING SET", "MEMO BOARD", "MEMOBOARD", "POSTCARD",
        ),
    ),
    (
        "Toys, Crafts & Party",
        (
            "TOY", "GAME", "DOLL", "DOLLY", "PLAYHOUSE", "SPACEBOY", "PARTY", "BUNTING", "BALLOON",
            "CRACKERS", "PAINT SET", "JIGSAW", "SKITTLES", "DOMINOES", "SOLDIER", "BINGO", "SNAP",
            "KIT", "CHILDRENS", "CHILDS", "KIDS", "TEDDY", "FELTCRAFT", "CRAFT", "KNITTING",
            "SPINNING TOP", "SKIPPING ROPE", "LUDO", "SNAKES & LADDERS", "NAUGHTS & CROSSES",
            "MODELLING CLAY", "COLOURING", "STENCIL", "DRAWING SLATE", "ROCKING HORSE", "GLIDER",
            "CANVAS", "SPORTING FUN",
        ),
    ),
    (
        "Storage & Organisation",
        (
            "TIN", "BOX", "BOXES", "BASKET", "STORAGE", "JAR", "DRAWER", "CASE", "CRATE", "CONTAINER",
            "PEGS", "CHEST", "CABINET",
        ),
    ),
    (
        "Garden & Outdoor",
        (
            "GARDEN", "GARDENERS", "PLANT", "PLANTER", "WATERING", "BIRD", "PICNIC", "FLOWER POT",
            "POT", "KNEELING", "HERB MARKER", "HAMMOCK", "BEACH", "SANDCASTLE", "WINDMILL", "BICYCLE",
        ),
    ),
    (
        "Bath & Beauty",
        (
            "SOAP", "BATH", "TOWEL", "BATHROOM", "WASHBAG", "SPONGE", "HAND WARMER", "MAKE UP",
            "LIP GLOSS", "TISSUES",
        ),
    ),
    (
        "Fashion & Accessories",
        (
            "NECKLACE", "BRACELET", "EARRING", "RING", "HAIR", "HAIRBAND", "BROOCH", "CHARM", "SCARF",
            "KEYRING", "KEY FOB", "UMBRELLA", "PARASOL", "FAN", "PONCHO",
        ),
    ),
    (
        "Home Décor",
        (
            "SIGN", "FRAME", "CLOCK", "CUSHION", "DOORMAT", "MAT", "WALL", "MIRROR", "ORNAMENT",
            "HEART", "HANGING", "DECORATION", "VASE", "GARLAND", "CHALKBOARD", "BLACKBOARD",
            "BLACK BOARD", "MAGNET", "HOOK", "DOORSTOP", "THROW", "BLANKET", "WREATH", "BIRDHOUSE",
            "PLAQUE", "BUTTERFLY", "HOT WATER BOTTLE", "RACK", "BUILDING BLOCK", "BLOCK LETTERS",
            "WICKER STAR", "DOOR HANGER", "PHOTO", "STOOL", "FILLER PAD", "COAT HANGER",
        ),
    ),
]

_COMPILED_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        category,
        # Allow a trailing plural "S" so "NAPKIN" also matches "NAPKINS".
        re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")S?\b"),
    )
    for category, keywords in CATEGORY_RULES
]

_LOWERCASE_WORDS = frozenset({"of", "and", "the", "in", "on", "with", "for", "a", "an", "to", "or"})

# Wholesale shorthand found in the raw descriptions.
_ABBREVIATIONS = {
    "ASS": "ASSORTED",
    "ASST": "ASSORTED",
    "ASSTD": "ASSORTED",
    "ANT": "ANTIQUE",
    "SML": "SMALL",
    "LRG": "LARGE",
    "CHILDS": "CHILD'S",
    "CHILDRENS": "CHILDREN'S",
}
_SET_OF = re.compile(r"\b(?:S|SET)\s*/\s*(\d+)\b")


def categorize(raw_description: str) -> str:
    """Return the first category whose keywords appear in the description."""
    text = " ".join(raw_description.upper().split())
    for category, pattern in _COMPILED_RULES:
        if pattern.search(text):
            return category
    return FALLBACK_CATEGORY


def _title_word(word: str, is_first: bool) -> str:
    lower = word.lower()
    if not is_first and lower in _LOWERCASE_WORDS:
        return lower
    # Keep short alphanumeric codes such as "A4", "3D" or "S/4" upper-case.
    if any(ch.isdigit() for ch in word) and len(word) <= 3:
        return word.upper()
    return "-".join(part[:1].upper() + part[1:].lower() for part in word.split("-"))


def prettify_title(raw_description: str) -> str:
    """Convert e.g. 'WHITE HANGING HEART T-LIGHT HOLDER ' to 'White Hanging Heart T-Light Holder'."""
    text = _SET_OF.sub(r"SET OF \1", raw_description.strip().upper())
    text = text.replace(" ,", ",")
    words = [_ABBREVIATIONS.get(word, word) for word in text.split()]
    return " ".join(_title_word(word, i == 0) for i, word in enumerate(words))


def describe(title: str, category: str) -> str:
    """Short storefront description built only from facts present in the dataset."""
    return (
        f"{title}, from our {category} range. Part of a real UK online gift-retail catalogue "
        "(UCI Online Retail dataset, 2010–2011)."
    )
