"""Tests for Chapter 7, Exercise 2 — parsing what models actually emit."""

from chapters.ch07_planning.exercises.exercise_1_plan import StepStatus
from chapters.ch07_planning.exercises.exercise_2_parse import json_array, parse_plan


class TestJsonArray:
    def test_plain(self):
        assert json_array('[1, 2]') == [1, 2]

    def test_empty_input(self):
        assert json_array("") == []
        assert json_array(None) == []

    def test_prose_around_it(self):
        assert json_array('Here is the plan: [1, 2] Hope that helps!') == [1, 2]

    def test_markdown_fence(self):
        assert json_array('```json\n[1, 2]\n```') == [1, 2]

    def test_fence_with_prose_outside(self):
        raw = 'Sure!\n```json\n[{"a": 1}, {"b": 2}]\n```\nLet me know.'
        assert len(json_array(raw)) == 2

    def test_malformed_json(self):
        assert json_array('[1, 2,') == []

    def test_an_object_is_not_an_array(self):
        assert json_array('{"a": 1}') == []


class TestParsePlan:
    def test_basic(self):
        p = parse_plan("goal", '[{"id":1,"description":"a"},{"id":2,"description":"b"}]')
        assert p.goal == "goal"
        assert len(p) == 2
        assert p.get(1).description == "a"

    def test_empty_input_gives_an_empty_plan(self):
        p = parse_plan("goal", "nonsense")
        assert len(p) == 0

    def test_dependencies(self):
        p = parse_plan("g", '[{"id":1,"description":"a"},'
                            '{"id":2,"description":"b","depends_on":[1]}]')
        assert p.get(2).depends_on == [1]

    def test_missing_depends_on(self):
        assert parse_plan("g", '[{"id":1,"description":"a"}]').get(1).depends_on == []

    def test_plain_strings_instead_of_objects(self):
        # models ignore your schema sometimes
        p = parse_plan("g", '["do this", "do that"]')
        assert len(p) == 2
        assert p.get(1).description == "do this"

    def test_step_key_instead_of_description(self):
        assert parse_plan("g", '[{"id":1,"step":"do it"}]').get(1).description == "do it"

    def test_empty_description_is_skipped(self):
        p = parse_plan("g", '[{"id":1,"description":""},{"id":2,"description":"real"}]')
        assert len(p) == 1

    def test_string_ids(self):
        assert parse_plan("g", '[{"id":"1","description":"a"}]').get(1) is not None

    def test_missing_ids_are_assigned(self):
        p = parse_plan("g", '[{"description":"a"},{"description":"b"}]')
        assert sorted(s.id for s in p.steps) == [1, 2]

    def test_non_dict_non_string_items_are_skipped(self):
        assert len(parse_plan("g", '[123, null, {"id":1,"description":"a"}]')) == 1


class TestRepairs:
    def test_dangling_dependency_is_dropped(self):
        # otherwise nothing is EVER ready and the executor hangs
        p = parse_plan("g", '[{"id":1,"description":"a","depends_on":[99]}]')
        assert p.get(1).depends_on == []
        assert [s.id for s in p.ready_steps()] == [1]

    def test_self_dependency_is_dropped(self):
        p = parse_plan("g", '[{"id":1,"description":"a","depends_on":[1]}]')
        assert p.get(1).depends_on == []

    def test_cycle_is_broken(self):
        raw = ('[{"id":1,"description":"a","depends_on":[2]},'
               '{"id":2,"description":"b","depends_on":[1]}]')
        p = parse_plan("g", raw)
        assert p.ready_steps(), "a cycle means nothing is ever ready: a silent hang"

    def test_three_way_cycle_is_broken(self):
        raw = ('[{"id":1,"description":"a","depends_on":[3]},'
               '{"id":2,"description":"b","depends_on":[1]},'
               '{"id":3,"description":"c","depends_on":[2]}]')
        assert parse_plan("g", raw).ready_steps()

    def test_forward_dependencies_are_removed(self):
        # step 1 depending on step 2 is a back-edge once you order by position
        raw = ('[{"id":1,"description":"a","depends_on":[2]},'
               '{"id":2,"description":"b"}]')
        p = parse_plan("g", raw)
        assert p.get(1).depends_on == []

    def test_legitimate_dependencies_survive_repair(self):
        raw = ('[{"id":1,"description":"a"},{"id":2,"description":"b"},'
               '{"id":3,"description":"c","depends_on":[1,2]}]')
        p = parse_plan("g", raw)
        assert p.get(3).depends_on == [1, 2]

    def test_unparseable_dependency_entries_are_dropped(self):
        p = parse_plan("g", '[{"id":1,"description":"a","depends_on":["x",null]}]')
        assert p.get(1).depends_on == []

    def test_every_plan_has_at_least_one_ready_step(self):
        # the invariant that matters: whatever the model emits, we can start
        for raw in [
            '[{"id":1,"description":"a","depends_on":[2]},{"id":2,"description":"b","depends_on":[1]}]',
            '[{"id":1,"description":"a","depends_on":[7]}]',
            '["a","b","c"]',
            '[{"id":1,"description":"a","depends_on":[1]}]',
        ]:
            p = parse_plan("g", raw)
            assert p.ready_steps(), f"deadlock from: {raw}"
