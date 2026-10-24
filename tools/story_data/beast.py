"""The Beast of {place} (Expansion 6 Part A, docs/ADVENTURES.md §6.2), written as data.

Run once to (re)write its entries into data/packs/06_adventures_events/ (adventures.json, beats.json, villains.json);
the other entries of those files are kept. The words are the game's own (EXPANSIONS.md §1.5).

    .venv/Scripts/python.exe tools/story_data/beast.py
"""

from __future__ import annotations

import json
from pathlib import Path

PACK = Path(__file__).resolve().parents[2] / "data" / "packs" / "06_adventures_events"

BLUEPRINT = {
    "name": "The Beast of {place}", "tiers": [1, 3], "from": ["beast"], "flavours": ["folk", "dark_fantasy"],
    "title": ["The Beast of {town}", "The Hunt for {villain}", "{villain_short} of {home}", "What Walks Above {town}",
              "The Hunger at {town}"],
    "hook": [
        "{patron} meets you at the door with the look of someone who has not slept. \"It is {villain}. It has come "
        "down from {home} again, and this time it took one of ours. You have the look of someone who could finish it.\"",
        "\"We have sent to the lord, and the lord sent no one,\" says {patron}. \"{villain} has killed at {town} and it "
        "will kill again. Whatever we can pay is yours, if you will hunt it.\"",
        "The whole of {town} seems to be at the well when you come, and the talk is all of {villain}. It is "
        "{patron} who asks you plainly: will you go up to {home} and put an end to it?",
        "{patron} has the hide of a dog that was torn in half laid out on the table. \"That was the bravest dog in "
        "{town},\" they say. \"{villain} did that in the dark, in a breath. Will you hunt it?\""],
    "premise": ["A named killer of the old songs has come down from {home} on {town}: find what it is, learn what it "
                "fears, and kill it in its den.",
                "{villain} is killing round {town} again. Read its kills, find the one who saw it, learn what it fears, "
                "and finish it at {home}.",
                "{town} is being eaten, a family at a time, by {villain} out of {home}. Somebody has to learn how it "
                "can be killed, and then go up and do it."],
    "places": {
        "home": "threat.home",
        "town": "settlement_near(home, 2, 18) | settlement_near(home, 0, 40)",
        "kill": "road_tile_near(town, 2, 7) | road_tile_near(home, 1, 12)",
        "lore": "settlement_with(temple, 0, 40) | town"},
    "cast": {
        "patron": {"pick": ["headman_of(town)", "notable_of(town)"]},
        "ally": {"pick": ["hunter_of(town)"]},
        "witness": {"pick": ["survivor_of(town)"]},
        "innocent": {"pick": ["settlement(town)"]}},
    "hidden": {"weakness": "weakness_of(villain)"},
    "chapters": [
        {"id": "killings", "need": "all",
         "title": ["The Killings", "Blood on the Hill Road", "What Came Down in the Night"],
         "goal": ["Go to where it last killed, read what it left, and find who saw it."],
         "opening": [
             "{town} counts its dead. Somewhere on the road below {home} is the last of them, and the one who lived.",
             "The first thing is to see what it did. The second is to find the one who saw it do it.",
             "Every hunt begins with the kill. {villain_short} left one on the road out of {town}, not two days ago."],
         "reveal": [
             "There is no doubt now. This is {villain}, that took {victim} in {victim_year} and has been fed on the "
             "fear of {area} ever since. It sleeps at {home}, and it is not afraid of anything that has hunted it yet.",
             "The old ones of {town} know the name, once they are made to say it: {villain}. It killed {victim}, years "
             "ago, and came back for more. Its den is {home}.",
             "Tracks, a name and a den: {villain}, the {beast} of the old songs, that killed {victim} in "
             "{victim_year}. Nobody has gone up to {home} after it and come back whole."],
         "steps": [
             {"kind": "go", "at": "kill", "beat": "beast_kill_found", "gives": ["lead:kill"]},
             {"kind": "search", "at": "kill", "beat": "beast_search_kill", "skill": "survival", "dc": 12,
              "gives": ["clue:size"]},
             {"kind": "witness", "who": "witness", "words": "beast_witness", "gives": ["clue:name"]}]},
        {"id": "price", "need": "all",
         "title": ["The Hunt's Price", "What It Fears", "Bait or Blood"],
         "goal": ["Learn what will hurt it, get the means, and choose how to bring it to you."],
         "opening": [
             "Nobody kills {villain} by walking up to it. You need to know what it fears, and to carry it with you.",
             "{patron} has done their part: they have told you everything they know. The rest is yours to find out.",
             "A beast that has lived through every hunt has a weakness, or it would have died. Find it."],
         "reveal": [
             "It came, and it bled, and it ran. Now it is in {home} with its wound, and there is nowhere else for it "
             "to go. Neither is there for you.",
             "{villain_short} knows you now. It will be waiting in the dark of {home}, and it will not run again.",
             "You have hurt it, and it has gone back to its den to lick the wound. It is now or never: up to {home}."],
         "steps": [
             {"kind": "learn", "about": "villain",
              "routes": ["sage(lore)", "ask(ally)", "nature(kill)", "divine()"], "beat": "beast_lore_at_kill",
              "gives": ["key:weakness"]},
             {"kind": "prepare", "what": "weakness", "gives": ["key:means"]},
             {"kind": "choose", "beat": "beast_bait_or_track"},
             {"kind": "slay", "who": "villain", "fled_ok": True}]},
        {"id": "den", "need": "all",
         "title": ["The Den", "Into {home}", "The Last of {villain_short}"],
         "goal": ["Go up to {home} and finish it."],
         "opening": [
             "The way to {home} is short, and seems long. You will not need to look for {villain_short}: it knows you "
             "are coming.",
             "{town} watches you go. Some of them pray; the rest only stand at the edge of the fields and wait.",
             "There is nothing left to learn and nothing left to buy. There is only {home}, and what sleeps in it."],
         "reveal": [
             "It is done.", "It is over.", "The den is quiet."],
         "steps": [
             {"kind": "go", "at": "home", "beat": "beast_the_den"},
             {"kind": "finale", "at": "home.deepest"}]}],
    "finale": {"boss": "villain", "template": "beast", "at": "home.deepest",
               "keys": {"weakness": ["weakness"], "bait": ["surprise"], "quiet": ["surprise"], "ally": ["ally_fights"]},
               "words": {
                   "warning": ["The air beyond this point stinks of old blood and rot. Whatever lives here is very "
                               "close, and it is awake.",
                               "Bones underfoot, gnawed white, and a breathing in the dark ahead that is not yours.",
                               "This is the end of the den. Rest now if you mean to, because there will be no rest "
                               "beyond it."],
                   "first": ["It rises from the bones, and keeps rising.",
                             "It knows you. It has been waiting.",
                             "Its eyes take the torchlight and give back none of it."]}},
    "endings": [
        {"id": "slain", "if": ["boss_dead"],
         "ops": [["beast_slain"], ["clear_site", "home"], ["danger", "home", -1], ["fame", 3],
                 ["history", "beast_hunt", 3]],
         "pages": {
             "place": ["{town} sleeps with its doors unbarred for the first time in a year. The children are let "
                       "out to the fields again, though their mothers still count them at dusk.",
                       "The people of {town} dragged what was left of {villain_short} into the square and burned it "
                       "there. Everyone came to watch, and nobody cheered until it was ash.",
                       "There is a new song in the inn at {town}, and it is about you. It is not a good song, but they "
                       "sing it every night.",
                       "{town} hung the skull of {villain} over the door of its hall, and the elders swear the flocks "
                       "are fatter for it already."],
             "patron": ["{patron} paid what they promised, and would have paid twice. \"I did not think anyone would "
                        "come,\" they said. \"Nobody ever does.\"",
                        "{patron} keeps a seat by the fire for you, they say, should you ever come back to {town}.",
                        "{patron} has sent word to every farm in {area}: whoever shelters you, shelters a friend of "
                        "{town}.",
                        "{patron} went out afterwards, alone, to see the body for themselves. They came back and "
                        "said nothing at all for a day."],
             "ally": ["{ally} has the beast's old runs for a trap-line now, and says the hares are bolder than they were.",
                      "{ally} tells the tale in the inn whenever someone buys the ale, and makes your part bigger "
                      "every time.",
                      "{ally} went back to the woods. They say they think of you when the light goes.",
                      "{ally} is the one the villages call for now, when something is at the flocks."],
             "witness": ["{witness} still will not take the hill road. But they sleep, now.",
                         "{witness} came to see the body, to be sure. They stood over it a long time.",
                         "{witness} lit a candle at the shrine for the ones who did not come back, and one for you.",
                         "{witness} has told it so often that they half believe they were brave."],
             "hero": ["You came back to {town} with blood to the elbow and the name {villain} in every mouth.",
                      "The hunt is over. You are a little more than you were: someone who hunted {villain} and "
                      "lived.",
                      "Somewhere a minstrel is already getting it wrong. That is what it is to be remembered.",
                      "You will not forget {villain}. Neither, now, will anyone in {area}."]}},
        {"id": "doom", "if": ["scheme_done"],
         "ops": [["fame", -1]],
         "pages": {
             "place": ["{town} is empty. The doors hang open and the hearths are cold. {villain} has the fields.",
                       "The last cart left {town} with the dawn. Whoever stays now stays with {villain}.",
                       "Nobody tends the graves at {town} now. The grass is up to the windows.",
                       "{town} stands, but nobody lives in it. They say the beast walks the street at night."],
             "patron": ["{patron} went with the others, and did not look back at you.",
                        "{patron} is somewhere on the roads with what is left of {town}.",
                        "{patron} asked you to hunt it. You did not, in time. They will not ask anyone again.",
                        "Nobody knows where {patron} went when {town} emptied."],
             "hero": ["It won. Not every hunt ends with a body.",
                      "{villain} still lives at {home}, fatter than it was.",
                      "There will be other hunters. Perhaps they will be in time.",
                      "You will hear the name {villain} again. It will not be a kind story."]}},
        {"id": "abandoned", "ops": [["threat_free"]],
         "pages": {
             "place": ["{town} waits for someone else to come.",
                       "In {town} they still speak of the hunter who came and went.",
                       "{town} bars its doors at dusk, as it did before you came.",
                       "{villain} is not dead. {town} knows it every night."],
             "hero": ["You left the hunt to others.",
                      "Some tales are not yours to finish.",
                      "{villain} will go on without you.",
                      "The road took you elsewhere, and {home} is behind you."]}}],
    "epithets": ["beast", "hunter"]}

