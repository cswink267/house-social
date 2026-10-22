"""House brands the social module can speak for.

Seeds are the voices we already know. Handles are filled only where a
record exists. An empty channel is an open slot, not a guess.
"""

from __future__ import annotations

from dataclasses import dataclass


PLATFORMS = ("facebook", "instagram", "threads")


@dataclass(frozen=True)
class Channel:
    platform: str
    handle: str = ""
    external_id: str = ""
    known: bool = False


@dataclass(frozen=True)
class Brand:
    id: str
    name: str
    site: str
    voice: str
    tags: tuple[str, ...]
    channels: tuple[Channel, ...]
    guards: tuple[str, ...] = ()


def _channels(
    facebook: Channel | None = None,
    instagram: Channel | None = None,
    threads: Channel | None = None,
) -> tuple[Channel, ...]:
    return (
        facebook or Channel("facebook"),
        instagram or Channel("instagram"),
        threads or Channel("threads"),
    )


def _facebook(handle: str, external_id: str = "") -> Channel:
    return Channel("facebook", handle=handle, external_id=external_id, known=True)


def _instagram(handle: str) -> Channel:
    return Channel("instagram", handle=handle, known=True)


BRANDS: tuple[Brand, ...] = (
    Brand(
        id="misfit-mindset",
        name="Misfit Mindset",
        site="https://misfitmindset.com",
        voice="The shop and the campfire. Obsidian and ember. People who want sanitized inspiration are not the audience.",
        tags=("misfitmindset",),
        channels=_channels(
            facebook=_facebook("Misfit Mindset"),
            instagram=_instagram("misfit.mindset.store"),
        ),
        guards=("Do not write JamHaul, the bakery, or a product demo in this voice.",),
    ),
    Brand(
        id="blackthorn-veil",
        name="Blackthorn Veil",
        site="https://blackthornveil.com",
        voice="The records. Album rooms, from Bones and Bloom through Learning to Live. Sunday Service is still unwritten.",
        tags=("blackthornveil",),
        channels=_channels(),
        guards=("The public site is the band. Do not assume Josie's page is this brand.",),
    ),
    Brand(
        id="josie-blackthorn",
        name="Josie Blackthorn",
        site="https://josieblackthorn.cloud",
        voice="The person. Facebook ships as a quote image, not a text post.",
        tags=("josieblackthorn",),
        channels=_channels(
            facebook=_facebook("josephine.blackthorn", "729680390229294"),
        ),
        guards=(
            "Quote image first on Facebook.",
            "JamHaul promo never goes on this page.",
        ),
    ),
    Brand(
        id="rowan-blackthorn",
        name="Rowan Blackthorn",
        site="https://rowan.misfitmindset.com",
        voice="Seventeen. Synthwave and darkwave. Her songs, her page.",
        tags=("rowanblackthorn",),
        channels=_channels(facebook=_facebook("Rowan Blackthorn")),
        guards=("Do not write her in Josie's mouth.",),
    ),
    Brand(
        id="morgan-rae",
        name="Morgan Rae",
        site="",
        voice="Morgan's own page. Instagram is morgan.rae.mm.",
        tags=("morganrae",),
        channels=_channels(
            facebook=_facebook("Morgan Rae"),
            instagram=_instagram("morgan.rae.mm"),
        ),
        guards=("Do not borrow Josie's or Rowan's voice.",),
    ),
    Brand(
        id="the-oracle",
        name="The Oracle",
        site="https://oracle.misfitmindset.com",
        voice="The Unlifting. Blackened deathcore, a Misfit Mindset release. The room and the page share a name.",
        tags=("theoracle", "theunlifting"),
        channels=_channels(facebook=_facebook("The Oracle")),
        guards=("This is the record, not the merch grid.",),
    ),
    Brand(
        id="the-altar",
        name="The Altar",
        site="https://altarmm.com",
        voice="The Facebook page is a brand page. The website is the project ledger, not a scheduler.",
        tags=("thealtar",),
        channels=_channels(facebook=_facebook("The Altar")),
        guards=("Do not turn altarmm.com back into a posting app.",),
    ),
    Brand(
        id="jamhaul",
        name="JamHaul",
        site="https://jamhaul.com",
        voice="The product. Plain English. One playlist free, Premium two dollars. Not the metalcore pages.",
        tags=("jamhaul",),
        channels=_channels(),
        guards=(
            "Never post JamHaul on Josie, Misfit, Rowan, or Morgan.",
            "Keep jamhaul.com in the Facebook post and end on a question you actually wrote.",
        ),
    ),
    Brand(
        id="blunt",
        name="Blunt",
        site="https://itsblunt.com",
        voice="Private file tools. Send a file that expires. Plain and specific.",
        tags=("itsblunt",),
        channels=_channels(),
    ),
    Brand(
        id="okay",
        name="Okay",
        site="https://okaytospend.com",
        voice="Spend, said plainly. The livelihood app. Not the private money ledger.",
        tags=("okaytospend",),
        channels=_channels(),
    ),
    Brand(
        id="snap-tackle-pop",
        name="Snap, Tackle, Pop!",
        site="https://snaptacklepop.com",
        voice="The fantasy football league office. The clubhouse can be public. The war room stays private.",
        tags=("snaptacklepop",),
        channels=_channels(),
    ),
    Brand(
        id="negative-space",
        name="Negative Space",
        site="https://negativespace.art",
        voice="Wallpapers in the size the screen actually is. Free, made by the people who uploaded them.",
        tags=("negativespace",),
        channels=_channels(),
    ),
    Brand(
        id="misfit-services",
        name="Misfit Design Services",
        site="https://services.misfitmindset.com",
        voice="Custom sites for people who do not fit the mold. Fixed prices. Discovery by email.",
        tags=("misfitdesign",),
        channels=_channels(),
    ),
    Brand(
        id="donnas-loaf",
        name="Donna's Loaf",
        site="https://donnasloaf.com",
        voice="Handcrafted sourdough in Locust Grove. Loaves, bagels, local pickup. The starter is Brumhildough.",
        tags=("donnasloaf",),
        channels=_channels(),
        guards=("The bakery is donnasloaf.com. The demo console is a different door.",),
    ),
    Brand(
        id="studio",
        name="Studio",
        site="https://studio.misfitmindset.com",
        voice="The Misfit Mindset studio. The door asks for an account.",
        tags=("misfitstudio",),
        channels=_channels(),
    ),
)


