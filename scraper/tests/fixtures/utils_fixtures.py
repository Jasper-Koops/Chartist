from typing import Any


PARTIES: dict[str, str] = {
    "ChristenUnie": "ChristenUnie",
    "FVD": "Forum voor Democratie",
    "SP": "Socialistische Partij",
    "PVV": "Partij voor de Vrijheid",
    "PvdD": "Partij voor de Dieren",
    "D66": "Democraten 66",
    "SGP": "Staatkundig Gereformeerde Partij",
    "BBB": "BoerBurgerBeweging",
    "CDA": "Christen-Democratisch Appèl",
    "DENK": "DENK",
    "50PLUS": "50PLUS",
    "VVD": "Volkspartij voor Vrijheid en Democratie",
    "JA21": "JA21",
    "VOLT": "Volt",
    "GroenLinks-PvdA": "Groenlinks - PvdA",
}


PARTY_API_RESPONSE: list[dict[str, str | int | None | bool]] = [
    {
        "AantalStemmen": 212532,
        "AantalZetels": 3,
        "Afkorting": "ChristenUnie",
        "ApiGewijzigdOp": "2023-12-14T09:22:19.8046131Z",
        "ContentLength": 2930,
        "ContentType": "image/gif",
        "DatumActief": "2001-03-15T00:00:00+01:00",
        "DatumInactief": None,
        "GewijzigdOp": "2023-12-14T10:21:08+01:00",
        "Id": "d720f5af-0516-408a-b830-0b6ffb8a581c",
        "NaamEN": "Christian Union",
        "NaamNL": "ChristenUnie",
        "Nummer": 2753,
        "Verwijderd": False,
    },
    {
        "AantalStemmen": 328225,
        "AantalZetels": 5,
        "Afkorting": "SP",
        "ApiGewijzigdOp": "2023-12-13T13:53:22.1323118Z",
        "ContentLength": 2876,
        "ContentType": "image/png",
        "DatumActief": "1994-05-17T00:00:00+02:00",
        "DatumInactief": None,
        "GewijzigdOp": "2023-12-13T14:52:16+01:00",
        "Id": "a3689bb6-3914-4d5c-a6a8-42e24582e299",
        "NaamEN": "Socialist Party",
        "NaamNL": "Socialistische Partij",
        "Nummer": 2768,
        "Verwijderd": False,
    },
    {
        "AantalStemmen": 235148,
        "AantalZetels": 3,
        "Afkorting": "PvdD",
        "ApiGewijzigdOp": "2023-12-06T13:48:27.8333518Z",
        "ContentLength": 11374,
        "ContentType": "image/jpeg",
        "DatumActief": "2006-11-30T00:00:00+01:00",
        "DatumInactief": None,
        "GewijzigdOp": "2023-12-05T15:36:07+01:00",
        "Id": "d3b4d880-ef37-4ce6-99ec-4940266ac466",
        "NaamEN": "Party for the Animals",
        "NaamNL": "Partij voor de Dieren",
        "Nummer": 2764,
        "Verwijderd": False,
    },
]


