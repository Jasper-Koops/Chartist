# Future features

Features and open questions that were discussed but deliberately left for later.

## Agreement per topic

**Goal:** show agreement between parties per policy area. Two parties can vote
alike on migration and opposite on climate; one overall percentage hides that.

**How to determine a motion's topic.** Findings from the Tweede Kamer API (Oct 2026):

- The `Voortouwcommissie` (lead committee) of a motion's Zaak is always
  "TK" (the plenary), so it is useless as a topic.
- Every motion belongs to a **Kamerstukdossier** with a title, e.g.
  "Dierenwelzijn", "Bestrijding georganiseerde criminaliteit", or a budget
  ("Vaststelling van de begrotingsstaten van het Ministerie van ..."). There are
  hundreds of dossiers, so they need grouping. Budget dossiers map cleanly to a
  ministry; the others need a mapping.
- A motion is submitted during a debate (e.g. "Tweeminutendebat Telecomraad").
  Such debates are held by a real committee (one per ministry, about 15), which
  would be the cleanest topic. **Not yet verified** that this can be retrieved
  reliably for every motion (Zaak -> Activiteit -> its committee).
- Alternative: classify the motion text (keywords or a language model).
  Flexible, but less transparent and less reproducible.

**Suggested approach:** verify the debate-committee route first; fall back to the
dossier for budget motions. Store the topic on `ParliamentaryItem` during the
import, then calculate the agreement matrix per topic (the same calculation as
the monthly agreement, grouped by topic instead of month).

## Other deferred items

- **PCA settings.** Each motion is standardized (`normalize=True`), so
  near-unanimous motions weigh as much as close votes. Revisit together with the
  choice of grouping algorithm.
- **New parliament after an election.** The analysed period starts at a
  hardcoded date (`PERIOD_START`, installation of the current parliament).
  Detecting a new parliament automatically is still open.
- **Analysis history retention.** Every analysis run is kept (about 0.5 MB per
  run now, growing with the period). If the database grows large, keep the
  latest runs plus one per month.
- **Link analyses to the import run** they were based on, to show "analysis
  based on data synced at ...".
- **Amendments and bills.** Only motions are imported; votes on amendments and
  bills use the same API structure.
- **Close votes and deciding parties.** Votes include each party's size
  (`FractieGrootte`), which is not stored yet; with it, show narrowly decided
  motions and how often a party's vote was decisive.
- **Motion success per party.** Share of a party's own motions that pass, and
  who supports them (needs the submitters from the API).
