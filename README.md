django-eventtools is a lightweight library designed to handle repeating and
one-off event occurrences for display on a website.


## Usage

Given the following models:

    from django.db import models

    from eventtools.models import BaseEvent, BaseOccurrence


    class Event(BaseEvent):
        title = models.CharField(max_length=100)


    class Occurrence(BaseOccurrence):
        event = models.ForeignKey(Event)

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

For each event instance you can do the following to get occurrences, which are
returned as pairs of datetimes - i.e. `(start, end)`, or a python generator
yielding occurrence pairs

    >>> event.next_occurrence
    >>> event.all_occurrences()
    >>> event.all_occurrences(from_date=datetime(2015, 1, 1, 10, 0))
    >>> event.all_occurrences(to_date=date(2016, 1, 1))
    >>> event.all_occurrences(to_date=date(2016, 1, 1),
                              to_date=date(2016, 12, 31))


Querysets can also be filtered, but this is less efficient so you should work
with occurrences where possible.

    >>> Event.objects.for_period(from_date=date(2015, 1, 1),
                                 to_date=date(2015, 12, 31))

All these methods work for occurrence

If you need more information about the occurrence than just a pair of dates,
add an occurrence_data property to your BaseOccurrence subclass - i.e.

    class Occurrence(BaseOccurrence):
        event = models.ForeignKey(Event)

        @property
        def occurrence_data(self):
            return {
                'event_title': self.event.title
            }

The result will be appended to the occurrence tuple, i.e. `(start, end, data)`


## Running tests

Assuming virtualenvwrapper is installed:

    > cd path-to/django-eventtools
    > mkvirtualenv test
    > ./setup.py install
    > ./runtests.py


## Todo

- Handle from_date more efficiently in BaseOccurrence.all_occurrences 
