# Portada — Product Spec

> **Status:** draft · 2026-08-28 · v2 — deterministic assembly + AI finishing pass
> Supersedes the v1 draft derived from the Claude Design prototype
> `Portada - App de miniaturas.dc.html` (project `7c253d52-196e-4126-b128-af24e7b27bf0`).
> The prototype's screens still hold. Its generation model does not: v1 assumed the AI composed the
> thumbnail. It doesn't. The app composes; the AI only finishes.

## 1. What Portada is

A phone app that produces the cover thumbnail for a podcast episode. The user keeps a reusable
library of photos tagged by the role each plays in a composition. Each role has a fixed place on the
canvas. The app pastes the selected photos into those places deterministically, draws the title, and
then runs the finished composite through an image model **once, as a filter**, to give it a polished,
unified look. Output: a 1280×720 image.

The name is the Spanish word for the cover of a publication.

## 2. Who it's for

Podcast creators who publish weekly and make their own thumbnails. The prototype is written for one
concrete show — *El Ring Podcast* — in Spanish. Single operator, working on a phone, probably the
same person who hosts.

## 3. The problem

Two problems, and the second is the one usually ignored.

**Time.** A weekly show needs a new thumbnail every week. Designing it yourself costs 30+ minutes,
every week, forever. Hiring is too slow and too expensive at weekly cadence.

**Consistency.** A channel's thumbnails are a set, not a series of one-offs. When each week's cover
is composed from scratch — by hand or by a model — the grid on the channel page looks like six
different shows. The identity lives in the *repetition*: the host always in the same place, the title
always in the same corner, the logo always the same size. That's what a viewer scrolling a feed
recognises before they read a word.

Asking an image model for "a podcast thumbnail" fails both: it's slow to steer, and it produces a
different composition every time.

## 4. The core bet

**Layout is a decision made once, not a decision made weekly. The AI is a finish, not a composer.**

Portada's wager is that almost everything that makes a thumbnail good is already fixed for a given
show — where the host goes, how big the guest is, where the title sits, what the logo does — and that
those things should be *code*, not a prompt. What genuinely changes each week is only the photos and
the title.

So the app composites the image itself, deterministically: same slots, same sizes, same type, same
z-order, every single week. Then a single AI pass over the finished composite unifies lighting,
blends the cutout edges, and grades the colour — the things that are hard to do with compositing
alone and that separate a collage from a cover.

Three consequences, and they are the point:

1. **The result is consistent by construction.** Two episodes differ only where they should.
2. **The AI can't ruin the composition,** because it never chooses it. It receives a finished image
   and is asked only to polish it.
3. **The AI is optional.** The deterministic assembly is already a publishable thumbnail. If the pass
   fails, times out, or costs too much, the app ships the assembly. Nothing blocks on the model.

This is the inverse of the v1 bet, which asked a model to compose from role-tagged photos. That bet
was unproven and load-bearing. This one is neither: the risky part is now the cheap, verifiable part.

The finishing pass is the first application of a rule that governs everything the AI will ever be
allowed to do here:

> **The AI decides; a script executes.** Its output is an *input to the renderer*, never the render
> itself — a choice from an enumerated set, a number inside a clamped range, an id from the library.
> Anything it returns that the schema doesn't recognise is discarded and the deterministic default
> stands.

That rule keeps the model inside what it is genuinely good at — judgement about tone, emphasis and
fit — and outside what it is bad at: geometry, text, identity, and staying the same as last week.
§12 is the roadmap for widening that judgement without giving up any of it.

## 5. Domain model

```
Template ─── Slot[] (role → position, size, anchor, z, treatment)   ← fixed per show
                │
Library ──┬─ Photo (role, label, description, cutout?, included?)
          │
Episode ──┼─ Brief (selected photos + title + filter strength)
          ├─ Assembly (deterministic 1280×720 composite — always exists)
          └─ Attempt[] (each an AI-finished render of the assembly)
```

- The **template** is the show's visual line. One per show, authored once, versioned. It is the
  durable design decision.
- The **library** persists across episodes and is the app's durable content. The home screen surfaces
  its size as a stat row (conductor · invitados · fondo/obj · logos).
- An **episode** is one thumbnail job.
- The **assembly** is deterministic and reproducible: the same photos + title + template always
  produce the same pixels. It is computed locally, in well under a second, and shown live while the
  user picks.
- **Attempts** are AI passes over that assembly. They remain first-class and numbered
  (`INTENTO 3/3`, chips `v1 v2 v3 · nuevo`) — but they now vary only in finish, never in layout.

## 6. The five roles, and where each lands

Each role is a slot in the template. Uploading a photo tagged `conductor` is telling the app *which
picture goes in the conductor slot* — nothing more is inferred.

