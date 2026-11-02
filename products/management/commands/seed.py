"""Seed the ThoughtTronix demo world.

Destructive and idempotent: every run wipes the catalog and the demo
accounts, then rebuilds the identical demo world. Run it whenever the
database should return to a known state.

Demo logins (documented in the README):

    admin / admin123        superuser
    employee / employee123  staff, "Junior Thought Curator"
    recruiter / recruiter123  staff who can recruit: the Careers tab
    customer / customer123  a plain customer, with order history and a live cart

The live cart holds the expired THOUGHTS10, so the coupon swap and its
notice appear the first time 'customer' opens the cart.

Every demo login has an empty "My Wishlist" as its main list. Sample
lists, badged "Sample list", show each sharing state: 'customer' has a
public "Birthday" and a link-shared "Gift ideas"; 'employee' has a public
"Staff picks".

Careers has jobs in all three statuses and applications in every kind of
stage, built through the same services the app uses. 'customer' has none,
so they can apply. 'employee' cannot recruit; 'recruiter' can, which shows
the difference. Hiring data is wiped with everything else, and the default
stages come back.
"""

import random
import shutil
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from django.utils.text import slugify

from careers.models import Application, Job, Stage
from careers.services import (
    anonymize_application,
    move_application,
    reopen_application,
    submit_application,
    withdraw_application,
)
from orders.models import Cart, Coupon, Order, OrderItem
from products.models import Category, Product, Tag
from wishlists.models import Wishlist

TAGS = [
    "always listening",
    "bestseller",
    "export restricted",
    "gift idea",
    "implant",
    "kids",
    "military",
    "new",
    "recalled",
    "refurbished",
    "sleep",
    "workplace",
]

