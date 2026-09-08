# PLAYBOOK-WWW-CANDY-MEDIA-CHROME-v1

**Mission:** Games-first media chrome for WWW (Wild Wild West Storybook / Spectre Spins) and Candy Factory — optional WebKit glyph pack as reference/restyle source for mute/volume HUD, Storybook playable-tape transport, bonus/cinema overlay, skip-10 animatic scrub.  
**Owner:** CoS  
**Checker:** Charter Checker  
**Cost:** $0  
**Merge:** no  
**officialSpine:** false (unchanged)

## Path
1. Icons live at `/workspace/ops/webkit-media-controls/icons/` (29: 27 SVG + 2 PNG) — reference only until restyled.
2. For HUD/tape/cinema: prefer `currentColor` (or Atelier restyle) — do not ship raw `#2e3436` / Apple chrome as brand.
3. Wire transport glyphs to existing Storybook stack (Svelte5 + Pixi8 + createSound); icons only — no WebKit runtime.
4. WWW western / Candy candy recolor via CSS color or Atelier redraw; devil-W animation lock respected.
5. Spectre-Atelier is art/animation source for WWW+Candy — chrome glyphs must not replace Atelier brand art.

## Done when
- [ ] Eval receipt reviewed (`EVAL-2026-09-08-webkit-media-controls.md`)
- [ ] Candidate glyph subset listed for WWW HUD + Candy HUD + Storybook tape (no brand Apple chrome)
- [ ] Recolor plan noted (`currentColor` or Atelier) — not applied until Charles/Atelier path says go
- [ ] No WebKit runtime merge; no invented metrics

## Halt
- **Atelier absorb: Charles YES 2026-09-08 — optional pack at assets/packs/media-controls/**
- Halt if any PR tries to merge WebKit runtime or ship un-restyled Apple chrome as player-facing brand
- Halt if work invents metrics or flips `officialSpine`


## Absorb receipt
Charles YES 2026-09-08. Landed: `C:\\Users\\Administrator\\.grok\\Spectre-Atelier\\assets\\packs\\media-controls\\` + box `/workspace/ops/webkit-media-controls/atelier-pack/`.