| Role        | Min | Slot                                     | z | Treatment                                             |
| ----------- | --- | ---------------------------------------- | - | ----------------------------------------------------- |
| `fondo`     | 0   | Full bleed 1280×720, cover-fit           | 0 | Desaturate, darken, vignette — it must sit *behind*    |
| `objeto`    | 0   | Centre band, max 2, ≤220px tall          | 1 | Cutout, drop shadow                                    |
| `invitado`  | 1   | Bottom, centred at x≈800, ~600px tall    | 2 | Cutout, bleeds off the bottom edge                     |
| `conductor` | 1   | Bottom right, centred at x≈1040, ~680px  | 3 | Cutout, bleeds off the bottom edge, in front           |
| `logo`      | 1   | Top-left, ≤200×90, fixed margin          | 5 | **Pasted as-is. Never scaled non-uniformly, never re-rendered** |
| *(title)*   | 1   | Left block, x 48→620, bottom-aligned     | 4 | Uppercase, auto-fit 64–104px, accent rule beneath      |

Reading the layout left to right: title block on the left, guest in the middle, host largest and
frontmost on the right, logo top-left, background behind everything. The host and guest overlap by
design — that overlap is part of the show's look, not an accident to be avoided.

Notes:

- **Cutouts.** `conductor`, `invitado` and `objeto` are composited as cutouts (background removed).
  This runs once per photo, at upload time, and the result is cached in the library — so the weekly
  path never waits on it. See §12.2.
- **No background is a real answer.** If no `fondo` is selected, the slot is filled with a gradient
  from the show's palette — deterministic, not generated. Consistency beats novelty here; a
  generated background would be the one element that changes every week for no reason. The palette
  authors **two** of them, light and dark, and the episode picks one: a closed list of names inside
  the template, not a knob that lets the layout drift (§11.1, §11.3).
- **The numbers above live in one template file.** Editing them changes every future thumbnail at
  once. That file *is* the show's visual identity, and it's the only place layout is decided.
- **An episode may nudge a figure.** `conductor`, `invitado` and `objeto` can be offset in x/y and
  reordered among themselves, in steps and within limits the template sets (§11.1). A nudge can't
  resize anything, can't leave the limits, and can't slip under the background or over the title.

## 7. The pipeline

```
 selected photos ──┐
 title ────────────┼──▶  ① ASSEMBLY  ──▶ ② AI FINISH ──▶ ③ RE-APPLY ──▶ 1280×720 PNG
 template ─────────┘      (local,          (one call,      (logo + title,
                           <1s, exact)      ~10–30s)        pixel-exact)
```

**① Assembly — deterministic.** Slots filled in z-order, title typeset, logo placed. Runs on-device.
Reproducible. Shown live in the flow as the user selects. This alone is a shippable thumbnail.

**② AI finish — one pass, structure-preserving.** The flattened assembly *without the logo and title
layers* is sent to the image model as its conditioning image.

- *May:* unify lighting across subjects that were shot in different rooms, blend hard cutout edges,
  add rim light and contact shadow, grade colour, add grain and depth.
- *Must not:* move, resize, duplicate or replace any subject; alter faces or identity; add people;
  render text; change the aspect ratio or crop.
- Strength is a single three-stop control — *Suave · Medio · Fuerte*, default **Medio**. It is the
  only generation knob in the product.

**③ Re-apply — deterministic.** Logo and title are composited back on top of the AI output at full
fidelity. This is why the logo rule holds absolutely and why the title is always crisp: neither ever
passes through the model. It also makes fixing a typo free — re-typeset and re-composite, no
regeneration, no cost.

**Failure is not a dead end.** If ② errors, times out, or the user cancels, the episode still has its
assembly, and the result screen offers it for download. The AI is upside, never a dependency.

## 8. The weekly workflow

Setup happens once. The recurring work is steps 3–8.

1. Upload photos of yourself with a range of expressions → tag `conductor`. *(cutouts computed now)*
2. Upload the show logo → tag `logo`.
3. *(Per episode)* Upload the guest's photos → tag `invitado`.
4. Pick which photos this episode uses — usually one tap per role. **The preview updates on each tap.**
5. Optionally add a background or props, or skip both.
6. Write the episode title. It is rendered on the thumbnail, uppercase, ~70 characters.
7. Optionally set the filter strength.
8. Generate. Compare with/without the finish. Download.

The difference from v1: by step 6 the user has already seen essentially the final image. Generation
is no longer a reveal — it's a polish on something already approved.

## 9. Screens

