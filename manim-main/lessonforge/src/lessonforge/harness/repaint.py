"""A poster's SCENE repainted by the image model on this machine; its arrows and its labels stay the drawing service's.

The owner, 2026-10-10: "make the skeleton using svg api then use diffusion based approaches to style it", and on the
decision that followed ("Repaint scene drawings with your image model, for scenes only"): yes. What was measured before
this was written is in ``docs/research/approaches/10_frame_and_local_pictures.md`` §6:

* the drawing service gets the STRUCTURE right (which arrow goes where, every word spelt) and looks flat; the image
  model (Z-Image-Turbo in the owner's ComfyUI) looks good and gets structure wrong. So each does its half: the scene
  of a poster (``base.png``: the things, no arrow, no label) is repainted image-to-image, and every arrow layer and
  every label is put back by code where the SVG had it. The model never draws an arrow or a letter;
* right for things and places (a plant, the Sun, sea, hills); WRONG for a drawing whose inner detail is the lesson (a
  cell's Golgi body became something else), and impossible for a drawing with no layers (a typeset one);
* strength is a dial with a cliff: at 0.6 to 0.65 a scene is repainted and stays put, above 0.7 things move from under
  their arrows. A water cycle at 0.65 came back with its river broken and its rain cloud faded.

So three things decide, in code, and a model only answers what it sees:

1. only a poster with a scene layer is a candidate (``manifest["base"]``), and only when a look at that scene says it
   is things and places (``KIND``): anything else is left as drawn;
2. the repainted drawing is compared with the original, side by side, and the judge LISTS what is missing, moved,
   changed into something else, broken or added (``SAME``). Anything listed is a refusal: it is tried once more, more
   gently, and then the drawing is left as drawn;
3. no room on a GPU, no image server, no vision model, any error: the drawing is left as drawn. Nothing here raises.

A repainted drawing is a FOLDER beside the original (``<drawing>/styled/``) with the same manifest, so
``figures.DiagramFigure`` shows it unchanged; the library's own files are never written over. What was decided about
a drawing is kept there (``styled/manifest.json`` or ``styled/refused.json``): the same drawing is never painted, or
looked at, twice.

The image server is the owner's own ComfyUI, started here on the GPU with most free memory and stopped again when
the lesson's drawings are done, so nothing is held on a shared GPU between lessons (the owner: "there is still space
in gpus use it … use gpustat to get gpu info").

**It is OFF unless ``HARNESS_REPAINT=1``** (2026-10-10, evening). The first runs through this module showed what the
morning's look had missed: the repainting I had called good had lost the water drops and the oxygen bubbles and
gained a cloud; with another seed the plant's roots came apart into loose strokes and two drops were added; and at
the strength where nothing breaks (0.5) the picture hardly looks different. The checks below refuse all of that,
which is what they are for, but a step that takes a minute and a half and then mostly leaves the drawing as it was
has not earned its place in every lesson. Small things are now put back (``restore_small``) and a refused try is
made again from another seed; the run on the library's twelve posters that would say how often that ends in a
repainting a person accepts could not be made: no GPU had the 12 GB it needs. Turn it on after that run.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .. import knobs
from .. import paths

#: (how much of the scene the model may repaint: 0 nothing, 1 all; the seed) for each try, in order, until one is
#: accepted. The same strength gives a sound picture from one seed and a plant with its roots in pieces from the next,
#: so a refused try is made again from another seed before it is made more gently.
TRIES = ((0.6, 7), (0.6, 11), (0.54, 7), (0.5, 11))
STEPS = 8
MIN_FREE_GB = 12.0            # the model ran with this much free on a GPU other jobs kept busy
START_SECONDS = 180.0         # an image server that has not answered by then is given up
PAINT_SECONDS = 240.0         # ... and so is one picture (14 s when the model is loaded, 38 s the first time)
#: The whole prompt. It does NOT say what is in the picture: told "the picture shows water drops", the model painted two
#: more of them (the first run through this module, 2026-10-10). The picture itself is what it has to go by.
STYLE = ("The same picture as a hand-painted school textbook illustration in soft gouache and coloured pencil: gentle shading, "
         "clean shapes, bright natural colours. Every object stays exactly where it is and what it is; nothing is added and "
         "nothing is taken away. No text, no letters, no numbers, no arrows, no labels, no borders.")

KIND = """You look at ONE drawing made for a school lesson. Its arrows and labels have been taken out; what is left is the scene.
Say what KIND of picture it is, and list what is drawn in it. Return ONLY JSON:
{"things": [{"thing": "two or three words", "where": "top left | centre | below the plant | … a few words"}],
 "kind": "scene" | "inside" | "figure", "why": "one sentence"}
