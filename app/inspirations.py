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
    ("viral", "Viral presets", "⚡"),
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

def X(id, cat, name, blurb, type, look, music, open, close, scenes, voice=True):
    return dict(id=id, cat=cat, name=name, blurb=blurb, type=type, look=look, music=music, open=open, close=close,
                scenes=scenes, voice=voice)


def PRESET(id, name, blurb, fx, title, subtitle="", sample="portrait", look="bold", music="tech", seconds=6, type="reel"):
    """A viral picture preset: your photo + a camera effect + words + music."""
    return dict(id=id, cat="viral", name=name, blurb=blurb, type=type, look=look, music=music, open=(title, subtitle),
                close=("", ""), scenes=[], voice=False,
                preset={"fx": fx, "title": title, "subtitle": subtitle, "seconds": seconds, "sample": sample})


EXAMPLES += [
    # ---------- Trending Templates (7 more) ----------
    X("pov", "trending", "POV: you…", "First-person 'POV' clip that puts the viewer in the moment.", "reel", "bold", "tech",
      ("POV:", "you finally took the trip"), ("Tag who you'd take", ""),
      [S("You land at 6 a.m.", "", "You land at six a.m. and the air smells different.", "airplane window view at sunrise over mountains"),
       S("No plan", "", "No plan. Just a backpack.", "backpack on a cobblestone street, morning"),
       S("Best decision", "", "Best decision of the year.", "traveller looking at a valley, golden light")]),
    X("things-i-wish", "trending", "Things I wish I knew", "Three lessons, one per scene. Careers, study, parenting, business.", "reel", "warm", "calm",
      ("3 things I wish I knew at 20", ""), ("Save this", "Share it with someone who needs it"),
      [S("1 · Start before you're ready", "", "One. Start before you feel ready. Nobody feels ready."),
       S("2 · Save 10% of everything", "Save 10%", "Two. Save ten percent of everything you earn."),
       S("3 · Your health is the job", "", "Three. Your health is not a hobby. It is the job.")]),
    X("rate-my", "trending", "Rate my setup", "Show your setup, desk, car or kitchen and ask for a score.", "reel", "bold", "tech",
      ("Rate my setup", "Be honest"), ("Out of 10?", "Comment your score"),
      [S("The desk", "", "Standing desk. Two screens.", "clean minimal desk setup with two monitors, LED light"),
       S("The chair", "", "The chair that saved my back.", "ergonomic office chair, soft light"),
       S("Cost", "₹ 85,000 total", "Total: eighty five thousand rupees.", "")]),
    X("glow-up", "trending", "Glow-up", "From where you started to where you are now. Personal or brand.", "reel", "bold", "tech",
      ("The glow-up", "Year 1 → Year 5"), ("Keep going", ""),
      [S("Year 1", "", "Year one. One phone, no followers.", "teenager filming with a phone in a small room"),
       S("Year 3", "10,000 followers", "Year three. Ten thousand people watching.", ""),
       S("Year 5", "", "Year five. A real studio.", "small professional video studio with lights")]),
    X("expectation-reality", "trending", "Expectation vs reality", "A funny contrast of how it should go and how it went.", "reel", "warm", "calm",
      ("Expectation vs reality", "Cooking edition"), ("We tried", ""),
      [S("Expectation", "", "Expectation: a perfect, golden cake.", "perfect golden cake on a stand, studio light"),
       S("Reality", "", "Reality: this.", "collapsed burnt cake on a messy kitchen counter"),
       S("Lesson", "", "Lesson: read the recipe first.")]),
    X("weekly-reset", "trending", "Sunday reset", "A calm routine in short steps. Very shareable.", "reel", "warm", "calm",
      ("Sunday reset", "4 small habits"), ("Ready for Monday", ""),
      [S("Clean one room", "", "Clean just one room."), S("Plan 3 meals", "", "Plan three meals for the week."),
       S("Lay out Monday", "", "Lay out Monday's clothes."), S("Phone off at 9", "", "Phone off at nine.")]),
    X("challenge", "trending", "30-day challenge", "Day 1 to day 30: show the progress of a challenge.", "reel", "bold", "tech",
      ("30-day challenge", "No sugar"), ("Would you try it?", ""),
      [S("Day 1", "", "Day one. Headache by lunch."), S("Day 10", "", "Day ten. Sleeping better."),
       S("Day 30", "Weight down 3 kg", "Day thirty. Three kilos down and more energy.")]),

    # ---------- Short Film (7 more) ----------
    X("the-call", "short_film", "The call", "Drama: a phone rings at night and changes a family's plans.", "youtube", "cinematic", "documentary",
      ("The Call", "A short film"), ("The End", ""),
      [S("2:14 a.m.", "", "Two fourteen a.m. The phone rings.", "phone lighting up on a bedside table in the dark"),
       S("Unknown number", "", "Unknown number. She answers anyway.", "woman holding a phone, face lit by screen"),
       S("We need you", "", "'We need you. Tonight.'", "car headlights on a wet empty road at night"),
       S("She goes", "", "She goes.", "woman walking towards a hospital entrance, dawn")]),
    X("grandma-recipe", "short_film", "Grandma's recipe", "A warm family story told through one dish.", "youtube", "warm", "calm",
      ("Grandma's Recipe", ""), ("Cook it for someone you love", ""),
      [S("A handwritten card", "", "A handwritten card, stained with oil.", "old handwritten recipe card, warm kitchen light"),
       S("Three generations", "", "Three generations have cooked from it.", "grandmother and child cooking together"),
       S("Today, my turn", "", "Today, it's my turn.", "young person stirring a pot, steam, warm light")]),
    X("silent-hero", "short_film", "The silent hero", "No dialogue: a small act of kindness in a busy city.", "youtube", "cinematic", "documentary",
      ("The Silent Hero", ""), ("Be someone's hero today", ""),
      [S("Rush hour", "", "", "busy city crossing, people rushing, cinematic"),
       S("A dropped wallet", "", "", "wallet on the ground among walking feet"),
       S("Run", "", "", "young man running through a crowd"),
       S("Thank you", "", "", "two strangers smiling, warm light")]),
    X("time-capsule", "short_film", "Time capsule", "Friends open a box they buried 20 years ago.", "youtube", "warm", "calm",
      ("Time Capsule", "A short film"), ("What would you bury today?", ""),
      [S("2004", "", "Two thousand and four. Five friends bury a box.", "kids burying a metal box in a backyard, film look"),
       S("2024", "", "Twenty years later, four of them come back.", "adults digging in the same backyard"),
       S("The letter", "", "Inside, a letter from the one who could not come.", "old letter in a rusty box, soft light")]),
    X("rain-delay", "short_film", "Rain delay", "Romantic comedy: two strangers stuck at a bus stop.", "youtube", "warm", "calm",
      ("Rain Delay", ""), ("Sometimes the delay is the plan", ""),
      [S("One umbrella", "", "One bus stop. One umbrella. Two strangers.", "bus stop in heavy rain, city lights"),
       S("Bus cancelled", "", "The bus is cancelled.", "digital sign showing CANCELLED"),
       S("Coffee?", "", "'Coffee, until it stops?'", "two people laughing in a small café, rain on the window")]),
    X("last-match", "short_film", "The last match", "Sports drama: one final game before retirement.", "youtube", "cinematic", "cinematic",
      ("The Last Match", ""), ("Thank you, captain", ""),
      [S("Twenty years", "", "Twenty years on this pitch.", "empty cricket stadium at dusk, cinematic"),
       S("One last game", "", "One last game.", "player tying shoes in a locker room"),
       S("The final over", "", "The final over.", "bowler running in, stadium lights"),
       S("Standing ovation", "", "Standing ovation.", "crowd standing and cheering, confetti")]),
    X("robot-friend", "short_film", "My robot friend", "Sci-fi for families: a lonely kid builds a friend.", "youtube", "warm", "cinematic",
      ("My Robot Friend", ""), ("The End", ""),
      [S("Nobody to play with", "", "New city. Nobody to play with.", "child alone in a room with boxes"),
       S("Spare parts", "", "So she builds a friend from spare parts.", "small handmade robot on a workbench, warm lamp"),
       S("It blinks", "", "It blinks.", "robot eyes lighting up, close-up"),
       S("Best friends", "", "Best friends.", "child and small robot walking in a park")]),

    # ---------- Music Video (7 more) ----------
    X("workout-beat", "music_video", "Workout beat", "Gym motivation: words on the beat.", "reel", "bold", "tech",
      ("No excuses", ""), ("Again tomorrow", ""), [S("Lift"), S("Breathe"), S("Push"), S("One more"), S("Done")], voice=False),
    X("wedding-lyric", "music_video", "Wedding lyric", "Romantic lyric lines for a wedding or anniversary film.", "youtube", "warm", "calm",
      ("Forever starts today", ""), ("", ""), [S("Two hearts"), S("One promise"), S("Every sunrise"), S("Together")], voice=False),
    X("festival-mood", "music_video", "Festival mood", "Colourful, fast word cuts for Diwali, Holi, Eid or Christmas.", "reel", "bold", "tech",
      ("Festival mood", ""), ("Celebrate", ""), [S("Lights"), S("Colours"), S("Family"), S("Sweets"), S("Joy")], voice=False),
    X("travel-montage", "music_video", "Travel montage", "Place names on the beat over your travel clips.", "youtube", "cinematic", "cinematic",
      ("Somewhere new", ""), ("Where next?", ""), [S("Mumbai"), S("Dubai"), S("Paris"), S("Tokyo"), S("Home")], voice=False),
    X("sad-lyric", "music_video", "Slow sad lyric", "Emotional lyric video, slow and dark.", "youtube", "cinematic", "documentary",
      ("Late night thoughts", ""), ("", ""), [S("You said forever"), S("Forever was short"), S("I still wait"), S("By the window")], voice=False),
    X("motivation-beat", "music_video", "Motivation beat", "Short motivational words, one per beat.", "reel", "bold", "tech",
      ("Start now", ""), ("Your move", ""), [S("Dream"), S("Plan"), S("Work"), S("Win")], voice=False),
    X("brand-anthem", "music_video", "Brand anthem", "Company values, one per beat, for events and screens.", "youtube", "corporate", "corporate",
      ("Who we are", ""), ("Together", ""), [S("Curious"), S("Honest"), S("Fast"), S("Customer first")], voice=False),

    # ---------- UGC Ads (7 more) ----------
    X("get-ready", "ugc", "Get ready with me", "GRWM style: a routine that shows the product naturally.", "reel", "warm", "calm",
      ("Get ready with me", "Office edition"), ("Link in bio", ""),
      [S("Step 1 · Face wash", "", "Step one. The gentle face wash. Thirty seconds."),
       S("Step 2 · Moisturiser", "", "Step two. Moisturiser with SPF."),
       S("Done in 5 minutes", "5 minutes", "Done in five minutes. Out the door.")]),
    X("honest-review", "ugc", "Honest review: pros and cons", "Builds trust: two pros, one con, a verdict.", "reel", "warm", "corporate",
      ("Honest review", "After 3 months"), ("Verdict: worth it", ""),
      [S("Pro · Battery", "Battery 2 days", "Pro: the battery lasts two days."),
       S("Pro · Camera", "", "Pro: the camera is great at night."),
       S("Con · Weight", "", "Con: it's a bit heavy.")]),
    X("small-business", "ugc", "Pack an order with me", "Behind the scenes of a small business. Loved by audiences.", "reel", "warm", "calm",
      ("Pack an order with me", ""), ("Thank you for supporting small business", ""),
      [S("The order", "", "A new order from Pune!", "hands holding a handwritten order note"),
       S("Wrapping", "", "Wrapped in recycled paper.", "hands wrapping a small box in brown paper, twine"),
       S("Thank-you note", "", "And always a thank-you note.", "small handwritten thank you card on a parcel")]),
    X("stitch-reply", "ugc", "Reply to a comment", "Answer a viewer's question on screen.", "reel", "bold", "tech",
      ("'Does it really work?'", "Replying to your comment"), ("Ask me anything", ""),
      [S("Short answer: yes", "", "Short answer: yes."), S("Here's proof", "Results in 14 days", "Here's my result after fourteen days."),
       S("Try it", "", "Try it and tell me.")]),
    X("before-buy", "ugc", "Watch before you buy", "Helpful buyer advice that builds trust.", "reel", "warm", "corporate",
      ("Watch this before you buy", ""), ("Save for later", ""),
      [S("Check the size", "", "Check the size. It's smaller than it looks."), S("Get the case", "", "Buy the case. Seriously."),
       S("Price", "₹ 3,499", "And it's on sale this week.")]),
    X("student-hack", "ugc", "Student hack", "A quick, relatable hack for students.", "reel", "bold", "tech",
      ("Student hack", ""), ("Follow for more", ""),
      [S("The problem", "", "Too many tabs, zero focus."), S("The hack", "", "Twenty five minutes on, five minutes off."),
       S("The result", "Twice as much done", "I finish twice as much.")]),
    X("mom-tested", "ugc", "Parent-tested", "Real-life test by a parent. Warm and honest.", "reel", "warm", "calm",
      ("Parent-tested", "Will it survive my kids?"), ("Survived!", ""),
      [S("Drop test", "", "Dropped. Twice."), S("Spill test", "", "Juice. Everywhere."), S("Still works", "", "Still works.")]),

    # ---------- Product Ads (7 more) ----------
    X("restaurant-menu", "product", "Restaurant special", "Today's dish, price and offer.", "square", "warm", "calm",
      ("Chef's special", "Tonight only"), ("Book a table", ""),
      [S("Paneer tikka", "₹ 349", "Smoky paneer tikka. Three forty nine.", "paneer tikka on a plate, warm restaurant light"),
       S("Fresh naan", "", "With fresh naan from the clay oven.", "naan bread coming out of a tandoor"),
       S("Free dessert", "", "And dessert is on us tonight.")]),
    X("real-estate", "product", "Property tour", "Walk through a home with key facts.", "youtube", "corporate", "corporate",
      ("3 BHK · Baner, Pune", "Ready to move"), ("Book a visit", ""),
      [S("Living room", "", "A bright living room with a city view.", "bright modern living room, large windows"),
       S("Area", "1,450 sq ft", "Fourteen fifty square feet.", ""),
       S("Price", "₹ 1,35,00,000", "One crore thirty five lakh.", "")]),
    X("app-launch", "product", "App launch", "Show what your app does in three quick screens.", "reel", "bold", "tech",
      ("Meet the app", "Budget in 1 tap"), ("Download free", ""),
      [S("Scan a bill", "", "Scan any bill."), S("See where money goes", "", "See where your money goes."),
       S("Save more", "Users save 18%", "Users save eighteen percent.")]),
    X("course-promo", "product", "Online course promo", "Promote a course or workshop.", "youtube", "warm", "corporate",
      ("Learn video editing", "in 30 days"), ("Enrol now", "Seats are limited"),
      [S("30 short lessons", "", "Thirty short lessons."), S("Real projects", "", "Real projects for your portfolio."),
       S("Students", "4,000 students", "Four thousand students so far.")]),
    X("fashion-drop", "product", "Fashion drop", "New collection, bold and fast.", "reel", "bold", "tech",
      ("New collection", "Monsoon 2026"), ("Shop the drop", ""),
      [S("Colours", "", "", "fashion model in a bright raincoat, studio"), S("Comfort", "", "", "close-up of soft fabric"),
       S("Limited", "", "", "clothes rack in a minimal boutique")]),
    X("gym-offer", "product", "Gym membership offer", "A gym or studio offer with the price.", "square", "bold", "tech",
      ("New year, new you", ""), ("Join today", ""),
      [S("Was", "₹ 12,000", "Was twelve thousand."), S("Now", "₹ 7,999", "Now seven nine nine nine for a year."),
       S("Free trainer", "", "Plus a free trainer for a month.")]),
    X("b2b-machine", "product", "Industrial machine ad", "A B2B ad for a machine or component.", "youtube", "corporate", "corporate",
      ("CNC-500", "Faster. Smarter. Cheaper to run."), ("Ask for a demo", ""),
      [S("Cycle time", "Cycle time -22%", "Twenty two percent faster cycles."), S("Energy", "Energy -15%", "Fifteen percent less energy."),
       S("Uptime", "Uptime 98%", "Ninety eight percent uptime.")]),

    # ---------- Film Trailer (7 more) ----------
    X("horror-teaser", "trailer", "Horror teaser", "Slow, scary, quiet. Ends on a title.", "youtube", "cinematic", "documentary",
      ("Don't open the door", ""), ("Room 9", "Coming this Halloween"),
      [S("The house was empty", "", "The house was empty for thirty years.", "abandoned house at night, fog"),
       S("Then the light came on", "", "Then one night, a light came on.", "single window glowing in a dark house"),
       S("Someone is home", "", "Someone is home.", "door slightly open, darkness inside")]),
    X("action-trailer", "trailer", "Action trailer", "Fast cuts, big words, a hero.", "youtube", "cinematic", "cinematic",
      ("One rule", ""), ("Zero Hour", "In cinemas"),
      [S("No backup", "", "No backup.", "agent on a rooftop at night, city lights"),
       S("No time", "", "No time.", "countdown clock, red light"),
       S("No mercy", "", "No mercy.", "car chase on a wet highway, motion blur")]),
    X("romcom-trailer", "trailer", "Rom-com trailer", "Light, funny, warm. Perfect for a short film launch.", "youtube", "warm", "calm",
      ("This summer", ""), ("Wrong Number", "Now streaming"),
      [S("She texted the wrong number", "", "She texted the wrong number…", "woman typing on a phone, laughing"),
       S("He texted back", "", "…he texted back.", "man smiling at his phone in a café"),
       S("Six months later", "", "Six months later, they still haven't met.", "two people walking past each other in a market")]),
    X("indie-festival", "trailer", "Festival trailer", "For a film festival submission: quiet, artistic.", "youtube", "cinematic", "documentary",
      ("Official selection", ""), ("The Quiet River", "A film by …"),
      [S("A village", "", "", "small village by a river, morning mist"),
       S("A secret", "", "", "old man looking at the river, profile"),
       S("A choice", "", "", "boat drifting on calm water")]),
    X("game-launch", "trailer", "Game launch trailer", "For an indie game or app: world, hook, date.", "youtube", "bold", "tech",
      ("Enter the city", ""), ("NEON RUN", "Out now"),
      [S("Run", "", "Run.", "neon city street, futuristic, night"), S("Dodge", "", "Dodge.", "character jumping between rooftops"),
       S("Survive", "Levels: 120", "A hundred and twenty levels.", "")]),
    X("series-teaser", "trailer", "Web series teaser", "Tease a new web series or podcast season.", "reel", "cinematic", "cinematic",
      ("Season 2", ""), ("Friday, 8 p.m.", ""),
      [S("They thought it was over", "", "They thought it was over."), S("It wasn't", "", "It wasn't."), S("New episodes", "8 episodes", "Eight new episodes.")]),
    X("event-trailer", "trailer", "Event trailer", "Build hype for a conference, concert or launch event.", "youtube", "cinematic", "cinematic",
      ("One night", ""), ("Summit 2026", "Mumbai · 12 December"),
      [S("Speakers", "40 speakers", "Forty speakers."), S("People", "3,000 people", "Three thousand people."),
       S("One stage", "", "One stage.", "concert stage with lights and crowd")]),

    # ---------- Social Content (7 more) ----------
    X("this-or-that", "social", "This or that", "Quick choices that get comments.", "reel", "bold", "tech",
      ("This or that?", ""), ("Comment your picks", ""),
      [S("Tea or coffee?"), S("Mountains or beach?"), S("Morning or night?"), S("Call or text?")], voice=False),
    X("behind-scenes", "social", "Behind the scenes", "Show how something is made. Builds trust.", "reel", "warm", "calm",
      ("Behind the scenes", "How we make it"), ("Follow the process", ""),
      [S("Sketch", "", "It starts with a sketch.", "hand sketching on paper, warm light"),
       S("Prototype", "", "Then a rough prototype.", "rough prototype on a workbench"),
       S("Final", "", "And finally, the real thing.", "finished product in studio light")]),
    X("team-intro", "social", "Meet the team", "Introduce people, one per scene.", "square", "warm", "corporate",
      ("Meet the team", ""), ("We're hiring", ""),
      [S("Priya · Design", "", "Priya, design. Loves clean lines."), S("Arjun · Engineering", "", "Arjun, engineering. Fixes anything."),
       S("Sara · Sales", "", "Sara, sales. Knows every customer by name.")]),
    X("milestone", "social", "Milestone thank-you", "Celebrate followers, customers or years.", "square", "bold", "tech",
      ("Thank you", ""), ("Here's to the next one", ""),
      [S("Followers", "100,000 followers", "One hundred thousand of you."), S("Thank you", "", "Thank you for every comment and share.")]),
    X("faq-answer", "social", "FAQ in 20 seconds", "Answer the most common question you get.", "reel", "warm", "calm",
      ("Most asked question", ""), ("Ask the next one", ""),
      [S("How long does delivery take?", "", "How long does delivery take?"), S("Delivery", "2 days", "Two days in most cities."),
       S("Free over ₹ 499", "", "And it's free over four ninety nine.")]),
    X("listicle", "social", "5 tools I use daily", "List post as a short video.", "reel", "bold", "tech",
      ("5 tools I use every day", ""), ("Which one do you use?", ""),
      [S("1 · Notes app", "", "One. A notes app for everything."), S("2 · Calendar blocks", "", "Two. Calendar blocks."),
       S("3 · Timer", "", "Three. A simple timer."), S("4 · Headphones", "", "Four. Noise cancelling headphones."),
       S("5 · Walks", "", "Five. A daily walk.")]),
    X("announcement", "social", "Big announcement", "Announce news with a build-up.", "square", "cinematic", "cinematic",
      ("Big news", ""), ("See you there", ""),
      [S("We're moving", "", "We're moving."), S("Bigger studio", "", "To a bigger studio."), S("Opening", "1 January", "Opening on the first of January.")]),

    # ---------- Explainer (7 more) ----------
    X("history-minute", "explainer", "History in a minute", "One event, explained in four scenes.", "youtube", "cinematic", "documentary",
      ("The first flight", "History in a minute"), ("Subscribe for more history", ""),
      [S("1903", "", "Nineteen oh three. Two brothers and a wooden plane.", "old wooden biplane on a beach, sepia"),
       S("12 seconds", "12 seconds", "The first flight lasted twelve seconds.", ""),
       S("Today", "100,000 flights a day", "Today, a hundred thousand flights take off every day.", "modern airport at sunset")]),
    X("money-basics", "explainer", "Money basics", "Personal finance made simple.", "youtube", "warm", "corporate",
      ("What is compound interest?", ""), ("Start early", ""),
      [S("You save", "₹ 1,000 a month", "You save one thousand rupees a month."),
       S("After 10 years", "₹ 2,06,000", "After ten years at eight percent, you have about two lakh six thousand."),
       S("After 30 years", "₹ 14,90,000", "After thirty years, almost fifteen lakh.")]),
    X("health-tip", "explainer", "Health explained", "One health idea, clearly and kindly explained.", "youtube", "warm", "calm",
      ("Why sleep matters", ""), ("Sleep well", ""),
      [S("Your brain cleans itself", "", "While you sleep, your brain clears out waste."),
       S("Adults need", "Seven to nine hours", "Adults need seven to nine hours."),
       S("One tip", "", "Same bedtime every day. Even weekends.")]),
    X("tech-explained", "explainer", "Tech explained simply", "A tech idea for non-technical people.", "youtube", "corporate", "tech",
      ("What is the cloud?", "Explained simply"), ("Now you know", ""),
      [S("Someone else's computer", "", "The cloud is simply someone else's computer."),
       S("Your photos live there", "", "Your photos are stored there, not on your phone."),
       S("Safer and everywhere", "", "So they are safe, and you can open them anywhere.")]),
    X("recipe-steps", "explainer", "Recipe in 4 steps", "A recipe as a clean step-by-step video.", "square", "warm", "calm",
      ("Masala chai", "in 4 steps"), ("Enjoy", ""),
      [S("1 · Boil water", "", "Boil water with ginger.", "pot of water boiling with ginger"),
       S("2 · Add spices", "", "Add cardamom and tea.", "spices falling into a pot"),
       S("3 · Add milk", "", "Add milk and simmer.", "milk poured into tea"),
       S("4 · Strain", "", "Strain and serve.", "chai poured into a glass, steam")]),
    X("onboarding", "explainer", "Welcome to the team", "Onboarding video for new employees.", "youtube", "corporate", "corporate",
      ("Welcome!", "Your first week"), ("We're glad you're here", ""),
      [S("Day 1", "Laptop and badge", "Day one: your laptop and badge."), S("Day 2", "Meet your buddy", "Day two: meet your buddy."),
       S("Day 3–5", "First project", "Days three to five: your first project.")]),
    X("safety-briefing", "explainer", "Safety briefing", "Workplace safety rules, clear and memorable.", "youtube", "corporate", "documentary",
      ("Safety first", "Shop floor rules"), ("Everyone home safe", ""),
      [S("Wear your PPE", "Helmet\nGlasses\nShoes", "Always wear your helmet, glasses and safety shoes."),
       S("Stop the line", "", "If something looks wrong, stop the line. Always."),
       S("Accidents", "Accidents -60%", "Since we started, accidents are down sixty percent.")]),

    # ---------- Viral presets (12): your photo + a camera effect + words + music ----------
    PRESET("v-zoom-punch", "Zoom punch", "Your photo punches in on every beat. Made for hype reels.", "zoom_punch", "Main character energy", sample="portrait"),
    PRESET("v-pull-back", "Pull-back reveal", "Starts close and pulls back to reveal the whole picture.", "pull_back", "Wait for it…", "", "landscape", "cinematic", "cinematic"),
    PRESET("v-spin-in", "Spin-in", "Your picture spins in from the centre. Great openers.", "spin_in", "Just dropped", "", "product"),
    PRESET("v-glitch", "Glitch", "Colour split and torn lines on the beat. Tech and gaming.", "glitch", "System update", "", "city"),
    PRESET("v-shake", "Camera shake", "Handheld energy for action, sport and travel.", "shake", "Let's go", "", "landscape"),
    PRESET("v-polaroid", "Polaroid drop", "Your photo drops in as a polaroid. Memories, birthdays.", "polaroid", "Best day ever", "Summer 2026", "city", "warm", "calm"),
    PRESET("v-split", "Split reveal", "Three panels slide in one after another.", "split_reveal", "New look", "", "portrait"),
    PRESET("v-vhs", "VHS retro", "90s tape look with a date stamp. Nostalgia.", "vhs", "Throwback", "", "landscape", "cinematic", "calm"),
    PRESET("v-flash-cuts", "Flash cuts", "A new framing on every beat, with a flash.", "flash_cuts", "Taste it", "", "food"),
    PRESET("v-duotone", "Duotone poster", "Two-colour poster look with a slow push.", "duotone", "Coming soon", "", "portrait", "bold", "cinematic"),
    PRESET("v-countdown", "3·2·1 countdown", "A countdown over your photo, then the reveal.", "countdown", "The reveal", "", "product", "bold", "tech", 6),
    PRESET("v-dreamy", "Dreamy drift", "Slow, soft push and drift. Calm and premium.", "drift", "Slow down", "", "landscape", "warm", "calm", 8),
]

