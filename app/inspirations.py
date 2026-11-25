"""Inspirations: 32 ready example videos in 8 categories, to start from and change.

Each example is a complete starter: scenes (on-screen title, points, narration, picture prompt), the
video type, the look, the music mood and the animation. "Use this example" turns it into a normal
project; with a topic and the local AI, the AI rewrites the example for that topic but keeps its shape.
All texts are original (categories inspired by common video-maker galleries; nothing copied)."""
import io

from . import project as P
from .ai import llm, writer, library

CATEGORIES = [
    ("trending", "Trending Templates", "✦"),
    ("short_film", "Short Film", "🎬"),
    ("music_video", "Music Video", "♫"),
    ("ugc", "UGC Ads", "🤳"),
    ("product", "Product Ads", "📦"),
    ("trailer", "Film Trailer", "🎞"),
    ("social", "Social Content", "💬"),
    ("explainer", "Explainer", "🎓"),
]


def S(title, notes="", script="", image=""):
    return {"title": title, "notes": notes, "script": script, "image": image}


# id, category, name, blurb, video type, look, music mood, opening (title, subtitle), closing (title, notes), scenes
EXAMPLES = [
    # ---------- Trending Templates ----------
    dict(id="before-after", cat="trending", name="Before / After", blurb="Show a transformation in one glance: before, after, the result. Rooms, bodies, gardens, products.",
         type="reel", look="bold", music="tech", open=("Before vs After", "Wait for it…"), close=("Which do you prefer?", "Follow for more"),
         scenes=[S("Before", "", "This is what the room looked like on day one.", "small dull living room, bare walls, harsh light"),
                 S("After", "", "And this is the same room, thirty days later.", "same living room redesigned, warm light, plants, cosy"),
                 S("Budget", "₹ 18,000 total", "Total budget: eighteen thousand rupees.", ""),
                 S("Time", "30 days", "Thirty days, weekends only.", "")]),
    dict(id="top5-countdown", cat="trending", name="Top 5 countdown", blurb="A fast countdown, number five to number one. Places, films, tips, gadgets.",
         type="reel", look="bold", music="tech", open=("Top 5 places to see before 30", "Number one is wild"), close=("Which one is yours?", "Comment below"),
         scenes=[S("5 · Leh, Ladakh", "", "Number five: Leh, Ladakh. Mountains like another planet.", "Ladakh mountains, blue lake, sunrise"),
                 S("4 · Kyoto", "", "Number four: Kyoto in autumn.", "Kyoto temple with red autumn leaves"),
                 S("3 · Santorini", "", "Number three: a Santorini sunset.", "white houses of Santorini at sunset"),
                 S("2 · Iceland", "", "Number two: the northern lights in Iceland.", "northern lights over a snowy Icelandic landscape"),
                 S("1 · Patagonia", "", "And number one: Patagonia. Nothing prepares you for it.", "Patagonia granite peaks, dramatic clouds")]),
    dict(id="did-you-know", cat="trending", name="Did you know?", blurb="One surprising fact, explained in three quick beats.",
         type="reel", look="warm", music="calm", open=("Did you know?", "A fact you won't forget"), close=("Now you know", "Save this for later"),
         scenes=[S("Honey never spoils", "", "Honey never spoils. Archaeologists found three thousand year old honey that was still good.", "jar of golden honey, warm light, macro"),
                 S("Why?", "Very little water\nNatural acids", "It has very little water and natural acids, so bacteria cannot grow.", ""),
                 S("Oldest honey found", "3,000 years old", "Three thousand years. Still edible.", "ancient clay jar in a museum, soft light")]),
    dict(id="day-in-life", cat="trending", name="A day in the life", blurb="Morning to evening of one person, in short timed scenes.",
         type="reel", look="warm", music="calm", open=("A day in the life", "of a café owner"), close=("That's my day", "Follow for part 2"),
         scenes=[S("5:30 · Bake", "", "Five thirty a.m. The bread goes in first.", "baker taking bread out of an oven, early morning"),
                 S("8:00 · Doors open", "", "Eight o'clock. The regulars are already waiting.", "small café with customers, morning sun"),
                 S("Cups today", "312 cups", "Three hundred and twelve cups of coffee today.", "barista pouring latte art, close-up"),
                 S("19:00 · Close", "", "Seven p.m. Lights off. Tomorrow, again.", "empty café at dusk, chairs on tables")]),

    # ---------- Short Film ----------
    dict(id="last-train", cat="short_film", name="The last train", blurb="A short drama: two strangers, one missed train, one night.",
         type="youtube", look="cinematic", music="cinematic", open=("The Last Train", "A short film"), close=("The End", ""),
         scenes=[S("11:58 p.m.", "", "Eleven fifty eight. She runs. The doors close.", "empty railway platform at night, rain, cinematic"),
                 S("A stranger", "", "On the bench, a stranger. Also missed it.", "two strangers on a platform bench, moody light"),
                 S("Until sunrise", "", "Six hours until the next train. They talk until sunrise.", "two silhouettes at dawn on a platform"),
                 S("Same train, next year", "", "One year later, same train. Same seat. Not strangers anymore.", "couple boarding a train in morning light")]),
    dict(id="night-shift", cat="short_film", name="Night shift", blurb="A quiet, human story about the people who work while we sleep.",
         type="youtube", look="cinematic", music="documentary", open=("Night Shift", "A short film"), close=("For everyone on the night shift", ""),
         scenes=[S("The city sleeps", "", "The city sleeps. She does not.", "night city skyline, a single lit hospital window"),
                 S("Ward 4", "", "Ward four. Twelve patients. One nurse.", "hospital corridor at night, blue light"),
                 S("3 a.m.", "", "Three a.m. A hand that needs holding.", "close-up of two hands, soft warm light"),
                 S("Morning", "", "In the morning, nobody saw it. That is the job.", "nurse walking out at dawn, tired, hopeful")]),
    dict(id="first-customer", cat="short_film", name="First customer", blurb="A founder story: from nothing to the first order. Bakery, studio, shop or startup.",
         type="youtube", look="warm", music="calm", open=("First Customer", "How it started"), close=("Still the same promise", ""),
         scenes=[S("A tiny kitchen", "", "It started in a tiny kitchen with one oven and a big loan.", "small home kitchen with one oven, warm nostalgic light"),
                 S("No orders", "", "Six weeks. No orders.", "empty order book on a table, soft light"),
                 S("The call", "", "Then one call. A wedding. Two hundred cakes.", "phone on a flour-covered table"),
                 S("Today", "", "Today, three shops. Same recipe. Same promise.", "bright bakery shop full of customers")]),
    dict(id="the-letter", cat="short_film", name="The letter", blurb="A mystery in four scenes: an old letter changes everything.",
         type="youtube", look="cinematic", music="cinematic", open=("The Letter", "A short film"), close=("Some letters arrive late", ""),
         scenes=[S("An old house", "", "Cleaning out her grandfather's house, she finds a letter.", "dusty attic, light through a small window"),
                 S("Never sent", "", "It was never sent. Dated nineteen sixty two.", "old handwritten letter, close-up, film grain"),
                 S("The address", "", "The address still exists.", "old street with a yellow door, cinematic"),
                 S("The door opens", "", "She knocks. The door opens.", "door opening, light pouring out")]),

    # ---------- Music Video (no narration: words on the beat) ----------
    dict(id="city-beat", cat="music_video", name="City beat", blurb="No voice: big words cut on the beat over city pictures.",
         type="youtube", look="bold", music="tech", voice=False, open=("City Beat", ""), close=("Turn it up", ""),
         scenes=[S("Run"), S("Jump"), S("Shine"), S("Louder"), S("Again"), S("Tonight")]),
    dict(id="city-lights", cat="music_video", name="Lyric video", blurb="A slow, cinematic lyric video: one line per scene.",
         type="youtube", look="cinematic", music="cinematic", voice=False, open=("City Lights", ""), close=("", ""),
         scenes=[S("The city never stops"), S("Neither do we"), S("Every light a promise"), S("Every road a plan")]),
    dict(id="hype-beat", cat="music_video", name="Hype reel", blurb="Vertical hype clip: words punch in on the beat. Drops, launches, events.",
         type="reel", look="bold", music="tech", voice=False, open=("New drop", ""), close=("Out now", ""),
         scenes=[S("Bold"), S("Loud"), S("Limited"), S("Yours")]),
    dict(id="lofi-loop", cat="music_video", name="Calm loop", blurb="A gentle, warm loop for a stream, a waiting room or a shop screen.",
         type="square", look="warm", music="calm", voice=False, open=("Take a breath", ""), close=("Welcome", ""),
         scenes=[S("Slow down"), S("Breathe in"), S("Enjoy the moment")]),

    # ---------- UGC Ads ----------
    dict(id="tried-a-week", cat="ugc", name="I tried it for a week", blurb="First-person, honest review style. Best with your own recording.",
         type="reel", look="warm", music="calm", open=("I tried it for a week", "Honest review"), close=("Would I keep it? Yes.", "Link in bio"),
         scenes=[S("Day 1", "Set up in 10 minutes", "Day one. It took ten minutes to set up. Easier than I thought."),
                 S("Day 3", "", "Day three. I stopped reaching for my old one."),
                 S("Day 7", "Saved 4 hours", "Day seven. It saved me four hours this week."),
                 S("The catch?", "", "The catch? I wish I had it last year.")]),
    dict(id="unboxing", cat="ugc", name="Unboxing", blurb="Open the box, show the first look, say what surprised you.",
         type="reel", look="bold", music="tech", open=("Unboxing", "Let's see what's inside"), close=("First impression: 9/10", ""),
         scenes=[S("The box", "", "Okay, the box is heavier than I expected.", "hands opening a premium box, top view"),
                 S("First look", "", "First look. The finish is really clean.", "close-up of new wireless earbuds, soft light"),
                 S("In the hand", "", "In the hand it feels solid. No rattles.", "hand holding a gadget, studio light")]),
    dict(id="three-reasons", cat="ugc", name="3 reasons I switched", blurb="Quick, persuasive list in your own words.",
         type="reel", look="warm", music="corporate", open=("3 reasons I switched", ""), close=("Your turn", "Try it free"),
         scenes=[S("1 · It's faster", "", "One. It's faster. Done in minutes, not hours."),
                 S("2 · It's simpler", "", "Two. It's simpler. Everything on one screen."),
                 S("3 · It's cheaper", "₹ 299 a month", "Three. It costs two hundred and ninety nine rupees a month.")]),
    dict(id="problem-fix", cat="ugc", name="Problem → fix", blurb="Name the pain, show the fix, show the result.",
         type="reel", look="bold", music="tech", open=("This was my problem", ""), close=("Problem solved", "Link in bio"),
         scenes=[S("The problem", "", "Every morning: tired, no time for breakfast."),
                 S("The fix", "", "Then I started prepping five breakfasts every Sunday."),
                 S("The result", "20 minutes saved a day", "Twenty minutes saved every single day.")]),

    # ---------- Product Ads ----------
    dict(id="feature-hero", cat="product", name="Feature hero", blurb="One product, three features, one call to action.",
         type="youtube", look="corporate", music="corporate", open=("Meet the X200", "Lighter. Quieter. Cheaper to run."), close=("X200 — available now", "Ask for a quote"),
         scenes=[S("Lighter", "Weight down 35%", "Thirty five percent lighter.", "sleek product, studio shot, white background"),
                 S("Quieter", "Noise 62 dB", "At sixty two decibels, you can talk next to it.", ""),
                 S("Cheaper to run", "Energy use -18%", "And it uses eighteen percent less energy.", "")]),
    dict(id="price-offer", cat="product", name="Sale offer", blurb="A short, bold sale clip with the new price counting.",
         type="square", look="bold", music="tech", open=("Festival sale", "This week only"), close=("Order before Sunday", ""),
         scenes=[S("Was", "₹ 4,999", "Was four thousand nine hundred and ninety nine."),
                 S("Now", "₹ 2,999", "Now two thousand nine hundred and ninety nine."),
                 S("Free delivery", "", "And free delivery, all week.")]),
    dict(id="spec-compare", cat="product", name="Us vs them", blurb="Your product against the alternatives, as growing bars.",
         type="youtube", look="corporate", music="corporate", open=("How we compare", "Real numbers"), close=("The numbers speak", ""),
         scenes=[S("Price per month", "Ours: ₹ 299\nBrand A: ₹ 449\nBrand B: ₹ 599", "Price per month. Ours is the lowest."),
                 S("Battery life", "Ours: 40 hrs\nBrand A: 28 hrs\nBrand B: 22 hrs", "And the battery lasts the longest.")]),
    dict(id="launch-teaser", cat="product", name="Launch teaser", blurb="Build curiosity: hints, a date, no full reveal.",
         type="reel", look="cinematic", music="cinematic", open=("Something new", ""), close=("1 · 12", "Save the date"),
         scenes=[S("Lighter", "", "", "silhouette of a product in the dark, rim light"),
                 S("Smarter", "", "", "close-up detail of an edge, dramatic light"),
                 S("Coming soon", "", "")]),

    # ---------- Film Trailer ----------
    dict(id="epic-trailer", cat="trailer", name="Epic film trailer", blurb="Big movie-trailer energy: world, threat, hero, title.",
         type="youtube", look="cinematic", music="cinematic", open=("This winter", ""), close=("Kingdom of Sand", "In cinemas"),
         scenes=[S("A kingdom at the edge of the desert", "", "A kingdom at the edge of the desert.", "ancient desert city at sunset, epic wide shot"),
                 S("The water is gone", "", "When the water disappears…", "dry cracked river bed, dramatic sky"),
                 S("One girl", "", "…one girl walks into the sand.", "lone figure walking into dunes, cinematic"),
                 S("To bring it back", "", "To bring it back.", "storm over dunes, epic")]),
    dict(id="doc-trailer", cat="trailer", name="Documentary trailer", blurb="A calm, serious trailer for a documentary or a brand story.",
         type="youtube", look="cinematic", music="documentary", open=("The Blue", "A documentary"), close=("Coming soon", ""),
         scenes=[S("71% of our planet", "Oceans cover 71%", "Oceans cover seventy one percent of our planet.", "aerial ocean waves, deep blue"),
                 S("We know so little", "", "We have explored less than a quarter of them.", "dark deep sea, faint light rays"),
                 S("One diver", "", "One diver set out to change that.", "diver descending into blue water")]),
    dict(id="mystery-teaser", cat="trailer", name="Thriller teaser", blurb="Short, dark, only questions. Ends on a date.",
         type="reel", look="cinematic", music="cinematic", open=("Nobody left the house", ""), close=("Friday", "In cinemas"),
         scenes=[S("Six guests", "", "Six guests. One locked house.", "old mansion at night, one lit window"),
                 S("Five in the morning", "", "In the morning, there were five.", "breakfast table with one empty chair"),
                 S("Who is lying?", "", "So who is lying?", "close-up of eyes in shadow")]),
    dict(id="anniversary", cat="trailer", name="Anniversary trailer", blurb="Celebrate years of a company, school or team, trailer style.",
         type="youtube", look="cinematic", music="cinematic", open=("25 Years", "1999 — 2024"), close=("Here's to the next 25", ""),
         scenes=[S("It started small", "", "It started with one room and one customer.", "old small workshop, warm film look"),
                 S("Customers served", "1,200 customers", "Today, twelve hundred customers.", ""),
                 S("Same promise", "", "And the same promise.", "team photo, warm light")]),

    # ---------- Social Content ----------
    dict(id="quote-day", cat="social", name="Quote of the day", blurb="One strong line, animated. Instagram, Facebook or LinkedIn.",
         type="square", look="warm", music="calm", voice=False, open=("Quote of the day", ""), close=("Follow for more", ""),
         scenes=[S("Small steps every day", "Big change every year")]),
    dict(id="tip-15s", cat="social", name="Tip in 15 seconds", blurb="One practical tip, fast and vertical.",
         type="reel", look="bold", music="tech", open=("15-second tip", ""), close=("Follow for daily tips", ""),
         scenes=[S("Phone on the other side of the room", "", "Put your phone on the other side of the room at night."),
                 S("You wake up faster", "Snooze down 70%", "You have to get up to stop the alarm. Snoozing drops seventy percent.")]),
    dict(id="myth-fact", cat="social", name="Myth vs fact", blurb="Bust a common myth in your field.",
         type="reel", look="bold", music="tech", open=("Myth vs Fact", ""), close=("Share this", ""),
         scenes=[S("Myth", "", "Myth: you need an hour a day to get fit."),
                 S("Fact", "", "Fact: twenty minutes, done well, is enough."),
                 S("Proof", "20 minutes a day", "Twenty minutes a day, four days a week.")]),
    dict(id="poll-question", cat="social", name="Poll / question", blurb="Ask your audience something and show the options.",
         type="square", look="warm", music="calm", open=("Quick question", ""), close=("Vote in the comments", ""),
         scenes=[S("Where would you go?", "Mountains\nBeach\nCity\nDesert", "Next holiday: mountains, beach, city or desert?")]),

    # ---------- Explainer ----------
    dict(id="four-steps", cat="explainer", name="How it works in 4 steps", blurb="A clear process, one step per scene. Apps, services, recipes.",
         type="youtube", look="corporate", music="corporate", open=("How it works", "4 simple steps"), close=("That's it", "Questions? Contact us"),
         scenes=[S("1 · Sign up", "Takes 1 minute", "Step one: sign up. It takes one minute."),
                 S("2 · Choose", "Pick what you need", "Step two: pick what you need."),
                 S("3 · Confirm", "Pay safely", "Step three: confirm and pay safely."),
                 S("4 · Enjoy", "Delivered in 2 days", "Step four: it arrives in two days.")]),
    dict(id="science-simple", cat="explainer", name="Science, simply", blurb="Explain one idea for curious people, in four short scenes.",
         type="youtube", look="warm", music="documentary", open=("Why is the sky blue?", "Explained in one minute"), close=("Now you know", "Subscribe for more"),
         scenes=[S("Sunlight has all colours", "", "Sunlight looks white, but it carries every colour.", "prism splitting light into a rainbow"),
                 S("Air scatters blue", "", "Tiny air molecules scatter blue light much more than red.", ""),
                 S("So the sky looks blue", "", "So wherever you look, blue light reaches your eyes.", "clear blue sky over a field"),
                 S("And sunsets?", "", "At sunset, light travels further, the blue is lost, and red remains.", "orange red sunset over the sea")]),
    dict(id="cost-breakdown", cat="explainer", name="Where the money goes", blurb="A breakdown as a growing chart: a budget, a product, a project.",
         type="youtube", look="corporate", music="corporate", open=("Where does the money go?", "A film budget, explained"), close=("Biggest lever: shooting days", ""),
         scenes=[S("Budget breakdown", "Crew: ₹ 9,00,000\nEquipment: ₹ 4,00,000\nLocations: ₹ 3,00,000\nPost-production: ₹ 2,50,000",
                   "The crew is by far the biggest cost, then equipment."),
                 S("Shooting days", "12 days", "Every extra shooting day adds to all of it.")]),
    dict(id="status-update", cat="explainer", name="Project status update", blurb="A crisp update for a team or client: progress, budget, risks.",
         type="youtube", look="corporate", music="documentary", open=("Project status", "Week 46"), close=("Next review: week 48", ""),
         scenes=[S("Progress", "Script 100%\nShooting 60%\nEditing 20%", "Script is done, shooting sixty percent, editing twenty."),
                 S("Budget", "Spent 48% of budget", "We have spent forty eight percent of the budget."),
                 S("Risks", "Weather on location\nActor availability", "Two risks: weather on location, and actor availability.")]),
]