EPITHETS = {
    "beast": ["Beastslayer", "the Hunter", "of the Long Hunt", "the Butcher of {villain_short}",
              "who Went Up to {home}", "Bane of {villain_short}"],
    "hunter": ["the Tracker", "Keen-Eye", "the Trapper", "Grey-Cloak", "the Patient", "who Never Misses"]}

WORDS = {
    "beast_witness": [
        "\"I was on the hill road with the cart,\" {witness} says, and has to stop. \"It came out of the scrub like the "
        "ground itself was getting up. It took the ox, not me. It looked at me, and took the ox.\"",
        "{witness} will not look at you while they tell it. \"Big as a haywain. It went up towards {home} with half the "
        "carcass in its jaws, and I never heard it breathe hard once.\"",
        "\"They'll tell you I was drunk,\" says {witness}. \"I wasn't. It stopped in the road to look at me. "
        "Then it went back towards {home}, slow, like it had all the time there is.\"",
        "{witness} shows you the scar first. \"It did that going past, without even stopping. If it had stopped I'd be dead. "
        "It wasn't hungry for me. Not that night.\""],
    "witness_tale": [
        "{witness} tells you what they saw, and their hands shake the whole time.",
        "\"I saw it,\" {witness} says. \"I wish to every god I hadn't.\"",
        "{witness} tells it plainly, as if they had told it many times to themselves in the dark."],
    "patron_brief": [
        "\"{goal}\" {patron} says. \"That is all I know to tell you. Go carefully.\"",
        "{patron} counts it off on their fingers. \"{goal} After that, you know more than I do.\"",
        "\"We are counting on you,\" says {patron}. \"{goal}\""],
    "dread": ["the dark that sits on {area}", "the hunger of {villain}", "what walks above {town}"],
    "dusk": ["the light going amber over the hills", "the last of the day leaving the fields",
             "the long shadows reaching for the road"],
    "carcass": ["what is left of a big ox, opened along the belly", "the remains of a carter's mule, half of it gone",
                "a cow, or what was a cow, dragged a long way from its field"],
    "track": ["marks in the soft earth as broad as a shield, pressed deep", "a furrow where something heavy dragged its kill",
              "the bark of an old ash torn away higher than a man can reach"]}