BY_ID = {e["id"]: e for e in EXAMPLES}
TYPE_LABEL = {"youtube": "16:9", "reel": "9:16", "square": "1:1", "corporate": "16:9"}


def public(e):
    cat = next(c for c in CATEGORIES if c[0] == e["cat"])
    return {"id": e["id"], "category": e["cat"], "category_label": cat[1], "icon": cat[2], "name": e["name"],
            "blurb": e["blurb"], "type": e["type"], "format": TYPE_LABEL[e["type"]], "look": e["look"],
            "music": e["music"], "voice": e.get("voice", True), "scenes": len(e["scenes"]),
            "thumb": f"/inspirations/thumb/{e['id']}.jpg", "preview": f"/inspirations/preview/{e['id']}.mp4",
            "kind": "preset" if e.get("preset") else "video", "fx": (e.get("preset") or {}).get("fx")}


def _preset_scene(e):
    """The scene of a picture preset, on a sample photo (the user's own photo replaces it in Tools › Video)."""
    from .sample_photos import sample
    pr = e["preset"]
    return {"kind": "content", "title": pr["title"], "notes": pr.get("subtitle", ""), "script": "", "image": None,
            "_photo": sample(pr.get("sample", "portrait")), "fx": pr["fx"]}


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
    if e.get("preset"):
        raise ValueError("Picture presets are used in Tools › Video with your own photo.")
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
    if e.get("preset"):
        at = {"countdown": 1.0, "spin_in": 1.5, "split_reveal": 1.5, "polaroid": 1.5}.get(e["preset"]["fx"], 2.4)
        im = motion.still(proj, _preset_scene(e), 1, 1, at=at, dur=float(e["preset"]["seconds"])).resize((640, 360))
    else:
        # the most telling scene: a chart or counter if there is one, else the first scene
        scenes = [dict(sc, kind="content", image=None, id=str(k)) for k, sc in enumerate(e["scenes"])]
        pick = next((s for s in scenes if motion.plan(proj, s)["type"] in ("bars", "counter")), scenes[0])
        im = motion.still(proj, pick, 1, len(scenes) + 2, at=4.0, dur=6.0).resize((640, 360))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(buf.getvalue())
    return buf.getvalue()


