import factory
from scraper.models import (
    Party,
    ParliamentaryItem,
    PartyVote,
    ParliamentaryItemStatusTypes,
    ParliamentaryItemTypes,
    VoteType,
)
from scraper.dto import AgendapuntZaakBesluitVolgordeDTO
import random


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
        "date_time_this_decade", before_now=True, after_now=False, tzinfo=None
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


class AgendapuntZaakBesluitVolgordeDTOFactory(factory.Factory):
    class Meta:
        model = AgendapuntZaakBesluitVolgordeDTO

    Id = factory.Faker("uuid4")
    Agendapunt_Id = factory.Faker("uuid4")
    BesluitSoort = factory.Faker(
        "random_element",
        elements=["stemming: aangenomen.", "stemming: verworpen."],
    )
    GewijzigdOp = factory.Faker(
        "date_time_this_decade", before_now=True, after_now=False, tzinfo=None
    )
    Zaak = factory.List([{"Id": factory.Faker("uuid4")}])
    Stemming = factory.LazyAttribute(
        lambda _: [
            {
                "Fractie_Id": factory.Faker("uuid4"),
                "Soort": random.choice(["Voor", "Tegen"]),
            }
            for _ in range(10)
        ]
    )