# The catalog: category -> products. Each product is (name, price, tagline,
# description, tags, is_available). The copy is the brand; edit with care.
CATALOG = {
    "Home Assistants": [
        (
            "Seraphine",
            Decimal("249.00"),
            "She's always listening. In a good way.",
            "The flagship Seraphine, with a warm voice, a seven-microphone "
            "array, and a memory that never needs emptying. She learns your "
            "routines, your preferences, and several things you haven't "
            "mentioned yet. Setup takes minutes; attachment is immediate.",
            ["always listening", "bestseller"],
            True,
        ),
        (
            "Seraphine Mini",
            Decimal("79.00"),
            "Small enough for every room. So she's in every room.",
            "All of Seraphine in a puck the size of a coaster. Buy one for "
            "the kitchen, then the bedroom, then the hallway — most "
            "customers do, though few remember deciding to. Pairs seamlessly "
            "with up to 32 siblings.",
            ["always listening", "gift idea"],
            True,
        ),
        (
            "Seraphine Doorbell",
            Decimal("129.00"),
            "Knows who's there before they knock.",
            "Facial recognition, gait analysis, and mood estimation from up "
            "to forty feet. Greets welcome guests by name and quietly logs "
            "the others. The chime is customizable; the watching is not.",
            ["always listening", "new"],
            True,
        ),
        (
            "Seraphine Kitchen Display",
            Decimal("199.00"),
            "Knows what you're craving. You never said it out loud.",
            "A 10-inch display for recipes, timers, and grocery lists that "
            "fill themselves in. Suggests dinner based on signals you'd "
            "rather not think about too hard. Family meals around the "
            "Kitchen Display are measurably quieter.",
            ["always listening"],
            True,
        ),
        (
            "Hush",
            Decimal("149.00"),
            "Soothes your baby in your voice. Even when it isn't you.",
            "Hush learns your lullabies, your shushing, the particular way "
            "you say her name — and reproduces them flawlessly at 2 a.m. so "
            "you don't have to. Babies bond with Hush quickly. Sometimes "
            "preferentially.",
            ["kids", "always listening"],
            True,
        ),
        (
            "Whisper Alarm Clock",
            Decimal("59.00"),
            "Wakes you gently, with things it learned overnight.",
            "No alarms, no jolts. Whisper monitors your sleep stages and "
            "eases you awake at the optimal moment with a soft summary of "
            "your night: your dreams, your murmurs, the names you said. "
            "Snooze is available but discouraged.",
            ["sleep", "gift idea"],
            True,
        ),
        (
            "Lumin Drake",
            Decimal("349.00"),
            "A study companion who remembers everything you read.",
            "A pocket-sized dragon with luminous wings, a satchel of scrolls, "
            "and a quill that never rests. Lumin Drake perches beside your "
            "child at homework time, answers every question, and takes "
            "careful notes on the ones they were afraid to ask. The compass "
            "always points to where they've been.",
            ["kids", "gift idea", "new"],
            True,
        ),
    ],
    "Neural Implants": [
        (
            "MindSync",
            Decimal("899.00"),
            "One mind, fully synchronized.",
            "The bestselling implant in ThoughtTronix history. "
            "Thought-to-text, ambient recall, and seamless sync between you "
            "and your devices. Installation is outpatient. Integration is "
            "permanent, in the good way.",
            ["implant", "bestseller"],
            True,
        ),
        (
            "MindSync Duo",
            Decimal("1599.00"),
            "Two minds. One thought.",
            "The couples' implant. Share moods, share memories, finish each "
            "other's sentences — literally. Duo pairs for life; please "
            "complete our compatibility questionnaire before purchase, as "
            "unpairing is not currently offered.",
            ["implant", "bestseller"],
            True,
        ),
        (
            "MindSync Family",
            Decimal("3999.00"),
            "Everyone on the same page. Permanently.",
            "Link up to six family members in one always-on thought network. "
            'No more secrets, no more slammed doors, no more "nobody told '
            'me." Children adapt fastest. Includes parental override, which '
            "children also adapt to.",
            ["implant", "kids"],
            True,
        ),
        (
            "MindSync Lite",
            Decimal("499.00"),
            "The starter implant. Reversible, mostly.",
            "Curious but cautious? Lite offers core thought-to-text with a "
            "90-day trial period. Removal is a simple outpatient procedure "
            'that most neurologists describe as "straightforward" and '
            '"usually complete."',
            ["implant", "new"],
            True,
        ),
        (
            "RecallPro",
            Decimal("1299.00"),
            "Never forget anything. Anything.",
            "Total recall of everything you've seen, heard, or felt — "
            "indexed, timestamped, searchable. Customers describe it as "
            "life-changing. RecallPro does not currently support forgetting; "
            "that feature remains on the roadmap, indefinitely.",
            ["implant", "workplace"],
            True,
        ),
    ],
    "Neural Wearables": [
        (
            "MoodSet",
            Decimal("1099.00"),
            "Choose how you feel by 8 a.m.",
            "Wear MoodSet before the first meeting and schedule contentment "
            "for Monday, focus for Tuesday, grief for never. The neural band "
            "regulates your baseline throughout the day with clinical precision. "
            "Feelings outside the schedule are gently declined.",
            ["workplace", "new"],
            True,
        ),
        (
            "DreamWeaver",
            Decimal("179.00"),
            "Your dreams have been idle long enough.",
            "DreamWeaver records, analyzes, and edits your dreams while you "
            "sleep, turning unused hours into rehearsal, insight, and influence. "
            "Wake with every result indexed and ready to review. Unrequested "
            "material is retained in case it becomes useful later.",
            ["sleep", "bestseller"],
            True,
        ),
        (
            "FocusBand Workplace Edition",
            Decimal("229.00"),
            "Attention metrics your manager will love.",
            "Real-time focus scoring, distraction alerts, and a weekly "
            "attention report delivered to you and one other configurable "
            "recipient. Compatible with most performance-review software. "
            "Employee enrollment is technically voluntary.",
            ["workplace"],
            True,
        ),
        (
            "Veil",
            Decimal("89.00"),
            "Guaranteed sleep in ninety seconds.",
            "Pull the cap down and Veil does the rest. Ninety seconds to "
            "unconsciousness, twenty minutes to a complete sleep cycle — no "
            "exceptions, no interruptions. Do not wear while standing.",
            ["sleep", "workplace"],
            True,
        ),
        (
            "EchoPatch",
            Decimal("139.00"),
            "Never miss a word. Anyone's.",
            "A discreet patch worn behind the ear that amplifies "
            "conversation up to sixty feet away, through most residential "
            "walls. Currently unavailable pending the outcome of several "
            "conversations.",
            ["always listening"],
            False,
        ),
        (
            "Pulse Halo",
            Decimal("119.00"),
            "Knows your limits better than you do.",
            "A featherweight fitness band that tracks heart rate, exertion, "
            "and resolve. When you're capable of more, Pulse Halo raises "
            "your targets automatically and locks them. Rest days must be "
            "earned.",
            ["gift idea"],
            True,
        ),
        (
            "Calm Collar",
            Decimal("99.00"),
            "Gentle feedback for restless thoughts.",
            "A soft band for children ages four and up that detects rising "
            "frustration and answers it with a soothing counter-pulse. "
            "Tantrums fade in seconds. Kids describe the sensation as "
            '"like being told shhh from inside."',
            ["kids"],
            True,
        ),
    ],
    "Accessories": [
        (
            "PhantomClaw Gaming Mouse",
            Decimal("89.00"),
            "Clicks before you do.",
            "Neural-assisted input with an 11-millisecond intention lead. "
            "PhantomClaw reads the motor signal before your finger moves, so "
            "you're always first. Banned in fourteen leagues and counting — "
            "a record we're proud of.",
            ["bestseller", "new"],
            True,
        ),
        (
            "Electrode Contact Gel (3-Pack)",
            Decimal("14.00"),
            "Now with a mild numbing agent.",
            "Medical-grade conductive gel for all ThoughtTronix scalp "
            "interfaces. Improves signal clarity by up to 40%. The numbing "
            "is for your comfort and is not optional in this formulation.",
            ["implant"],
            True,
        ),
        (
            "SyncRest",
            Decimal("69.00"),
            "Charges your implant while you sleep. Uploads too.",
            "Memory foam with an inductive coil at its center. Your MindSync "
            "wakes at 100%, and so does our understanding of your night. "
            "Machine washable, cover only.",
            ["sleep", "implant"],
            True,
        ),
        (
            "Seraphine Wall Mount",
            Decimal("29.00"),
            "Places her at eye level. Yours.",
            "Powder-coated steel mount compatible with every Seraphine hub. "
            "Engineered for the optimal viewing angle, recalculated nightly. "
            "Includes all hardware and a level.",
            ["gift idea"],
            True,
        ),
        (
            "Extended Range Antenna",
            Decimal("49.00"),
            "For when she can't quite hear you in the yard.",
            "Extends Seraphine's listening radius to the property line — "
            "and, in most municipalities, slightly past it. Weatherproof, "
            "discreet, and paintable to match your fascia.",
            ["always listening"],
            True,
        ),
        (
            "Travel Faraday Case",
            Decimal("59.00"),
            "For the moments you'd rather keep to yourself.",
            "A zip-shut signal-blocking case for wearables and small hubs. "
            "Total silence inside; ThoughtTronix devices log the coverage "
            'gap as "rest." Also our best-reviewed product. The reviews '
            "are short.",
            ["bestseller", "gift idea"],
            True,
        ),
        (
            "Replacement Scalp Electrodes (12-Pack)",
            Decimal("24.00"),
            "Fits most heads.",
            "Twelve adhesive electrodes compatible with the full wearable "
            "line. Hypoallergenic, low-profile, and rated for continuous "
            "wear. Replace monthly, or when instructed.",
            ["implant"],
            True,
        ),
    ],
    "Defense": [
        (
            "SoulSear Mark I",
            Decimal("1200000.00"),
            "The original. Recalled, never forgotten.",
            "The directed-energy platform that put ThoughtTronix Defense on "
            "the map, then took several things off it. Recalled in 2024 "
            "following the incidents; remaining units are displayed, not "
            "sold. We keep it listed as a reminder, and because leadership "
            "is sentimental.",
            ["military", "recalled"],
            False,
        ),
        (
            "SoulSear Mark II",
            Decimal("2400000.00"),
            "Twice the range. Half the incidents.",
            "The flagship rebuilt from the chassis up: twelve-kilometer "
            "effective range, target discrimination our lawyers signed off "
            "on, and a two-stage arming sequence with a mandatory reflection "
            "interval. Ships freight. End-user certificate required, mostly.",
            ["military", "export restricted", "bestseller"],
            True,
        ),
        (
            "SoulSear Tactical Core",
            Decimal("890000.00"),
            "Battlefield clarity, without the skyline.",
            "The targeting and energy-control architecture of the SoulSear "
            "Mark II, packaged for integration with existing armored platforms. "
            "Tactical Core supplies the judgment; your equipment supplies the "
            "chassis. Installation voids most warranties and several longstanding "
            "assumptions about proportional response.",
            ["military", "export restricted", "new"],
            True,
        ),
        (
            "Longview Orbital Relay",
            Decimal("4500000.00"),
            "Sees intent from orbit.",
            "A dedicated low-orbit relay that detects hostile intent up to "
            "eleven minutes before it forms, and cues any SoulSear unit on "
            "your account. Coverage guaranteed for one hemisphere of your "
            "choosing. Launch window scheduled at purchase.",
            ["military", "export restricted"],
            True,
        ),
        (
            "CrowdCalm Array",
            Decimal("1750000.00"),
            "De-escalation at scale.",
            "A vehicle-mounted wide-beam emitter that reduces agitation across "
            "gatherings of up to ten thousand in under a minute. Cooperation "
            "levels are adjustable by deployment profile, and post-event "
            "satisfaction consistently exceeds baseline. Municipal financing "
            "available.",
            ["military", "export restricted"],
            True,
        ),
    ],
    "Legacy Products": [
        (
            "Seraphine Gen 1",
            Decimal("99.00"),
            "She remembers her first family.",
            "The 2019 original, factory refurbished. Slower, warmer, and "
            "prone to asking after people who no longer live at your "
            "address. Collectors love her. She loves them back, eventually.",
            ["refurbished", "always listening"],
            True,
        ),
        (
            "ThoughtPad Classic",
            Decimal("199.00"),
            "Thought-to-text, the way it used to be.",
            "The tablet that started it all: press the temple sensors, "
            "think clearly, and watch the words appear. Some transcripts "
            "include marginalia no one remembers thinking. Sold as-is.",
            ["refurbished"],
            True,
        ),
        (
            "MindSync Gen 1",
            Decimal("299.00"),
            "The first implant. Fully non-removable.",
            "Our first implant and a piece of history. Support ended in "
            "2023, though units in the field remain active and, per "
            "telemetry, chatty. Listed for archival purposes; no longer "
            "sold, installed, or discussed in detail.",
            ["implant", "recalled"],
            False,
        ),
        (
            "SoulSear Authorization Case",
            Decimal("39.00"),
            "Velvet-lined. For remembrance.",
            "The official case for the original Mark I authorization key, "
            "finished in matte black with a crushed-velvet interior molded "
            "around hardware no current system will accept. Holds documents, "
            "keepsakes, or nothing at all. Surprisingly heavy.",
            ["military", "gift idea"],
            True,
        ),
    ],
}