_preview_locks = {}
PREVIEW_FPS = 24
PREVIEW_SCENE = 2.8        # seconds per scene in the preview


def preview_path(eid):
    from .config import MODELS_DIR
    from .version import app_version
    return MODELS_DIR / "previews" / f"{eid}-{app_version()}.mp4"


def preview(eid):
    """A short animated preview (about 10 s, 640x360, with the example's music): the opening and the first
    three scenes, drawn by the motion engine on this laptop. Made the first time it is played, then cached."""
    import subprocess
    import threading
    from . import motion
    from .ffmpeg_utils import ffmpeg_bin
    e = BY_ID[eid]
    out = preview_path(eid)
    lock = _preview_locks.setdefault(eid, threading.Lock())
    with lock:                                   # two clicks on the same example make it once
        if out.exists():
            return out
        out.parent.mkdir(parents=True, exist_ok=True)
        proj = {"id": "inspiration", "look": e["look"], "title": e["open"][0], "subtitle": e["open"][1],
                "presenter": "", "company": "", "contact": "", "logo": None}
        voice = e.get("voice", True)
        if e.get("preset"):                      # a picture preset: the whole effect on a sample photo
            scenes, length = [_preset_scene(e)], float(e["preset"]["seconds"])
        else:
            scenes = [{"kind": "title", "title": e["open"][0], "notes": e["open"][1], "script": "", "image": None}]
            scenes += [dict(sc, kind="content", image=None, script=sc["script"] if voice else "") for sc in e["scenes"][:3]]
            length = PREVIEW_SCENE
        n_f = int(length * PREVIEW_FPS)
        total = len(scenes) * length
        tmp = out.with_suffix(".part.mp4")
        cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{motion.W}x{motion.H}", "-r", str(PREVIEW_FPS), "-i", "-",
               "-i", str(library.music_file(e["music"])),
               "-filter_complex", f"[0:v]scale=640:360:flags=bilinear,format=yuv420p[v];"
                                  f"[1:a]volume=0.8,afade=t=out:st={total - 1.5:.2f}:d=1.5[a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
               "-c:a", "aac", "-b:a", "96k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(tmp)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for k, s in enumerate(scenes):
                sc = motion.Scene(proj, s, k + 1, len(scenes), length, 0.3, length - 0.8)
                for f in range(n_f):
                    proc.stdin.write(sc.frame(f / PREVIEW_FPS).tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Preview failed:\n" + err[-800:])
        tmp.replace(out)
        return out


assert len(EXAMPLES) == 100 and len(BY_ID) == 100 and all(e["music"] in library.MOODS for e in EXAMPLES)