"things": EVERY separate thing drawn, the small ones too (three drops of water, two bubbles), each with where it is; things
of one kind that stand together are one entry ("two clouds, top right"). At most fourteen entries.
"scene": things and places as the eye sees them from outside: a landscape, the sky, the sea, hills, a river, a plant, a tree,
an animal, a house, people, everyday objects, the Sun, clouds.
"inside": a drawing whose INNER DETAIL is what the lesson teaches and must stay exactly as drawn: a cell and its organelles,
an organ or a body system, a cross-section or a cut-away, the parts of a machine or an instrument, an atom or a molecule, a
circuit, apparatus set up for an experiment.
"figure": a geometric figure, a graph, a chart, a table, a number line, a ray diagram, a map, or anything made mostly of
lines, symbols and writing.
When you hesitate between "scene" and another kind, answer the other kind."""

SAME = """Two pictures of one drawing for a school lesson stand side by side. A, on the left, is the original. B, on the right, is the
same drawing with its scene repainted in another style. The arrows are the same in both and were put back by a program.
You are given the numbered list of THINGS IN A, each with where it is. For EACH thing, look at the same place in B and answer:
"same": it is there, it is still that kind of thing, and it is where it was (a shift smaller than the thing itself is "same");
"gone": it is not there, or has faded until it can hardly be seen;
"different": it has become another thing, or is in pieces (a river with gaps in it, roots that are now loose strokes);
"elsewhere": it is in B, clearly at another place.
Then look for things in B that are in NO place of A: an extra drop, cloud, bird, stone, tree, face, sign.
Return ONLY JSON: {"checks": [{"n": 1, "thing": "as in the list", "in_b": "same | gone | different | elsewhere", "seen": "what you see in B there"}],
 "new_in_b": ["each thing that is in B and nowhere in A, with where it is"]}