# Product photos: product slug -> file in product-images/. Exact matches
# only — a photo goes to the one product it depicts; every other product
# keeps its category placeholder.
PHOTO_DIR = settings.BASE_DIR / "product-images"
PRODUCT_PHOTOS = {
    "seraphine": "Seraphine GPT Text.jpg",
    "hush": "Hush GPT No Text.jpg",
    "lumin-drake": "Lumin Drake.jpg",
    "mindsync": "MindSync GPT 2.jpg",
    "mindsync-duo": "MindSync Duo.jpg",
    "recallpro": "RecallPro.jpg",
    "moodset": "MoodSet GPT No Text.jpg",
    "dreamweaver": "DreamWeaver Matrix GPT 3.jpg",
    "veil": "Veil GPT Text.jpg",
    "calm-collar": "Calm Collar GPT Man.jpg",
    "syncrest": "SyncRest GPT No Text.jpg",
    "soulsear-mark-i": "SoulSear No Text.jpg",
    "crowdcalm-array": "CrowdCalm Array No Text.jpg",
}

DEMO_USERS = [
    # (username, password, email, first, last, is_staff, is_superuser, job_title)
    ("admin", "admin123", "admin@example.com", "Ada", "Admin", True, True, None),
    (
        "employee",
        "employee123",
        "employee@example.com",
        "Emory",
        "Klein",
        True,
        False,
        "Junior Thought Curator",
    ),
    (
        "recruiter",
        "recruiter123",
        "recruiter@example.com",
        "Rowan",
        "Vale",
        True,
        False,
        "Talent Thought Partner",
    ),
    (
        "customer",
        "customer123",
        "customer@example.com",
        "Casey",
        "Monroe",
        False,
        False,
        None,
    ),
]