BY_ID = {e["id"]: e for e in EXAMPLES}
TYPE_LABEL = {"youtube": "16:9", "reel": "9:16", "square": "1:1", "corporate": "16:9"}


def public(e):
    cat = next(c for c in CATEGORIES if c[0] == e["cat"])
    return {"id": e["id"], "category": e["cat"], "category_label": cat[1], "icon": cat[2], "name": e["name"],
            "blurb": e["blurb"], "type": e["type"], "format": TYPE_LABEL[e["type"]], "look": e["look"],
            "music": e["music"], "voice": e.get("voice", True), "scenes": len(e["scenes"]),
            "thumb": f"/inspirations/thumb/{e['id']}.jpg"}


def catalogue():
    return {"categories": [{"id": c, "label": l, "icon": i, "count": sum(e["cat"] == c for e in EXAMPLES)}
                           for c, l, i in CATEGORIES],
            "examples": [public(e) for e in EXAMPLES]}


def _fill(proj, e, scenes):
    """Put the example's opening, scenes and closing into a (new) project."""
    voice = e.get("voice", True)
    t, sub = e["open"]
    first, last = proj["slides"][0], proj["slides"][-1]
    first["title"], first["notes"] = t, sub
    first["script"] = f"{t}. {sub}".strip(". ") + "." if voice and t else ""
    last["title"], last["notes"] = e["close"]
    last["script"] = (". ".join(x for x in e["close"] if x) + ".") if voice and any(e["close"]) else ""
    for sc in scenes:
        s = P.add_content_slide(proj, sc["title"], sc.get("notes", ""))
        s["script"] = sc.get("script", "") if voice else ""
        s["image_prompt"] = sc.get("image") or ""
    proj["title"], proj["subtitle"] = t or e["name"], sub


