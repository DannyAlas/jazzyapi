import json
from typing import Union

import drawsvg as draw
import redis
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from api.models import EmbedInfo, JSONDecoder, Phrase
from api.utils import get_characters_and_times

redcon = redis.Redis(host="10.32.32.20", port=6379, db=0)

app = FastAPI()


@app.get("/")
async def read_item(request: Request):
    return RedirectResponse("/docs")


@app.get("/typewriter")
def main(
    font: str = "Fira+Code",
    weight: int = 400,
    size: int = 20,
    style: str = "normal",
    duration: int = 5000,
    color: str = "36BCF7FF",
    background: str = "00000000",
    repeat: bool = False,
    center: bool = False,
    vCenter: bool = True,
    multiline: bool = False,
    width: int = 435,
    height: int = 50,
    pause: int = 1000,
    lines: str = "The+five+boxing+wizards+jump+quickly;How+vexingly+quick+daft+zebras+jump",
) -> StreamingResponse:

    true_duration = (lines.count(";") + 2 * pause) + duration

    lines_list = lines.split(";")

    total_characters, display_time = get_characters_and_times(
        lines_list, true_duration, multiline, pause
    )

    d = draw.Drawing(
        width,
        height,
        origin=(0, 0),
        animation_config=draw.types.SyncedAnimationConfig(
            duration=display_time[len(display_time) - 1],
        ),
    )

    # FONTS
    font = font.replace("+", " ")
    d.embed_google_font(font)

    # BACKGROUND
    d.append(draw.Rectangle(0, 0, width, height, fill=f"#{background}"))

    # TEXT POSITION
    if vCenter:
        if multiline:
            # i have no idea why i need to add 17 to the y position to center it vertically, but it works
            y = (height / 2 - (size * (lines.count(";") + 1)) / 2) + 17
        else:
            y = height / 2 + size / 3
    else:
        y = size
    if center:
        center = True
        x = width / 2
        y -= 9
    else:
        center = False
        x = 0
        draw.native_animation.animate_text_sequence(
            d,
            display_time,
            total_characters,
            size,
            x,
            y,
            font_family=font,
            font_weight=weight,
            font_style=style,
            fill=f"#{color}",
            center=center,
        )

        def iter():
            yield d.as_svg()

        return StreamingResponse(iter(), media_type="image/svg+xml")


@app.get("/profile-counter")
def get_counter() -> StreamingResponse:
    redcon.incr("profile-counter")
    # creeate a quick text incrementing counteruvi
    count = redcon.get("profile-counter").decode("utf-8")
    len_l = len("Profile views") * 5.5 + 4
    len_r = len(str(count)) * 5.5 * 1.5
    svg_len = len_l + len_r + 4
    d = draw.Drawing(
        svg_len,
        20,
        origin=(0, 0),
    )
    d.embed_google_font("Verdana")
    grad = draw.LinearGradient(x1=0, y1=0, x2=0, y2="100%", id="b")
    grad.add_stop(0, "#bbb", opacity=".1")
    grad.add_stop(1, "#000", opacity=".1")
    d.append(grad)
    mask = draw.Mask(id="a")
    mask.append(
        draw.Rectangle(
            x=0, y=0, width=svg_len, height=20, mask="url(#a)", fill="#fff", rx="3"
        )
    )
    d.append(mask)
    # <rect width="120.7" height="20" fill="url(#b)"/>
    d.append(
        draw.Rectangle(len_l, 0, svg_len - len_l, 20, fill="#f88469", mask="url(#a)")
    )
    l = draw.Text(
        "Profile views",
        font_size=11,
        x=3,
        y=15,
        font_family="Verdana",
        font_weight=400,
        fill="#fff",
    )
    r = draw.Text(
        count,
        font_size=11,
        x=len_l + 4,
        y=15,
        width=len_r,
        font_family="Verdana",
        font_weight=400,
        fill="#fff",
    )
    d.append(
        draw.Text(
            "Profile views",
            font_size=11,
            x=3,
            y=16,
            font_family="Verdana",
            font_weight=400,
            fill="#000",
            opacity=".3",
        )
    )
    d.append(
        draw.Text(
            count,
            font_size=11,
            x=len_l + 4,
            y=16,
            width=len_r,
            font_family="Verdana",
            font_weight=400,
            fill="#000",
            opacity=".3",
        )
    )
    d.append(draw.Rectangle(0, 0, len_l, 20, fill="#555", mask="url(#a)"))
    d.append(l)
    # drop shadow
    d.append(r)
    d.append(draw.Rectangle(0, 0, svg_len, 20, fill="url(#b)"))

    def iter():
        yield d.as_svg()

    return StreamingResponse(iter(), media_type="image/svg+xml")


@app.get("/dgg/phrases")
def get_dgg_phrases() -> JSONResponse:
    phrases = redcon.get("dgg_phrase_cache")
    if phrases:
        import json

        return JSONResponse(status_code=200, content=json.loads(phrases))
    else:
        return JSONResponse(status_code=404, content={"error": "Not found"})


# add query param to get only the top n embeds, default to 10
@app.get("/dgg/embeds")
def get_dgg_embeds(
    max: int = 10, is_live_only: bool = False, platform: Union[str, None] = None
) -> JSONResponse:
    embeds = redcon.get("dgg_embeds_cache")
    lst = json.loads(embeds, cls=JSONDecoder)
    embeds = [EmbedInfo(**x) for x in lst]
    embeds.sort(key=lambda x: x.watchers, reverse=True)
    if is_live_only:
        embeds = [x for x in embeds if x.type == "live"]
    if platform:
        embeds = [x for x in embeds if x.platform.lower() == platform.lower()]
    embeds = embeds[:max]
    embeds = jsonable_encoder(embeds)
    return JSONResponse(status_code=200, content=embeds)
