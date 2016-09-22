django-eventtools is a lightweight library designed to handle repeating and
one-off event occurrences for display on a website.

[![Circle CI](https://circleci.com/gh/gregplaysguitar/django-eventtools.svg?style=svg)](https://circleci.com/gh/gregplaysguitar/django-eventtools)
[![codecov](https://codecov.io/gh/gregplaysguitar/django-eventtools/branch/master/graph/badge.svg)](https://codecov.io/gh/gregplaysguitar/django-eventtools)
[![Latest Version](https://img.shields.io/pypi/v/django-eventtools.svg?style=flat)](https://pypi.python.org/pypi/django-eventtools/)


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
            repeat='RRULE:FREQ=YEARLY')
    >>> daily = Occurrence.objects.create(
            event=event,
            start=datetime(2016, 1, 1, 7, 0),
            end=datetime(2016, 1, 1, 8, 0),
            repeat='RRULE:FREQ=DAILY')

`Event` and `Occurrence` instances, and their associated querysets, all support
the `all_occurrences` method, which takes two optional arguments - `from_date`
and `to_date`, which may be dates or datetimes. `from_date` defaults to the
current day, `to_date` to `None`. The method returns a python generator
yielding tuples in the format `(start, end, instance)` - for example:

    >>> Event.objects.all().all_occurrences()
    >>> event.all_occurrences(from_date=datetime(2015, 1, 1, 10, 0))
    >>> event.occurrence_set.all().all_occurrences(to_date=date(2016, 1, 1))
    >>> occurrence.all_occurrences(from_date=date(2016, 1, 1),
                                   to_date=date(2016, 12, 31))

`instance` is an instance of the corresponding BaseOccurrence subclass.

A `next_occurrence` method is also provided, taking the same arguments,
but returning a single occurrence tuple.

    >>> event.next_occurrence()
    >>> event.next_occurrence(from_date=date(2016, 1, 1))

The method `first_occurrence` also returns a single occurrence tuple, but
takes no arguments.

### Queryset filtering

Event and Occurrence querysets can be filtered, but due to uncertainty
with repetitions, `from_date` filtering is only an approximation (whereas
`to_date` filtering is accurate). If you need a queryset filtered exactly,
pass `exact=True` - this will filter using generated occurrences but still
return a queryset - but be careful with this as it may be very slow and/or
CPU-hungry. For example

    >>> Event.objects.for_period(from_date=date(2015, 1, 1),
                                 to_date=date(2015, 12, 31))
    >>> event.occurrence_set.for_period(from_date=date(2015, 1, 1), exact=True)

### Sorting querysets

Event and Occurrence querysets can also be sorted by their next occurrence
using the `sort_by_next` method. By default this sorts instances by their
first occurrence; the optional `from_date` argument will sort by the next
occurrence after `from_date`. For example

    >>> Event.objects.all().sort_by_next()
    >>> event.occurrence_set.for_period(from_date=date(2015, 1, 1)) \
    >>>      .sort_by_next(date(2015, 1, 1))

Note that this method returns a sorted list, not a queryset.

## Custom repeat intervals

Occurrences can repeat using any interval that can be expressed as an
[rrulestr](https://labix.org/python-dateutil#head-e987b581aebacf25c7276d3e9214385a12a091f2).
To customise the available options, set `EVENTTOOLS_REPEAT_CHOICES` in
your django settings. The default value is

    EVENTTOOLS_REPEAT_CHOICES = (
        ("RRULE:FREQ=DAILY", 'Daily'),
        ("RRULE:FREQ=WEEKLY", 'Weekly'),
        ("RRULE:FREQ=MONTHLY", 'Monthly'),
        ("RRULE:FREQ=YEARLY", 'Yearly'),
    )

Set `EVENTTOOLS_REPEAT_CHOICES = None` to make repeat a plain-text field.

## Running tests

Use tox (<https://pypi.python.org/pypi/tox>):

    > pip install tox
    > cd path-to/django-eventtools
    > tox
