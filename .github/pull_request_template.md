### What changed

<!-- One or two sentences. What a reviewer would need to know before reading
     the diff. -->

### Why

<!-- Closes #123, or the reasoning if there is no issue. -->

### How it was verified

<!-- The part that matters. The pipeline proves the tests still pass; it does
     not prove the new thing works. Say what you actually did. -->

- [ ] `pytest` passes
- [ ] `ruff check` passes
- [ ] looked at it in a browser — widths: <!-- e.g. 375, 900, 1200 -->
- [ ] measured it — <!-- which tool in tools/, and the numbers -->
- [ ] n/a, and here is why:

### Checklist

- [ ] No credential, key, or `.env` in the diff. New settings are in
      `.env.example` as a placeholder.
- [ ] Comments explain *why*, not what.
- [ ] Extends what already exists rather than adding a parallel way to do it.
- [ ] If `sizes` or a CSS breakpoint changed, both sides were changed together.
- [ ] If images were added or regenerated, `tools/gen_image_variants.py` was
      re-run and `variants.json` is in the diff.
- [ ] If the schema changed, the right file was updated — CI loads both to seed
      the test database, so a stale schema fails the pipeline.

### Anything a reviewer should look at twice
