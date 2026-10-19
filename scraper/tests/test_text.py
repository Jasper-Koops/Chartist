from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from scraper.tests.factories import ParliamentaryItemFactory
from scraper.text import extract_motion_text, motion_core


def core(xml: bytes) -> list[str]:
    """The core of a motion, as derived from its stored full text."""
    return motion_core(extract_motion_text(xml))


MOTION_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<wetgeving>
  <al>De Kamer,</al>
  <al>gehoord de beraadslaging,</al>
  <al>Constaterende dat er sprake is van een tekort aan woningen,</al>
  <al>Constaterende dat de bouwproductie achterblijft bij de doelstelling,</al>
  <al>Overwegende dat sneller bouwen bijdraagt aan het oplossen van de wooncrisis,</al>
  <al>Verzoekt de regering om de vergunningverlening te versnellen,</al>
  <al>Spreekt uit dat betaalbaar wonen een grondrecht is,</al>
  <al>en gaat over tot de orde van de dag.</al>
</wetgeving>"""


class TestMotionCore(TestCase):
    def test_extracts_constaterende(self) -> None:
        bullets = core(MOTION_XML)
        self.assertIn(
            "Constaterende dat er sprake is van een tekort aan woningen",
            bullets,
        )

    def test_extracts_multiple_constaterende(self) -> None:
        bullets = core(MOTION_XML)
        constaterende = [
            b for b in bullets if b.lower().startswith("constaterende")
        ]
        self.assertEqual(2, len(constaterende))

    def test_extracts_overwegende(self) -> None:
        bullets = core(MOTION_XML)
        self.assertIn(
            "Overwegende dat sneller bouwen bijdraagt aan het oplossen van de wooncrisis",
            bullets,
        )

    def test_extracts_verzoekt(self) -> None:
        bullets = core(MOTION_XML)
        self.assertIn(
            "Verzoekt de regering om de vergunningverlening te versnellen",
            bullets,
        )

    def test_extracts_spreekt_uit_multiword_prefix(self) -> None:
        bullets = core(MOTION_XML)
        self.assertIn(
            "Spreekt uit dat betaalbaar wonen een grondrecht is", bullets
        )

    def test_excludes_boilerplate_de_kamer(self) -> None:
        bullets = core(MOTION_XML)
        self.assertNotIn("De Kamer", bullets)

    def test_excludes_boilerplate_gehoord(self) -> None:
        bullets = core(MOTION_XML)
        self.assertNotIn("gehoord de beraadslaging", bullets)

    def test_excludes_order_of_the_day(self) -> None:
        bullets = core(MOTION_XML)
        self.assertNotIn("en gaat over tot de orde van de dag.", bullets)

    def test_trailing_comma_stripped(self) -> None:
        xml = b"<root><al>Constaterende dat dit een test is,</al></root>"
        bullets = core(xml)
        self.assertEqual(["Constaterende dat dit een test is"], bullets)

    def test_total_bullet_count(self) -> None:
        bullets = core(MOTION_XML)
        self.assertEqual(5, len(bullets))

    def test_empty_xml_returns_empty_list(self) -> None:
        bullets = core(b"<root></root>")
        self.assertEqual([], bullets)


def motion_xml(*lines: str) -> bytes:
    body = "".join(f"<al>{line}</al>" for line in lines)
    return f'<?xml version="1.0" encoding="UTF-8"?><kamerstuk>{body}</kamerstuk>'.encode()


class TestExtractMotionBoundaries(TestCase):
    def test_motion_of_no_confidence(self) -> None:
        xml = motion_xml(
            "De Kamer,",
            "gehoord de beraadslaging,",
            "zegt het vertrouwen in het kabinet op,",
            "en gaat over tot de orde van de dag.",
            "Wilders",
        )
        self.assertEqual(
            ["zegt het vertrouwen in het kabinet op"],
            core(xml),
        )

    def test_keeps_sub_points_and_other_openings(self) -> None:
        xml = motion_xml(
            "De Kamer,",
            "gehoord de beraadslaging,",
            "constaterende dat de wereldwijde minimumbelasting bestaat;",
            "van oordeel dat Pijler 2 moet bijdragen aan doelbereik;",
            "verzoekt de regering krachtig in te zetten op:",
            "een gelijk speelveld;",
            "forse vermindering van regeldruk",
            "en gaat over tot de orde van de dag.",
            "Vermeer",
        )
        self.assertEqual(
            [
                "constaterende dat de wereldwijde minimumbelasting bestaat;",
                "van oordeel dat Pijler 2 moet bijdragen aan doelbereik;",
                "verzoekt de regering krachtig in te zetten op:",
                "een gelijk speelveld;",
                "forse vermindering van regeldruk",
            ],
            core(xml),
        )

    def test_end_marker_without_period(self) -> None:
        xml = motion_xml(
            "De Kamer,",
            "gehoord de beraadslaging,",
            "neemt de inhoud van dit advies over;",
            "en gaat over tot de orde van de dag",
            "Jetten",
            "Bontenbal",
        )
        self.assertEqual(
            ["neemt de inhoud van dit advies over;"],
            core(xml),
        )

    def test_excludes_signatories(self) -> None:
        bullets = core(
            motion_xml(
                "gehoord de beraadslaging,",
                "verzoekt de regering iets te doen,",
                "en gaat over tot de orde van de dag.",
                "Wilders",
            )
        )
        self.assertNotIn("Wilders", bullets)

    def test_fallback_without_end_marker(self) -> None:
        xml = motion_xml(
            "gehoord de beraadslaging,",
            "verzoekt de regering iets te doen,",
            "Wilders",
        )
        self.assertEqual(
            ["verzoekt de regering iets te doen"],
            core(xml),
        )

    def test_start_without_gehoord_de_beraadslaging(self) -> None:
        xml = motion_xml(
            "De Kamer,",
            "constaterende dat defensiebedrijven investeren,",
            "verzoekt de regering capaciteit te borgen,",
            "en gaat over tot de orde van de dag.",
            "Ceulemans",
        )
        self.assertEqual(
            [
                "constaterende dat defensiebedrijven investeren",
                "verzoekt de regering capaciteit te borgen",
            ],
            core(xml),
        )

    def test_end_marker_without_en(self) -> None:
        xml = motion_xml(
            "De Kamer,",
            "gehoord de beraadslaging,",
            "te en maken voor toezichthouders;",
            "gaat over tot de orde van de dag.",
            "Bromet",
        )
        self.assertEqual(
            ["te en maken voor toezichthouders;"],
            core(xml),
        )


class TestExtractListItems(TestCase):
    def test_list_items_keep_their_marker(self) -> None:
        # Structure as published, e.g. kst-21501-20-2447.
        xml = b"""<?xml version="1.0" encoding="UTF-8"?><kamerstuk>
          <al>De Kamer,</al>
          <al>gehoord de beraadslaging,</al>
          <al-groep>
            <al>verzoekt de regering zich in te zetten voor:</al>
            <lijst type="expliciet">
              <li><li.nr>\xe2\x80\x93</li.nr><al>het behoud van veto's;</al></li>
              <li><li.nr>1.</li.nr><al>de Kopenhagencriteria,</al>
                <al>als uitgangspunt</al></li>
            </lijst>
            <al>en gaat over tot de orde van de dag.</al>
          </al-groep>
          <al-groep><al>Becker</al></al-groep>
        </kamerstuk>"""
        self.assertEqual(
            [
                "verzoekt de regering zich in te zetten voor:",
                "\u2013 het behoud van veto's;",
                "1. de Kopenhagencriteria",
                "als uitgangspunt",
            ],
            core(xml),
        )


PUBLISHED_XML = """<?xml version="1.0" encoding="UTF-8"?><kamerstuk>
  <titel>MOTIE VAN HET LID BECKER C.S.</titel>
  <datumtekst>Voorgesteld <datum isodatum="2026-10-12">12 oktober 2026</datum></datumtekst>
  <tekst>
    <al>De Kamer,</al>
    <al>gehoord de beraadslaging,</al>
    <al>overwegende dat dit plan goede elementen bevat;</al>
    <al-groep>
      <al>verzoekt de regering zich in te zetten voor:</al>
      <lijst>
        <li><li.nr>–</li.nr><al>het behoud van veto's;</al></li>
        <li><li.nr>–</li.nr><al>geen veto's voor nieuwe lidstaten,</al></li>
      </lijst>
      <al>en gaat over tot de orde van de dag.</al>
    </al-groep>
    <al-groep><al>Becker</al><al>Keijzer</al></al-groep>
  </tekst>