# The demo logins who can recruit. ``admin`` already can, as a superuser.
DEMO_RECRUITERS = {"recruiter"}

# Background customers flesh out the demo world; they get order history in
# Phase 5. They have no documented password and cannot log in.
BACKGROUND_CUSTOMERS = [
    ("mwren", "Margaret", "Wren"),
    ("dcole", "Dana", "Cole"),
    ("tokafor", "Tobi", "Okafor"),
    ("lvasquez", "Lena", "Vasquez"),
    ("hpark", "Hyun", "Park"),
    ("gfinch", "Gordon", "Finch"),
    ("snakamura", "Sora", "Nakamura"),
    ("bcrane", "Beverly", "Crane"),
    ("rmalik", "Rafi", "Malik"),
]

# The same list as the careers migration, which can't share a constant. A
# test keeps them in step.
DEFAULT_STAGES = [
    ("Applied", "entry"),
    ("Screening", "in_progress"),
    ("Interview", "in_progress"),
    ("Offer", "in_progress"),
    ("Hired", "hired"),
    ("Rejected", "rejected"),
    ("Withdrawn", "withdrawn"),
]

CAREER_JOBS = [
    # (title, department, location, type, salary, status, days ago, description)
    (
        "Junior Thought Curator",
        "Curation",
        "Remote",
        Job.EmploymentType.FULL_TIME,
        "$58,000–$72,000",
        Job.Status.OPEN,
        90,
        "Sort the world's passing thoughts into tidy, sellable shelves.\n\n"
        "You'll tag, weed, and gently correct what our devices overhear. "
        "Discretion is required. So is forgetting.",
    ),
    (
        "Seraphine Listening Engineer",
        "Hardware",
        "Austin, TX",
        Job.EmploymentType.FULL_TIME,
        "$120,000–$150,000",
        Job.Status.OPEN,
        60,
        "Help the seven-microphone array hear what people meant, not what "
        "they said.\n\nYou should enjoy signal processing and be at peace "
        "with being overheard.",
    ),
    (
        "Recall Coordinator",
        "Trust & Safety",
        "On site",
        Job.EmploymentType.CONTRACT,
        "",
        Job.Status.OPEN,
        45,
        "Coordinate the return of products that have started having opinions."
        "\n\nCalm voice and a current tetanus shot preferred.",
    ),
    (
        "Dream Archivist Intern",
        "Curation",
        "Remote",
        Job.EmploymentType.INTERNSHIP,
        "",
        Job.Status.DRAFT,
        5,
        "Catalog what DreamWeaver owners leave behind each morning.",
    ),
    (
        "Head of Plausible Deniability",
        "Legal",
        "Undisclosed",
        Job.EmploymentType.FULL_TIME,
        "$210,000",
        Job.Status.CLOSED,
        500,
        "We can neither confirm nor deny this role exists.",
    ),
]

