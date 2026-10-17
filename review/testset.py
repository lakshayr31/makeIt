"""Test set: 2 clean designs + designs broken on purpose, each with the findings we expect."""

import copy
import json

from PIL import Image, ImageDraw

from review.design import ROOT, font

WORK = "assets/work"
LOGO_WHITE, LOGO_NAVY, LOGO_CYAN = (
    f"assets/brand-kit/10_Logo/10_Logo/{f}"
    for f in (
        "01_0f4c5387-a60d-4a27-93e8-9f5223676154.png",
        "02_2f020a69-e294-4971-b448-760f8b1827ad.png",
        "03_a6d69555-61d3-43ba-a7ab-e38d56a3805c.png",
    )
)
CHARM_PERCENT = (
    "assets/brand-kit/22_Charms/22_Charms/03_ca497862-09a8-4d79-803b-bfd96b145e47.png"
)
CHARM_THUMB = (
    "assets/brand-kit/22_Charms/22_Charms/07_c1d8ba28-b4bb-4067-bcfb-72de14e56c76.png"
)
BLOOM_BG = "assets/brand-kit/24_Background_Templates/24_Background_Templates/04_4bd578f8-72e9-4ed3-9361-d7642f371d5a.png"
WOMAN = f"{WORK}/woman_cutout.png"


def make_cards():
    """Cashflow UI card: a correct one, and one whose chart became a strip of photo."""
    for name, broken in (("card_cashflow.png", False), ("card_broken.png", True)):
        im = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, 399, 299], 22, fill="#FFFFFF")
        d.text((28, 26), "Cashflow", font=font(30, bold=False), fill="#6B6F7B")
        d.text((28, 70), "£12,500", font=font(58), fill="#000856")
        if broken:
            strip = (
                Image.open(ROOT / WOMAN)
                .convert("RGBA")
                .crop((200, 700, 900, 820))
                .resize((344, 70))
            )
            im.alpha_composite(strip, (28, 190))
        else:
            pts = [(28, 260), (90, 230), (150, 245), (220, 200), (290, 215), (372, 175)]
            d.polygon(pts + [(372, 270), (28, 270)], fill="#DDF1FB")
            d.line(pts, fill="#2BB673", width=6)
        im.save(ROOT / WORK / name)


def base_feed():
    return {
        "id": "A_clean_feed",
        "canvas": {"w": 1080, "h": 1350, "format": "feed", "bg": "#000856"},
        "elements": [
            {
                "id": "e3",
                "type": "photo",
                "z": 1,
                "asset": WOMAN,
                "bbox": [480, 560, 600, 752],
            },
            {
                "id": "e5",
                "type": "charm",
                "z": 1.5,
                "asset": CHARM_PERCENT,
                "bbox": [380, 600, 110, 113],
            },
            {
                "id": "e1",
                "type": "text",
                "z": 2,
                "text": "Data in.\nDoubt out.",
                "bbox": [70, 90, 620, 260],
                "font": {"size": 110, "color": "#FFFFFF", "bold": True},
            },
            {
                "id": "e2",
                "type": "button",
                "z": 3,
                "text": "Try Xero today",
                "fill": "#00B8E4",
                "radius": 14,
                "bbox": [70, 400, 420, 100],
                "font": {"size": 44, "color": "#000856", "bold": True},
            },
            {
                "id": "e4",
                "type": "card",
                "z": 3,
                "asset": f"{WORK}/card_cashflow.png",
                "bbox": [80, 760, 320, 240],
            },
            {
                "id": "e6",
                "type": "logo",
                "z": 4,
                "asset": LOGO_CYAN,
                "bbox": [70, 1210, 280, 80],
            },
        ],
    }


def base_story():
    return {
        "id": "B_clean_story",
        "canvas": {"w": 1080, "h": 1920, "format": "story", "bg": "#FFFFFF"},
        "elements": [
            {
                "id": "b1",
                "type": "bloom",
                "z": 1,
                "asset": BLOOM_BG,
                "bbox": [380, 700, 700, 1243],
            },
            {
                "id": "b2",
                "type": "text",
                "z": 2,
                "text": "Get paid\nfaster.",
                "bbox": [90, 330, 700, 280],
                "font": {"size": 120, "color": "#000856", "bold": True},
            },
            {
                "id": "b3",
                "type": "button",
                "z": 3,
                "text": "Start free trial",
                "fill": "#000856",
                "radius": 14,
                "bbox": [90, 660, 480, 110],
                "font": {"size": 48, "color": "#FFFFFF", "bold": True},
            },
            {
                "id": "b4",
                "type": "charm",
                "z": 3,
                "asset": CHARM_THUMB,
                "bbox": [700, 900, 200, 218],
            },
            {
                "id": "b5",
                "type": "logo",
                "z": 4,
                "asset": LOGO_NAVY,
                "bbox": [90, 1080, 280, 80],
            },
        ],
    }


def _variant(base, name, expected, change):
    d = copy.deepcopy(base)
    d["id"] = name
    els = {e["id"]: e for e in d["elements"]}
    change(d, els)
    d["expected"] = expected
    return d


def build():
    make_cards()
    A, B = base_feed(), base_story()
    A["expected"], B["expected"] = [], []
    designs = [
        A,
        B,
        _variant(
            A,
            "A1_head_cut",
            [["cut_off_subject", "e3"]],
            lambda d, e: e["e3"].update(
                crop=[0, 300, 1120, 1104], bbox=[480, 721, 600, 591]
            ),
        ),
        _variant(
            A,
            "A2_text_on_face",
            [["covers_content", "e1"]],
            lambda d, e: e["e1"].update(bbox=[440, 600, 620, 260]),
        ),
        _variant(
            A,
            "A3_logo_off_canvas",
            [["off_canvas", "e6"]],
            lambda d, e: e["e6"].update(bbox=[-90, 1210, 280, 80]),
        ),
        _variant(
            A,
            "A4_logo_wrong_colour",
            [["logo_colour_pair", "e6"]],
            lambda d, e: e["e6"].update(asset=LOGO_NAVY),
        ),
        _variant(
            A,
            "A5_stretched_photo",
            [["stretched", "e3"]],
            lambda d, e: e["e3"].update(bbox=[430, 560, 650, 752]),
        ),
        _variant(
            A,
            "A6_button_overflow",
            [["text_overflow", "e2"]],
            lambda d, e: e["e2"].update(
                text="Try Xero today and start your free trial"
            ),
        ),
        _variant(
            A,
            "A7_low_contrast_text",
            [["low_contrast", "e1"], ["off_palette", "e1"]],
            lambda d, e: e["e1"]["font"].update(color="#1A237E"),
        ),
        _variant(
            A,
            "A8_broken_card",
            [["card_content_broken", "e4"]],
            lambda d, e: e["e4"].update(asset=f"{WORK}/card_broken.png"),
        ),
        _variant(
            A,
            "A9_stray_bar",
            [["stray_artefact", "*"]],
            lambda d, e: d["elements"].append(
                {
                    "id": "e7",
                    "type": "background",
                    "z": 0.5,
                    "fill": "#FFFFFF",
                    "bbox": [455, 640, 14, 640],
                }
            ),
        ),
        _variant(
            B,
            "B1_safe_zone",
            [["safe_zone", "b2"]],
            lambda d, e: e["b2"].update(bbox=[90, 120, 700, 280]),
        ),
    ]
    out = ROOT / "review" / "testset"
    out.mkdir(parents=True, exist_ok=True)
    for d in designs:
        (out / f"{d['id']}.json").write_text(json.dumps(d, indent=1))
    return designs


if __name__ == "__main__":
    print(len(build()), "designs")
