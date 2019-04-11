from collections import defaultdict
from contextlib import ExitStack
from dataclasses import dataclass
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property

from .fields import StateMachineField
from .signals import state_changed
from .tasks import TransitionTask
from .utils import lock_object, thread_lock_object


__version__ = '0.1.0'


class TransitionException(Exception):
    pass


@dataclass
class Transition:
    start: int
    end: int
    precondition: callable = None
    side_effect: callable = None


def precondition(precondition):
    def wrap(func):
        func._precondition = precondition
        return func
    return wrap


class StartAndTransition:
    def __init__(self, state, transition):
        self.state = state
        self.transition = transition

    def __str__(self):
        return f'{self.state} -> {self.transition.__name__}'

    def __or__(self, other):
        if not isinstance(other, State):
            raise ImproperlyConfigured('Must use the transition operator `|` from a `State` to a callable')
        precondition = getattr(self.transition, '_precondition', None)
        return Transition(
            start=self.state.value,
            end=other.value,
            side_effect=self.transition,
            precondition=precondition,
        )


class State:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value.name

    def __or__(self, other):
        # the transition function must be callable, or be None, if there is no side_effect
        if not callable(other) and other is not None:
            raise ImproperlyConfigured('Must use the transition operator `>` from a `State` to a callable')
        return StartAndTransition(self, other)


class TransitionFailed(Exception):
    def __init__(self, error_state, **kwargs):
        self.error_state = error_state
        self.kwargs = kwargs


class GraphNode:
    def __init__(self, name):
        self.name = name
        self.targets = []

    def __str__(self):
        return f'{self.name.name}'

    def __repr__(self):
        return str(self)

    def find(self, goal_name, visited_nodes=None):
        if visited_nodes is None:
            visited_nodes = set()
        if self.name == goal_name:
            return [self]
        for t in self.targets:
            if t in visited_nodes:  # do not loop
                continue
            visited_nodes.add(t)
            found = t.find(goal_name, visited_nodes)
            if found:
                return [self, *found]


class keyeddefaultdict(defaultdict):
    def __missing__(self, key):
        node = self[key] = self.default_factory(key)
        return node


