# Restyling a flat diagram without breaking its structure: a web survey (2026-10-10)

The owner, 18:20: "see image styling approaches online also". A research agent was given what had been measured that
day (plain image-to-image has a narrow window between "no visible gain" and "structure breaks": doc 11 §7) and asked
for approaches that restyle a picture while every object stays where it is, the same kind of thing, nothing added or
removed, small objects kept; with open weights, a licence a product may use, and a fit on shared GPUs.

**How to read this.** It is the agent's report, shortened. Every licence line below is quoted as the agent read it on
2026-10-10 with the page it read it on; none was read again by the session that filed this. Statements marked
[inference] are the agent's own, not a source's. Nothing here has been run on this machine.

## Verdict

Keep one whole-image diffusion pass, but hold structure with an **edge ControlNet for the Z-Image-Turbo that is already
on disk**, and back it with a **deterministic texture pass that cannot move, drop or add anything**. Instruction-edit
models rank below both for this job.

## What was verified

- **A ControlNet for Z-Image-Turbo exists and ComfyUI runs it without custom nodes.**
  `alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1` (15 control blocks plus 2 refiner blocks; "lite" files use 3).
  Control types on its card: Canny, HED, Depth, Pose, MLSD; Scribble from the 2601 files; Gray in 2602. No "lineart"
  type is named. Recommended `control_context_scale` 0.65 to 1.00. A Tile file sits in the same repo. ComfyUI core
  (`comfy_extras/nodes_model_patch.py`) has `ModelPatchLoader` and `ZImageFunControlnet` ("Apply Fun ControlNet":
  strength, optional image, inpaint_image, mask, start_percent, end_percent). Licence: "license: apache-2.0"
  (https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union-2.1/raw/main/README.md).
  Files: `Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602-8steps.safetensors` (2.02 GB),
  `…-Union-2.1-2602-8steps.safetensors` (6.71 GB), `Z-Image-Turbo-Fun-Controlnet-Tile-2.1-2601-8steps.safetensors`.
- **Z-Image-Edit is not released** (the Tongyi-MAI README lists it as "To be released").
- **Edit models do not reliably hold structure.** TexBench (March 2026) scores "Structure" on texture-only edits:
  Qwen-Image-Edit-2511 0.569, Qwen-2509 0.642, Nano Banana Pro 0.801, the specialised TexEditor 0.929; the paper says
  existing models "tend to regenerate the edited subject".
- **The closest published work is CAGE** (IIIT Delhi, April 2026): a code-rendered educational diagram goes through
  SDXL with a Canny ControlNet, with labels masked by OCR and re-rendered. That is this project's design. It publishes
  no strength or denoise values and no code. Chat2SVG (CVPR 2025) uses SDEdit with a tile ControlNet on SVG renders
  and reports that this "introduces new semantic parts such as the lion's beard".

## The four questions that were asked

1. **Is there a recipe for high denoise with the layout locked?** Yes: ControlNet with image-to-image is standard (the
   diffusers guide runs SDXL at strength 0.99 with conditioning scale 0.5; MistoLine's authors give strength 1.0,
   end_percent 0.9, denoise 0.93; for Z-Image practitioners report control strength 0.7 to 0.8). No source gives
   values for flat-illustration inputs, and none runs the Z-Image ControlNet with denoise below 1.
2. **Do edges keep small objects?** Not reliably (ControlNet++ measured standard ControlNet at lineart SSIM 0.705;
   InstanceDiffusion reports small instances detected at AP 5.5 against 45.0 for large). Z-Image's patch is 16 px:
   a 25 px water drop is two or three tokens [arithmetic]. Practitioners composite small shapes back, which is what
   `repaint.restore_small` does.
3. **Is per-layer styling more reliable?** No published tool restyles given SVG groups separately and recomposites
   them. [inference] Clipping each layer to its own silhouette guarantees place and shape, but an isolated shape
   loses its context and one pass per layer breaks the time budget; cheaper is one whole pass, then accept or reject
   per SVG shape by mask, filling rejects from the deterministic version.
