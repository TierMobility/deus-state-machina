Deus State Machina
==================

Deus State Machina is a state machine for django that makes sure that you're
not accidentally shooting yourself in the foot when doing things concurrently.

Deus state machina gives you:

 - One place to define your state machine transitions
 - No need for state checking
 - No more saving your model manually
 - State transitions define which how the model changes
 - No more race conditions!
    (for both database and threading)

Getting started
---------------

```pip install deus-state-machina```

Example:
--------

Given that you have code that works like this:

```python
UNKNOWN = 0
ALIVE = 1
DEAD = 2

class Cat(models.Model):                
    state = IntegerField(choices=[
        (UNKNOWN, 'Unknown'), 
        (ALIVE, 'Alive'), 
        (DEAD, 'Dead'),
    ])
    can_meow = models.Boolean(default=False)
    time_of_death = models.DateTimeField(null=True)

    def survive(self):
        if self.state == UNKNOWN:
            self.state = ALIVE 
            self.can_meow = True
            self.save()

    def rip(self):
        if self.state == UNKNOWN: 
            self.state = DEAD 
            self.time_of_death = now()
            self.save()
```

You can use deus state machina instead like so:

You define your state machine:

```python
from deus_state_machina import State, StateMachine

class CatStateMachine(StateMachine):
    Unknown = State(0)
    Alive = State(1)
    Dead = State(2)

    def survive(self, instance, transition):
        instance.can_meow = True

    def rip(self, instance, transition):
        instance.time_of_death = now()

    transitions = [
        Unknown | survive | Alive,
        Unknown | rip | Dead,
    ]
```

Note how you have to wrap each state as `State`.

You can then use this in your model:
   
```python 
from deus_state_machina import StateMachineField

class Cat(models.Model):
    state = models.IntegerField(choices=...)
    state_machine = StateMachineField(CatStateMachine, 'state')
```
You can then trigger a state transition like this:

```python
cat = Cat.objects.first()
if random.random() > 0.5:
    cat.state_machine.survive()
else:
    cat.state_machine.rip()
```
Or alternatively, using the target state in the `transition_to` call:

```python
cat = Cat.objects.first()
if random.random() > 0.5:
    cat.state_machine.transition_to(ALIVE)
else:
    cat.state_machine.transition_to(DEAD)
```
You can integrate deus state machine step by step replacing
one state transition at a time. Note that it has database
locking and thread locking overhead compared to cowboy state
machines.
