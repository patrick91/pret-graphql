import asyncio
import typing
from dataclasses import InitVar

from urllib.parse import urljoin

import strawberry

from browser import get_browser

SEMAPHORE = None


def get_semaphore():
    """Returns a shared semaphore"""
    global SEMAPHORE

    if SEMAPHORE is None:
        SEMAPHORE = asyncio.Semaphore(10, loop=asyncio.get_event_loop())

    return SEMAPHORE


@strawberry.type
class NutritionalInformation:
    """Nutrition per serving"""

    energy_in_kcalories: typing.Optional[float] = None
    fat: typing.Optional[float] = None
    saturated_fat: typing.Optional[float] = None
    carbs: typing.Optional[float] = None
    sugars: typing.Optional[float] = None
    fibre: typing.Optional[float] = None
    protein: typing.Optional[float] = None
    salt: typing.Optional[float] = None
    sodium: typing.Optional[float] = None

    @staticmethod
    def from_rows(rows_data):
        """Creates a NutritionalInformation from data scraped from pret's website.

        Implemented in a very naive way, but it is good enough for a POC"""
        info = {}

        for row in rows_data:
            prop_name = row["property"].lower()

            if "kcal" in prop_name:
                prop_name = "energy_in_kcalories"
            elif "fat" in prop_name:
                prop_name = "fat"
            elif "saturates" in prop_name:
                prop_name = "saturated_fat"
            elif "carbohydrate" in prop_name:
                prop_name = "carbs"
            elif "sugars" in prop_name:
                prop_name = "sugars"
            elif "fibre" in prop_name:
                prop_name = "fibre"
            elif "protein" in prop_name:
                prop_name = "protein"
            elif "salt" in prop_name:
                prop_name = "salt"
            elif "sodium" in prop_name:
                prop_name = "sodium"
            else:
                prop_name = None

            if prop_name is not None:
                info[prop_name] = row["valuePerPortion"]

        return NutritionalInformation(**info)


@strawberry.type
class MenuItem:
    name: str
    description: str
    link: InitVar[str]

    def __post_init__(self, link):
        self._link = link

    @strawberry.field
    async def nutritional_information(
        self, info
    ) -> typing.Optional[NutritionalInformation]:
        async with get_semaphore():
            browser = await get_browser()
            page = await browser.newPage()

            try:
                url = urljoin("https://www.pret.co.uk", self._link)

                await page.goto(url)

                rows = await page.querySelectorAll(".table-box table tr")

                tasks = [
                    page.evaluate(
                        """(row) => ({
                            property: row.querySelector('th').textContent.trim(),
                            value: row.querySelector('td:nth-child(2), th:nth-child(2)').textContent.trim(),
                            valuePerPortion: row.querySelector('td:nth-child(3), th:nth-child(3)').textContent.trim(),
                        })""",
                        row,
                    )
                    for row in rows
                ]

                rows = await asyncio.gather(*tasks)

                return NutritionalInformation.from_rows(rows)
            except Exception as e:
                print("something went wrong", e)
            finally:
                await page.close()


@strawberry.type
class Category:
    name: str
    link: InitVar[str]

    def __post_init__(self, link):
        self._link = link

    @strawberry.field
    async def items(self, info) -> typing.List[MenuItem]:
        try:
            url = urljoin("https://www.pret.co.uk", self._link)

            browser = await get_browser()
            page = await browser.newPage()

            await page.goto(url)

            elements = await page.querySelectorAll("article.article")

            tasks = [
                page.evaluate(
                    """(element) => ({
                        name: element.querySelector('h3').textContent.trim(),
                        description: element.querySelector('p').textContent.trim(),
                        link: element.querySelector('a.link').getAttribute('href'),
                    })""",
                    element,
                )
                for element in elements
            ]

            items = await asyncio.gather(*tasks)

            return [MenuItem(**item) for item in items]

        finally:
            await page.close()

        return []


async def resolve_categories(root, info) -> typing.List[Category]:
    try:
        url = "https://www.pret.co.uk/en-gb/our-menu/"

        browser = await get_browser()
        page = await browser.newPage()
        await page.goto(url)

        elements = await page.querySelectorAll(
            ".section-menu a.menu-item[href*=our-menu]"
        )

        categories = await asyncio.gather(
            *[
                page.evaluate(
                    """(element) => ({
                        name: element.textContent.trim(),
                        link: element.getAttribute('href'),
                    })""",
                    element,
                )
                for element in elements
            ]
        )

        return [Category(**category) for category in categories]
    finally:
        await page.close()

    return []


@strawberry.type
class Query:
    categories: typing.List[Category] = strawberry.field(
        resolver=resolve_categories
    )

    @strawberry.field
    async def category(self, info, slug: str) -> typing.Optional[Category]:
        categories = await resolve_categories(None, info)

        category = next(
            (x for x in categories if x.name.lower() == slug), None
        )

        return category


schema = strawberry.Schema(query=Query)
