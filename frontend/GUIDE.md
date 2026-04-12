# Reading the Elephant Dashboard

A plain-English walkthrough of every chart, table, and number on the analysis page. Read this once and the dashboard will make sense.

---

## The big idea

Elephants make lots of sounds (rumbles, trumpets, roars). We recorded many calls, measured each one as a list of numbers (pitch, loudness, formants, etc.), and asked the computer three questions:

1. **How many *types* of calls are there?** (clustering)
2. **Which type goes with which behavior?** (association)
3. **Who made each call, and what did it probably mean?** (classification + inference)

Every card on the dashboard answers one piece of that puzzle.

---

## Top bar — the 5 stat chips

These are the headline numbers. Read them first.

| Chip | What it means |
|---|---|
| **Calls analyzed** | Total number of individual vocalizations in the dataset. More = more reliable stats. |
| **Call types** | How many acoustically distinct "words" the clustering found. Think of these as the elephant vocabulary size. |
| **Behaviors** | How many different behavioral contexts were observed (feeding, greeting, alarm, etc.). |
| **Elephants** | Number of unique individual callers. |
| **Context accuracy** | When we try to guess the behavior from sound alone, how often we get it right (cross-validated). **>50% means sound really does carry meaning.** Random guessing would be ~10-15%. |

---

## 1. Call-type clusters (UMAP scatter)

**What you see:** a cloud of dots, each dot is one call. Dots of the same color belong to the same cluster. Dotted polygons are the cluster boundaries. Green shading shows where calls are densest.

**How to read it:**
- **Tight, well-separated blobs** = clearly distinct call types. Good.
- **Overlapping blobs** = call types that sound similar — the elephants may not treat them as different "words."
- **Labels like C0, C1, C2...** mark the center of each cluster. The legend on the right tells you the top behavior for each.
- **Hover a dot** to see the filename, cluster, behavior, caller, and pitch.

**What to infer:** if you see, say, 12 clean clusters, that's a rough estimate of "how many distinct call types elephants use." Compare to other species — dolphins have ~20-30, vervet monkeys have ~6.

> *UMAP squishes the 20 acoustic features into a 2D map so your eyes can see it. Distance on the map ≈ acoustic similarity.*

---

## 2. PMI heatmap — "which call means what"

**What you see:** a grid. Rows = call types (S0, S1, ...). Columns = behaviors (feeding, greeting, alarm, ...). Cell color = PMI score.

- **Green cell** = this call type shows up with this behavior **much more often than chance**. Strong association.
- **Yellow cell** = neutral / expected rate.
- **Red cell** = this call type is **avoided** in this behavior.

**How to read it:** scan each row. If symbol S3 has one bright green cell (e.g. under "alarm") and everything else is yellow/red, S3 is **context-specific** — it's basically the "alarm word." If a row is uniformly yellow, that call is a **general-purpose** sound.

**What to infer:** context-specific calls (PMI > 2) are the closest thing to "words with meaning." General-purpose calls are more like "uh" or "hmm."

---

## 3. Transition matrix — call sequences

**What you see:** a grid. Row = current call. Column = next call. Dark purple = "this transition happens a lot."

**How to read it:**
- **Dark diagonal** = calls repeat themselves (elephant says "rumble rumble rumble").
- **Dark off-diagonal cells** = predictable sequences ("A always follows B") — possible **grammar / syntax**.
- **Uniform pale grid** = calls are random-order, no syntax.

**What to infer:** repeated non-random transitions are a hint of *combinatorial* communication (stringing sounds together like words in a sentence). Real discovery if you find any.

---

## 4. Vowel space (F1 / F2 scatter)

**What you see:** dots plotted with F2 (horizontal) vs F1 (vertical), both axes reversed — this is how linguists plot **human vowels**.

**How to read it:**
- **F1** = how open the mouth is (low F1 = closed like "ee", high F1 = open like "ah").
- **F2** = tongue front/back position.
- **Clusters of dots** = distinct "mouth shapes" the elephant uses repeatedly.

**What to infer:** if you see 3-5 clean clusters here, elephants have **vowel-like articulation** — a huge deal, because it suggests they actively shape their vocal tract for different sounds, not just vary pitch.

