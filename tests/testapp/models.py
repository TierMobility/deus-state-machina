from django.db import models
from django.db.models import IntegerField

from deus_state_machina import StateMachine, State, precondition, TransitionFailed
from deus_state_machina.fields import StateMachineField


class TestStates:
    START = 0
    TRANSITION_TO_MIDDLE_ENABLED = 1
    MIDDLE = 2
    END = 3
    ANOTHER_END = 4

    THE_WAY_TO_FAILURE = 5
    FAILURE_IS_ACTUALLY_AN_OPTION = 6
    FAIL = 7

    @classmethod
    def choices(cls):
        return [(v, k) for k, v in cls.__dict__.items() if not k.startswith('_') and k[0].upper() == k[0]]


class TestStateMachine(StateMachine):
    Start = State(TestStates.START)
    TransitionToMiddleEnabled = State(TestStates.TRANSITION_TO_MIDDLE_ENABLED)
    Middle = State(TestStates.MIDDLE)
    End = State(TestStates.END)
    AnotherEnd = State(TestStates.ANOTHER_END)

    TheWayToFailure = State(TestStates.THE_WAY_TO_FAILURE)
    Fail = State(TestStates.FAIL)
    FailureIsActuallyAnOption = State(TestStates.FAILURE_IS_ACTUALLY_AN_OPTION)

    def enable_transition_to_middle(self, obj, transition, *, can_transition_to_middle):
        obj.can_transition_to_middle = can_transition_to_middle

    @precondition(lambda obj: obj.can_transition_to_middle)
    def go_to_middle(self, obj, transition):
        pass

    @precondition(lambda obj: False)
    def never_gonna_happen(self, obj, transition):
        pass

    @precondition(lambda obj: True)
    def do_side_effect(self, obj, transition):
        obj.do_side_effect()

    def this_transition_will_fail(self, obj, transition):
        raise TransitionFailed(TestStates.FAIL)

    start = TestStates.START
    transitions = [
        Start | enable_transition_to_middle | TransitionToMiddleEnabled,
        Start | None | TheWayToFailure,
        TheWayToFailure | this_transition_will_fail | FailureIsActuallyAnOption,
        TheWayToFailure | None | Fail,
        TransitionToMiddleEnabled | go_to_middle | Middle,
        Middle | never_gonna_happen | End,
        Middle | do_side_effect | AnotherEnd,
    ]


class StateMachineTestModel(models.Model):
    state = IntegerField(default=TestStates.START, choices=TestStates.choices())
    state_machine = StateMachineField(TestStateMachine, 'state')
    can_transition_to_middle = models.BooleanField(default=False)

    def do_side_effect(self):
        pass