def create(eid, name=None):
    """A new project made from the example, unchanged (works offline)."""
    e = BY_ID[eid]
    proj = P.new_project(name or e["name"])
    _fill(proj, e, e["scenes"])
    proj.update(look=e["look"], motion="motion", video_type=e["type"], example=eid,
                intro=e["look"] == "corporate",
                captions=e.get("voice", True))
    from .maker import use_library_music
    use_library_music(proj, e["music"])
    if not e.get("voice", True):
        proj["music"]["volume"] = 0.55            # music video: the music is the soundtrack
    P.save(proj)
    return proj


def adapt(proj, eid, topic, language="en", progress=lambda f, m: None):
    """The local AI rewrites the example's scenes for the user's topic, keeping their shape."""
    e = BY_ID[eid]
    voice = e.get("voice", True)
    shape = "\n".join(f"{k + 1}. title: {s['title']} | points: {s['notes'].replace(chr(10), '; ') or '-'} | "
                      f"narration: {s['script'] or '-'}" for k, s in enumerate(e["scenes"]))
    progress(0.1, "The AI is adapting the example to your topic")
    data = llm.generate_json(
        f"Here is an example video script ({e['name']}, style: {e['blurb']}):\n{shape}\n\n"
        f"Rewrite it for this topic: {topic}\n"
        f"Keep exactly {len(e['scenes'])} scenes and the same structure, tone and length. Keep points short; "
        "where the example has numbers, use realistic numbers for the topic only if the topic states them, "
        "otherwise use placeholders like 'X%'. "
        + (f"Narration in {writer.lang_name(language)}, same length as the example. " if voice else "No narration. ") +
        f"Also write a new opening title and subtitle and a closing line. Picture prompts in English, no text in images. "
        'Return JSON: {"open": ["title", "subtitle"], "close": ["title", "line"], '
        '"scenes": [{"title": "...", "points": ["..."], "line": "...", "image": "..."}]}',
        "You adapt video templates to new topics. Answer in JSON only.", temperature=0.6, num_ctx=8192)
    scenes = writer._doc_items(data) if voice else [
        {"title": str(s.get("title") or "").strip(), "points": s.get("points") or [], "line": "", "image": s.get("image", "")}
        for s in (data.get("scenes") or []) if isinstance(s, dict) and s.get("title")]
    if len(scenes) < max(1, len(e["scenes"]) // 2):
        raise llm.LLMError("The local AI could not adapt this example. Try again, or use it unchanged.")
    mine = dict(e)
    o, c = data.get("open") or [], data.get("close") or []
    mine["open"] = (str(o[0]) if o else e["open"][0], str(o[1]) if len(o) > 1 else "")
    mine["close"] = (str(c[0]) if c else e["close"][0], str(c[1]) if len(c) > 1 else "")
    # replace the example scenes with the adapted ones
    proj["slides"] = [proj["slides"][0], proj["slides"][-1]]
    _fill(proj, mine, [{"title": s["title"], "notes": "\n".join(s.get("points") or []), "script": s.get("line", ""),
                        "image": s.get("image", "")} for s in scenes])
    progress(1, "Done")
    return proj


def thumbnail(eid):
    """A 640x360 JPEG of the example's key scene in its look (drawn on this laptop, cached)."""
    from . import motion
    from .config import MODELS_DIR
    from .version import app_version
    e = BY_ID[eid]
    cache = MODELS_DIR / "thumbs" / f"{eid}-{app_version()}.jpg"
    if cache.exists():
        return cache.read_bytes()
    proj = {"id": "inspiration", "look": e["look"], "title": e["open"][0], "subtitle": e["open"][1],
            "presenter": "", "company": "", "contact": "", "logo": None}
    # the most telling scene: a chart or counter if there is one, else the first scene
    scenes = [dict(sc, kind="content", image=None, id=str(k)) for k, sc in enumerate(e["scenes"])]
    pick = next((s for s in scenes if motion.plan(proj, s)["type"] in ("bars", "counter")), scenes[0])
    im = motion.still(proj, pick, 1, len(scenes) + 2, at=4.0, dur=6.0).resize((640, 360))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(buf.getvalue())
    return buf.getvalue()


assert len(EXAMPLES) == 32 and all(e["music"] in library.MOODS for e in EXAMPLES)
