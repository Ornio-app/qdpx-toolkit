"""Unit tests for the plain dataclass model in refi_qda.model.

These construct model objects directly (no XML involved) to verify the
model's own behaviour -- hierarchy flattening and Project's GUID lookup
helpers -- independent of the parser.
"""

from __future__ import annotations

from refi_qda.model import (
    Case,
    Code,
    Memo,
    Project,
    Source,
    TextSource,
    Variable,
    VariableType,
)


def _make_codebook() -> list[Code]:
    grandchild = Code(guid="c3", name="Diet", is_codable=True)
    child = Code(guid="c2", name="Health", is_codable=True, children=[grandchild])
    folder = Code(guid="c1", name="Topics", is_codable=False, children=[child])
    return [folder]


def test_code_iter_all_is_depth_first_and_includes_self() -> None:
    folder = _make_codebook()[0]
    names = [code.name for code in folder.iter_all()]
    assert names == ["Topics", "Health", "Diet"]


def test_code_folder_is_not_codable() -> None:
    folder = _make_codebook()[0]
    assert folder.is_codable is False
    assert folder.children[0].is_codable is True


def test_memo_is_a_text_source_alias() -> None:
    # Memo is intentionally a type alias, not a subclass -- see model.py.
    assert Memo is TextSource
    memo = Memo(guid="m1", name="A memo", plain_text_content="hello")
    assert isinstance(memo, TextSource)


def test_project_iter_codes_flattens_whole_codebook() -> None:
    project = Project(name="Test", codebook=_make_codebook())
    guids = {code.guid for code in project.iter_codes()}
    assert guids == {"c1", "c2", "c3"}


def test_project_find_code_searches_nested_hierarchy() -> None:
    project = Project(name="Test", codebook=_make_codebook())
    found = project.find_code("c3")
    assert found is not None
    assert found.name == "Diet"
    assert project.find_code("does-not-exist") is None


def test_project_find_source_only_searches_top_level() -> None:
    source: Source = TextSource(guid="s1", name="doc.txt")
    project = Project(name="Test", sources=[source])
    assert project.find_source("s1") is source
    assert project.find_source("s2") is None


def test_project_find_case_and_variable() -> None:
    variable = Variable(guid="v1", name="Age", type_of_variable=VariableType.INTEGER)
    case = Case(guid="k1", name="Participant 1")
    project = Project(name="Test", variables=[variable], cases=[case])
    assert project.find_variable("v1") is variable
    assert project.find_case("k1") is case
    assert project.find_variable("missing") is None
