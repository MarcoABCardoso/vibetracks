# Composition guide — writing soundtracks that don't sound generated

Lessons distilled from legendary game scores, translated into concrete VibeTracks
moves. Read this before composing; the `/soundtrack` skill points here. The goal is
to one-shot a score that feels *intentional and coherent*, not like five variations
on a loop.

## The one rule: cohesion comes from transformation, not repetition

Undertale builds almost its entire soundtrack from a few motifs ("His Theme,"
"Megalovania," "Bonetrousle" are relatives). Zelda's Lullaby and the Final Fantasy
Prelude recur for decades. The melody is the same DNA; the **mood is changed by
transforming it**, not by writing a new tune or replaying the old one verbatim.

Define a tiny motif library in the bible (1 primary `main_theme` + 1–2 secondary,
e.g. a `danger` phrase). Then recolor it per cue with these knobs on a `motif` part:

| Technique | Spec | Musical effect | Heard in |
|-----------|------|----------------|----------|
| Transpose | `"transpose": -12` | Same tune, new register/key — darker low, brighter high | Everywhere |
| Augmentation | `"stretch": 2.0` | Half-speed → grand, mournful, "the sad version" | Undertale ballads |
| Diminution | `"stretch": 0.5` | Double-speed → frantic, comedic, urgent | Undertale battles |
| Fragment | `"slice": [0, 3]` | Quote just the hook's head as a callback | Leitmotif teases |
| Inversion | `"invert": true` | Mirror the contour — familiar yet new | Bach → Castlevania |
| Retrograde | `"retrograde": true` | Play it backwards — an eerie echo | Tension cues |

These stack (retrograde → invert → transpose → stretch). **State the full theme in
exactly one track** (usually the title); everywhere else, transform or fragment it.

## Write a melody worth transforming

A theme you can't hum won't carry a score (Kondo's Zelda/Mario themes, Mitsuda's
Chrono Trigger). When authoring a motif in the bible:

- **Narrow range, mostly stepwise**, with 1–2 expressive leaps for shape. Avoid
  wandering — a listener should be able to sing it back.
- **A clear rhythmic fingerprint.** The rhythm alone should be recognizable (think
  the dotted Final Fantasy victory rhythm). Vary note lengths; don't make everything
  quarter notes.
- **Call and response.** Build it as a question phrase + an answer phrase
  (antecedent/consequent): the first half rises or stays open, the second resolves.
  In specs, that's often two `slice`s of one motif, or two motifs that trade off.

## Energy lives in the accompaniment

Castlevania's "Bloody Tears" and Mega Man are simple melodies over **relentless
arpeggios and a moving bass**. Don't make the melody busier to add drive — make the
parts under it move:

- **Bass that moves**, not just root whole-notes: octave jumps, walking lines,
  eighth/sixteenth pulses (`[["A2",0.5],["A2",0.5],["A2",0.5],["A3",0.5], ...]`).
- **Arpeggio ostinato** (`arp`/`pluck` part) running continuous figures via `repeat`.
- **Counterpoint**: give a second voice its own line answering the lead (a `pluck`
  playing the `danger` motif under the `lead`, as `battle`/`boss` do).

Conversely, for calm cues, *thin it out* — let the melody breathe over pads.

## Let harmony do the emotional work

The progression sets the mood before a single melody note lands:

- **Tension / menace** → harmonic minor, the `dim` chord, a `E`-major dominant in A
  minor, chromatic root motion, pedal points (one bass note held under shifting
  chords). Castlevania, Metroid, boss themes.
- **Wonder / triumph** → major, `sus2`/`add9` color, plagal (F→C) and `maj7`
  cadences, modal brightness. Victory fanfares, Zelda overworld.
- **Wistful / adventurous** → minor with major-chord borrowings (Am … F … C … E),
  unexpected but smooth root motion. Chrono Trigger, Hollow Knight.

Keep the *key family* shared across the score; change *quality and cadence* per cue.

## Form: make the loop breathe

A loop that dumps everything in bar 1 fatigues fast. Build an arc:

- **intro** (once) sets palette/key with restraint.
- **A** states the idea; **B** contrasts it (new progression, register, or a
  transformed motif) — see how every demo track now has an A→B form.
- Use dynamics: drop parts out and bring them back. **Silence and space are tools**
  (Undertale's quiet beats, Hollow Knight's restraint). Don't fear an empty bar.

