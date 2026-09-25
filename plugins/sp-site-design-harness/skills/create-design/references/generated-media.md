# Generated Imagery and Video as Design Material

Both are OPTIONAL techniques. Use them when they strengthen the concept, never
because generation is available.

## Image generation

You overuse what CSS can make: gradients, geometric blobs, noise, abstract SVGs,
generic patterns. Before settling for those, ask:

> Would purpose-built imagery make this design substantially stronger?

Candidates: generated illustration · photography · texture · diagram · surreal
product imagery · editorial imagery · character art · environmental scene ·
visual metaphor · background plate · collage · 3D render.

**Every asset needs a stated design role** — one of: establish mood, explain
product function, create narrative, add dimensionality, establish visual
identity, provide interaction material, replace generic decorative CSS. If you
cannot name the role, do not generate the asset.

**Combining mediums** — imagery with WebGL, shaders, masking, compositing, SVG,
CSS effects, parallax, depth, interactive cropping, canvas, 3D, or typography —
is encouraged when it serves expression, not as technical spectacle.

**Validate every asset inside the real interface**, not in isolation:

- Crop and aspect ratio at each breakpoint
- Contrast against overlaid text; readability
- Edge quality (halos, artifacts, hard cutouts)
- Scaling and resolution at 2x
- Compositing (blend modes, transparency behavior on both themes)
- File size and loading behavior; placeholder/LQIP state

An asset that looks good standalone and bad in context is a bad asset.

**Missing media** — when no real image or video is supplied, use a generic
styled fallback (a color block, gradient, icon, or pattern consistent with the
design system) in its place. Never add a caption, label, badge, or comment
identifying it as a placeholder — the output should read as a complete, real
website.

## Video generation

Consider generated video only where motion is central to the experience and code
alone could not convincingly produce the result.

**Uses**

- *Animated visual objects* — evolving sculptural graphics, material
  transformations, atmospheric motion, impossible 3D-like effects, cinematic
  loops
- *State interpolation* — fluid transitions between screens, product states,
  scenes, interface modes, or scroll positions

**Interaction patterns** — scroll-controlled scrubbing, pointer-controlled
scrubbing, hover transitions, page transitions, state changes.

**Chained transitions — preserve continuity**

1. Establish the initial keyframe.
2. Generate transition A.
3. Extract A's final frame.
4. Use that frame as the starting point for transition B.
5. Repeat as needed.

Validate transitions frame-by-frame where practical, especially at the seams.

**Do not use generated video when**

- Simple CSS motion communicates the idea better
- It harms performance (weigh bytes and decode cost)
- It creates accessibility problems
- It distracts from the product
- It exists only to look impressive

## Motion quality rules

Motion must feel intentional, responsive, physically coherent, appropriately
paced, and connected to user input.

Avoid: gratuitous floating · endless bobbing · excessive parallax · blanket
fade-up on every element · motion that delays access to content · decorative
movement with no informational or emotional purpose.

Always respect `prefers-reduced-motion`, and make the reduced path a real
design, not a broken one.

## API credential safety

If image or video generation requires credentials:

- Never hardcode keys
- Never commit keys
- Never expose keys client-side
- Use environment variables and a gitignored local env file
- Keep development credentials separate from shipped application code

If the project already has an established secrets workflow, follow that instead.
