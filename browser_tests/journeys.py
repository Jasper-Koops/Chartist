"""Run separately: python manage.py test browser_tests.journeys."""

from datetime import date, datetime, timezone
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    expect,
    sync_playwright,
)

from analyzer.agreement import run_agreement_analysis
from analyzer.models import (
    PCAAnalysis,
    PCAComponent,
    PCAComponentPartyScore,
    PCAItemLoading,
)
from scraper.models import ParliamentaryItem, Party, PartyVote, VoteType


@override_settings(
    DEBUG=True,
    LANGUAGE_CODE="en",
    INTERNAL_IPS=[],
    ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"],
)
class BrowserJourneys(StaticLiveServerTestCase):
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page

    def setUp(self) -> None:
        self.parties = [
            Party.objects.create(
                api_id=f"party-{i}",
                abbreviation=f"P{i}",
                name=f"Party {i}",
                participation_rate=100,
            )
            for i in range(3)
        ]
        self.excluded = Party.objects.create(
            api_id="former", abbreviation="Former", name="Former party"
        )
        analysis = PCAAnalysis.objects.create(total_explained_variance=0.75)
        components = [
            PCAComponent.objects.create(
                analysis=analysis, number=i + 1, explained_variance=value
            )
            for i, value in enumerate([0.5, 0.2, 0.05])
        ]
        PCAComponentPartyScore.objects.bulk_create(
            [
                PCAComponentPartyScore(
                    component=component,
                    party=party,
                    score=(i - 1) * 10 + j * (-1) ** i,
                )
                for i, party in enumerate(self.parties)
                for j, component in enumerate(components)
            ]
        )
        self.items = [
            ParliamentaryItem.objects.create(
                api_id=f"motion-{i}",
                title=f"Motion about housing {i}",
                date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                vote_date=date(2026, 1 + i // 60, 15),
                item_type="Motion",
                status="Accepted",
                text=["De Kamer,", "verzoekt de regering woningen te bouwen"],
                document_id=f"kst-test-{i}",
            )
            for i in range(120)
        ]
        PartyVote.objects.bulk_create(
            [
                PartyVote(
                    party=party,
                    parliamentary_item=item,
                    vote=VoteType.FOR if (i + j) % 3 else VoteType.AGAINST,
                )
                for i, item in enumerate(self.items)
                for j, party in enumerate(self.parties)
            ]
        )
        PCAItemLoading.objects.bulk_create(
            [
                PCAItemLoading(
                    component=component,
                    parliamentary_item=item,
                    loading=0.01 * (-1) ** (i + j),
                )
                for i, item in enumerate(self.items)
                for j, component in enumerate(components)
            ]
        )
        PartyVote.objects.filter(
            party=self.parties[0], parliamentary_item=self.items[0]
        ).update(vote=VoteType.SPLIT)
        PartyVote.objects.filter(
            party=self.parties[1], parliamentary_item=self.items[0]
        ).update(vote=VoteType.ABSTAIN)
        from analyzer.analysis import calculate_party_participation_rate

        calculate_party_participation_rate()
        run_agreement_analysis()
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        self.browser = self.playwright.chromium.launch(
            args=["--enable-unsafe-swiftshader"]
        )
        self.addCleanup(self.browser.close)
        self.context = self.browser.new_context(
            viewport={"width": 375, "height": 812}, locale="en-GB"
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def tearDown(self) -> None:
        folder = Path(".browser-artifacts")
        folder.mkdir(exist_ok=True)
        self.page.screenshot(path=str(folder / f"{self._testMethodName}.png"))
        self.assertEqual([], self.errors)
        super().tearDown()

    def test_navigation_at_phone_tablet_and_desktop_widths(self) -> None:
        for width in (320, 375, 960, 961, 1200):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 812})
                self.page.goto(f"{self.live_server_url}/motions/")
                menu = self.page.get_by_role("button", name="Menu", exact=True)
                nav = self.page.get_by_role(
                    "navigation", name="Main", exact=True
                )
                if width <= 960:
                    menu.click()
                    expect(nav).to_be_visible()
                    expect(nav.get_by_role("link")).to_have_count(4)
                    menu.press("Escape")
                    expect(nav).to_be_hidden()
                    expect(menu).to_be_focused()
                    menu.click()
                    self.page.get_by_role(
                        "searchbox", name="Search motions", exact=True
                    ).click()
                    expect(nav).to_be_hidden()
                    menu.click()
                else:
                    expect(menu).to_be_hidden()
                    expect(nav).to_be_visible()
                self.assertLessEqual(
                    self.page.evaluate("document.documentElement.scrollWidth"),
                    width,
                )
                nav.get_by_role("link", name="Methodology", exact=True).click()
                expect(self.page.get_by_role("heading", level=1)).to_have_text(
                    "How to read Chartist"
                )
                self.assertEqual(
                    1, self.page.locator('a[href="/methodology/"]').count()
                )

    def test_statistics_wrap_and_highlights_have_plotted_scores(self) -> None:
        self.page.goto(
            f"{self.live_server_url}/?view=flat&party={self.excluded.pk}"
        )
        expect(self.page.locator("#map-logos .map-logo")).to_have_count(3)
        options = self.page.locator("#focus option:not([disabled])")
        expect(options).to_have_count(3)
        self.assertNotIn("Former", options.all_text_contents())
        self.assertNotIn("party=", self.page.url)
        expect(self.page.locator("#stat-period")).not_to_have_text("-")
        for width in (320, 375, 640, 1200):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 812})
                fits = self.page.locator("#stat-period").evaluate("""node => {
                        const range = document.createRange();
                        range.selectNodeContents(node);
                        const text = range.getBoundingClientRect();
                        const cell = node.closest('.stat').getBoundingClientRect();
                        return text.left >= cell.left - 1 && text.right <= cell.right + 1;
                    }""")
                self.assertTrue(fits)

    def test_variance_follows_view_in_caption_statistics_and_exports(
        self,
    ) -> None:
        self.page.emulate_media(reduced_motion="reduce")
        self.page.add_init_script("""(() => {
            window.exportText = [];
            const original = CanvasRenderingContext2D.prototype.fillText;
            CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
                window.exportText.push(String(text));
                return original.call(this, text, ...args);
            };
        })();""")
        self.page.goto(f"{self.live_server_url}/?view=flat")
        controls = self.page.get_by_role("toolbar", name="Map", exact=True)
        for view, caption, statistic in [
            ("2D", "70.0%", "70%"),
            ("3D", "75.0%", "75%"),
            ("2D", "70.0%", "70%"),
        ]:
            with self.subTest(view=view):
                controls.get_by_role("button", name=view, exact=True).click()
                expect(self.page.locator("#map-total")).to_contain_text(caption)
                expect(self.page.locator("#stat-variance")).to_have_text(
                    statistic
                )
                expect(
                    self.page.locator("#stat-variance + .label abbr")
                ).to_have_attribute(
                    "title",
                    f"Combined, the axes explain {caption} of the differences.",
                )
                self.page.evaluate("window.exportText = []")
                with self.page.expect_download() as pending:
                    self.page.locator("#download").click()
                download = pending.value
                self.assertTrue(
                    download.suggested_filename.startswith(
                        f"chartist-map-{view.lower()}-"
                    )
                )
                self.assertEqual(
                    b"\x89PNG\r\n\x1a\n", Path(download.path()).read_bytes()[:8]
                )
                text = self.page.evaluate("window.exportText.join(' ')")
                self.assertIn(
                    f"{view} · Combined, the axes explain {caption} of the differences.",
                    text,
                )
                Path(".browser-artifacts").mkdir(exist_ok=True)
                download.save_as(
                    f".browser-artifacts/variance-{view.lower()}.png"
                )

    def test_map_controls_and_party_navigation(self) -> None:
        self.page.goto(f"{self.live_server_url}/")
        expect(self.page.locator("#map-logos .map-logo")).to_have_count(3)
        expect(
            self.page.get_by_role("button", name="Explore the map", exact=True)
        ).to_be_visible()
        self.page.get_by_role(
            "button", name="Explore the map", exact=True
        ).click()
        controls = self.page.get_by_role("toolbar", name="Map", exact=True)
        expect(
            controls.get_by_role("button", name="2D", exact=True)
        ).to_have_attribute("aria-pressed", "true")
        controls.get_by_role("button", name="Logos", exact=True).click()
        controls.get_by_role(
            "combobox", name="Highlight", exact=True
        ).select_option(str(self.parties[0].pk))
        expect(self.page.locator("#map-logos .is-focus")).to_have_count(1)
        self.page.locator("#fullscreen").click()
        expect(self.page.locator("#plot-frame")).to_have_class(
            "plot-frame is-fullscreen"
        )
        with self.page.expect_download() as pending:
            self.page.locator("#download").click()
        download = pending.value
        self.assertTrue(
            download.suggested_filename.startswith("chartist-map-2d-logos-")
        )
        self.assertEqual(
            b"\x89PNG\r\n\x1a\n", Path(download.path()).read_bytes()[:8]
        )
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#plot-frame")).to_have_class("plot-frame")
        self.page.locator("#map-logos .is-focus").click()
        expect(self.page.get_by_role("heading", level=1)).to_contain_text(
            "Party 0"
        )

    def test_motion_distinguishes_split_and_non_participation(self) -> None:
        self.page.goto(f"{self.live_server_url}/motion/{self.items[0].pk}/")
        split = self.page.locator(".vote-group").filter(
            has=self.page.get_by_text("Evenly split", exact=True)
        )
        absent = self.page.locator(".vote-group").filter(
            has=self.page.get_by_text("Did not vote", exact=True)
        )
        expect(split.locator(".party-tag")).to_have_text(["P0"])
        expect(absent.locator(".party-tag")).to_have_text(["P1"])
        expect(self.page.locator("#vote-groups .party-tag")).to_have_count(3)

    def test_party_comparison_motion_and_axis_journey(self) -> None:
        self.page.goto(f"{self.live_server_url}/party/{self.parties[0].pk}/")
        self.page.locator("#ranking .compare").first.click()
        expect(self.page.locator("#summary")).to_contain_text("voted the same")
        expect(self.page.locator("#timeline")).to_be_visible()
        self.page.locator("#motions a.title").first.click()
        expect(self.page.locator("#text")).to_contain_text("woningen te bouwen")
        expect(self.page.locator("#documents a")).to_have_count(2)
        self.page.locator("#axes .motion-axis").first.click()
        expect(self.page.get_by_role("heading", level=1)).to_have_text(
            "What drives PC1"
        )
        expect(self.page.locator("#positive .row-link")).to_have_count(25)
        self.page.locator("#positive .row-link").first.click()
        expect(self.page.locator("#vote-groups .party-tag")).to_have_count(3)
