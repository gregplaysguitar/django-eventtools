# Example

    # myapp/models.py

    from django.db import models

    from eventtools.models import BaseEvent, BaseOccurrence


    class Event(BaseEvent):
        title = models.CharField(max_length=100)


    class Occurrence(BaseOccurrence):
        event = models.ForeignKey(Event)


## Usage

Create a sample event & occurrences

    >>> from datetime import datetime
    >>> from dateutil import rrule
    >>> from myapp.models import Event
    >>> event = Event.objects.create(title='Test event')
    >>> once_off = Occurrence.objects.create(
            event=event,
            start=datetime(2016, 1, 1, 12, 0),
            end=datetime(2016, 1, 1, 2, 0))
    >>> christmas = Occurrence.objects.create(
            event=event,
            start=datetime(2015, 12, 25, 7, 0),
            end=datetime(2015, 12, 25, 22, 0),
            repeat.rrule.YEARLY)
    >>> daily = Occurrence.objects.create(
            event=event,
            start=datetime(2016, 1, 1, 7, 0),
            end=datetime(2016, 1, 1, 8, 0),
            repeat.rrule.DAILY)

Get occurrences

    >>> event.all_occurrences()

## Occurrence data


## Running tests

Assuming virtualenvwrapper is installed:

    > cd path-to/django-eventtools
    > mkvirtualenv test
    > ./setup.py install
    > ./runtests.py


## Todo

- Handle from_date more efficiently in BaseOccurrence.all_occurrences 