---

## 5. Context distribution bars

**What you see:** one bar per behavior, height = number of calls in that behavior.

**How to read it:** just a sanity check. Tall bars = behaviors we have lots of data for (our predictions for those are more trustworthy). Short bars = under-sampled behaviors (don't over-interpret those).

---

## 6. Caller identifiability (horizontal bars)

**What you see:** the top 15 most acoustically distinctive elephants, ranked. Longer bar = more unique voice.

**How to read it:**
- **High score** = this elephant sounds different from everyone else — the classifier can pick them out. Like someone with a very recognizable voice.
- **Low score** = this elephant sounds average / blends in.

**What to infer:** individuals with very high scores are candidates for **individual signatures** (think: elephants having "names" or at least recognizable voices). The `n=` label shows how many calls we have for them — don't trust a high score if n is tiny.

---

## 7. Voice profiles table

Each row is one elephant. Columns are the average of their acoustic features (mean F0, mean duration, HNR, etc.).

**How to read it:** scan down a column. Big differences between elephants in the same column = that feature varies a lot by individual (good for ID). If everyone's mean_f0 is nearly the same, F0 is not very diagnostic.

Compare rows to ask: "does elephant A systematically have a higher pitch / longer calls / more harmonic voice than elephant B?"

---

## 8. Caller–context affinity table

**Columns:**
- **N** = number of calls we have from this elephant.
- **Top contexts** = the behaviors they vocalize in most.
- **χ² (chi-squared)** = how skewed their context distribution is. Big number = they strongly prefer certain contexts over others.
- **Type** — **specialist** (chi² high → this elephant mostly vocalizes during, e.g., feeding) or **generalist** (vocalizes evenly across behaviors).

**What to infer:** specialists may have social roles (e.g., the matriarch does most alarm calls). Generalists are "average" members.

---

## 9. Sample interpretations (WHO / WHAT / WHY cards)

Each card is the pipeline's **best guess** at what one specific call meant.

- **Filename + cluster** — which call and which acoustic type.
- **Caller age/sex** — who made it (e.g., "adult female").
- **Quote** — a templated interpretation: "Probably *<action>* — *<emotional read>*."
- **Confidence** — how sure the model is. Low confidence = take it with salt.
- **Alternative** — the second-best guess.
- **Tags** — color-coded:
  - Green/red/teal = **valence** (positive / negative / neutral emotional tone)
  - Red/orange/yellow = **arousal** (how intense/excited)
  - Purple = **predicted behavioral context**

**How to read them:** these are *illustrative* — the pipeline doesn't actually "understand" elephants. Think of it as: "given the numbers, the closest human-language gloss would be…"

---

## Quick inference cheat-sheet

| If you see… | It means… |
|---|---|
| Context accuracy > 40% | Sound really encodes behavior. Elephant calls are *meaningful*, not random. |
| Several clean UMAP clusters | Elephants use a discrete vocabulary, not a gradient of sounds. |
| Green cells scattered across the PMI heatmap | Each call type has a specific job. |
| Dark off-diagonal transition cells | Possible grammar/syntax — calls occur in patterns. |
| Clustered F1/F2 vowel space | Elephants actively articulate different "vowels." |
| Elephants with very high identifiability | Good candidates for individual voice signatures ("names"). |
| Many "specialist" callers | Social role differentiation — different elephants do different vocal jobs. |

---

## What the dashboard can NOT tell you

- **Exact meanings.** No one knows what elephants "really" say. The interpretation cards are informed guesses.
- **Intent.** We see correlation between sound and behavior, not intent.
- **Grammar in the human sense.** Transition regularities are suggestive, not proof of syntax.

Treat everything here as **hypotheses with evidence strengths**, not facts.

---

## TL;DR — how to read it in 30 seconds

1. Check **context accuracy** — is it above chance? (yes = worth analyzing)
2. Count **clusters** on the UMAP scatter — that's the vocabulary size.
3. Look for **green cells** on the PMI heatmap — those are the meaningful call-types.
4. Scan the **identifiability bars** — which elephants have distinctive voices.
5. Read a few **interpretation cards** for flavor.

That's the whole story.