## How much repetition is too much? (count is the wrong question)

"State the theme, then loop it 8×" is the fastest way a score turns generic — but
the raw repeat count is *not* what fatigues the ear. Three things decide it:

- **Unit length** — the longer the repeating chunk, the fewer verbatim repeats it
  tolerates (roughly inversely). A 1-bar riff can run many times; an 8-beat melodic
  phrase wants variation after one or two statements. Eight repeats of a 2-bar hook
  isn't "too many repeats" — it's *too short a period looped too tightly*.
- **Salience** — the ear tracks the loudest / highest / most-tuneful line for change
  and treats everything else as a bed. So tolerance is *layered*, not global.
- **Variance around it** — repetition with *any* evolving dimension (orchestration,
  register, dynamics, a countermelody, the harmony underneath) sustains far longer
  than literal repetition.

The crux, in VibeTracks terms: a `motif` on the `lead` and an arpeggio on the `arp`
can both `repeat` 8× in the *same bars* — the melody grates, the arp is invisible.
**Same count, opposite verdict.** Put the high repeat-counts on the parts that can
absorb them:

| Part / role | Verbatim repeats before it fatigues | Move |
|-------------|-------------------------------------|------|
| Foreground melody (`lead` motif, 2+ bars) | ~1–2 (≈4 with variation) | State once per section, then fragment/transform or hand off |
| Short hook / riff (1–2 bars) | 2–4 | Fine as an identity; still recontextualize eventually |
| `arp`/`pluck` ostinato, harp arpeggio | 4–16+ (effectively unlimited) | Let *this* carry the big `repeat: N` load |
| `drums` groove | whole section | Vary with a fill every 4–8 bars |
| `bass` | wants motion | Walk it / octave-jump; a static root pedals *tension*, not groove |

**Why ~3–4 is the turning point:** after two or three hearings the ear has learned
the pattern and stops predicting it; with no new information, attention drifts. So
state → restate → *depart* (the phrasing "rule of three": AAB, antecedent/consequent).

**The one escape hatch:** heavy verbatim repetition survives if *one* dimension
climbs monotonically. Ravel's *Boléro* repeats two themes ~9× each with zero melodic
change, carried entirely by an orchestration crescendo; Pachelbel's 2-bar ground
bass repeats 28× under ever-varying upper voices. If you must repeat a lot (a long
loop, a build), make sure something — density, dynamics, a `filter` opening, parts
layering in — is on a one-way climb.

The rule to internalise: **don't count repeats — ask "what has the listener learned,
and am I still giving them something?"** Push the theme to the foreground *once* per
section (`repeat: 1`–`2`), let the ostinato and bass do the churning, and give each
block an A→B frame so the learned material always returns recontextualised.

## Match the music to what the player is doing

| Cue | Tempo | Density | Harmony | Theme treatment |
|-----|-------|---------|---------|-----------------|
| Title / menu | mid | full, anthemic | home key, clear | full statement (the anchor) |
| Exploration / town | slow–mid | sparse, textural | warm, consonant | fragment or *mood over melody* (Metroid/DKC) |
| Battle | fast | busy, driving | minor, propulsive | own riff + motif as counterpoint |
| Boss | fastest | dense, dissonant | harmonic minor, `dim` | fragment/inversion, menacing |
| Victory / fanfare | brisk | bright, short | major, plagal | short iconic stinger, quote the head |

Ambient/exploration music often has **no hummable lead at all** — the texture *is*
the theme. That's a feature, not a gap.

## Pre-flight checklist (before you call it done)

- [ ] One motif library; the **full theme appears in only one track**.
- [ ] Every other cue **transforms or fragments** the motif (stretch/invert/slice/
      transpose) rather than restating or ignoring it.
- [ ] No **foreground** melody repeats verbatim more than ~2× without variation;
      the big `repeat` counts live on the ostinato/bass/drums, not the lead.
- [ ] The melody is singable: narrow range, clear rhythm, call-and-response.
- [ ] Drive comes from a **moving bass + ostinato**, not a busier melody.
- [ ] Harmony fits the cue's emotion; key family is shared, cadences differ.
- [ ] Each track has contrast (A/B) and at least one moment of space.
- [ ] Tempo/density/dissonance match the cue's gameplay function.
