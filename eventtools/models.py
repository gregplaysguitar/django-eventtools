# -*- coding: utf-8 -*-

from dateutil import rrule
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q, Case, When, Value
from django.core.exceptions import ValidationError
from django.utils.timezone import get_default_timezone


# set EVENTTOOLS_REPEAT_CHOICES = None to make this a plain textfield
REPEAT_CHOICES = getattr(settings, 'EVENTTOOLS_REPEAT_CHOICES', (
    ("RRULE:FREQ=DAILY", 'Daily'),
    ("RRULE:FREQ=WEEKLY", 'Weekly'),
    ("RRULE:FREQ=MONTHLY", 'Monthly'),
    ("RRULE:FREQ=YEARLY", 'Yearly'),
))
REPEAT_MAX = 200


def max_future_date():
    return datetime(date.today().year + 10, 1, 1, 0, 0)


def first_item(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


def is_naive(dt):
    """
    Returns true if the passed datetime has no timezone data.
    Pattern is from the python datetime module documentation.
    """
    return not (dt.tzinfo is not None and
                dt.tzinfo.utcoffset(dt) is not None)


def convert_tz(dt):
    """
    Convert a naive datetime argument to a tz-aware datetime. Uses the local
    timezone if defined in DJango, otherwise UTC is used. If the passed value
    is not a datetime instance, it is returned unchanged.
    """
    tz = get_default_timezone()
    if is_naive(dt) and settings.USE_TZ and hasattr(tz, 'localize'):
        return get_default_timezone().localize(dt)
    return dt


def as_datetime(d, end=False):
    """Normalise a date/datetime argument to a datetime for use in filters

    If a date is passed, it will be converted to a datetime with the time set
    to 0:00, or 23:59:59 if end is True. Datetime object returned is naive."""
    if type(d) is date:
        date_args = tuple(d.timetuple())[:3]
        if end:
            time_args = (23, 59, 59)
        else:
            time_args = (0, 0, 0)
        value = datetime(*(date_args + time_args))

    # otherwise assume it's a datetime
    else:
        value = d
    return value


def strip_tz(dt):
    """
    Removes timezone information from a passed datetime. If localize is true,
    the resulting time is calculated before being made naive to ensure correct
    calculation of recurrences.

    Passed values that are not datetime instances are returned unchanged.
    """
    if not isinstance(dt, datetime):
        return dt

    localtz = get_default_timezone()
    if settings.USE_TZ and hasattr(localtz, "normalize"):
        dt = localtz.normalize(dt)

    # Now destroy timezone data.
    naive_date = dt.replace(tzinfo=None)

    return naive_date


def combine_occurrences(generators, limit):
    """Merge the occurrences in two or more generators, in date order.

       Returns a generator. """

    count = 0
    grouped = []
    for gen in generators:
        try:
            next_date = tuple([strip_tz(x) for x in next(gen)])
        except StopIteration:
            pass
        else:
            grouped.append({'generator': gen, 'next': next_date})

    while limit is None or count < limit:
        # all generators must have finished if there are no groups
        if not len(grouped):
            return

        # work out which generator will yield the earliest date (based on
        # start - end is ignored)
        next_group = None
        for group in grouped:
            if not next_group or group['next'][0] < next_group['next'][0]:
                next_group = group

        # yield the next (start, end) pair, with occurrence data
        yield (convert_tz(next_group['next'][0]),
               convert_tz(next_group['next'][1]), next_group['next'][2])
        count += 1

        # update the group's next item, so we don't keep yielding the same date
        try:
            next_group['next'] = next(next_group['generator'])
        except StopIteration:
            # remove the group if there's none left
            grouped.remove(next_group)


def filter_invalid(approx_qs, from_date, to_date):
    """Filter out any results from the queryset which do not have an occurrence
       within the given range. """

    # work out what to exclude based on occurrences
    exclude_pks = []
    for obj in approx_qs:
        if not obj.next_occurrence(from_date=from_date, to_date=to_date):
            exclude_pks.append(obj.pk)

    # and then apply the filtering to the queryset itself
    return approx_qs.exclude(pk__in=exclude_pks)


class BaseQuerySet(models.QuerySet):
    """Base QuerySet for models which have occurrences. """

    def for_period(self, from_date=None, to_date=None, exact=False):
        # subclasses should implement this
        raise NotImplementedError()

    def sort_by_next(self, from_date=None):
        """Sort the queryset by next_occurrence.

        Note that this method necessarily returns a list, not a queryset. """

        def sort_key(obj):
            occ = obj.next_occurrence(from_date=from_date)
            return occ[0] if occ else None
        return sorted([e for e in self if sort_key(e)], key=sort_key)

    def all_occurrences(self, from_date=None, to_date=None, limit=None):
        """Return a generator yielding a (start, end) tuple for all occurrence
           dates in the queryset, taking repetition into account, up to a
           maximum limit if specified. """

        # winnow out events which are definitely invalid
        qs = self.for_period(from_date, to_date)

        return combine_occurrences(
            (obj.all_occurrences(from_date, to_date)
             for obj in qs), limit)


class BaseModel(models.Model):
    """Abstract model providing common occurrence-related functionality. """

    def all_occurrences(self, from_date=None, to_date=None):
        raise NotImplementedError()

    def next_occurrence(self, from_date=None, to_date=None):
        """Return next occurrence as a (start, end) tuple for this instance,
           between from_date and to_date, taking repetition into account. """
        if not from_date:
            from_date = convert_tz(datetime.now())
        return first_item(
            self.all_occurrences(from_date=from_date, to_date=to_date))

    def first_occurrence(self):
        """Return first occurrence as a (start, end) tuple for this instance.
        """
        return first_item(self.all_occurrences())

    class Meta:
        abstract = True


class EventQuerySet(BaseQuerySet):
    """QuerySet for BaseEvent subclasses. """

    def for_period(self, from_date=None, to_date=None, exact=False):
        """Filter by the given dates, returning a queryset of Occurrence
           instances with occurrences falling within the range.

           Due to uncertainty with repetitions, from_date filtering is only an
           approximation. If exact results are needed, pass exact=True - this
           will use occurrences to exclude invalid results, but may be very
           slow, especially for large querysets. """

        filtered_qs = self

        # to_date filtering is accurate
        if to_date:
            to_date = as_datetime(to_date, True)
            filtered_qs = filtered_qs.filter(
                Q(occurrence__start__lte=to_date)).distinct()

        if from_date:
            # but from_date isn't, due to uncertainty with repetitions, so
            # just winnow down as much as possible via queryset filtering
            from_date = as_datetime(from_date)
            filtered_qs = filtered_qs.filter(
                Q(occurrence__end__isnull=False,
                  occurrence__end__gte=from_date) |
                Q(occurrence__start__gte=from_date) |
                (~Q(occurrence__repeat='') &
                 (Q(occurrence__repeat_until__gte=from_date) |
                  Q(occurrence__repeat_until__isnull=True)))).distinct()

            # filter out invalid results if requested
            if exact:
                filtered_qs = filter_invalid(filtered_qs, from_date, to_date)

        return filtered_qs


class EventManager(models.Manager.from_queryset(EventQuerySet)):
    use_for_related_fields = True


class BaseEvent(BaseModel):
    """Abstract model providing occurrence-related methods for events.

       Subclasses should have a related BaseOccurrence subclass. """

    objects = EventManager()

    def all_occurrences(self, from_date=None, to_date=None, limit=None):
        """Return a generator yielding a (start, end) tuple for all dates
           for this event, taking repetition into account. """
        return self.occurrence_set.all_occurrences(from_date, to_date,
                                                   limit=limit)

    class Meta:
        abstract = True


class OccurrenceQuerySet(BaseQuerySet):
    """QuerySet for BaseOccurrence subclasses. """

    def for_period(self, from_date=None, to_date=None, exact=False):
        """Filter by the given dates, returning a queryset of Occurrence
           instances with occurrences falling within the range.

           Due to uncertainty with repetitions, from_date filtering is only an
           approximation. If exact results are needed, pass exact=True - this
           will use occurrences to exclude invalid results, but may be very
           slow, especially for large querysets. """

        filtered_qs = self

        # to_date filtering is accurate
        if to_date:
            to_date = as_datetime(to_date, True)
            filtered_qs = filtered_qs.filter(Q(start__lte=to_date)).distinct()

        if from_date:
            # but from_date isn't, due to uncertainty with repetitions, so
            # just winnow down as much as possible via queryset filtering
            from_date = as_datetime(from_date)
            filtered_qs = filtered_qs.filter(
                Q(end__isnull=False, end__gte=from_date) |
                Q(start__gte=from_date) |
                (~Q(repeat='') &
                 (Q(repeat_until__gte=from_date) |
                  Q(repeat_until__isnull=True)))).distinct()

            # filter out invalid results if requested
            if exact:
                filtered_qs = filter_invalid(filtered_qs, from_date, to_date)

        return filtered_qs


class OccurrenceManager(models.Manager.from_queryset(OccurrenceQuerySet)):
    use_for_related_fields = True

    def migrate_integer_repeat(self):
        self.update(repeat=Case(
            When(repeat=rrule.YEARLY,
                 then=Value("RRULE:FREQ=YEARLY")),
            When(repeat=rrule.MONTHLY,
                 then=Value("RRULE:FREQ=MONTHLY")),
            When(repeat=rrule.WEEKLY,
                 then=Value("RRULE:FREQ=WEEKLY")),
            When(repeat=rrule.DAILY,
                 then=Value("RRULE:FREQ=DAILY")),
            default=Value(""),
        ))


class ChoiceTextField(models.TextField):
    """Textfield which uses a Select widget if it has choices specified. """

    def formfield(self, **kwargs):
        if self.choices:
            # this overrides the TextField's preference for a Textarea widget,
            # allowing the ModelForm to decide which field to use
            kwargs['widget'] = None
        return super(ChoiceTextField, self).formfield(**kwargs)


class BaseOccurrence(BaseModel):
    """Abstract model providing occurrence-related methods for occurrences.

       Subclasses will usually have a ForeignKey pointing to a BaseEvent
       subclass. """

    start = models.DateTimeField(db_index=True)
    end = models.DateTimeField(db_index=True, null=True, blank=True)

    repeat = ChoiceTextField(choices=REPEAT_CHOICES, default='', blank=True)
    repeat_until = models.DateField(null=True, blank=True)

    def clean(self):
        if self.start and self.end and self.start >= self.end:
            msg = u"End must be after start"
            raise ValidationError(msg)

        if self.repeat_until and self.repeat is None:
            msg = u"Select a repeat interval, or remove the " \
                  u"'repeat until' date"
            raise ValidationError(msg)

        if self.start and self.repeat_until and \
           self.repeat_until < self.start.date():
            msg = u"'Repeat until' cannot be before the first occurrence"
            raise ValidationError(msg)

    objects = OccurrenceManager()

    def all_occurrences(self, from_date=None, to_date=None, limit=REPEAT_MAX):
        """Return a generator yielding a (start, end) tuple for all dates
           for this occurrence, taking repetition into account. """

        if not self.start:
            return

        from_date = from_date and strip_tz(as_datetime(from_date))
        to_date = to_date and strip_tz(as_datetime(to_date, True))
        naive_start = strip_tz(self.start)
        naive_end = strip_tz(self.end)

        if not self.repeat:
            if (not from_date or naive_start >= from_date or
                (naive_end and naive_end >= from_date)) and \
               (not to_date or naive_start <= to_date):
                yield (self.start, self.end, self.occurrence_data)
        else:
            delta = (self.end - self.start) if self.end else timedelta(0)
            repeater = self.get_repeater()

            # start from the first occurrence at the earliest
            if not from_date or from_date < naive_start:
                from_date = naive_start

            # look until the last occurrence, up to an arbitrary maximum date
            if self.repeat_until and (
                    not to_date or
                    as_datetime(self.repeat_until, True) < to_date):
                to_date = as_datetime(self.repeat_until, True)
            elif not to_date:
                to_date = max_future_date()

            # start is used for the filter, so modify from_date to take the
            # occurrence length into account
            from_date -= delta

            repeater = repeater.between(from_date, to_date, inc=True)

            count = 0
            for occ_start in repeater:
                count += 1
                if count > limit:
                    return

                yield (convert_tz(occ_start), convert_tz(occ_start + delta),
                       self.occurrence_data)

    def get_repeater(self):
        # Timings to get all_occurrences() for a set of 2500 Occurrence objects
        # with rrule.DAILY repeat
        # Without method call (inline repeat)
        # CPU times: user 53.4 s, sys: 76 ms, total: 53.4 s
        # Wall time: 55.8 s

        # With method call
        # CPU times: user 53.5 s, sys: 100 ms, total: 53.6 s
        # Wall time: 56 s
        # The subclassing benefit seems much larger than the performance hit
        start = strip_tz(self.start)
        return rrule.rrulestr(self.repeat, dtstart=start)

    @property
    def occurrence_data(self):
        return self

    class Meta:
        ordering = ('start', 'end')
        abstract = True

    def __unicode__(self):
        return u"%s" % (self.start,)
