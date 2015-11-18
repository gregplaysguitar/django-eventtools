django-eventtools is a lightweight library designed to handle repeating and
one-off event occurrences for display on a website.

## Installation

Download the source from https://pypi.python.org/pypi/django-eventtools/
and run `python setup.py install`, or:

    > pip install django-eventtools

Django 1.8 or higher is required.


## Setup

Given the following models:

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

`Event` and `Occurrence` instances, and their associated querysets, all support
the `all_occurrences` method, which takes two optional arguments - `from_date`
and `to_date`, which may be dates or datetimes. `from_date` defaults to the
current day, `to_date` to `None`. The method returns a python generator
yielding tuples in the format `(start, end, data)` - for example:

    >>> Event.objects.all().all_occurrences()
    >>> event.all_occurrences(from_date=datetime(2015, 1, 1, 10, 0))
    >>> event.occurrence_set.all().all_occurrences(to_date=date(2016, 1, 1))
    >>> occurrence.all_occurrences(from_date=date(2016, 1, 1),
                                   to_date=date(2016, 12, 31))

A `next_occurrence` method is also provided, taking the same arguments,
but returning a single occurrence tuple.

    >>> event.next_occurrence()
    >>> event.next_occurrence(from_date=date(2016, 1, 1))


### Queryset filtering

Querysets can also be filtered, but due to uncertainty with repetitions,
from_date filtering is only an approximation (to_date filtering is accurate).
If you need a queryset filtered exactly, pass `exact=True` - this will filter
using occurrences but still return a queryset - but be careful with this as it
may be very slow. For example

    >>> Event.objects.for_period(from_date=date(2015, 1, 1),
                                 to_date=date(2015, 12, 31))
    >>> event.occurrence_set.for_period(from_date=date(2015, 1, 1), exact=True)


### Adding additional data to occurrence tuples

If you need more information about the occurrence than just a pair of dates,
add an occurrence_data property to your `BaseOccurrence` subclass - i.e.

    class Occurrence(BaseOccurrence):
        event = models.ForeignKey(Event)

        @property
        def occurrence_data(self):
            return {
                'event_title': self.event.title,
                'image': self.event.image,
            }

The result will be appended to the occurrence tuple, i.e. `(start, end, data)`


## Running tests

Assuming virtualenvwrapper is installed:

    > cd path-to/django-eventtools
    > mkvirtualenv test
    > ./setup.py install
    > ./runtests.py


## Todo

✔ Handle from_date more efficiently in BaseOccurrence.all_occurrences
- Test for_period methods with exact=False
- Python 3 tests (tox)
- Docs
