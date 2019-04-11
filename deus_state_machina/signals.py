from django.dispatch import Signal

state_changed = Signal(providing_args=['instance', 'state'])


def emit_signal_on_state(model, target_field_name, target_state, signal):
    def handler(instance, state, field_name, **kwargs):
        if field_name != target_field_name or state != target_state:
            return
        signal.send(sender=model, instance=instance)

    state_changed.connect(handler, sender=model, weak=False)