BEATS = {
    "story_hook": {
        "family": "hook", "picture": "here", "title": ["{villain}"],
        "text": [["{hook}", "Word is going round, and it is all the same word: {hook}",
                  "{hook} Everyone you meet seems to be talking of nothing else."]],
        "choices": [
            {"label": ["I will hunt it. (A tale begins: the journal keeps it.)"], "ops": [["take_hook"]]},
            {"label": ["Not now."], "ops": [["decline_hook"]],
             "result": ["Someone else, then. Or no one. You put it out of your mind, almost."]}]},
    "beast_kill_found": {
        "family": "step", "picture": "place",
        "text": [["The road leaves the fields here and goes on between banks of scrub, and at the bend you find it: "
                  "{carcass}. The crows go up all at once.",
                  "You smell it before you see it. Off the road, in the ditch, {carcass}, and the flies thick over it.",
                  "There is a bend in the road where the scrub closes in, and it is there: {carcass}, and the ground "
                  "round it torn up."],
                 ["Whatever did this was not hungry. It ate the best of it and left the rest, as if to say it could.",
                  "Beyond the carcass the scrub is flattened in a wide swathe going off towards {home}.",
                  "Nothing on the road but you, and the wind in the scrub, and that smell."]],
        "choices": [{"label": ["Look closer."], "ops": [["clue", "kill"]],
                     "result": ["You kneel by it. Whatever left this, you will know it again."]}]},
    "beast_search_kill": {
        "family": "step", "picture": "place",
        "text": [["You go over the ground round the kill, a yard at a time: {track}.",
                  "Now you look properly. There is a story in the trampled ground, if you can read it: {track}.",
                  "The wounds first, then the ground: {track}, and blood on the scrub at a man's height."]],
        "choices": [
            {"label": ["Read the tracks, however long it takes."], "check": {"skill": "survival", "dc": 12},
             "success": [["clue", "size"], ["clue", "lair_way"]], "failure": [["clue", "size"], ["time", 180]],
             "result": ["It is big, bigger than anything that should live in {area}, and it went back up towards "
                        "{home} by a way the herders do not use."],
             "fail_result": ["It takes you half the day, and a good deal of swearing, but in the end the ground "
                             "tells you: it is big, and it went up towards {home}."]},
            {"label": ["Take a tooth from the carcass, broken off in the wound. Proof for {town}."],
             "ops": [["clue", "size"], ["flag", "took_tooth"]],
             "result": ["The tooth is as long as your finger and yellow with age. {town} will believe you now."]},
            {"label": ["Burn the carcass, so it draws nothing else down from {home}."],
             "ops": [["clue", "size"], ["flag", "burned_carcass"], ["time", 60]],
             "result": ["The smoke goes up black and greasy. Whatever watches from the hills will know someone is "
                        "here, and is not afraid."]}]},
    "beast_bait_or_track": {
        "family": "step", "picture": "place",
        "text": [["You know what it fears now. What is left is to bring it to you, or to go to it.",
                  "There are two ways to hunt a beast like {villain}: make it come to you, or follow it until it "
                  "turns. Both have killed better hunters than you.",
                  "{ally} lays it out plainly. \"Stake out bait and wait, or follow its trail till it turns."
                  " Your choice. I know which one I'd pick, and I'm not telling you.\""]],
        "choices": [
            {"label": ["Stake out a bait here, and wait in the dark."], "requires": {"item": ["raw_meat",
                                                                                                     "cooked_meat",
                                                                                                     "rations"]},
             "ops": [["flag", "baited"], ["key", "bait"], ["use", "raw_meat", "cooked_meat", "rations"], ["time", 360],
                     ["named_fight", "villain"]],
             "result": ["The night is long and cold and nothing comes, and nothing, and then the bait is gone and "
                        "{villain_short} is among you."]},
            {"label": ["Follow its trail, and let it turn on you."],
             "ops": [["flag", "tracked"], ["time", 240], ["fatigue", 10], ["named_fight", "villain"]],
             "result": ["The trail goes on through the scrub and the broken ground, and then there is no more trail, "
                        "because {villain_short} has stopped running."]}]},
    "beast_the_den": {
        "family": "step", "picture": "place",
        "text": [["{home} gapes in the hillside. Nothing grows near the mouth of it, and the bones there are not "
                  "all sheep.",
                  "You reach {home} with the wind in your face, which is the only luck you have had. The den's mouth "
                  "breathes out a warm stink.",
                  "Here it is: {home}. Below the mouth, a midden of bones and wool, and a path worn smooth by "
                  "something heavy coming and going."]],
        "choices": [
            {"label": ["Go in quietly, keeping to the walls."], "check": {"skill": "stealth", "dc": 13},
             "success": [["key", "quiet"], ["flag", "went_quietly"]], "failure": [["flag", "went_quietly"]],
             "result": ["You go in as quiet as breath. If it sleeps, it will wake to you standing over it."],
             "fail_result": ["A stone turns under your boot and rattles away into the dark. Somewhere below, "
                             "something stops breathing to listen."]},
            {"label": ["Light a fire at the mouth and let the smoke go in first."],
             "requires": {"item": ["firewood", "oil_flask", "torch"]},
             "ops": [["flag", "smoked_it"], ["time", 60]],
             "result": ["The smoke rolls into the den. From somewhere deep comes the sound of something heavy moving, "
                        "and then a noise like no animal you know."]},
            {"label": ["Go in with everything you have, and let it know you are coming."],
             "ops": [["flag", "went_loudly"]],
             "result": ["You go in shouting. Let it come. You are done with waiting."]}]},
    "beast_omen": {
        "family": "villain", "picture": "here", "where": ["road", "wild", "camp"],
        "text": [["{omen}", "You stop on the way, and look, and wish you had not. {omen}",
                  "{omen} Nobody else on the road seems to have seen it, or they will not say."],
                 ["You go on, but you go on faster.", "It is a long way yet to anywhere with a door that bars.",
                  "{villain_short} is not far. It wants you to know that."]]},
    "beast_carcass": {
        "family": "villain", "where": ["camp"], "time": ["dawn", "day"], "picture": "camp_night",
        "when": {"adventure": {"chapter": ["killings", "price"], "at_large": True}},
        "text": [["In the morning there is a dead hind at the edge of your camp, laid out as neat as a gift, its "
                  "throat torn out.",
                  "At first light you find it: a sheep's head, set on a stone where the fire was, watching the "
                  "camp.",
                  "Something came in the night, and went, and left you a carcass at the edge of the firelight. "
                  "Nobody heard a thing."],
                 ["It knows where you sleep. It wants you to know it knows.",
                  "{villain_short} does not need to write letters.",
                  "The message is plain enough: it is not afraid of you."]],
        "choices": [
            {"label": ["Burn it, and break camp."], "ops": [["flag", "burned_its_gift"]],
             "result": ["You burn it, and go, and keep looking back."]},
            {"label": ["Study it: how it was killed tells you something."], "check": {"skill": "nature", "dc": 12},
             "success": [["clue", "villain"]], "failure": [["time", 30]],
             "result": ["The bite is the bite of the old songs. You learn a little of how it kills."],
             "fail_result": ["It tells you nothing you did not know, except that it was very strong."]}]},
    "beast_test_night": {
        "family": "villain", "where": ["camp"], "time": ["night"], "picture": "camp_night",
        "when": {"adventure": {"chapter": ["killings", "price"], "at_large": True}},
        "text": [["In the dead of night the horses scream, and then there is something huge between the fire and "
                  "the dark.",
                  "The watch shouts once, and you wake to a weight hitting the edge of camp and a smell like a "
                  "slaughterhouse.",
                  "It comes in the black hour before dawn, testing: a rush at the firelight, and then gone, and then "
                  "a rush from the other side."]],
        "choices": [
            {"label": ["Stand to the fire and drive it off."], "check": {"skill": "athletics", "dc": 13},
             "success": [["attention", 1]], "failure": [["hurt", "1d6"], ["attention", 1]],
             "result": ["You stand, and shout, and swing, and it goes. It was only testing you."],
             "fail_result": ["It knocks you down on its way out of the light, and is gone before you are up."]},
            {"label": ["Throw it the meat you carry, and let it go."], "requires": {"item": ["raw_meat",
                                                                                            "cooked_meat"]},
             "ops": [["use", "raw_meat", "cooked_meat"], ["flag", "fed_it"]],
             "result": ["It takes the meat and goes. You have taught it something, and you are not sure what."]}]},
    "beast_lore_at_kill": {
        "family": "step", "picture": "place", "where": ["road", "wild"],
        "text": [["You come back to the kill to look again, now that you know what you are looking for.",
                  "The kill is older now, and the crows have done their work, but there is more here to read.",
                  "The bones of the kill tell their story to anyone who knows the beasts of {area}."]],
        "choices": [
            {"label": ["Think back on every beast-tale you know."], "check": {"skill": "nature", "dc": 13},
             "success": [["clue", "villain"], ["step_done"]], "failure": [["time", 120]],
             "result": ["{weakness_lore}"],
             "fail_result": ["Nothing comes. You will have to ask someone who knows."]}]},
}

