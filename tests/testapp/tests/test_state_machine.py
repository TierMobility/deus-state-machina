from django.test import TestCase
from unittest.mock import patch

from tests.testapp.models import StateMachineTestModel, TestStates


class TestStateMachineField(TestCase):
    @patch('tests.testapp.models.StateMachineTestModel.do_side_effect')
    def test_successful_state_transition(self, side_effect_mock):
        obj = StateMachineTestModel()
        self.assertEqual(TestStates.START, obj.state)
        obj.state_machine.transition_to(
            TestStates.TRANSITION_TO_MIDDLE_ENABLED, can_transition_to_middle=True
        )
        self.assertEqual(TestStates.TRANSITION_TO_MIDDLE_ENABLED, obj.state)
        obj.state_machine.go_to_middle()
        obj.state_machine.transition_to(TestStates.ANOTHER_END)
        self.assertEqual(TestStates.ANOTHER_END, obj.state)
        self.assertEqual(1, side_effect_mock.call_count)

    def test_failure(self):
        obj = StateMachineTestModel()
        self.assertEqual(TestStates.START, obj.state)
        obj.state_machine.transition_to(TestStates.THE_WAY_TO_FAILURE)
        obj.state_machine.transition_to(TestStates.FAILURE_IS_ACTUALLY_AN_OPTION)
        self.assertEqual(TestStates.FAIL, obj.state)

    def test_failure_transition_through(self):
        obj = StateMachineTestModel()
        self.assertEqual(TestStates.START, obj.state)
        obj.state_machine.transition_through(TestStates.FAILURE_IS_ACTUALLY_AN_OPTION)
        self.assertEqual(TestStates.FAIL, obj.state)

    def test_transition_by_side_effect_name(self):
        obj = StateMachineTestModel()
        self.assertEqual(TestStates.START, obj.state)
        obj.state_machine.enable_transition_to_middle(can_transition_to_middle=True)
        self.assertEqual(obj.state, TestStates.TRANSITION_TO_MIDDLE_ENABLED)

    def test_transition_by_side_effect_wrong_params(self):
        obj = StateMachineTestModel()
        self.assertEqual(TestStates.START, obj.state)
        with self.assertRaises(TypeError):
            obj.state_machine.enable_transition_to_middle()
        self.assertEqual(obj.state, TestStates.START)

    def test_transition_to_side_effect_wrong_method_name(self):
        obj = StateMachineTestModel()
        self.assertEqual(TestStates.START, obj.state)
        with self.assertRaises(AttributeError):
            obj.state_machine.i_dont_exist()
        self.assertEqual(obj.state, TestStates.START)