class StateMachine:
    start = None
    transitions = None

    def __init__(self, field_name, state_field_name):
        if self.__class__.start is None:
            raise ImproperlyConfigured('You must set a `start` state')
        if self.__class__.transitions is None:
            raise ImproperlyConfigured('You must set a `transitions` to a list of `Transition` objects')
        self.field_name = field_name
        self.state_field_name = state_field_name

    def get_possible_transitions(self, obj):
        current = self.get_current_state(obj)
        for t in self.transitions:
            if t.start == current and (t.precondition is None or t.precondition(obj)):
                yield t

    def get_current_state(self, obj):
        return getattr(obj, self.state_field_name)

    def _how_to_get_to(self, obj, target_state):
        nodes = keyeddefaultdict(GraphNode)
        for tr in self.transitions:
            nodes[tr.start].targets.append(nodes[tr.end])
        current_state = self.get_current_state(obj)
        graph_edges = nodes[current_state].find(target_state)
        if graph_edges:
            return [e.name for e in graph_edges[1:]]  # leave out the start state

    def transition_through(self, obj, target_state):
        states = self._how_to_get_to(obj, target_state)
        while states:
            self.transition_to(obj, states[0])
            states = self._how_to_get_to(obj, target_state)

    def _possible_next_transitions(self, obj):
        current = self.get_current_state(obj)
        # find the proper transition
        return (transition for transition in self.transitions if transition.start == current)

    @cached_property
    def _all_side_effect_names(self):
        return set(t.side_effect.__name__ for t in self.transitions if t.side_effect)

    def _select_transition_for_side_effect_name(self, obj, side_effect_name):
        for t in self._possible_next_transitions(obj):
            if t.side_effect.__name__ == side_effect_name:
                return t
        raise TransitionException(
            f'Cannot transition from {self.get_current_state(obj).name} to using side effect {side_effect_name}'
        )

    def pretty_state_name(self, obj, state):
        try:
            field = next(field for field in obj.__class__._meta.get_fields() if field.name == self.state_field_name)
        except StopIteration:
            return ''
        try:
            return next(name for val, name in field.choices if val == state)
        except:
            return ''

    def _select_transitions_for_end_state(self, obj, end_state):
        transitions = list(t for t in self._possible_next_transitions(obj) if t.end == end_state)
        if transitions:
            return transitions
        current = self.get_current_state(obj)
        current_label = self.pretty_state_name(obj, current)
        end_label = self.pretty_state_name(obj, end_state)
        raise TransitionException(f'Cannot transition from {str(current)} ({current_label}) to {str(end_state)} ({end_label})')

    def _perform_transition(self, obj, transition, *args, **kwargs):
        # validate precondition
        if transition.precondition is not None and not transition.precondition(obj):
            side_effect_name = f' using "{transition.side_effect.__name__}"' if transition.side_effect else ''
            raise TransitionException(
                f'Cannot transition from {transition.start.name} to {transition.end.name}{side_effect_name}, precondition failed!'
            )
        # try to execute the side_effect
        try:
            if transition.side_effect is not None:
                transition.side_effect(self, obj, transition, *args, **kwargs)
            new_state = transition.end
            setattr(obj, self.state_field_name, new_state)
            # trigger any automatic transitions that might happen after this one
            obj.save()
            return self.get_current_state(obj)
        except TransitionFailed as exc:
            # transition to an error state if this transition failed
            return self.transition_to(obj, exc.error_state, **exc.kwargs)

    def _transition_to(self, obj, state_or_transition, *args, **kwargs):
        if isinstance(state_or_transition, Transition):
            transition = state_or_transition
        else:
            if isinstance(state_or_transition, State):
                # unpack the value of the State wrapper to allow calling `transition_to` using
                # the original enum, or using the wrapped `State(enum)`
                state_or_transition = state_or_transition.value
            transitions = self._select_transitions_for_end_state(obj, state_or_transition)
            if len(transitions) > 1:
                start = transitions[0].start.name
                end = transitions[0].end.name
                edge_names = ', '.join(t.side_effect.__name__ for t in transitions)
                raise TransitionException(
                    f'Ambigious transition: {start} -> {end}, call one of the edges instead: {edge_names}'
                )
            transition = transitions[0]
        return self._perform_transition(obj, transition, *args, **kwargs)

    def transition_to(self, obj, state_or_transition, *args, **kwargs):
        # the object could only be modified concurrently in another thread, so let's lock it
        with ExitStack() as es:
            es.enter_context(thread_lock_object(obj))
            if obj.pk:
                # if this object was saved already, we need to lock it to make sure there are no
                # concurrent modifications happening
                es.enter_context(lock_object(obj))
                # now that we have the locks, reload the object from db to prevent errors due to local
                # manipultaions; This could be skipped if the state machine is the only machanism
                # that chagens the object, but this we cannot know
                obj.refresh_from_db()
            end_state = self._transition_to(obj, state_or_transition, *args, **kwargs)
        state_changed.send_robust(
            sender=obj.__class__, instance=obj, state=end_state, field_name=self.state_field_name
        )
        return end_state

    def async_transition_to(self, obj, state, transition_through=False, *args, **kwargs):
        if obj.pk is None:
            raise TransitionException(f'You need to `save()` the object to be able to transition async')
        if args or kwargs:
            raise ValueError('Async Transitions do not yet support parameterized transitions')
        TransitionTask.schedule_transition(
            obj, self.state_field_name, state, transition_through=transition_through
        )

    def async_transition_through(self, obj, state, *args, **kwargs):
        self.async_transition_to(obj, state, transition_through=True, *args, **kwargs)