BESLUIT_API_RESPONSE: list[dict[str, Any]] = [
    {
        "AgendapuntZaakBesluitVolgorde": 3,
        "Agendapunt_Id": "b981c506-a965-47b3-826c-744142a35da7",
        "ApiGewijzigdOp": "2025-12-16T15:20:05.9121252Z",
        "BesluitSoort": "Stemmen - aangenomen",
        "BesluitTekst": "Aangenomen.",
        "GewijzigdOp": "2025-12-16T16:19:59.787+01:00",
        "Id": "67fabb78-9fcc-46cd-9f17-0054954b671e",
        "Opmerking": None,
        "Status": "Besluit",
        "Stemming": [
            {
                "Fractie_Id": "77f9b6f1-b1a9-4d1b-a05e-9936e79d8fa5",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "ae48391e-ce4d-47e0-86e3-ee310282f66f",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "e0b7b638-de3c-47cc-85bd-341dd65ea33d",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "62c1a13c-85ff-40ed-90f7-a9546d61f869",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "0208097d-ef04-438a-8c29-eebb84956204",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "4e9f6f5b-2544-4667-8134-6b85c4ebb4e0",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "d3b4d880-ef37-4ce6-99ec-4940266ac466",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "626555ac-e836-44e3-9978-a6a7f0abc3ce",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "d720f5af-0516-408a-b830-0b6ffb8a581c",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "deb74bb5-63a9-4ffc-98ed-af577167452e",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "7476e97a-3243-4122-9df6-ba7d82a5279b",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "65129918-f256-4975-9da4-488da34d6695",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "fab6e7e1-9d63-446a-a6e1-e1c74e3f679e",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "a3689bb6-3914-4d5c-a6a8-42e24582e299",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "a34bf6c8-834e-4dba-b4d2-f2f1b3957bd2",
                "Soort": "Tegen",
            },
        ],
        "StemmingsSoort": "Met handopsteken",
        "Verwijderd": False,
        "Zaak": [],
    },
    {
        "AgendapuntZaakBesluitVolgorde": 4,
        "Agendapunt_Id": "c94577ba-e5e2-422c-9486-da8e69369609",
        "ApiGewijzigdOp": "2025-12-17T12:18:38.5061715Z",
        "BesluitSoort": "Stemmen - aangenomen",
        "BesluitTekst": "Aangenomen.",
        "GewijzigdOp": "2025-12-17T13:18:36.047+01:00",
        "Id": "59b3219e-d798-4b15-a7b9-0066221f82db",
        "Opmerking": None,
        "Status": "Besluit",
        "Stemming": [
            {
                "Fractie_Id": "d3b4d880-ef37-4ce6-99ec-4940266ac466",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "65129918-f256-4975-9da4-488da34d6695",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "626555ac-e836-44e3-9978-a6a7f0abc3ce",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "7476e97a-3243-4122-9df6-ba7d82a5279b",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "77f9b6f1-b1a9-4d1b-a05e-9936e79d8fa5",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "e0b7b638-de3c-47cc-85bd-341dd65ea33d",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "d720f5af-0516-408a-b830-0b6ffb8a581c",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "a34bf6c8-834e-4dba-b4d2-f2f1b3957bd2",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "0208097d-ef04-438a-8c29-eebb84956204",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "a3689bb6-3914-4d5c-a6a8-42e24582e299",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "4e9f6f5b-2544-4667-8134-6b85c4ebb4e0",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "ae48391e-ce4d-47e0-86e3-ee310282f66f",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "62c1a13c-85ff-40ed-90f7-a9546d61f869",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "deb74bb5-63a9-4ffc-98ed-af577167452e",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "fab6e7e1-9d63-446a-a6e1-e1c74e3f679e",
                "Soort": "Voor",
            },
        ],
        "StemmingsSoort": "Met handopsteken",
        "Verwijderd": False,
        "Zaak": [
            {
                "Afgedaan": True,
                "Alias": None,
                "ApiGewijzigdOp": "2025-12-17T12:18:40.9400305Z",
                "Citeertitel": None,
                "GestartOp": "2024-12-16T00:00:00+01:00",
                "GewijzigdOp": "2024-12-17T13:18:36.05+01:00",
                "Grondslagvoorhang": None,
                "GrootProject": False,
                "HuidigeBehandelstatus": None,
                "Id": "669e6b7e-2f11-4ef6-99bd-336e25711dbf",
                "Kabinetsappreciatie": "Oordeel Kamer",
                "Nummer": "2025Z22235",
                "Onderwerp": "Motie van de leden Bikker en Erkens over zich in Europa inzetten voor het verbeteren van informatiedeling en beleidsafstemming om de dreiging van jihadisme te verminderen",
                "Organisatie": "Tweede Kamer",
                "Soort": "Motie",
                "Status": "Vrijgegeven",
                "Termijn": None,
                "Titel": "Europese Raad",
                "Vergaderjaar": "2025-2026",
                "Verwijderd": False,
                "Volgnummer": 2333,
            }
        ],
    },
    {
        "AgendapuntZaakBesluitVolgorde": 2,
        "Agendapunt_Id": "87c756ef-94c8-4e3c-8342-0177bb9ca28e",
        "ApiGewijzigdOp": "2025-11-25T14:23:42.1679245Z",
        "BesluitSoort": "Stemmen - verworpen",
        "BesluitTekst": "Verworpen.",
        "GewijzigdOp": "2025-11-25T15:23:38.367+01:00",
        "Id": "e459c657-2a45-464c-b074-012e7edbfc59",
        "Opmerking": None,
        "Status": "Besluit",
        "Stemming": [
            {
                "Fractie_Id": "65129918-f256-4975-9da4-488da34d6695",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "77f9b6f1-b1a9-4d1b-a05e-9936e79d8fa5",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "626555ac-e836-44e3-9978-a6a7f0abc3ce",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "a34bf6c8-834e-4dba-b4d2-f2f1b3957bd2",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "e0b7b638-de3c-47cc-85bd-341dd65ea33d",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "fab6e7e1-9d63-446a-a6e1-e1c74e3f679e",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "d3b4d880-ef37-4ce6-99ec-4940266ac466",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "7476e97a-3243-4122-9df6-ba7d82a5279b",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "a3689bb6-3914-4d5c-a6a8-42e24582e299",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "ae48391e-ce4d-47e0-86e3-ee310282f66f",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "4e9f6f5b-2544-4667-8134-6b85c4ebb4e0",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "d720f5af-0516-408a-b830-0b6ffb8a581c",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "0208097d-ef04-438a-8c29-eebb84956204",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "62c1a13c-85ff-40ed-90f7-a9546d61f869",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "deb74bb5-63a9-4ffc-98ed-af577167452e",
                "Soort": "Voor",
            },
        ],
        "StemmingsSoort": "Met handopsteken",
        "Verwijderd": False,
        "Zaak": [
            {
                "Afgedaan": True,
                "Alias": None,
                "ApiGewijzigdOp": "2025-11-28T13:02:55.1284343Z",
                "Citeertitel": None,
                "GestartOp": "2025-11-19T00:00:00+01:00",
                "GewijzigdOp": "2025-11-25T15:23:43.387+01:00",
                "Grondslagvoorhang": None,
                "GrootProject": False,
                "HuidigeBehandelstatus": None,
                "Id": "e10688d3-ba68-457b-a2a1-95dae0ee7e2e",
                "Kabinetsappreciatie": "Ontijdig",
                "Nummer": "2025Z20036",
                "Onderwerp": "Motie van het lid Neijenhuis over bij een RNI-inschrijving actief wijzen op de verzekeringsplicht",
                "Organisatie": "Tweede Kamer",
                "Soort": "Motie",
                "Status": "Vrijgegeven",
                "Termijn": None,
                "Titel": "Arbeidsmigratie en sociale zekerheid",
                "Vergaderjaar": "2025-2026",
                "Verwijderd": False,
                "Volgnummer": 173,
            }
        ],
    },
    {
        "AgendapuntZaakBesluitVolgorde": 4,
        "Agendapunt_Id": "1f90543d-404b-46cd-9578-d8aa40122a23",
        "ApiGewijzigdOp": "2025-12-16T15:20:08.1015484Z",
        "BesluitSoort": "Stemmen - aangenomen",
        "BesluitTekst": "Aangenomen.",
        "GewijzigdOp": "2025-12-16T16:19:59.827+01:00",
        "Id": "0946bfdb-10cd-4330-906a-019ca6affa4c",
        "Opmerking": None,
        "Status": "Besluit",
        "Stemming": [
            {
                "Fractie_Id": "fab6e7e1-9d63-446a-a6e1-e1c74e3f679e",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "62c1a13c-85ff-40ed-90f7-a9546d61f869",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "ae48391e-ce4d-47e0-86e3-ee310282f66f",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "a3689bb6-3914-4d5c-a6a8-42e24582e299",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "7476e97a-3243-4122-9df6-ba7d82a5279b",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "4e9f6f5b-2544-4667-8134-6b85c4ebb4e0",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "d3b4d880-ef37-4ce6-99ec-4940266ac466",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "77f9b6f1-b1a9-4d1b-a05e-9936e79d8fa5",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "deb74bb5-63a9-4ffc-98ed-af577167452e",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "0208097d-ef04-438a-8c29-eebb84956204",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "626555ac-e836-44e3-9978-a6a7f0abc3ce",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "a34bf6c8-834e-4dba-b4d2-f2f1b3957bd2",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "e0b7b638-de3c-47cc-85bd-341dd65ea33d",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "d720f5af-0516-408a-b830-0b6ffb8a581c",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "65129918-f256-4975-9da4-488da34d6695",
                "Soort": "Voor",
            },
        ],
        "StemmingsSoort": "Met handopsteken",
        "Verwijderd": False,
        "Zaak": [
            {
                "Afgedaan": True,
                "Alias": None,
                "ApiGewijzigdOp": "2025-12-16T15:20:10.4129039Z",
                "Citeertitel": None,
                "GestartOp": "2025-12-10T00:00:00+01:00",
                "GewijzigdOp": "2025-12-16T16:20:04.863+01:00",
                "Grondslagvoorhang": None,
                "GrootProject": False,
                "HuidigeBehandelstatus": None,
                "Id": "5434a48b-6c4d-4c34-a77a-c48d00362503",
                "Kabinetsappreciatie": "Oordeel Kamer",
                "Nummer": "2025Z21576",
                "Onderwerp": "Motie van de leden Grinwis en Schutz over besluitvorming en budget betreffende vernieuwing van het spui- en gemaalcomplex in IJmuiden ",
                "Organisatie": "Tweede Kamer",
                "Soort": "Motie",
                "Status": "Vrijgegeven",
                "Termijn": None,
                "Titel": "Waterbeleid",
                "Vergaderjaar": "2025-2026",
                "Verwijderd": False,
                "Volgnummer": 725,
            }
        ],
    },
    {
        "AgendapuntZaakBesluitVolgorde": 6,
        "Agendapunt_Id": "894f8ab9-8176-4947-a8d1-f7d03abd1f04",
        "ApiGewijzigdOp": "2025-12-02T15:04:24.2056694Z",
        "BesluitSoort": "Stemmen - aangenomen",
        "BesluitTekst": "Aangenomen.",
        "GewijzigdOp": "2025-12-02T16:04:17.433+01:00",
        "Id": "ea4067f7-40e3-4839-9cce-01e7af4ca94d",
        "Opmerking": None,
        "Status": "Besluit",
        "Stemming": [
            {
                "Fractie_Id": "a3689bb6-3914-4d5c-a6a8-42e24582e299",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "fab6e7e1-9d63-446a-a6e1-e1c74e3f679e",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "0208097d-ef04-438a-8c29-eebb84956204",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "7476e97a-3243-4122-9df6-ba7d82a5279b",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "deb74bb5-63a9-4ffc-98ed-af577167452e",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "4e9f6f5b-2544-4667-8134-6b85c4ebb4e0",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "a34bf6c8-834e-4dba-b4d2-f2f1b3957bd2",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "ae48391e-ce4d-47e0-86e3-ee310282f66f",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "62c1a13c-85ff-40ed-90f7-a9546d61f869",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "e0b7b638-de3c-47cc-85bd-341dd65ea33d",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "d720f5af-0516-408a-b830-0b6ffb8a581c",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "626555ac-e836-44e3-9978-a6a7f0abc3ce",
                "Soort": "Tegen",
            },
            {
                "Fractie_Id": "d3b4d880-ef37-4ce6-99ec-4940266ac466",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "77f9b6f1-b1a9-4d1b-a05e-9936e79d8fa5",
                "Soort": "Voor",
            },
            {
                "Fractie_Id": "65129918-f256-4975-9da4-488da34d6695",
                "Soort": "Voor",
            },
        ],
        "StemmingsSoort": "Met handopsteken",
        "Verwijderd": False,
        "Zaak": [
            {
                "Afgedaan": True,
                "Alias": None,
                "ApiGewijzigdOp": "2025-12-18T10:45:01.6905063Z",
                "Citeertitel": None,
                "GestartOp": "2025-11-27T00:00:00+01:00",
                "GewijzigdOp": "2025-12-02T16:04:17.44+01:00",
                "Grondslagvoorhang": None,
                "GrootProject": False,
                "HuidigeBehandelstatus": None,
                "Id": "fa2d7dfb-5122-44c5-8f8a-65a44ce83b56",
                "Kabinetsappreciatie": "Oordeel Kamer",
                "Nummer": "2025Z20772",
                "Onderwerp": "Motie van het lid Dobbe over de Russische centralebanktegoeden aanspreken voor steun aan Oekraïne",
                "Organisatie": "Tweede Kamer",
                "Soort": "Motie",
                "Status": "Vrijgegeven",
                "Termijn": None,
                "Titel": "Situatie in Oekraïne ",
                "Vergaderjaar": "2025-2026",
                "Verwijderd": False,
                "Volgnummer": 248,
            }
        ],
    },
]
