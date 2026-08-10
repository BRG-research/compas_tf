"""``BaseModel.find_groups_with_names`` - lifting an assembly out of a big model."""

import pytest
from compas.geometry import Translation
from compas_model.elements import BeamElement
from compas_model.elements import Group

from compas_tf.base_model import ModelElementNotFound
from compas_tf.model import TFModel


def _model():
    """Two nested groups plus a loose one, wired like the floor model.

    floor/quarter_0/beam_a --- beam_b \\quarter_1
                         \\--- bolt    (loose, its own top-level group)

    Plus two dowels with no interaction at all - the contact search skips the
    fasteners in the real model - one sitting in quarter_0, one far away.
    """
    model = TFModel(name="test")
    floor = model.add_element(Group(name="floor"))
    quarter_0 = model.add_element(Group(name="quarter_0"), parent=floor)
    quarter_1 = model.add_element(Group(name="quarter_1"), parent=floor)
    fasteners = model.add_element(Group(name="fasteners"))

    beam_a = model.add_element(BeamElement(width=1, depth=1, length=2, name="beam_a"), parent=quarter_0)
    beam_b = model.add_element(BeamElement(width=1, depth=1, length=2, name="beam_b"), parent=quarter_1)
    bolt = model.add_element(BeamElement(width=1, depth=1, length=1, name="bolt"), parent=fasteners)

    model.add_element(BeamElement(width=0.1, depth=0.1, length=0.5, name="dowel_in"), parent=fasteners)
    dowel_out = model.add_element(BeamElement(width=0.1, depth=0.1, length=0.5, name="dowel_out"), parent=fasteners)
    dowel_out.transformation = Translation.from_vector([100, 0, 0])

    model.add_interaction(beam_a, beam_b)
    model.add_interaction(beam_a, bolt)
    model.add_interaction(beam_b, bolt)
    return model


def _names(model):
    return {element.name for element in model.elements()}


def test_interactions_between_the_extracted_groups_survive():
    """The reason this exists at all.

    Extracting the groups one at a time and merging the results keeps only the
    interactions internal to each - the joint BETWEEN them, which is the one you
    asked for, is exactly what gets dropped.
    """
    model = _model()

    together = model.find_groups_with_names(["quarter_0", "quarter_1"])
    assert together.graph.number_of_edges() == 1

    separately = TFModel(name="separately").merge(
        [
            model.find_group_with_name("quarter_0"),
            model.find_group_with_name("quarter_1"),
        ]
    )
    assert separately.graph.number_of_edges() == 0


def test_ancestors_are_kept_pruned_to_the_groups_asked_for():
    """Unlike ``find_group_with_name``, which drops the ancestors and folds their
    placement into the model transformation, so group transformations further up
    would have to be re-applied by hand."""
    extracted = _model().find_groups_with_names(["quarter_0"])

    assert _names(extracted) == {"floor", "quarter_0", "beam_a"}
    assert extracted.find_element_with_name("beam_a").treenode.parent.element.name == "quarter_0"


def test_neighbors_brings_in_the_loose_fasteners_without_cascading():
    """A bay is bolted together with elements that live outside it.

    Only one step out, though: the bolt also touches ``beam_b``, and if the
    walk continued from what it just pulled in, the whole model would follow one
    edge at a time.
    """
    model = _model()

    assert _names(model.find_groups_with_names(["quarter_0"])) == {"floor", "quarter_0", "beam_a"}
    assert _names(model.find_groups_with_names(["quarter_0"], neighbors=True)) == {
        "floor",
        "quarter_0",
        "beam_a",
        "quarter_1",
        "beam_b",
        "fasteners",
        "bolt",
        "dowel_in",  # no interaction at all - found by its box, see below
    }


def test_an_element_with_no_interaction_is_found_by_its_box():
    """The contact search skips the fasteners - a faceted dowel touches its own
    hole once per facet - so they have no graph edge and the neighbour walk is
    blind to them. Geometry is the only signal left, and it must not reach
    beyond the bay."""
    extracted = _names(_model().find_groups_with_names(["quarter_0"], neighbors=True))

    assert "dowel_in" in extracted
    assert "dowel_out" not in extracted


def test_the_source_is_left_untouched_and_the_copy_is_independent():
    model = _model()

    extracted = model.find_groups_with_names(["quarter_0", "quarter_1"], name="bay")

    assert extracted.name == "bay"
    assert len(list(model.elements())) == 9  # 4 groups + 3 beams + 2 dowels
    assert model.graph.number_of_edges() == 3
    guids = {element.guid for element in model.elements()}
    assert not guids & {element.guid for element in extracted.elements()}


def test_a_name_that_matches_no_group_is_an_error():
    """Silently returning the groups that did match would hand back a model that
    looks fine and is missing a wing of the building."""
    with pytest.raises(ModelElementNotFound):
        _model().find_groups_with_names(["quarter_0", "quarter_9"])