| Screen              | Purpose                                                                                       |
| ------------------- | --------------------------------------------------------------------------------------------- |
| **Inicio**          | Show name, *Nueva miniatura* entry point, three recent episodes, library stats                 |
| **Flujo** (6 steps) | Role pickers ×5, then title, with a **live thumbnail preview pinned above the step**           |
| **Generando**       | The assembly is already on screen; the pass runs over it. Status: unificando luz → fundiendo bordes → color final → aplicando logo y título |
| **Resultado**       | The thumbnail, an **A/B toggle *Sin filtro · Con filtro***, Descargar / Regenerar / Editar, the attempt strip, a recap of what was used |
| **Historial**       | Grid of past episodes with dates and attempt counts                                            |
| **Photo sheet**     | Per-photo detail: description, re-run cutout, or delete from the library                       |

The *Generando* screen no longer hides a black box: the user is watching their own composite get
finished, which is what makes the wait tolerable — and if it fails, they lose nothing they were
already looking at.

## 10. Output

- **1280×720 PNG**, 16:9 — YouTube's thumbnail spec. Still an inference about the primary
  distribution target, not something the design states. See §13.6.
- Both the assembly and the finished render are retained per attempt, and both are downloadable.

## 11. Product rules

1. **Layout belongs to the template; an episode may nudge, not rearrange.** The template is
   authored once per show and is the product's guarantee of consistency. What an episode can change
   is short, named in the template, and bounded by it: which of the two palette gradients answers
   "no background", and — for the three figures — an offset in x/y plus their order among
   themselves. Sizes, slots, typography, the title block and everything else stay in the file.
   "Fixed" was too fixed: with real photos the guest sometimes ends up hidden, and fixing that one
   thumbnail meant editing the template and changing the whole channel.
2. **The app composes. The AI finishes.** The model never decides placement, never sees the logo or
   the title, and never runs more than once per attempt.
3. **The AI decides; a script executes.** Wherever a model is given a choice — now, or in any module
   of §12 — it returns a validated parameter, never output that is used directly. Every such choice
   has a deterministic default that stands when the model is off, slow, or wrong.
4. **The assembly is always valid output.** The AI pass may fail; the episode may not.
5. **The logo is never reinterpreted, never non-uniformly scaled, never model-touched.**
6. **The title is typeset, not generated,** and editing it costs nothing.
7. **The library is the durable asset; the episode is disposable.** Tag a photo once, reuse it for a
   year. Cutouts are computed at upload and cached.
8. **Absence is a valid input.** No background means the show's palette, not an error and not a
   surprise.
9. **Minimum friction per episode.** Six steps, two skippable, most reduced to one tap.
10. **Preview before spend.** The user sees the composition before any paid call is made.
11. **Nothing is destructive without review.** Deleting a photo is two steps behind the sheet.

## 12. Modular AI — the extension path

Not in v1, but the reason v1 is built this way. Every layout value that §6 hardcodes is a decision
somebody has to make. Today the template makes them, once. Each one could instead be made *per
episode* by a model — provided it comes back as a parameter, not as pixels.

### 12.1 The contract

Every module obeys the same shape, without exception:

```
inputs (title, photo metadata, palette, …)
        │
        ▼
   [ AI module ]  ──▶  small typed JSON  ──▶  [ schema validation ]  ──▶  renderer
                                                      │
                                                 invalid / absent
                                                      │
                                                      ▼
                                              deterministic default
```

Four rules make this safe:

1. **Enumerated or clamped, never free.** A module chooses *variant B of three*, or a scale *between
   0.9 and 1.15*, or *photo id 7*. It never returns coordinates it invented, and never returns prose
   that gets pasted anywhere.
2. **Every module has a deterministic default** — the value the template already uses. A module that
   is off, fails, times out or returns garbage is indistinguishable from one that was never built.
3. **Bounded even at its extremes.** The allowed range is authored so that *every* value inside it is
   still on the show's line. A module cannot make an off-brand thumbnail, only a differently-good one.
4. **Independently testable.** Because each module is one knob with a known default, it can be A/B'd
   on its own: same episode, module on vs. off, which thumbnail does the creator pick. Modules ship
   one at a time, each having earned it.

### 12.2 Candidate modules

Ordered roughly by strength of fit and smallness of blast radius — which is also the order to build
them.

