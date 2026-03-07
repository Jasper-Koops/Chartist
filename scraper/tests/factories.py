import factory
from scraper.models import (
    Party,
    ParliamentaryItem,
    PartyVote,
    ParliamentaryItemStatusTypes,
    ParliamentaryItemTypes,
    VoteType,
)
from django.utils import timezone
from scraper.dto import BesluitDTO, ZaakBesluitDTO


class PartyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Party

    api_id = factory.Faker("uuid4")


class ParliamentaryItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ParliamentaryItem

    api_id = factory.Faker("uuid4")
    title = factory.Faker("sentence", nb_words=6)
    date = factory.Faker(
        "date_time_this_decade",
        before_now=True,
        after_now=False,
        tzinfo=timezone.get_current_timezone(),
    )
    item_type = ParliamentaryItemTypes.MOTION
    status = factory.Iterator(
        [status for status in ParliamentaryItemStatusTypes]
    )


class PartyVoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PartyVote

    party = factory.SubFactory(PartyFactory)
    parliamentary_item = factory.SubFactory(ParliamentaryItemFactory)
    vote = VoteType.FOR


class BesluitDTOFactory(factory.Factory):
    class Meta:
        model = BesluitDTO

    Id = factory.Faker("uuid4")
    Agendapunt_Id = factory.Faker("uuid4")
    BesluitSoort = factory.Iterator(
        [
            ParliamentaryItemStatusTypes.ACCEPTED,
            ParliamentaryItemStatusTypes.REJECTED,
        ]
    )
    GewijzigdOp = factory.Faker(
        "date_time_this_decade",
        before_now=True,
        after_now=False,
        tzinfo=timezone.get_current_timezone(),
    )
    Stemming = factory.List([])


class ZaakBesluitDTOFactory(factory.Factory):
    class Meta:
        model = ZaakBesluitDTO

    Id = factory.Faker("uuid4")
    Onderwerp = factory.Faker("sentence", nb_words=10)
    Vergaderjaar = "2025-2026"
    GestartOp = factory.Faker(
        "date_time_this_decade",
        before_now=True,
        after_now=False,
        tzinfo=timezone.get_current_timezone(),
    )
    GewijzigdOp = factory.Faker(
        "date_time_this_decade",
        before_now=True,
        after_now=False,
        tzinfo=timezone.get_current_timezone(),
    )
    Besluit = factory.LazyAttribute(lambda _: [BesluitDTOFactory()])
    Document = factory.List([])