</kamerstuk>""".encode()


class TestExtractFullText(TestCase):
    def test_full_text_as_published(self) -> None:
        self.assertEqual(
            [
                "Voorgesteld 12 oktober 2026",
                "De Kamer,",
                "gehoord de beraadslaging,",
                "overwegende dat dit plan goede elementen bevat;",
                "verzoekt de regering zich in te zetten voor:",
                "\u2013 het behoud van veto's;",
                "\u2013 geen veto's voor nieuwe lidstaten,",
                "en gaat over tot de orde van de dag.",
            ],
            extract_motion_text(PUBLISHED_XML),
        )

    def test_core_of_full_text(self) -> None:
        self.assertEqual(
            [
                "overwegende dat dit plan goede elementen bevat;",
                "verzoekt de regering zich in te zetten voor:",
                "\u2013 het behoud van veto's;",
                "\u2013 geen veto's voor nieuwe lidstaten",
            ],
            motion_core(extract_motion_text(PUBLISHED_XML)),
        )

    def test_without_date_line(self) -> None:
        lines = extract_motion_text(
            motion_xml(
                "De Kamer,",
                "gehoord de beraadslaging,",
                "verzoekt de regering iets te doen,",
                "en gaat over tot de orde van de dag.",
            )
        )
        self.assertEqual("De Kamer,", lines[0])

    def test_fallback_keeps_punctuation(self) -> None:
        self.assertEqual(
            ["verzoekt de regering iets te doen,"],
            extract_motion_text(
                motion_xml("verzoekt de regering iets te doen,", "Wilders")
            ),
        )

    def test_core_of_text_stored_without_formula(self) -> None:
        # Texts stored before the full text was: only the core lines.
        self.assertEqual(
            ["constaterende dat het regent", "verzoekt de regering"],
            motion_core(
                ["constaterende dat het regent,", "verzoekt de regering"]
            ),
        )


class TestMotionTextApi(APITestCase):
    def test_detail_has_full_and_core_text(self) -> None:
        item = ParliamentaryItemFactory(text=extract_motion_text(PUBLISHED_XML))
        data = self.client.get(
            reverse("parliamentaryitem-detail", args=[item.id])
        ).data
        self.assertEqual("Voorgesteld 12 oktober 2026", data["text"][0])
        self.assertEqual(
            "overwegende dat dit plan goede elementen bevat;",
            data["core_text"][0],
        )
