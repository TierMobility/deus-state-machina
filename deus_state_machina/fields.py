from django.db.models import Field

class BoundStateMachine:
    def __init__(self, state_machine, obj):
        self.state_machine = state_machine
        self.obj = obj

    def get_current_state(self):
        return self.state_machine.get_current_state(self.obj)

    def transition_to(self, state, *args, **kwargs):
        return self.state_machine.transition_to(self.obj, state, *args, **kwargs)

    def transition_through(self, state):
        return self.state_machine.transition_through(self.obj, state)

    def async_transition_to(self, state, *args, **kwargs):
        return self.state_machine.async_transition_to(self.obj, state, *args, **kwargs)

    def async_transition_through(self, state, *args, **kwargs):
        return self.state_machine.async_transition_through(self.obj, state, *args, **kwargs)

    def auto_transition(self):
        return self.state_machine.auto_transition(self.obj)

    def __getattr__(self, item):
        # allow triggering state transitions by calling the edges/side_effect name on the state_machine,
        # e.g. for a state machine like this:
        #   [Start | do_stuff | End]
        # you can either call:
        #   state_machine.transition_to(END)
        # or you call the edge:
        #   state_machine.do_stuff()
        # depending on you knowing which edge you want to take, or which state you want to reach
        try:
            return super().__getattr__(item)
        except AttributeError:
            if item not in self.state_machine._all_side_effect_names:
                raise

            def closure(*args, **kwargs):
                as_task = kwargs.pop('as_task', False)
                transition = self.state_machine._select_transition_for_side_effect_name(self.obj, item)
                if as_task:
                    self.async_transition_to(transition, **kwargs)
                else:
                    self.transition_to(transition, *args, **kwargs)

            return closure


class StateMachineFieldProxy(object):
    def __init__(self, state_machine):
        self.state_machine = state_machine

    def __get__(self, instance, owner):
        return BoundStateMachine(self.state_machine, instance)


class StateMachineField:
    def __init__(self, state_machine_class, state_field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_machine_class = state_machine_class
        self.state_field_name = state_field_name

    # def deconstruct(self):
    #     name, path, args, kwargs = super().deconstruct()
    #     kwargs["state_machine_class"] = self.state_machine_class
    #     kwargs["state_field_name"] = self.state_field_name
    #     return name, path, args, kwargs

    def contribute_to_class(self, cls, name, **kwargs):
        handler = self.state_machine_class(name, self.state_field_name)
        proxy = StateMachineFieldProxy(handler)
        setattr(cls, name, proxy)
