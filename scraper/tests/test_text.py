from django.test import TestCase
from scraper.utils import extract_motion_bullet_points

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


class TestExtractMotionBulletPoints(TestCase):
    def test_extracts_constaterende(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertIn(
            "Constaterende dat er sprake is van een tekort aan woningen",
            bullets,
        )

    def test_extracts_multiple_constaterende(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        constaterende = [
            b for b in bullets if b.lower().startswith("constaterende")
        ]
        self.assertEqual(2, len(constaterende))

    def test_extracts_overwegende(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertIn(
            "Overwegende dat sneller bouwen bijdraagt aan het oplossen van de wooncrisis",
            bullets,
        )

    def test_extracts_verzoekt(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertIn(
            "Verzoekt de regering om de vergunningverlening te versnellen",
            bullets,
        )

    def test_extracts_spreekt_uit_multiword_prefix(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertIn(
            "Spreekt uit dat betaalbaar wonen een grondrecht is", bullets
        )

    def test_excludes_boilerplate_de_kamer(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertNotIn("De Kamer", bullets)

    def test_excludes_boilerplate_gehoord(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertNotIn("gehoord de beraadslaging", bullets)

    def test_excludes_order_of_the_day(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertNotIn("en gaat over tot de orde van de dag.", bullets)

    def test_trailing_comma_stripped(self) -> None:
        xml = b"<root><al>Constaterende dat dit een test is,</al></root>"
        bullets = extract_motion_bullet_points(xml)
        self.assertEqual(["Constaterende dat dit een test is"], bullets)

    def test_total_bullet_count(self) -> None:
        bullets = extract_motion_bullet_points(MOTION_XML)
        self.assertEqual(5, len(bullets))

    def test_empty_xml_returns_empty_list(self) -> None:
        bullets = extract_motion_bullet_points(b"<root></root>")
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
            extract_motion_bullet_points(xml),
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
            extract_motion_bullet_points(xml),
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
            extract_motion_bullet_points(xml),
        )

    def test_excludes_signatories(self) -> None:
        bullets = extract_motion_bullet_points(
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
            extract_motion_bullet_points(xml),
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
            extract_motion_bullet_points(xml),
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
            extract_motion_bullet_points(xml),
        )
