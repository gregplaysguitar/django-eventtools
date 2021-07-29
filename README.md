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

```python
from django.db import models

from eventtools.models import BaseEvent, BaseOccurrence


class MyEvent(BaseEvent):
    title = models.CharField(max_length=100)


class MyOccurrence(BaseOccurrence):
    event = models.ForeignKey(MyEvent)
```

## Usage

Create a sample event & occurrences

    >>> from datetime import datetime
    >>> from myapp.models import MyEvent
    >>> event = MyEvent.objects.create(title='Test event')
    >>> once_off = MyOccurrence.objects.create(
            event=event,
            start=datetime(2016, 1, 1, 12, 0),
            end=datetime(2016, 1, 1, 2, 0))
    >>> christmas = MyOccurrence.objects.create(
            event=event,
            start=datetime(2015, 12, 25, 7, 0),
            end=datetime(2015, 12, 25, 22, 0),
            repeat='RRULE:FREQ=YEARLY')
    >>> daily = MyOccurrence.objects.create(
            event=event,
            start=datetime(2016, 1, 1, 7, 0),
            end=datetime(2016, 1, 1, 8, 0),
            repeat='RRULE:FREQ=DAILY')

Event and Occurrence instances, and their associated querysets, all support
the `all_occurrences` method, which takes two optional arguments - `from_date`
and `to_date`, which may be dates or datetimes. `from_date` and `to_date` 
default to `None`. The method returns a python generator
yielding tuples in the format `(start, end, instance)` - for example:

    >>> MyEvent.objects.all().all_occurrences()
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

Event and Occurrence querysets can be filtered, but note that a `from_date`
filtered queryset may contain false positives because it's not possible to tell
for sure if a event will happen _after_ a certain date without evaluating
repetition rules, meaning it can't be part of a database query. If you need a
queryset filtered exactly, pass `exact=True` - this will filter the queryset by
id, based on generated occurrences. Be careful with this option though as it
may be very slow and/or CPU-hungry. For example

    >>> MyEvent.objects.for_period(from_date=date(2015, 1, 1),
                                 to_date=date(2015, 12, 31))
    >>> event.occurrence_set.for_period(from_date=date(2015, 1, 1), exact=True)

Note `to_date` filtering is always accurate, because the query only needs to
consider the event's first occurrence.

### Sorting querysets

Event and Occurrence querysets can also be sorted by their next occurrence
using the `sort_by_next` method. By default this sorts instances by their
first occurrence; the optional `from_date` argument will sort by the next
occurrence after `from_date`. For example

    >>> MyEvent.objects.all().sort_by_next()
    >>> event.occurrence_set.for_period(from_date=date(2015, 1, 1)) \
    >>>      .sort_by_next(date(2015, 1, 1))

Note that this method returns a sorted list, not a queryset.

## Custom repeat intervals

Occurrences can repeat using any interval that can be expressed as an
[rrulestr](https://labix.org/python-dateutil#head-e987b581aebacf25c7276d3e9214385a12a091f2).
To customise the available options, set `EVENTTOOLS_REPEAT_CHOICES` in
your django settings. The default value is

```python
EVENTTOOLS_REPEAT_CHOICES = (
    ("RRULE:FREQ=DAILY", 'Daily'),
    ("RRULE:FREQ=WEEKLY", 'Weekly'),
    ("RRULE:FREQ=MONTHLY", 'Monthly'),
    ("RRULE:FREQ=YEARLY", 'Yearly'),
)
```

Set `EVENTTOOLS_REPEAT_CHOICES = None` to make repeat a plain-text field.

## Occurrence cancellations or modifications

Cancelling or modifying a single occurrence repetition is not currently supported, but can be implemented by overriding a couple of methods. For example, the following allows cancellations or one-off modifications to the start time of a repetition:

```python
from eventtools.models import (BaseEvent, BaseOccurrence, default_naive)
from django.db import models


class MyEvent(BaseEvent):
	pass


class MyEventOccurrence(BaseOccurrence):
    event = models.ForeignKey(MyEvent)
    overrides = models.ManyToManyField('MyEventOccurrenceOverride', blank=True)

    def get_repeater(self):
        rule = super().get_repeater()  # gets rruleset from parent method
        ruleset.rrule(rule)
        for override in self.overrides.all():
            ruleset.exdate(default_naive(override.start))  # remove occurrence
            if override.modified_start:  # reschedule occurrence if defined
                ruleset.rdate(default_naive(override.modified_start))
        return ruleset


class MyEventOccurrenceOverride(models.Model):
    start = models.DateTimeField()  # must match targeted repetition exactly
    # new start, leave blank to cancel
    modified_start = models.DateTimeField(blank=True, null=True)  
```

Note that start times must match exactly, so if the MyEventOccurrence start is changed, any previously-matching overrides will no longer be applied.

## Running tests

Use tox (<https://pypi.python.org/pypi/tox>):

    > pip install tox
    > cd path-to/django-eventtools
    > tox
