# Video & Voice Studio — bug log

| # | Symptom | Root cause | Fix | Covered by |
|---|---|---|---|---|
| 1 | Music did not get quieter under the voice when previewing the ducking curve (`musicGainAt` returned full volume while a voice clip played). | The ramp factor `k` started at 1 ("normal level") and was only lowered outside the voice clip, so inside the clip the gain stayed at 100 %. | Start `k` at 0 (fully ducked) inside the clip; ramp to 1 only before/after it. | `tests/studio/timeline.test.mjs` › *music ducks under the voice and recovers* |
| 2 | Opening a project file with an unknown template id kept that id, so the page fell back silently but the file stayed invalid. | `validateProject` spread the file over the defaults *after* choosing the safe template, overwriting it. | Re-apply the validated template id after the spread. | `tests/studio/store.test.mjs` › *project JSON round trip and validation* |