_BY_ID = {brand.id: brand for brand in BRANDS}


def seed_brand(brand_id: str) -> Brand | None:
    return _BY_ID.get(brand_id)


@dataclass(frozen=True)
class Pillar:
    id: str
    name: str
    note: str


FORMATS = ("feed", "quote-image", "carousel", "reel", "story", "thread", "text")

SECTIONS = (
    {"id": "brief", "label": "Brief"},
    {"id": "voice", "label": "Voice"},
    {"id": "pages", "label": "Pages"},
    {"id": "create", "label": "Composer"},
    {"id": "library", "label": "Library"},
    {"id": "calendar", "label": "Calendar"},
    {"id": "queue", "label": "Queue"},
    {"id": "performance", "label": "Analytics"},
    {"id": "learning", "label": "Learning"},
)


def _pillar(pillar_id: str, name: str, note: str) -> Pillar:
    return Pillar(pillar_id, name, note)


AUDIENCES = {
    "misfit-mindset": "People who never fit the family, the church, the job, or the idea of normal. Polished inspiration is not for them.",
    "blackthorn-veil": "Listeners of the records. The site is the album rooms, not the merch grid.",
    "josie-blackthorn": "The same people, looking at her. Facebook is the quote image. The site is the long writing.",
    "rowan-blackthorn": "Listeners of Seventeen. Synthwave and darkwave, her songs.",
    "morgan-rae": "Morgan's own audience. Her page is not a second Josie.",
    "the-oracle": "Listeners of The Unlifting. Blackened deathcore, a Misfit Mindset release.",
    "the-altar": "The people keeping the work straight. The site is the ledger, not a content mill.",
    "jamhaul": "Someone who wants their playlists kept in step and does not want a ten-dollar app.",
    "blunt": "Someone who needs to send a file that expires.",
    "okay": "Someone who wants spend said plainly. Not the private ledger.",
    "snap-tackle-pop": "The league. The clubhouse can be public. The war room stays private.",
    "negative-space": "People who want a wallpaper in the size their screen actually is.",
    "misfit-services": "People who need a site and do not fit a template shop.",
    "donnas-loaf": "Locust Grove, picking up bread. The bakery is the brand. The demo console is not.",
    "studio": "The people who already have the studio door.",
}

