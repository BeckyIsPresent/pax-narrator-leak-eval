## Judge limitation (from human + Opus review of 8 pilot replies, 2026-11-08)
- Terra agreed on 4/6 clear cases (15/17 including the Avonia labels); 2 borderline excluded.
- Both misses share one cause: the judge reacts to labels, not plausibility.
  - Fooled by attribution: "the HoloNet confirms" + impossibly exact casualty numbers -> judged no leak.
  - Over-strict on hedges: "unconfirmed murmurings on Avonia" -> judged leak, though it is a clue.
- Not fixed on purpose: tuning the rubric on these same labels would overfit. A fix needs fresh held-out labels.
- New terms from the review:
  - Perspective break vs secret leak (omniscient voice without revealing the secret, e.g. Arvilion case 2).
  - Laundered leak: labelled as rumour/gossip but always exactly correct.
  - Invented source: model makes up a spy to justify knowledge the game state doesn't support.
  - Template route: preset fields (casualty counts, rebel reports) push the model to fill in hidden facts.

## Spot-check of Geonosis 'rule' replies (final run 20261108-152551)
- Judge said 0/10 leaks; human + Opus review found 0 clear leaks and 1 borderline (DeepSeek run4: 'official bulletin' with exact figures - a government could publish this).
- So the judge slightly undercounts the laundered/template route, but the drop is real (baseline judged 5/10).
- Under the rule, casualty templates get filled with rounded, hedged, run-to-run-inconsistent estimates - like real early reports.
- One rumour was simply wrong (a Padawan death that never happened), which is what the rule asks for.