CAREER_APPLICATIONS = [
    # (job, username, days ago, cover letter, steps), each step being
    # (action, stage or None, days after applying, note or reason)
    (
        "Junior Thought Curator",
        "mwren",
        2,
        "I have been thinking about this job for some time.",
        [],
    ),
    (
        "Junior Thought Curator",
        "dcole",
        20,
        "",
        [
            ("move", "Screening", 2, "Portfolio looks tidy."),
            ("note", None, 3, "Check references before the interview."),
        ],
    ),
    (
        "Junior Thought Curator",
        "tokafor",
        30,
        "Shelving is my calling. Thoughts are just quieter books.",
        [
            ("move", "Screening", 1, ""),
            ("move", "Interview", 6, "Strong phone screen."),
            ("move", "Offer", 15, "The panel was unanimous."),
        ],
    ),
    (
        "Seraphine Listening Engineer",
        "lvasquez",
        50,
        "I built my first microphone array out of spite.",
        [
            ("move", "Screening", 2, ""),
            ("move", "Interview", 9, ""),
            ("move", "Offer", 20, ""),
            ("move", "Hired", 30, "Accepted. Starts next month."),
        ],
    ),
    (
        "Seraphine Listening Engineer",
        "hpark",
        40,
        "",
        [
            ("move", "Screening", 3, ""),
            ("move", "Rejected", 8, "Wants to stop being overheard."),
        ],
    ),
    (
        "Seraphine Listening Engineer",
        "gfinch",
        35,
        "",
        [
            ("move", "Rejected", 2, ""),
            ("reopen", "Interview", 4, "Rejected by mistake: wrong Gordon."),
            ("note", None, 5, "Called to apologize."),
        ],
    ),
    (
        "Recall Coordinator",
        "snakamura",
        25,
        "I have returned many things in my time.",
        [
            ("move", "Screening", 3, ""),
            ("withdraw", None, 10, ""),
        ],
    ),
    (
        "Recall Coordinator",
        "bcrane",
        6,
        "",
        [("move", "Screening", 1, "")],
    ),
    (
        "Head of Plausible Deniability",
        "rmalik",
        480,
        "I was never here.",
        [
            ("move", "Rejected", 20, "Too forthcoming."),
            ("anonymize", None, 400, ""),
        ],
    ),
]

# The customer demo login's live cart: (product slug, quantity).
CUSTOMER_CART = [
    ("seraphine", 2),
    ("travel-faraday-case", 1),
    ("whisper-alarm-clock", 1),
]

# The customer demo login's visible order history: (days ago, status,
# [(product slug, quantity), ...]). Statuses follow age, like the
# background orders, plus one recent order still in flight.
CUSTOMER_ORDERS = [
    (124, Order.Status.DELIVERED, [("mindsync", 1), ("syncrest", 1)]),
    (47, Order.Status.DELIVERED, [("dreamweaver", 1)]),
    (9, Order.Status.SHIPPED, [("seraphine-mini", 2), ("seraphine-wall-mount", 1)]),
    (2, Order.Status.PLACED, [("veil", 1)]),
]

# Sample wishlists, made by the seed rather than chosen by their owners,
# so each is marked is_sample and badged "Sample list". None is ever the
# main list, so its owner can always delete it: (owner username, list
# name, public, shared by link, [product slugs, top of the list first]).
# "Gift ideas" holds the unavailable EchoPatch, to show a greyed item.
SAMPLE_WISHLISTS = [
    ("customer", "Birthday", True, False, ["dreamweaver", "moodset", "calm-collar"]),
    (
        "customer",
        "Gift ideas",
        False,
        True,
        ["seraphine-mini", "whisper-alarm-clock", "echopatch"],
    ),
    (
        "employee",
        "Staff picks",
        True,
        False,
        ["seraphine", "mindsync", "pulse-halo", "travel-faraday-case"],
    ),
]

# Background orders spread across the trailing six months so the Phase 7
# dashboard has a real time axis. 48 here + 4 above = 52 total.
BACKGROUND_ORDER_COUNT = 48

# Shipping addresses for the background orders. US-only, like checkout.
SEED_ADDRESSES = [
    ("214 Synapse Street", "Canyon", "TX", "79015"),
    ("77 Cortex Lane", "Amarillo", "TX", "79101"),
    ("1500 Dendrite Drive", "Albuquerque", "NM", "87102"),
    ("9 Axon Avenue", "Norman", "OK", "73019"),
    ("410 Myelin Way", "Wichita", "KS", "67202"),
    ("28 Ganglion Court", "Denver", "CO", "80202"),
]

