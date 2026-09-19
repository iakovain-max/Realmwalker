"""What townsfolk can do for you besides talk: trade, and services such as rooms, meals, baths,
healing, repairs and animals (services arrive with M5 part 4)."""

from __future__ import annotations


def choices(conv) -> list:
    """Extra menu entries for this person's trade and services."""
    from realmwalker.game import economy
    from realmwalker.game.dialogue import Choice

    npc = conv.npc
    game = conv.game
    out = []
    spec = economy.shop_spec(game, npc)
    if spec is not None:
        out.append(Choice("trade", f"Let me see your {spec['name']}."))
        shop = economy.shop_state(game, npc)
        today = game.moment.total_days
        if shop.get("haggle_day") != today:
            out.append(Choice("haggle", "[Persuasion] Haggle over your prices."))
    return out


def choose(conv, choice) -> str | None:
    from realmwalker.game import economy

    if choice.id == "trade":
        conv.you_say("Let me see what you have.")
        return "trade"
    if choice.id == "haggle":
        conv.you_say("Surely you can do better than that.")
        conv.note(economy.haggle(conv.game, conv.npc))
    return None
