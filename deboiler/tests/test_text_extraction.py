from dataclasses import dataclass

import pytest

from deboiler import Deboiler
from deboiler.dataset.json_dataset import JsonDataset
from deboiler.tests.fixtures import get_fixture_path


@dataclass
class ExamplePage:
    url: str
    title: str
    headings: list[str]
    lists: list[str]
    language: str


example_pages = [
    ExamplePage(
        url="https://www.globality.com/innovation-blog",
        title="Globality | Innovation Blog",
        headings=[
            "From Our Corner of the Globe",
            "The Globality Innovation Blog",
            "Subscribe",
            "Follow Us",
        ],
        lists=[
            "* All",
            "* Categories",
        ],
        language="en",
    ),
    ExamplePage(
        url="https://www.globality.com/es/why-globality",
        title="Globality | Por qué Globality",
        headings=[
            "Define el alcance en horas en lugar de meses",
            "Prueba la verdadera contratación autogestionada",
            "Ahorro de costos comprobado",
            "Ahorros de costos en todos los sectores",
            "Reinventa la contratación. Remodela el negocio.",
            "Proceso tradicional de contratación",
            "Smart Sourcing potenciado por IA",
            "Exclusivamente inclusivo",
            "Revoluciona la contratación. Para siempre.",
        ],
        lists=[
            "* Incremento de los costos por sobrecompra o aumento del alcance",
            "* Compras poco óptimas debido a la falta de datos",
            "* Proceso oneroso y lento desde la definición hasta la concesión",
            "* Falta de alineación en los objetivos y métricas del negocio",
            "* Aumento significativo del ahorro de costos",
            "* Toma de decisiones efectiva impulsada por los datos",
            "* Proceso acelerado de contratación guiado por IA",
            "* Alineación de las partes interesadas mediante el uso de herramientas de colaboración en tiempo real",
        ],
        language="es",
    ),
]


dataset = JsonDataset(
    get_fixture_path() / "globality.com.jsonl", status_key=None, content_type_key=None
)
deboiler = Deboiler(n_processes=1)


@pytest.mark.parametrize("example_page", example_pages)
def test_text_extraction(example_page):
    raw_page = dataset[example_page.url]
    parsed_page = raw_page.parse()
    output_page = deboiler.transform_parsed_page(parsed_page)

    for attrib in ["title", "language"]:
        assert getattr(output_page, attrib) == getattr(example_page, attrib)

    for attrib in ["lists", "headings"]:
        assert all(
            item_text in getattr(output_page, attrib) for item_text in getattr(example_page, attrib)
        )


# TODO
# add test coverage for breadcrumb extraction