TEMPER = {
    "speaks": False,
    "moves": {"omen": 3, "carcass": 2, "test": 1},
    "first_words": [
        "It does not roar. It breathes, long and slow, and the sound fills the dark.",
        "It comes out of the dark without hurry, as if this is the hundredth time and you are the hundredth hunter.",
        "A sound like a mill-wheel turning, somewhere in the dark ahead. Then it comes.",
        "It lowers itself, and gathers, and looks at you with something like hate.",
        "It shakes itself, and old blood flies from it, and it opens its jaws wide.",
        "It smells you before it sees you, and it is glad."],
    "omens": [
        "A dead raven on the path, its head bitten clean away.",
        "Every dog in the hamlet you pass is howling, and none of them will say why.",
        "The birds go quiet in the trees around you, all at once, as if a door had shut.",
        "The brambles torn and wet at the height of your shoulder, as if something big had pushed through.",
        "A shepherd's crook broken in two and thrown down in the road.",
        "Somewhere far off, on the wind, a sound that might be a laugh and is certainly not.",
        "The horses will not settle. They stare at the treeline with their ears flat.",
        "A trail of blood crossing the road, still wet, going nowhere you can see."]}

MOVES = {"omen": {"beat": "beast_omen", "attention": [0, 9]},
         "carcass": {"beat": "beast_carcass", "attention": [1, 9]},
         "test": {"beat": "beast_test_night", "attention": [2, 9]}}

