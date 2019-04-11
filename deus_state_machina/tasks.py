from django.core.exceptions import ImproperlyConfigured

try:
    from celery.task import Task
except ImportError:
    class Task:
        def __init__(self, *args, **kwargs):
            raise ImproperlyConfigured('You must install celery to be able to use async transitions!')
from django.apps import apps


class TransitionTask(Task):
    @classmethod
    def schedule_transition(
        cls, obj, state_machine_field, target_state_or_edge, transition_through=False, *args, **kwargs
    ):
        from django.contrib.contenttypes.models import ContentType
        from deusstatemachina import Transition

        if isinstance(target_state_or_edge, Transition):
            transition: Transition = target_state_or_edge
            transition_to = {'type': 'edge', 'method_name': transition.side_effect.__name__}
        else:
            transition_to = {'type': 'state', 'target_state': target_state_or_edge}

        content_type = ContentType.objects.get_for_model(obj)
        TransitionTask().delay(
            content_type.app_label,
            content_type.model,
            obj.pk,
            state_machine_field,
            transition_to,
            transition_through,
            transition_args=args,
            transition_kwargs=kwargs,
        )

    def run(
        self,
        app_label,
        model,
        pk,
        state_machine_field,
        transition_to,
        transition_through,
        transition_args,
        transition_kwargs,
        *args,
        **kwargs
    ):
        Model = apps.get_model(app_label, model)
        obj = Model.objects.get(pk=pk)
        state_machine = getattr(obj, state_machine_field)
        if transition_to['type'] == 'state':
            target_state = transition_to['target_state']
            if transition_through:
                state_machine.transition_through(target_state)
            else:
                state_machine.transition_to(target_state, *transition_args, **transition_kwargs)
        elif transition_to['type'] == 'edge':
            getattr(state_machine, transition_to['method_name'])(*transition_args, **transition_kwargs)