4. **Are there zero-risk filters?** Yes. Bousseau et al. (2006) split watercolour rendering into an abstraction step
   and an effect step; [inference] a flat SVG is already the abstraction, so only the effects are needed: paper
   texture, pigment grain, edge darkening, edge wobble. Tools: SVG `feTurbulence` with `feDisplacementMap` (in
   browsers since 2015); `svg2roughjs` on Rough.js ("MIT license", https://github.com/fskpf/svg2roughjs); `p5.brush`
   ("MIT license", https://github.com/acamposuribe/p5.brush); G'MIC ("distributed under the CeCILL free software
   licenses", https://gmic.eu/); ImageMagick `-paint`. [inference] Kuwahara and oil-paint filters smooth, and will
   barely change art that is already flat: the look has to come from added grain, rims and wobble.

## Ranking for this project

| | approach | how structure is held | licence as read | risk of adding or removing | |
|---|---|---|---|---|---|
| 1 | Z-Image-Turbo + Fun ControlNet Union 2.1, with image-to-image | an edge / soft-edge / gray hint, which can be drawn from the SVG itself | apache-2.0 | lower than plain image-to-image, not zero | try first |
| 2 | deterministic effects pass (no model) | geometry is not regenerated | MIT tools; G'MIC CeCILL | none | build as the floor and the fallback |
| – | region protection and composite-back, with 1 | chosen pixels are not touched | core ComfyUI nodes | none for protected pixels | use with 1 |
| 3 | FLUX.2 klein 4B (instruction edit) | nothing explicit | apache-2.0 (https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/raw/main/README.md) | high | cheapest test of the edit route |
| 4 | SDXL + line ControlNet + style LoRA or IP-Adapter (CAGE's stack) | canny / lineart / tile ControlNet | openrail++, apache-2.0 | as 1 | fallback; a second stack to keep |
| 5 | Qwen-Image-Edit-2511 | nothing explicit | apache-2.0 | high (TexBench Structure 0.569) | only with a LoRA trained on before/after pairs |
| ✗ | FLUX.1 Kontext [dev], FLUX.2 klein 9B, Qwen-Image-2.1 | – | non-commercial or research-only ("This model falls under the FLUX.1 [dev] Non-Commercial License."; "flux-non-commercial-license"; "FOR NON-COMMERCIAL PURPOSES ONLY") | – | not in a product |

## What to try, in order

1. The ControlNet: confirm the node on this build (`GET /object_info/ZImageFunControlnet`), put the lite 2602 file in a
   `model_patches` folder, draw the hint straight from the SVG's outlines at output size (so no preprocessor can drop
   a small shape), sweep denoise 0.7 / 0.85 / 1.0 against control strength 0.65 / 0.8 / 1.0 on the known failures
   (the drops at the roots, the roots, the peak under its arrow) with two seeds, scored by `repaint.changes`. Keep
   the prompt to style words: listing objects multiplies them (measured here).
2. The deterministic floor, used for every small shape, for anatomy-type drawings, and for any region a check
   refuses: no structural risk, no GPU, and every picture is usable whatever the model does.
3. FLUX.2 klein 4B, only as the cheap test of whether instruction editing holds a diagram at all.

## What the agent could not verify

No source runs the Z-Image ControlNet below denoise 1 or gives values for flat inputs; whether this machine's ComfyUI
build has the node; speeds on these GPUs; how G'MIC's `brushify` behaves on flat art (untested); several pages
refused the fetch (the stable-diffusion-art.com guide, the Codrops feTurbulence article, docs.opencv.org).

## Sources the agent read (all on 2026-10-10)

Z-Image and its ControlNet: the two `alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union` model cards and file lists;
`comfyanonymous/ComfyUI` `comfy_extras/nodes_model_patch.py`; docs.comfy.org `tutorials/image/z-image/z-image-turbo`;
`Tongyi-MAI/Z-Image` README and the Turbo model's transformer and VAE configs.
Edit models: the model cards of Qwen-Image-Edit-2511, Qwen-Image-2.1 (and its LICENSE), FLUX.2 klein 4B and 9B,
FLUX.1 Kontext [dev] and the FLUX.1-dev licence text, OmniGen2, HiDream-E1.1, Step1X-Edit-v1p2, FireRed-Image-Edit-1.1,
LongCat-Image-Edit, USO; artificialanalysis.ai's open-weights editing board; arXiv 2603.18488 (TexEditor / TexBench),
2601.20175 (TeleStyle); blog.comfy.org "the complete style transfer handbook" (March 2026).
Control settings: huggingface.co/docs/diffusers/using-diffusers/controlnet; the MistoLine, xinsir union, IP-Adapter and
SD1.5 lineart cards; `lquesada/ComfyUI-Inpaint-CropAndStitch`.
Research: arXiv 2604.09691 (CAGE), 2411.16602 (Chat2SVG), 2404.07987 (ControlNet++), 2402.03290 (InstanceDiffusion),
2605.19624, 2602.19254 (RegionRoute); the NeuralRemaster project page.
Without a model: Bousseau et al. 2006 (artis.inrialpes.fr/Publications/2006/BKTS06); `fskpf/svg2roughjs`;
`acamposuribe/p5.brush`; gmic.eu; `chflame163/ComfyUI_LayerStyle`; MDN on `feTurbulence`; the AdaIN, WCT2, CAST,
StyTR-2, StyleID, ebsynth and Paint Transformer repositories.