BOSS = {"tiers": [1, 3], "roles": ["beast"], "hp": 1.6, "resistances": 1, "actions": 2, "menu": ["move", "strike"],
        "phase": {"at": 0.5, "kind": "frenzy", "lines": [
            "Cornered and bleeding, it stops being careful.",
            "It howls, and when it comes again it comes like a landslide.",
            "Something breaks in it. It is past fear now, and past cunning."]},
        "before": {"at": 0.5, "kind": "breaks_off", "lines": [
            "It has had enough of you, for now. It turns and goes, faster than anything that size should move.",
            "Bleeding, it backs off a step, and another, and then it is gone into the dark towards its den.",
            "It gives one long look at you, as if to remember your faces, and runs."]}}

FIRE_LORE = ["The old ones say {villain_short} hates fire more than it hates the hunters: its wounds that are burned do "
             "not close.",
             "Fire. The tales all agree on it. Whatever {villain_short} is, burning flesh stays burned.",
             "\"Bring fire,\" the old songs say of beasts like this one. \"Iron cuts, but fire ends.\""]
BAIT_LORE = ["It is greedy, the tales say. It has never once passed by a meal laid out for it, though it knew it was "
             "a trap.",
             "Its hunger is its weakness: lay out meat and it will come to it, every time, and come blind.",
             "Old hunters of {area} say it is bait that kills such beasts, not blades: it cannot help itself."]
