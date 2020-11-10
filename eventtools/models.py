# -*- coding: utf-8 -*-

from dateutil import rrule
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q, Case, When, Value
from django.core.exceptions import ValidationError

from django.utils.timezone import make_aware, is_naive, make_naive, is_aware
from django.utils.translation import gettext_lazy as _

from six import python_2_unicode_compatible


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


def default_aware(dt):
    """Convert a naive datetime argument to a tz-aware datetime, if tz support
       is enabled. """

    if settings.USE_TZ and is_naive(dt):
        return make_aware(dt)

    # if timezone support disabled, assume only naive datetimes are used
    return dt


def default_naive(dt):
    """Convert an aware datetime argument to naive, if tz support
       is enabled. """

    if settings.USE_TZ and is_aware(dt):
        return make_naive(dt)

    # if timezone support disabled, assume only naive datetimes are used
    return dt


def as_datetime(d, end=False):
    """Normalise a date/datetime argument to a datetime for use in filters

    If a date is passed, it will be converted to a datetime with the time set
    to 0:00, or 23:59:59 if end is True."""

    if type(d) is date:
        date_args = tuple(d.timetuple())[:3]
        if end:
            time_args = (23, 59, 59)
        else:
            time_args = (0, 0, 0)
        new_value = datetime(*(date_args + time_args))
        return default_aware(new_value)
    # otherwise assume it's a datetime
    return default_aware(d)


def combine_occurrences(generators, limit):
    """Merge the occurrences in two or more generators, in date order.

       Returns a generator. """

    count = 0
    grouped = []
    for gen in generators:
        try:
            next_date = next(gen)
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
        yield next_group['next']
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


def filter_from(qs, from_date, q_func=Q):
    """Filter a queryset by from_date. May still contain false positives due to
       uncertainty with repetitions. """

    from_date = as_datetime(from_date)
    return qs.filter(
        q_func(end__isnull=False, end__gte=from_date) |
        q_func(start__gte=from_date) |
        (~q_func(repeat='') & (q_func(repeat_until__gte=from_date) |
         q_func(repeat_until__isnull=True)))).distinct()


class OccurrenceMixin(object):
    """Class mixin providing common occurrence-related functionality. """

    def all_occurrences(self, from_date=None, to_date=None):
        raise NotImplementedError()

    def next_occurrence(self, from_date=None, to_date=None):
        """Return next occurrence as a (start, end) tuple for this instance,
           between from_date and to_date, taking repetition into account. """
        if not from_date:
            from_date = datetime.now()
        return first_item(
            self.all_occurrences(from_date=from_date, to_date=to_date))

    def first_occurrence(self):
        """Return first occurrence as a (start, end) tuple for this instance.
        """
        return first_item(self.all_occurrences())


class BaseQuerySet(models.QuerySet, OccurrenceMixin):
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
            (obj.all_occurrences(from_date, to_date) for obj in qs), limit)


class BaseModel(models.Model, OccurrenceMixin):
    """Abstract model providing common occurrence-related functionality. """

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
        prefix = self.model.occurrence_filter_prefix()

        def wrap_q(**kwargs):
            """Prepend the related model name to the filter keys. """

            return Q(**{'%s__%s' % (prefix, k): v for k, v in kwargs.items()})

        # to_date filtering is accurate
        if to_date:
            to_date = as_datetime(to_date, True)
            filtered_qs = filtered_qs.filter(
                wrap_q(start__lte=to_date)).distinct()

        if from_date:
            # but from_date isn't, due to uncertainty with repetitions, so
            # just winnow down as much as possible via queryset filtering
            filtered_qs = filter_from(filtered_qs, from_date, wrap_q)

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

    @classmethod
    def get_occurrence_relation(cls):
        """Get the occurrence relation for this class - use the first if
           there's more than one. """

        # get all related occurrence fields
        relations = [rel for rel in cls._meta.get_fields()
                     if isinstance(rel, models.ManyToOneRel) and
                     issubclass(rel.related_model, BaseOccurrence)]

        # assume there's only one
        return relations[0]

    @classmethod
    def occurrence_filter_prefix(cls):
        rel = cls.get_occurrence_relation()
        return rel.name

    def get_related_occurrences(self):
        rel = self.get_occurrence_relation()
        return getattr(self, rel.get_accessor_name()).all()

    def all_occurrences(self, from_date=None, to_date=None, limit=None):
        """Return a generator yielding a (start, end) tuple for all dates
           for this event, taking repetition into account. """

        return self.get_related_occurrences().all_occurrences(
            from_date, to_date, limit=limit)

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
            filtered_qs = filter_from(filtered_qs, from_date)

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


@python_2_unicode_compatible
class BaseOccurrence(BaseModel):
    """Abstract model providing occurrence-related methods for occurrences.

       Subclasses will usually have a ForeignKey pointing to a BaseEvent
       subclass. """

    start = models.DateTimeField(db_index=True, verbose_name=_('start'))
    end = models.DateTimeField(
        db_index=True, null=True, blank=True, verbose_name=_('end'))

    repeat = ChoiceTextField(
        choices=REPEAT_CHOICES, default='', blank=True,
        verbose_name=_('repeat'))
    repeat_until = models.DateField(
        null=True, blank=True, verbose_name=_('repeat_until'))

    def clean(self):
        if self.start and self.end and self.start >= self.end:
            msg = u"End must be after start"
            raise ValidationError(msg)

        if self.repeat_until and not self.repeat:
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

        from_date = from_date and as_datetime(from_date)
        to_date = to_date and as_datetime(to_date, True)

        if not self.repeat:
            if (not from_date or self.start >= from_date or
                (self.end and self.end >= from_date)) and \
               (not to_date or self.start <= to_date):
                yield (self.start, self.end, self.occurrence_data)
        else:
            delta = (self.end - self.start) if self.end else timedelta(0)
            repeater = self.get_repeater()

            # start from the first occurrence at the earliest
            if not from_date or from_date < self.start:
                from_date = self.start

            # look until the last occurrence, up to an arbitrary maximum date
            if self.repeat_until and (
                    not to_date or
                    as_datetime(self.repeat_until, True) < to_date):
                to_date = as_datetime(self.repeat_until, True)
            elif not to_date:
                to_date = default_aware(max_future_date())

            # start is used for the filter, so modify from_date to take the
            # occurrence length into account
            from_date -= delta

            # always send naive datetimes to the repeater
            repeater = repeater.between(default_naive(from_date),
                                        default_naive(to_date), inc=True)

            count = 0
            for occ_start in repeater:
                count += 1
                if count > limit:
                    return

                # make naive results aware
                occ_start = default_aware(occ_start)
                yield (occ_start, occ_start + delta, self.occurrence_data)

    def get_repeater(self):
        """Get rruleset instance representing this occurrence's repetitions.

        Subclasses may override this method for custom repeat behaviour.
        """

        ruleset = rrule.rruleset()
        rule = rrule.rrulestr(self.repeat, dtstart=default_naive(self.start))
        ruleset.rrule(rule)
        return ruleset

    @property
    def occurrence_data(self):
        return self

    class Meta:
        ordering = ('start', 'end')
        abstract = True

    def __str__(self):
        return u"%s" % (self.start)
