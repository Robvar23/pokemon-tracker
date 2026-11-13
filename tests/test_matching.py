import copy

from tracker.config import DEFAULT_CONFIG, normalise_card
from tracker.matching import card_url, condition_code, evaluate, found_words, words_for_card


def cfg(**over):
    c = copy.deepcopy(DEFAULT_CONFIG)
    c.update(over)
    return c


def listing(**kw):
    d = {"language": "English", "condition": "NM", "country": "Germany", "has_photo": True,
         "comment": "", "price": "54,90 €", "seller": "SparkTrader"}
    d.update(kw)
    return d


CARD = normalise_card({"url": "https://www.cardmarket.com/en/Pokemon/Products/Singles/Ascended-Heroes/Pikachu-ex-ASC276"})


def test_whole_words_only():
    assert found_words("PSA 10 candidate!", ["PSA 10 candidate"]) == ["PSA 10 candidate"]
    assert found_words("PSA 100 candidate", ["PSA 10 candidate"]) == []
    assert found_words("clean! no WHITENING", ["Clean!", "No whitening"]) == ["Clean!", "No whitening"]
    assert found_words("Certified fresh", ["Cert"]) == []


def test_keyword_alerts_and_ignore_wins():
    c = cfg()
    assert evaluate(c, CARD, listing(comment="Clean! Fresh pull with grade potential"))[0]
    ok, _, reason = evaluate(c, CARD, listing(comment="Clean! but slightly OC"))
    assert not ok and "OC" in reason
    assert not evaluate(c, CARD, listing(comment="Shipped in a toploader"))[0]
    assert not evaluate(c, CARD, listing(comment=""))[0]


def test_no_keywords_means_every_listing():
    c = cfg()
    c["keywords"] = {"watch": [], "ignore": ["damaged"]}
    assert evaluate(c, CARD, listing(comment=""))[0]
    assert not evaluate(c, CARD, listing(comment="damaged corner"))[0]


def test_card_filters():
    c = cfg()
    good = "Clean!"
    assert not evaluate(c, CARD, listing(comment=good, language="Japanese"))[0]
    assert not evaluate(c, CARD, listing(comment=good, condition="EX"))[0]
    assert evaluate(c, CARD, listing(comment=good, condition="MT"))[0]
    photo_card = dict(CARD, photos="yes")
    assert not evaluate(c, photo_card, listing(comment=good, has_photo=False))[0]
    country_card = dict(CARD, countries=["Netherlands"])
    assert not evaluate(c, country_card, listing(comment=good))[0]


def test_alerts_tab_criteria():
    c = cfg()
    c["criteria"] = {"countries": ["Netherlands", "Belgium"], "languages": [], "min_condition": ""}
    assert not evaluate(c, CARD, listing(comment="Clean!"))[0]
    assert evaluate(c, CARD, listing(comment="Clean!", country="Belgium"))[0]


def test_per_card_keywords():
    c = cfg()
    card = dict(CARD, use_all_keywords=False, keywords_off=["Mint"], extra_keywords=["Gem mint"],
                use_all_ignored=False, ignored_off=["PSA 9"], extra_ignored=["1st edition"])
    watch, ignore = words_for_card(c, card)
    assert "Mint" not in watch and "Gem mint" in watch
    assert "PSA 9" not in ignore and "1st edition" in ignore
    assert evaluate(c, card, listing(comment="Gem mint copy"))[0]
    assert evaluate(c, card, listing(comment="Clean! came back PSA 9"))[0]
    assert not evaluate(c, card, listing(comment="Clean! 1st edition"))[0]
    # Switch is on: switched-off words still count
    assert "Mint" in words_for_card(c, dict(card, use_all_keywords=True))[0]


def test_card_url_filters():
    u = card_url(dict(CARD, languages=["English", "German"], min_condition="NM"))
    assert u.endswith("Pikachu-ex-ASC276?language=1,3&minCondition=2")
    u2 = card_url(dict(CARD, url=CARD["url"] + "?language=7&sellerType=1", languages=[], min_condition=""))
    assert u2.endswith("?sellerType=1")


def test_condition_names():
    assert condition_code("Near Mint") == "NM"
    assert condition_code("nm") == "NM"
    assert condition_code("Light Played") == "LP"


def test_mint_is_not_near_mint():
    assert found_words("Near Mint, fast shipping", ["Mint"]) == []
    assert found_words("near-mint copy", ["Mint"]) == []
    assert found_words("Psa 10, mint , fast ship !", ["Mint"]) == ["Mint"]
    assert found_words("Mint condition, near mint corners", ["Mint"]) == ["Mint"]
    assert found_words("Near Mint", ["Near Mint"]) == ["Near Mint"]