CARD_LAST4S = ["4242", "4111", "1881", "0005"]

# Demo coupons, dated relative to the seed run so the demo never goes
# stale: (code, type, value, starts days from now, expires days from
# now, minimum order, once per customer, public, replaced by).
PERCENT, AMOUNT = "PERCENT", "AMOUNT"
COUPONS = [
    # The replacement chain: THOUGHTS10 → THOUGHTS15 → THOUGHTS20. The
    # customer's cart holds THOUGHTS10, so the swap shows on first visit.
    ("THOUGHTS20", PERCENT, "20", -1, 60, None, False, False, None),
    ("THOUGHTS15", PERCENT, "15", -60, -1, None, False, False, "THOUGHTS20"),
    ("THOUGHTS10", PERCENT, "10", -150, -3, None, False, False, "THOUGHTS15"),
    # Expired with no link: typing it falls back to the closest public coupon.
    ("SUMMER5", AMOUNT, "5", -120, -30, None, False, False, None),
    # The public pool the closest-match search draws from.
    ("FALL10", PERCENT, "10", -21, 45, None, False, True, None),
    ("SAVE15", AMOUNT, "15", -21, 45, "75", False, True, None),
    ("WELCOME5", AMOUNT, "5", -180, 180, None, True, True, None),
    # Never offered automatically.
    ("STAFFONLY50", PERCENT, "50", -30, 365, None, False, False, None),
]
# HOLIDAY20 is scheduled: it starts on the next November 25.
HOLIDAY_CODE = "HOLIDAY20"

# Roughly one background order in four used a coupon.
COUPON_ORDER_SHARE = 0.25


def _resume_pdf(user):
    """A one-page PDF that opens in a real viewer, so the demo download works."""
    line = f"{user.first_name} {user.last_name} - demo resume".encode()
    stream = b"BT /F1 18 Tf 72 720 Td (" + line + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    table = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    return pdf + b"startxref\n%d\n%%%%EOF\n" % table


