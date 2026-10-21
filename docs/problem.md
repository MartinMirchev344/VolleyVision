# Problem definition

Help a volleyball coach or analyst review a permitted recorded rally with player
tracks, ball detections, candidate action events, and human-reviewed scoring. The
initial audience is an ABLE Mentor showcase; a usable application is a later goal.

Use fixed, preferably elevated behind-end-line footage; elevated sideline footage
is acceptable but may shift model performance. Avoid camera cuts, movement, multiple
courts and hidden boundaries in the first example. Manual calibration defines both
the strict court and the playable free zone so legal outside-court play is not
automatically discarded.

Week 1 establishes local tools and feasibility evidence. There is no supplied
recording or cleared pretrained checkpoint. See `reports/experiments.md` for measured
checks and unresolved work. A short reliable rally takes priority over a misleading
whole-match demo. Full analytics, named identities, automatic points, public hosting
and metric movement estimates are excluded initially.