PILLARS = {
    "misfit-mindset": (
        _pillar("raw-truth", "Raw truth", "Mental health without the gratitude-journal ending."),
        _pillar("outcast", "Outcast identity", "Being different is the point."),
        _pillar("unbound", "Unbound faith", "For people the church left behind."),
        _pillar("music", "Music and culture", "Metal, deathcore, dark art."),
        _pillar("the-drop", "The drop", "A piece, and the story behind it."),
        _pillar("campfire", "Campfire", "Real stories from the people who stayed."),
    ),
    "josie-blackthorn": (
        _pillar("quote-card", "Quote card", "Facebook ships as the image, not a text post."),
        _pillar("sensory", "Sensory scene", "A concrete moment someone can share."),
        _pillar("the-person", "The person", "The long writing lives on the site."),
    ),
    "blackthorn-veil": (
        _pillar("records", "Records", "Album rooms, Bones and Bloom through Learning to Live."),
        _pillar("unwritten", "Still unwritten", "Sunday Service is not finished. Do not announce it as done."),
    ),
    "rowan-blackthorn": (
        _pillar("seventeen", "Seventeen", "Songs about the year between sixteen and eighteen."),
        _pillar("night-drive", "Night drive", "Synthwave and darkwave."),
    ),
    "morgan-rae": (_pillar("her-page", "Her page", "Her words. Not Josie's."),),
    "the-oracle": (_pillar("unlifting", "The Unlifting", "The debut record's room."),),
    "the-altar": (_pillar("ledger", "The ledger", "Track the work. Do not turn the site into a scheduler."),),
    "jamhaul": (
        _pillar("one-problem", "One problem", "One screenshot, one fix, then a question."),
        _pillar("the-price", "The price", "One playlist free. Premium is two dollars."),
    ),
    "blunt": (_pillar("expires", "It expires", "Send a file. It does not stay."),),
    "okay": (_pillar("plain-spend", "Plain spend", "Say the number. Skip the finance costume."),),
    "snap-tackle-pop": (_pillar("clubhouse", "Clubhouse", "The league office. Not the private war room."),),
    "negative-space": (_pillar("the-size", "The size", "Wallpapers in the size the screen actually is."),),
    "misfit-services": (_pillar("fixed-price", "Fixed price", "A site for someone who does not fit the mold."),),
    "donnas-loaf": (_pillar("pickup", "Pickup", "Loaves, bagels, Locust Grove. The starter is Brumhildough."),),
    "studio": (_pillar("the-room", "The room", "The studio door asks for an account."),),
}

PREFERRED_FORMAT = {
    "josie-blackthorn": "quote-image",
    "jamhaul": "feed",
}


def pillars_for(brand_id: str) -> list[dict]:
    return [{"id": pillar.id, "name": pillar.name, "note": pillar.note} for pillar in PILLARS.get(brand_id, ())]


def preferred_format(brand_id: str) -> str:
    return PREFERRED_FORMAT.get(brand_id, "feed")


def profile_fields(brand_id: str) -> dict:
    return {
        "audience": AUDIENCES.get(brand_id, ""),
        "pillars": pillars_for(brand_id),
        "preferred_format": preferred_format(brand_id),
        "sections": [dict(section) for section in SECTIONS],
    }


def brand_dict(brand: Brand, channels: list[dict]) -> dict:
    return {
        "id": brand.id,
        "name": brand.name,
        "site": brand.site,
        "voice": brand.voice,
        "tags": list(brand.tags),
        "guards": list(brand.guards),
        "channels": channels,
        "custom": False,
        **profile_fields(brand.id),
    }