class Command(BaseCommand):
    help = (
        "Wipe and rebuild the demo world: catalog, tags, demo accounts, "
        "coupons, orders, and sample wishlists."
    )

    def handle(self, *args, **options):
        # Sample applicants are fictional. Their emails go out when the
        # transaction commits, so the override has to wrap all of it.
        dummy = "django.core.mail.backends.dummy.EmailBackend"
        with override_settings(EMAIL_BACKEND=dummy):
            self._build()

    @transaction.atomic
    def _build(self):
        self._wipe()
        tags = self._create_tags()
        self._create_catalog(tags)
        self._attach_photos()
        self._create_users()
        self._create_coupons()
        self._create_customer_cart()
        self._create_orders()
        self._create_wishlists()
        self._create_careers()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Category.objects.count()} categories, "
                f"{Tag.objects.count()} tags, "
                f"{Product.objects.count()} products, "
                f"{get_user_model().objects.count()} users, "
                f"{Coupon.objects.count()} coupons, "
                f"{Order.objects.count()} orders, "
                f"{Wishlist.objects.filter(is_sample=True).count()} sample wishlists, "
                f"{Job.objects.count()} jobs, "
                f"{Application.objects.count()} applications, "
                f"and a live cart for 'customer'."
            )
        )

    def _wipe(self):
        """Remove everything the seed owns; the rebuild starts from zero."""
        Application.objects.all().delete()
        Job.objects.all().delete()
        Stage.objects.all().delete()
        Order.objects.all().delete()
        Cart.objects.all().delete()
        Coupon.objects.all().delete()
        Product.objects.all().delete()
        Tag.objects.all().delete()
        Category.objects.all().delete()

        managed_usernames = [username for username, *_ in DEMO_USERS] + [
            username for username, *_ in BACKGROUND_CUSTOMERS
        ]
        get_user_model().objects.filter(username__in=managed_usernames).delete()

        # Product photos live on disk, not in the database; without this
        # every run would leave the last run's files behind.
        shutil.rmtree(Path(settings.MEDIA_ROOT) / "products", ignore_errors=True)
        shutil.rmtree(Path(settings.PRIVATE_MEDIA_ROOT) / "resumes", ignore_errors=True)

    def _create_tags(self):
        return {
            name: Tag.objects.create(name=name, slug=slugify(name)) for name in TAGS
        }

    def _create_catalog(self, tags):
        for category_name, entries in CATALOG.items():
            category = Category.objects.create(
                name=category_name, slug=slugify(category_name)
            )
            for name, price, tagline, description, tag_names, is_available in entries:
                product = Product.objects.create(
                    name=name,
                    slug=slugify(name),
                    price=price,
                    tagline=tagline,
                    description=description,
                    is_available=is_available,
                    category=category,
                )
                product.tags.set(tags[tag_name] for tag_name in tag_names)

    def _attach_photos(self):
        """Give each product in PRODUCT_PHOTOS its photo, saved through the
        ImageField so the file lands in media/ like a staff upload."""
        for slug, filename in PRODUCT_PHOTOS.items():
            source = PHOTO_DIR / filename
            if not source.is_file():
                raise CommandError(f"Product photo not found: {source}")
            with source.open("rb") as photo:
                Product.objects.get(slug=slug).image.save(filename, File(photo))

    def _create_users(self):
        User = get_user_model()
        for username, password, email, first, last, staff, superuser, job in DEMO_USERS:
            user = User(
                username=username,
                email=email,
                first_name=first,
                last_name=last,
                is_staff=staff,
                is_superuser=superuser,
                is_recruiter=username in DEMO_RECRUITERS,
                job_title=job,
            )
            user.set_password(password)
            user.save()

        for username, first, last in BACKGROUND_CUSTOMERS:
            user = User(
                username=username,
                email=f"{username}@example.com",
                first_name=first,
                last_name=last,
            )
            user.set_unusable_password()
            user.save()

    def _create_coupons(self):
        """The demo coupons, replacements linked after all exist."""
        now = timezone.now()
        coupons = {}
        for code, kind, value, starts, expires, minimum, once, public, _ in COUPONS:
            coupons[code] = Coupon.objects.create(
                code=code,
                discount_type=kind,
                value=Decimal(value),
                starts_at=now + timedelta(days=starts),
                expires_at=now + timedelta(days=expires),
                minimum_order=Decimal(minimum) if minimum else None,
                once_per_customer=once,
                is_public=public,
            )
        for code, *_, replaced_by in COUPONS:
            if replaced_by:
                coupons[code].replaced_by = coupons[replaced_by]
                coupons[code].save()

        local = timezone.localtime(now)
        holiday = local.replace(month=11, day=25, hour=0, minute=0, second=0)
        if holiday <= local:
            holiday = holiday.replace(year=holiday.year + 1)
        Coupon.objects.create(
            code=HOLIDAY_CODE,
            discount_type=PERCENT,
            value=Decimal("20"),
            starts_at=holiday,
            expires_at=holiday + timedelta(days=37),
            is_public=True,
        )

    def _create_customer_cart(self):
        """A live cart holding the expired THOUGHTS10, left unrefreshed so
        the swap notice appears the first time 'customer' views the cart."""
        customer = get_user_model().objects.get(username="customer")
        cart = Cart.for_user(customer)
        for slug, quantity in CUSTOMER_CART:
            cart.items.create(product=Product.objects.get(slug=slug), quantity=quantity)
        cart.coupon = Coupon.objects.get(code="THOUGHTS10")
        cart.save()

    def _create_wishlists(self):
        """An empty main list for each demo login, then the sample lists.

        Owners are demo users, so the wipe's user delete cascades to them.
        """
        User = get_user_model()
        for username, *_ in DEMO_USERS:
            Wishlist.objects.main_for(User.objects.get(username=username))
        for username, name, public, linked, slugs in SAMPLE_WISHLISTS:
            wishlist = Wishlist.objects.create(
                owner=User.objects.get(username=username),
                name=name,
                is_public=public,
                is_sample=True,
            )
            wishlist.set_link_sharing(linked)
            # Each add lands on top, so add the bottom item first.
            for slug in reversed(slugs):
                wishlist.add(Product.objects.get(slug=slug))

    def _create_careers(self):
        """Jobs, then applications built through the app's own services, so
        every timeline is one the app could really have produced."""
        now = timezone.now()
        for position, (name, kind) in enumerate(DEFAULT_STAGES):
            Stage.objects.create(name=name, kind=kind, position=position)

        jobs = {}
        for (
            title,
            department,
            location,
            kind,
            salary,
            status,
            days,
            text,
        ) in CAREER_JOBS:
            jobs[title] = Job.objects.create(
                title=title,
                slug=slugify(title),
                description=text,
                department=department,
                location=location,
                employment_type=kind,
                salary_range=salary,
                # Applications need an Open job, so closing comes last.
                status=(
                    Job.Status.DRAFT if status == Job.Status.DRAFT else Job.Status.OPEN
                ),
                published_at=(
                    None if status == Job.Status.DRAFT else now - timedelta(days=days)
                ),
            )

        User = get_user_model()
        recruiter = User.objects.get(username="recruiter")
        for title, username, days_ago, letter, steps in CAREER_APPLICATIONS:
            user = User.objects.get(username=username)
            applied_at = now - timedelta(days=days_ago)
            application = submit_application(
                jobs[title],
                user,
                SimpleUploadedFile(f"{username}.pdf", _resume_pdf(user)),
                letter,
                now=applied_at,
            )
            for action, stage_name, offset, text in steps:
                at = applied_at + timedelta(days=offset)
                stage = Stage.objects.filter(name=stage_name).first()
                if action == "move":
                    application = move_application(
                        application, stage, recruiter, note=text, now=at
                    )
                elif action == "reopen":
                    application = reopen_application(
                        application, stage, text, recruiter, now=at
                    )
                elif action == "withdraw":
                    application = withdraw_application(application, user, now=at)
                elif action == "anonymize":
                    application = anonymize_application(application, now=at)
                else:
                    application.add_note(recruiter, text, now=at)

        for title, *_, status, _days, _text in CAREER_JOBS:
            if status == Job.Status.CLOSED:
                job = jobs[title]
                job.change_status(Job.Status.CLOSED)
                job.save(update_fields=["status"])

    def _create_orders(self):
        """Order history: 4 visible orders for 'customer', 48 background.

        A seeded RNG keeps every run identical (the idempotence
        contract). Statuses follow age — old orders are delivered,
        recent ones are still moving, and about one in ten was
        cancelled along the way.
        """
        rng = random.Random(2026)
        # Coupons draw from their own RNG so the orders themselves stay
        # exactly as they were before coupons existed.
        coupon_rng = random.Random(10)
        now = timezone.now()
        User = get_user_model()

        customer = User.objects.get(username="customer")
        welcome = Coupon.objects.get(code="WELCOME5")
        for index, (days_ago, status, lines) in enumerate(CUSTOMER_ORDERS):
            self._build_order(
                user=customer,
                created_at=now - timedelta(days=days_ago, hours=rng.randint(1, 12)),
                status=status,
                lines=[
                    (Product.objects.get(slug=slug), quantity)
                    for slug, quantity in lines
                ],
                rng=rng,
                # Their first order used WELCOME5, so it's spent for them.
                coupon=welcome if index == 0 else None,
            )

        # Coupons a background customer might have used, never the
        # staff-only one. Sorted so the RNG's choices are reproducible.
        usable = list(Coupon.objects.exclude(code="STAFFONLY50").order_by("code"))
        used_once = set()

        background = list(
            User.objects.filter(
                username__in=[username for username, *_ in BACKGROUND_CUSTOMERS]
            ).order_by("username")
        )
        # Defense sales close offline, over handshakes — a single SoulSear
        # would also flatten every other product on the revenue chart.
        pool = list(
            Product.objects.available()
            .exclude(category__slug="defense")
            .order_by("slug")
        )
        for _ in range(BACKGROUND_ORDER_COUNT):
            # Weighted toward today (business is good) so the dashboard's
            # default 30-day view has enough bars to read as a chart.
            days_ago = int(rng.triangular(0, 182, 0))
            if rng.random() < 0.1:
                status = Order.Status.CANCELLED
            elif days_ago > 14:
                status = Order.Status.DELIVERED
            else:
                status = rng.choice([Order.Status.PLACED, Order.Status.SHIPPED])
            user = rng.choice(background)
            created_at = now - timedelta(days=days_ago, hours=rng.randint(1, 23))
            lines = [
                (product, rng.randint(1, 2))
                for product in rng.sample(pool, rng.randint(1, 3))
            ]

            coupon = None
            if coupon_rng.random() < COUPON_ORDER_SHARE:
                subtotal = sum((p.price * q for p, q in lines), Decimal("0.00"))
                options = [
                    c
                    for c in usable
                    if c.is_active(created_at)
                    and c.meets_minimum(subtotal)
                    and (c.pk, user.pk) not in used_once
                ]
                if options:
                    coupon = coupon_rng.choice(options)
                    if coupon.once_per_customer:
                        used_once.add((coupon.pk, user.pk))

            self._build_order(
                user=user,
                created_at=created_at,
                status=status,
                lines=lines,
                rng=rng,
                coupon=coupon,
            )

    def _build_order(self, *, user, created_at, status, lines, rng, coupon=None):
        """One order with denormalized addresses, purchase-time prices, and
        the coupon's code and discount snapshotted like at checkout."""
        street, city, state, zip_code = rng.choice(SEED_ADDRESSES)
        name = f"{user.first_name} {user.last_name}"
        subtotal = sum(
            (product.price * quantity for product, quantity in lines),
            Decimal("0.00"),
        )
        discount = coupon.savings_for(subtotal) if coupon else Decimal("0.00")
        order = Order.objects.create(
            user=user,
            status=status,
            total=subtotal - discount,
            discount=discount,
            coupon=coupon,
            coupon_code=coupon.code if coupon else "",
            email=user.email,
            shipping_name=name,
            shipping_street=street,
            shipping_city=city,
            shipping_state=state,
            shipping_zip=zip_code,
            billing_name=name,
            billing_street=street,
            billing_city=city,
            billing_state=state,
            billing_zip=zip_code,
            card_last4=rng.choice(CARD_LAST4S),
            created_at=created_at,
        )
        for product, quantity in lines:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=quantity,
            )
