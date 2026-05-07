import pytest


@pytest.fixture
def sample_course_units():
    from diploma_equivalence.domain.models import CourseUnit, DisciplineType, Institution

    return [
        CourseUnit(
            institution=Institution.UFPE,
            code="IF755",
            title="Algoritmos e Estruturas de Dados",
            type=DisciplineType.OBRIGATORIO,
            ch_total=60,
            syllabus="Algoritmos de busca e ordenação. Estruturas lineares e não-lineares.",
        ),
        CourseUnit(
            institution=Institution.UFPE,
            code="IF766",
            title="Programação Concorrente",
            type=DisciplineType.ELETIVO,
            ch_total=60,
            syllabus="Threads, semáforos, monitores, memória compartilhada.",
        ),
    ]
