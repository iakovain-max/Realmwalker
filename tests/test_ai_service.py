"""The AI client and service against the mock Player2 server (never the real app)."""

import time

import pytest

from realmwalker.ai.client import P2Error, Player2Client
from realmwalker.ai.prompts import PromptLibrary, parse_template
from realmwalker.ai.service import AIService, AIStatus, Priority
from realmwalker.ai.store import FlavorStore
from realmwalker.ai.tasks import SAMPLE_TAVERN, sample_tavern_fallback, sample_tavern_variables
from realmwalker.core.rng import RNG
from realmwalker.paths import Paths
from tools.mock_player2 import MockPlayer2

UNREACHABLE = "http://127.0.0.1:9/v1"


def make_service(base_url: str, **kwargs) -> AIService:
    svc = AIService(prompts=PromptLibrary(Paths().prompts), client_factory=lambda: Player2Client(base_url),
                    retry_interval=0.2, **kwargs)
    svc.start()
    return svc


def wait_for(cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return False


def run_one(svc: AIService, variables=None):
    results = []
    svc.submit(SAMPLE_TAVERN, variables or {"region": "a marsh", "season": "winter", "culture": "Norse-sounding"},
               callback=results.append)
    assert wait_for(lambda: svc.poll() or results, 10)
    return results[0]


# ---------------------------------------------------------------------------- client
def test_client_health_joules_chat(mock_p2):
    with Player2Client(mock_p2.base_url) as c:
        assert c.health() == "mock-1.0"
        assert c.joules() == (500, "")
        reply = c.chat([{"role": "user", "content": 'Reply with {"a": "<text>"}'}])
        assert '"a"' in reply.content


def test_client_offline():
    with Player2Client(UNREACHABLE) as c, pytest.raises(P2Error) as err:
        c.health()
    assert err.value.kind == "offline"


@pytest.mark.parametrize("mode,kind", [("http402", "energy"), ("http401", "auth"), ("http429", "rate"),
                                       ("http500", "server"), ("empty", "empty"), ("truncated", "truncated")])
def test_client_error_kinds(mode, kind):
    with MockPlayer2(mode) as mock, Player2Client(mock.base_url) as c, pytest.raises(P2Error) as err:
        c.chat([{"role": "user", "content": "hi"}])
    assert err.value.kind == kind


def test_game_key_header_is_sent_when_configured(mock_p2):
    c = Player2Client(mock_p2.base_url, game_key="abc123")
    assert c._http.headers["player2-game-key"] == "abc123"
    c.close()


# ---------------------------------------------------------------------------- prompts
def test_prompt_files_exist_and_render():
    lib = PromptLibrary(Paths().prompts)
    t = lib.get("sample_tavern")
    assert t.setting_int("max_tokens", 0) > 0
    text = t.render({"region": "a moor", "season": "winter", "culture": "x", "schema": "{}"})
    assert "a moor" in text and "{region}" not in text


def test_template_header_and_literal_braces():
    t = parse_template("x", "@max_tokens: 50\n# comment\nHello {name}, keep {this} and {\"a\": 1}")
    assert t.settings == {"max_tokens": "50"}
    assert t.render({"name": "Mira"}) == 'Hello Mira, keep {this} and {"a": 1}'


# ---------------------------------------------------------------------------- service
def test_service_goes_online_and_generates(mock_p2):
    svc = make_service(mock_p2.base_url)
    try:
        assert wait_for(lambda: svc.status == AIStatus.ONLINE)
        assert svc.client_version == "mock-1.0" and svc.joules == 500
        result = run_one(svc)
        assert result.ok, result.error
        assert set(result.data) == set(SAMPLE_TAVERN.schema.fields)
    finally:
        svc.stop()


@pytest.mark.parametrize("mode", ["fenced", "prose", "wrapped", "garbage_then_ok"])
def test_service_recovers_messy_replies(mode):
    with MockPlayer2(mode) as mock:
        svc = make_service(mock.base_url)
        try:
            assert wait_for(lambda: svc.status == AIStatus.ONLINE)
            result = run_one(svc)
            assert result.ok, result.error
            if mode == "garbage_then_ok":
                assert result.attempts == 2
        finally:
            svc.stop()


@pytest.mark.parametrize("mode", ["garbage", "refusal", "http500", "empty", "truncated"])
def test_service_fails_cleanly_on_bad_replies(mode):
    with MockPlayer2(mode) as mock:
        svc = make_service(mock.base_url)
        try:
            assert wait_for(lambda: svc.status == AIStatus.ONLINE)
            result = run_one(svc)
            assert not result.ok and result.error
        finally:
            svc.stop()


def test_out_of_energy_status():
    with MockPlayer2("http402") as mock:
        svc = make_service(mock.base_url)
        try:
            assert wait_for(lambda: svc.status == AIStatus.ONLINE)
            assert not run_one(svc).ok
            assert wait_for(lambda: svc.status == AIStatus.NO_ENERGY)
        finally:
            svc.stop()


def test_offline_requests_fail_fast():
    svc = make_service(UNREACHABLE)
    try:
        assert wait_for(lambda: svc.status == AIStatus.OFFLINE)
        start = time.monotonic()
        result = run_one(svc)
        assert not result.ok and time.monotonic() - start < 1.0
    finally:
        svc.stop()


def test_disabled_and_simulated_offline(mock_p2):
    svc = make_service(mock_p2.base_url, enabled=False)
    try:
        assert svc.status == AIStatus.DISABLED
        assert not run_one(svc).ok
        svc.set_enabled(True)
        assert wait_for(lambda: svc.status == AIStatus.ONLINE)
        svc.set_simulated_offline(True)
        assert svc.status == AIStatus.SIMULATED_OFFLINE and not run_one(svc).ok
        calls = mock_p2.chat_calls
        svc.set_simulated_offline(False)
        assert wait_for(lambda: svc.status == AIStatus.ONLINE)
        assert mock_p2.chat_calls == calls
    finally:
        svc.stop()


def test_priority_order(mock_p2):
    svc = AIService(prompts=PromptLibrary(Paths().prompts), client_factory=lambda: Player2Client(mock_p2.base_url),
                    workers=1)
    svc._status = AIStatus.ONLINE
    order = []
    variables = {"region": "r", "season": "s", "culture": "c"}
    svc.submit(SAMPLE_TAVERN, variables, priority=Priority.BACKGROUND, callback=lambda r: order.append("bg"))
    svc.submit(SAMPLE_TAVERN, variables, priority=Priority.URGENT, callback=lambda r: order.append("urgent"))
    svc.start()  # workers start after both are queued, so priority decides
    try:
        assert wait_for(lambda: svc.poll() is not None and len(order) == 2, 10)
        assert order == ["urgent", "bg"]
    finally:
        svc.stop()


def test_callback_errors_do_not_escape(mock_p2):
    svc = make_service(mock_p2.base_url)
    try:
        assert wait_for(lambda: svc.status == AIStatus.ONLINE)

        def boom(result):
            raise RuntimeError("bad callback")

        svc.submit(SAMPLE_TAVERN, {"region": "r", "season": "s", "culture": "c"}, callback=boom)
        assert svc.wait_idle(5)
        svc.poll()  # must not raise
    finally:
        svc.stop()


# ---------------------------------------------------------------------------- fallback and store
def test_fallback_tavern_is_complete_and_deterministic(data):
    variables = sample_tavern_variables(RNG(4), data)
    a = sample_tavern_fallback(RNG(1), data, variables)
    b = sample_tavern_fallback(RNG(1), data, variables)
    assert a == b
    assert all(isinstance(a[k], str) and a[k] for k in SAMPLE_TAVERN.schema.fields)
    assert "{" not in a["description"]
    SAMPLE_TAVERN.schema.clean(a)  # fallback text satisfies the same schema as AI text


def test_store_upgrade_only_if_unseen():
    store = FlavorStore()
    store.put("k", {"t": "fallback"}, "fallback")
    assert store.offer_ai("k", {"t": "ai"})
    assert store.get("k") == {"t": "ai"} and store.source("k") == "ai"
    store.put("seen", {"t": "fallback"}, "fallback")
    store.mark_seen("seen")
    assert not store.offer_ai("seen", {"t": "ai"})
    assert store.get("seen") == {"t": "fallback"}


def test_store_ensure_and_round_trip(mock_p2):
    svc = make_service(mock_p2.base_url)
    try:
        assert wait_for(lambda: svc.status == AIStatus.ONLINE)
        store = FlavorStore()
        first = store.ensure("tavern:1", lambda: {"name": "fallback"}, svc, SAMPLE_TAVERN,
                             {"region": "r", "season": "s", "culture": "c"})
        assert first == {"name": "fallback"}
        assert svc.wait_idle(5) and wait_for(lambda: (svc.poll(), store.source("tavern:1") == "ai")[1])
        restored = FlavorStore.from_dict(store.to_dict())
        assert restored.get("tavern:1") == store.get("tavern:1")
        # Once stored, the same key is never regenerated.
        calls = mock_p2.chat_calls
        store.ensure("tavern:1", lambda: {"name": "other"}, svc, SAMPLE_TAVERN, {})
        assert mock_p2.chat_calls == calls
    finally:
        svc.stop()


def test_empty_replies_are_not_retried():
    with MockPlayer2("truncated") as mock:
        svc = make_service(mock.base_url)
        try:
            assert wait_for(lambda: svc.status == AIStatus.ONLINE)
            result = run_one(svc)
            assert not result.ok and result.attempts == 1 and mock.chat_calls == 1
        finally:
            svc.stop()


def test_background_requests_pause_when_energy_is_low():
    with MockPlayer2("ok", joules=3) as mock:
        svc = make_service(mock.base_url)
        try:
            assert wait_for(lambda: svc.status == AIStatus.ONLINE)
            results = []
            svc.submit(SAMPLE_TAVERN, {"region": "r", "season": "s", "culture": "c"}, priority=Priority.BACKGROUND,
                       callback=results.append)
            svc.poll()
            assert results and not results[0].ok and "energy" in results[0].error
            assert run_one(svc).ok  # the player is waiting: still allowed
            assert mock.chat_calls == 1
        finally:
            svc.stop()


def test_every_prompt_is_filled_by_the_facts_the_game_gives_it(data):
    """A prompt with a slot nothing fills would go to the AI with '{slot}' in it."""
    import copy

    from realmwalker.ai import tasks
    from realmwalker.game import death, magic_items, quests
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldGenerator, WorldOptions
    from realmwalker.world.tables import Tables

    tables = Tables(data)
    world = WorldGenerator(WorldOptions("Promptland", 8, "small"), tables).generate()
    game = new_game(copy.deepcopy(world), tables)
    game.survival = False
    lib = PromptLibrary(Paths().prompts)

    item = None
    for i in range(50):
        item = magic_items.make(game, RNG(i, "prompt"), tier=4)
        if item is not None:
            break
    assert item is not None
    from realmwalker.game.people import npcs_in, prepare_town

    town = next(s for s in game.world.settlements if s.kind in ("town", "city"))
    prepare_town(game, town)
    npc = next(n for n in npcs_in(game.world, town.id) if n.job in quests.giver_jobs(game))
    quest = quests.make_offer(game, npc, game.world.rng.child("prompt-quest"))
    game.over = {"cause": "killed in a test", "place": "nowhere"}
    record = death.die(game)

    cases = [(tasks.MAGIC_ITEM, magic_items.dressing_facts(game, item)),
             (tasks.OBITUARY, death.obituary_facts(game, record))]
    if quest is not None:
        cases.append((tasks.QUEST, quests.ai_facts(game, quest)))
    for task, facts in cases:
        template = lib.get(task.name)
        text = template.render({**{k: str(v) for k, v in facts.items()}, "schema": "{}"})
        for slot in ("{giver}", "{task}", "{name}", "{powers}", "{deeds}", "{who}", "{death}", "{base}"):
            assert slot not in text, (task.name, slot)
        assert len(text) > 100