FEAR_LORE = ["Fire frightens it, as it frightens every beast: a burning brand thrust in its face will make it shy.",
             "It is a beast still, for all its name: fire in the hand will turn it, for a moment.",
             "The hunters' trick is old and simple: a torch in the face, and it falters long enough for a blow."]

WEAKNESSES = {
    "troll": [{"id": "troll_fire", "name": "fire", "keys": ["vulnerable(fire)"], "lore": FIRE_LORE,
               "means": ["oil_flask", "alchemists_fire", "torch"]}],
    "giant_spider": [{"id": "spider_fire", "name": "fire", "keys": ["vulnerable(fire)"], "lore": FIRE_LORE,
                      "means": ["torch", "oil_flask", "alchemists_fire"]}],
    "ogre": [{"id": "ogre_greed", "name": "its greed", "keys": ["surprise"], "lore": BAIT_LORE,
              "means": ["raw_meat", "cooked_meat", "rations"]}],
    "brown_bear": [{"id": "bear_greed", "name": "its hunger", "keys": ["surprise"], "lore": BAIT_LORE,
                    "means": ["raw_meat", "cooked_meat", "rations"]}],
    "dire_wolf": [{"id": "wolf_fire", "name": "fire in the hand", "keys": ["frightened(1)"], "lore": FEAR_LORE,
                   "means": ["torch", "oil_flask"]}],
    "beast": [{"id": "beast_fire", "name": "fire in the hand", "keys": ["frightened(1)"], "lore": FEAR_LORE,
               "means": ["torch", "oil_flask"]}]}


def _write(name: str, update) -> None:
    p = PACK / name
    d = json.loads(p.read_text(encoding="utf-8"))
    update(d)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    def adv(d):
        d["blueprints"]["beast"] = BLUEPRINT
        d["words"].update(WORDS)
        d["epithets"].update(EPITHETS)

    def beats(d):
        d["beats"].update(BEATS)

    def vil(d):
        d["tempers"]["bestial"] = TEMPER
        d["moves"].update(MOVES)
        d["bosses"]["beast"] = BOSS
        d["weaknesses"].update(WEAKNESSES)

    def thr(d):
        d["kinds"]["beast"]["tempers"] = ["bestial"]
        d["kinds"]["beast"]["blueprints"] = ["beast"]

    _write("adventures.json", adv)
    _write("beats.json", beats)
    _write("villains.json", vil)
    _write("threats.json", thr)


if __name__ == "__main__":
    main()