A difference of colour shade, texture, shading, outline, brushwork or amount of detail is NOT a difference: B is meant to
look painted. Soil with specks in it, grass with rougher blades, a cloud with softer edges are "same"."""
#: A verdict belongs to the questions that gave it: other questions, and the drawing is looked at again.
VERSION = hashlib.sha256((KIND + SAME + STYLE + repr(TRIES)).encode("utf-8")).hexdigest()[:10]
_NOT_SAME = ("gone", "different", "elsewhere")

_SERVER = threading.Lock()    # one image server at a time, whoever asks


def enabled() -> bool:
    return (knobs.get("HARNESS_REPAINT") or "0").strip() == "1"


def server_dir() -> Path:
    """Where the image server is installed (``LOCAL_IMAGE_SERVER``, default: the owner's ComfyUI)."""
    return Path(os.getenv("LOCAL_IMAGE_SERVER") or "/workspace/models/ComfyUI")


def server_url() -> str:
    return (os.getenv("LOCAL_IMAGE_URL") or "http://127.0.0.1:8189").rstrip("/")


def _python() -> Path:
    return server_dir() / "venv" / "bin" / "python"


def installed() -> bool:
    """Whether the image server and the model's three files are on this machine."""
    local = server_dir() / "models_local"
    return (_python().is_file() and (server_dir() / "main.py").is_file()
            and (local / "unet" / "z_image_turbo_bf16.safetensors").is_file()
            and any((local / d / "qwen_3_4b.safetensors").is_file() for d in ("text_encoders", "clip"))
            and (local / "vae" / "ae.safetensors").is_file())


def gpu_room() -> list[tuple[int, float]]:
    """(GPU, free GB) for every GPU, most room first; [] when nobody can say.

    ``nvidia-smi`` is asked first. On 2026-10-10 it answered "driver/library version mismatch" for a whole day while the
    GPUs went on working: then the image server's own Python asks torch, which could still see them.
    """
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20)
        rows = [line.split(",") for line in out.stdout.strip().splitlines()] if out.returncode == 0 else []
        room = [(int(a), float(b) / 1024.0) for a, b in (r for r in rows if len(r) == 2)]
        if room:
            return sorted(room, key=lambda r: -r[1])
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        code = ("import json, torch\n"
                "print(json.dumps([[i, torch.cuda.mem_get_info(i)[0] / 2**30] for i in range(torch.cuda.device_count())]"
                " if torch.cuda.is_available() else []))")
        out = subprocess.run([str(_python()), "-c", code], capture_output=True, text=True, timeout=120)
        room = [(int(a), float(b)) for a, b in json.loads(out.stdout.strip().splitlines()[-1])] if out.returncode == 0 else []
        return sorted(room, key=lambda r: -r[1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return []


def _answers(url: str, timeout: float = 4.0) -> bool:
    try:
        import requests  # noqa: PLC0415
        return requests.get(f"{url}/system_stats", timeout=timeout).ok
    except Exception:  # noqa: BLE001 - not up is an answer
        return False


@contextmanager
def server(log=print):
    """The image server's address for the length of the block, or None when there is none to be had.

    One that already answers is used and left running: it is somebody else's. Otherwise it is started on the GPU with
    most free memory, with folders of its own in the workspace, and STOPPED when the block ends, which gives the
    memory back.
    """
    url, started = server_url(), None
    with _SERVER:
        try:
            if _answers(url):
                yield url
                return
            if not installed():
                log("[repaint] the image model is not on this machine: the drawing stays as drawn")
                yield None
                return
            room = gpu_room()
            if not room or room[0][1] < MIN_FREE_GB:
                log("[repaint] no GPU has room for the image model now"
                    + (f" (most free: {room[0][1]:.0f} GB on GPU {room[0][0]}, it needs {MIN_FREE_GB:.0f})" if room else "")
                    + ": the drawing stays as drawn")
                yield None
                return
            work = paths.sub("local_models")
            for name in ("comfy_in", "comfy_out", "comfy_tmp", "comfy_user"):
                (work / name).mkdir(exist_ok=True)
            base = server_dir()
            # The installation's own list of model folders points at a place that no longer exists: ours says where they are.
            (work / "model_paths.yaml").write_text(
                "lessonforge:\n"
                f"    base_path: {base}/\n"
                "    vae: models_local/vae/\n"
                "    text_encoders: |\n         models_local/text_encoders/\n         models_local/clip/\n"
                "    diffusion_models: |\n         models_local/unet/\n         models_local/diffusion_models/\n", encoding="utf-8")
            host, port = url.split("//", 1)[-1].rsplit(":", 1) if ":" in url.split("//", 1)[-1] else ("127.0.0.1", "8189")
            command = [str(_python()), "main.py", "--listen", host, "--port", port, "--cuda-device", str(room[0][0]),
                       "--extra-model-paths-config", str(work / "model_paths.yaml"), "--output-directory", str(work / "comfy_out"),
                       "--input-directory", str(work / "comfy_in"), "--temp-directory", str(work / "comfy_tmp"),
                       "--user-directory", str(work / "comfy_user"), "--database-url", f"sqlite:///{work / 'comfy.db'}",
                       "--disable-auto-launch", "--disable-all-custom-nodes"]
            with open(work / "comfy.log", "ab") as out:
                started = subprocess.Popen(command, cwd=str(base), stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
            began = time.time()
            while time.time() - began < START_SECONDS and started.poll() is None and not _answers(url, 2.0):
                time.sleep(2.0)
            if started.poll() is not None or not _answers(url):
                log("[repaint] the image server did not start (see local_models/comfy.log): the drawing stays as drawn")
                yield None
                return
            log(f"[repaint] the image model is up on GPU {room[0][0]} ({room[0][1]:.0f} GB were free), {time.time() - began:.0f} s")
            yield url
        finally:
            if started is not None and started.poll() is None:
                started.terminate()
                try:
                    started.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    started.kill()


def _workflow(image: str, prompt: str, width: int, height: int, strength: float, seed: int, name: str) -> dict:
    """Image to image with Z-Image-Turbo: the picture is encoded, a share of it is painted again, and it is decoded."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "11": {"class_type": "LoadImage", "inputs": {"image": image}},
        "12": {"class_type": "ImageScale", "inputs": {"image": ["11", 0], "upscale_method": "lanczos", "width": width, "height": height,
                                                      "crop": "disabled"}},
        "13": {"class_type": "VAEEncode", "inputs": {"pixels": ["12", 0], "vae": ["3", 0]}},
        "7": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["7", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["13", 0],
                                                    "seed": seed, "steps": STEPS, "cfg": 1.0, "sampler_name": "res_multistep",
                                                    "scheduler": "simple", "denoise": strength}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": name}},
    }


def paint(url: str, picture, prompt: str, strength: float, seed: int = 7):
    """``picture`` (a PIL image) repainted, at its own size. Raises on any failure; the caller leaves the drawing alone."""
    import requests  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    flat = Image.new("RGB", picture.size, "white")
    flat.paste(picture.convert("RGBA"), mask=picture.convert("RGBA").split()[3])
    name = f"lessonforge_{uuid.uuid4().hex[:10]}"
    sent = io.BytesIO()
    flat.save(sent, format="PNG")
    up = requests.post(f"{url}/upload/image", files={"image": (f"{name}.png", sent.getvalue(), "image/png")},
                       data={"overwrite": "true"}, timeout=60)
    up.raise_for_status()
    stored = up.json()
    image = (f"{stored['subfolder']}/" if stored.get("subfolder") else "") + stored["name"]
    width, height = (max(16, round(v / 16) * 16) for v in flat.size)          # the model works in blocks of sixteen pixels
    asked = requests.post(f"{url}/prompt", json={"prompt": _workflow(image, prompt, width, height, strength, seed, name),
                                                 "client_id": uuid.uuid4().hex}, timeout=60)
    asked.raise_for_status()
    prompt_id, began = asked.json()["prompt_id"], time.time()
    while True:
        history = requests.get(f"{url}/history/{prompt_id}", timeout=30).json()
        if prompt_id in history:
            entry = history[prompt_id]
            if (entry.get("status") or {}).get("status_str") == "error":
                raise RuntimeError(json.dumps((entry.get("status") or {}).get("messages"))[:300])
            made = [i for out in (entry.get("outputs") or {}).values() for i in out.get("images") or []]
            if not made:
                raise RuntimeError("the image server returned no picture")
            got = requests.get(f"{url}/view", params={"filename": made[0]["filename"], "subfolder": made[0].get("subfolder", ""),
                                                      "type": made[0].get("type", "output")}, timeout=120)
            got.raise_for_status()
            return Image.open(io.BytesIO(got.content)).convert("RGB").resize(flat.size, Image.LANCZOS)
        if time.time() - began > PAINT_SECONDS:
            raise TimeoutError(f"no picture after {PAINT_SECONDS:.0f} s")
        time.sleep(1.0)


def _jpeg(image, most: int = 1800) -> str:
    image = image.convert("RGB")
    image.thumbnail((most, most))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=86)
    return base64.b64encode(out.getvalue()).decode("ascii")


def _on_white(image):
    from PIL import Image  # noqa: PLC0415
    image = image.convert("RGBA")
    ground = Image.new("RGBA", image.size, "white")
    ground.alpha_composite(image)
    return ground.convert("RGB")


def with_arrows(scene, manifest: dict, folder: Path):
    """The scene with every arrow layer of the drawing laid on it where the SVG had it: the drawing without its labels."""
    from PIL import Image  # noqa: PLC0415
    ax0, ay0 = (manifest.get("art_box") or [0, 0])[:2]
    whole = scene.convert("RGBA").copy()
    for part in manifest.get("parts") or []:
        file = folder / str(part.get("png") or "")
        if file.is_file():
            layer = Image.open(file).convert("RGBA")
            whole.alpha_composite(layer, (int(part["box"][0] - ax0), int(part["box"][1] - ay0)))
    return whole


def side_by_side(first, second):
    """A | B on one sheet, each marked with its letter, for the judge that compares them."""
    from PIL import Image, ImageDraw  # noqa: PLC0415
    a, b = _on_white(first), _on_white(second).resize(first.size)
    gap = max(12, a.width // 60)
    sheet = Image.new("RGB", (a.width * 2 + gap, a.height), "#202020")
    sheet.paste(a, (0, 0))
    sheet.paste(b, (a.width + gap, 0))
    pen, size = ImageDraw.Draw(sheet), max(26, a.height // 14)
    for letter, x in (("A", 0), ("B", a.width + gap)):
        pen.rectangle([x, 0, x + size, size], fill="#202020")
        pen.text((x + size * .28, size * .12), letter, fill="white", font_size=int(size * .7))
    return sheet


def restore_small(scene, painted):
    """``(the repainted scene with every SMALL thing the repainting lost put back, how many were)``.

    The image model cannot hold on to a thing a few pixels across. The three drops of water at the plant's roots and the
    bubbles of oxygen beside its leaf were gone from every repainting of the photosynthesis poster, at every strength
    tried: the judge listed them on 2026-10-10, after a person had called two of those repaintings good. A small thing
    is found in the ORIGINAL as a patch that stands out from what surrounds it; where the repainting shows nothing
    standing out at that place, the original's own pixels are put back there, as an arrow's are. What the repainting
    kept (the Sun's rays, a pebble) is left as it painted it.
    """
    import numpy as np  # noqa: PLC0415
    from PIL import Image, ImageFilter  # noqa: PLC0415
    from scipy import ndimage  # noqa: PLC0415
    first, second = _on_white(scene), _on_white(painted).resize(scene.size)
    a, b = np.asarray(first).astype(np.int16), np.asarray(second).astype(np.int16)
    height, width = a.shape[:2]

    def stands_out(image):
        """How far each pixel is from what surrounds it (its neighbourhood's median, taken at a quarter of the size)."""
        small = Image.fromarray(image.astype(np.uint8)).resize((max(1, width // 4), max(1, height // 4)), Image.BILINEAR)
        ground = np.asarray(small.filter(ImageFilter.MedianFilter(9)).resize((width, height), Image.BILINEAR)).astype(np.int16)
        return np.abs(image - ground).sum(axis=2)

    in_a, in_b = stands_out(a), stands_out(b)
    patches, _ = ndimage.label(in_a > 70)
    lost, count = np.zeros((height, width), bool), 0
    for n, box in enumerate(ndimage.find_objects(patches), 1):
        if box is None:
            continue
        patch = patches[box] == n
        area, tall, wide = int(patch.sum()), box[0].stop - box[0].start, box[1].stop - box[1].start
        if area < 12 or area > 0.0012 * width * height or max(tall, wide) > 0.05 * width:
            continue                                     # a speck, or a thing large enough for the model to keep
        if in_b[box][patch].mean() < 0.45 * in_a[box][patch].mean():
            lost[box] |= patch
            count += 1
    if not count:
        return second, 0
    mask = Image.fromarray((ndimage.binary_dilation(lost, iterations=2) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    out = second.copy()
    out.paste(first, mask=mask)
    return out, count


def kind_of(scene, look, ask: str = "") -> dict:
    """What a look at the scene says it is: ``{"kind", "things", "why"}`` (kind "" when nobody answered)."""
    raw = look(f"The drawing was asked for as: {ask[:200]}" if ask else "Look at the drawing.", KIND, _jpeg(_on_white(scene), 1100)) or {}
    kind = str(raw.get("kind") or "").strip().lower()
    things = []
    for item in raw.get("things") if isinstance(raw.get("things"), list) else []:
        name = str(item.get("thing") if isinstance(item, dict) else item or "").strip()
        if name:
            things.append({"thing": name[:40], "where": str(item.get("where") or "")[:40] if isinstance(item, dict) else ""})
    return {"kind": kind if kind in ("scene", "inside", "figure") else "", "things": things[:14], "why": str(raw.get("why") or "")[:200]}


def changes(before, after, look, things: list[dict]) -> list[dict] | None:
    """What is not the same in the repainting, thing by thing, and what is new in it; None when nobody answered.

    The judge is handed the list of what the original holds and answers for each thing. Asked only "what changed?" it
    named three things as moved in a repainting where nothing had (and, on another, missed roots that had come apart).
    A thing of the list it does not answer for counts as not the same: silence is not a pass.
    """
    listed = "\n".join(f"{n}. {t['thing']}" + (f" ({t['where']})" if t.get("where") else "") for n, t in enumerate(things, 1))
    raw = look(f"A is the original drawing, B is the repainted one.\nTHINGS IN A:\n{listed}", SAME, _jpeg(side_by_side(before, after)))
    if not isinstance(raw, dict) or not isinstance(raw.get("checks"), list):
        return None
    found, answered = [], set()
    for item in raw["checks"]:
        try:
            n = int(item.get("n"))
        except (AttributeError, TypeError, ValueError):
            continue
        if not 1 <= n <= len(things) or n in answered:
            continue
        answered.add(n)
        how = str(item.get("in_b") or "").strip().lower()
        if how != "same":
            found.append({"thing": things[n - 1]["thing"], "how": next((c for c in _NOT_SAME if c in how), how[:20] or "not answered"),
                          "seen": str(item.get("seen") or "")[:120]})
    found += [{"thing": t["thing"], "how": "not answered", "seen": ""} for n, t in enumerate(things, 1) if n not in answered]
    for new in raw.get("new_in_b") if isinstance(raw.get("new_in_b"), list) else []:
        if str(new).strip():
            found.append({"thing": str(new)[:60], "how": "added", "seen": ""})
    return found


def _source_of(manifest: dict, folder: Path) -> str:
    """What a repainting belongs to: the scene's own bytes and where its arrows lie."""
    digest = hashlib.sha256((folder / str(manifest["base"])).read_bytes())
    digest.update(json.dumps([(p.get("id"), p.get("box")) for p in manifest.get("parts") or []]).encode())
    return digest.hexdigest()[:16]


def kept(folder: Path, manifest: dict) -> tuple[bool, str | None]:
    """(decided before?, the repainted manifest's path or None) for a drawing, from what was kept beside it."""
    styled = folder / "styled"
    try:
        source = _source_of(manifest, folder)
        done = json.loads((styled / "manifest.json").read_text(encoding="utf-8"))
        if (done.get("styled") or {}).get("of") == source and (done.get("styled") or {}).get("version") == VERSION \
                and (styled / str(done["base"])).is_file():
            return True, str(styled / "manifest.json")
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        refused = json.loads((styled / "refused.json").read_text(encoding="utf-8"))
        if refused.get("of") == _source_of(manifest, folder) and refused.get("version") == VERSION:
            return True, None
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return False, None


def _refuse(folder: Path, manifest: dict, why: str, detail=None) -> None:
    styled = folder / "styled"
    styled.mkdir(exist_ok=True)
    (styled / "refused.json").write_text(json.dumps({"of": _source_of(manifest, folder), "version": VERSION, "why": why, "detail": detail,
                                                     "when": time.strftime("%Y-%m-%d %H:%M")}, indent=1, ensure_ascii=False), encoding="utf-8")


def _write(folder: Path, manifest: dict, scene, record: dict, name: str = "styled") -> str:
    """The repainted drawing as a folder of its own beside the original: same manifest, the scene and what shows it new.

    ``name``: the folder and the manifest key the record is kept under ("styled" for a repainting by the image model,
    "paper" for the filter of ``harness/paperlook.py``, which changes the scene in the same place and nothing else).
    """
    from PIL import Image, ImageChops, ImageFilter  # noqa: PLC0415
    styled = folder / name
    styled.mkdir(exist_ok=True)
    (styled / "refused.json").unlink(missing_ok=True)
    for file in folder.iterdir():                          # every layer, close-up and panel the manifest may name
        if file.is_file() and (file.suffix.lower() == ".png" or file.name == "holds.json"):   # … and what the drawing was read to hold
            shutil.copy2(file, styled / file.name)
    scene.convert("RGBA").save(styled / str(manifest["base"]))
    art = with_arrows(scene, manifest, folder)
    art.save(styled / str(manifest["art"]))
    whole_name = str(manifest.get("whole") or "")
    if whole_name and (folder / whole_name).is_file():
        # The drawing shown whole: the repainted art, and over it whatever the service's own drawing has that its art
        # has not (the boxes of words, the title), taken pixel for pixel from the original.
        whole = Image.open(folder / whole_name).convert("RGB")
        ax0, ay0, ax1, ay1 = manifest.get("art_box") or [0, 0, whole.width, whole.height]
        old_art = _on_white(Image.open(folder / str(manifest["art"])))
        canvas = Image.new("RGB", whole.size, "white")
        canvas.paste(old_art, (int(ax0), int(ay0)))
        words = ImageChops.difference(whole, canvas).convert("L").point(lambda v: 255 if v > 10 else 0)
        words = words.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.6))
        new = Image.new("RGB", whole.size, "white")
        new.paste(_on_white(art), (int(ax0), int(ay0)))
        new.paste(whole, mask=words)
        new.convert("RGBA").save(styled / whole_name)
    out = {**manifest, "folder": str(styled.resolve()), name: record}
    (styled / "manifest.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return str(styled / "manifest.json")


def styled(manifest_path, ask: str = "", look=None, url: str | None = None, log=print) -> str | None:
    """The repainted drawing's manifest for a drawing in the library, or None when it is to stay as drawn.

    ``look`` is the vision judge (``vision_review.default_judge``); ``url`` an image server that is already up (``server``).
    Either missing and the drawing has not been decided before: None, and nothing is kept, so it is asked again when
    they are there.
    """
    try:
        manifest_path = Path(str(manifest_path))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        folder = Path(manifest.get("folder") or manifest_path.parent)
        if manifest.get("styled") or folder.name == "styled":
            return str(manifest_path)                    # already a repainted drawing
        if manifest.get("paper"):
            return None                                  # already given the filter's look (harness/paperlook.py): left as it is
        if not manifest.get("base") or not (folder / str(manifest["base"])).is_file():
            return None                                  # no scene layer: nothing here can be repainted safely
        decided, path = kept(folder, manifest)
        if decided:
            return path
        if look is None or url is None:
            return None
        from PIL import Image  # noqa: PLC0415
        scene = Image.open(folder / str(manifest["base"])).convert("RGBA")
        what = kind_of(scene, look, ask)
        if what["kind"] != "scene":
            if what["kind"]:                             # an answer, and it says no: kept. No answer: asked again next time
                _refuse(folder, manifest, f"not a scene of things and places ({what['kind']}: {what['why'][:120]})", what)
                log(f"[repaint] the drawing stays as drawn: its picture is {what['kind']}, not a scene of things and places")
            return None
        if not what["things"]:
            return None                                  # nothing to hold the repainting to: asked again another time
        before = with_arrows(scene, manifest, folder)
        tried = []
        for n, (strength, seed) in enumerate(TRIES):
            began = time.time()
            painted, put_back = restore_small(scene, paint(url, _on_white(scene), STYLE, strength, seed=seed))
            seconds = round(time.time() - began, 1)
            after = with_arrows(painted, manifest, folder)
            found = changes(before, after, look, what["things"])
            tried.append({"strength": strength, "seed": seed, "seconds": seconds, "small_things_put_back": put_back, "changed": found})
            try:                                         # what the judge saw, for a person: kept whatever is decided
                (folder / "styled").mkdir(exist_ok=True)
                side_by_side(before, after).save(folder / "styled" / f"compared_{n + 1}.jpg", quality=84)
            except OSError:
                pass
            if found is None:
                log("[repaint] nobody could compare the repainted drawing with the original: it stays as drawn")
                return None                              # not kept: the judge may answer another time
            if not found:
                record = {"of": _source_of(manifest, folder), "version": VERSION, "strength": strength, "seed": seed,
                          "seconds": seconds, "small_things_put_back": put_back, "things": what["things"],
                          "when": time.strftime("%Y-%m-%d %H:%M"), "tries": tried}
                log(f"[repaint] the scene was repainted on this machine in {seconds:.0f} s (strength {strength}); "
                    f"its {len(manifest.get('parts') or [])} arrow layers and its labels are the drawing's own")
                return _write(folder, manifest, painted, record)
            log(f"[repaint] try {n + 1} (strength {strength}): not the same drawing ("
                + "; ".join(f"{c['thing']}: {c['how']}" for c in found[:4]) + ")"
                + ("; trying again" if n + 1 < len(TRIES) else "; the drawing stays as drawn"))
        _refuse(folder, manifest, "the repainted scene was not the same scene", tried)
        return None
    except Exception as exc:  # noqa: BLE001 - a better look is an improvement, never a requirement
        log(f"[repaint] left as drawn ({type(exc).__name__}: {str(exc)[:140]})")
        return None


def candidates(lesson: dict) -> dict[str, str]:
    """``{manifest path: what it was asked for as}`` for every prepared drawing a lesson builds up part by part."""
    found: dict[str, str] = {}
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else {}
            if figure.get("kind") == "diagram" and figure.get("manifest"):
                found.setdefault(str(figure["manifest"]), str(figure.get("ask") or ""))
    return found


def restyle_lesson(lesson: dict, look=None, log=print) -> dict:
    """Repaint the scene of each poster a lesson shows and point its beats at the repainted drawing.

    Returns ``{"asked", "repainted", "kept_as_drawn"}``. The image server is started only when a drawing is a
    candidate that has not been decided before, and stopped before this returns.
    """
    summary = {"asked": 0, "repainted": 0, "kept_as_drawn": 0}
    if not enabled():
        return summary
    swap: dict[str, str] = {}
    undecided = []
    for path, ask in candidates(lesson).items():
        try:
            manifest = json.loads(Path(path).read_text(encoding="utf-8"))
            folder = Path(manifest.get("folder") or Path(path).parent)
        except (OSError, ValueError):
            continue
        if manifest.get("styled") or not manifest.get("base"):
            continue
        summary["asked"] += 1
        decided, done = kept(folder, manifest)
        if decided:
            if done:
                swap[path] = done
                log("[repaint] this drawing was repainted on an earlier run: that one is used")
            continue
        undecided.append((path, ask))
    if undecided:
        if look is None:
            from . import vision_review  # noqa: PLC0415
            look = vision_review.default_judge(temperature=0.0)
        if look is None:
            log("[repaint] no vision model to check a repainted drawing with: the drawing stays as drawn")
        else:
            with server(log=log) as url:
                for path, ask in undecided if url else []:
                    done = styled(path, ask=ask, look=look, url=url, log=log)
                    if done:
                        swap[path] = done
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else {}
            if figure.get("kind") == "diagram" and str(figure.get("manifest")) in swap:
                figure["manifest"] = swap[str(figure["manifest"])]
    summary["repainted"] = len(swap)
    summary["kept_as_drawn"] = summary["asked"] - len(swap)
    return summary