| Module | Input | Output | Why the AI is good at it |
| ------ | ----- | ------ | ------------------------ |
| **Title emphasis** | The title string | Per-word weight: `normal · grande · acento` | Pure language. Knowing that *"LA VERDAD sobre el CASO"* stresses two words is a reading-comprehension task, and the renderer already knows how to set three sizes |
| **Line breaking** | Title + block width | Break points | Where a phrase splits without breaking sense — again language, not layout |
| **Photo selection** | Title + the library descriptions already in §5 | A photo id per role | This is what the v1 descriptions (*"gesto de sorpresa"*) were always for: match the host's expression to the episode's tone |
| **Accent colour** | Background photo + title tone | One entry from the show's authored palette | Judgement over a fixed set — it cannot invent a colour that clashes because it cannot invent a colour |
| **Focal point** | Background photo | An (x, y) inside the image for the cover-fit crop | "Where is the subject" is a vision task; the crop maths stays in the renderer |
| **Composition variant** | Everything | One of N *authored* layouts (host left / host right / two-shot) | The riskiest for consistency, so the set stays small and every member is designed by hand. The AI picks; it never positions |
| **Filter strength** | The assembly | `suave · medio · fuerte` | Judging how much unification an image needs |
| **Prop suggestion** | Title + library | An `objeto` id, or none | Same shape as photo selection |

Note what is absent and stays absent: nothing in this table lets a model emit a coordinate, a font
size in pixels, a hex colour, a piece of copy, or a layer order. Those remain the renderer's.

### 12.3 The tension to watch

Every module trades consistency for fit. That is the trade the product exists to control, not to
maximise. A module is worth shipping only when the fit it buys is visible *and* the variation it
introduces is invisible in the channel grid (§15.3). If enabling a module makes six consecutive
thumbnails read as six shows, the module is wrong however good any single one of them looks.

## 13. Not in v1

- Every module in §12. v1 hardcodes all of them at their defaults.
- Multiple templates, or user-editable layout. One template per show, authored in code.
- Multiple shows or multiple users
- Manual editing of the generated image (crop, reposition, restyle)
- Direct publishing to YouTube or anywhere else
- AI-generated backgrounds
- Video, animated thumbnails, or other aspect ratios
- Analytics on thumbnail performance

## 14. Open questions

Three from the v1 spec are now closed: the title is composited (§7③), the composition risk is gone
(§4), and regeneration is no longer the only path to a result (§11.3). What remains:

1. **How much can the finish change before it breaks likeness?** The whole product now rests on a
   pass that improves an image without altering the faces in it. Testable today against the
   deterministic assembly, with no UI — and the *Suave/Medio/Fuerte* stops should be calibrated from
   that test, not guessed.
2. **Which cutout method?** Segmentation quality on hair and edges is what separates the assembly
   from looking cut-and-pasted. On-device vs. API, and what the user does when a cutout comes out
   wrong (manual touch-up? re-run? reject the photo?).
3. **Which model for the finish?** It needs image-to-image with strong structure preservation.
   Gemini 2.5 Flash Image remains a candidate; so does any model exposing a low-strength img2img or
   structure-conditioned pass. Undecided, and now a much lower-stakes choice than in v1.
4. **Where does the assembly run?** On-device compositing is what makes the live preview possible.
   Confirm the canvas/graphics path on the target platform, and whether the same code produces the
   final full-resolution render.
5. **Backend, or entirely on-device?** Where photos and cutouts live, whether the library syncs, what
   happens offline. Note that offline now yields a complete thumbnail, minus the finish.
6. **Distribution targets.** Is 1280×720 the only output, or are square and vertical variants needed
   for Spotify, Instagram and shorts? Cheap now: extra ratios are extra templates, not extra prompts.
7. **Privacy.** The library is by definition a collection of identifiable faces, including guests who
   are not users. Storage, retention and consent are unaddressed.
8. **Cost per attempt, and who absorbs it.** One call per attempt, and the free assembly path means
   the floor is zero.
9. **Native iOS or web?** The prototype is drawn in an iPhone frame but implemented as web DOM.
10. **Accounts.** Implied by a persistent library and history, absent from the design.

## 15. How we'll know it works

The product succeeds if a creator uses it every week without reverting to their old method. In the
order these should be tested:

1. **The assembly alone is publishable.** Before any model work: does the deterministic composite,
   with real photos and a real title, look like something the creator would post? If yes, the product
   already has a floor — and the rest is upside.
2. **The finish improves it without breaking it.** Side-by-side, the creator prefers the filtered
   version, and the faces are still theirs.
3. **Consistency across episodes.** Six consecutive thumbnails laid out as a channel grid read as one
   show. This is the metric v1 had no way to state.
4. **Time per episode** — under two minutes from *Nueva miniatura* to download, once the library is
   populated.
5. **Attempts to acceptance** — should now trend towards one, since layout no longer varies. Repeated
   regeneration is a signal the finish is miscalibrated, not that the user is picky.
6. **Library reuse** — conductor and logo uploaded once, reused across many episodes.
7. **Retention** — used for four consecutive episodes.

Once modules (§12) start shipping, each gets its own test and no other: same episode, module on vs.
off, which thumbnail does the creator pick — measured against §15.3, not against how clever the
module is.
