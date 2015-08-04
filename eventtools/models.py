# -*- coding: utf-8 -*-

from dateutil import rrule
from datetime import timedelta, date, datetime

from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property


def first_item(gen):
    try:
        return gen.next()
    except StopIteration:
        return None


def as_datetime(d, end=False):
    if type(d) is date:
        date_args = tuple(d.timetuple())[:3]
        if end:
            time_args = (23, 59, 59)
        else:
            time_args = (0, 0, 0)
        return datetime(*(date_args + time_args))


class SortableQuerySet(models.QuerySet):
    """TODO"""
    
    def sort_by_next(self, start=None):
        """Sort the queryset by next_occurrence. Note that this method 
           necessarily returns a list, not a queryset. """  
         
        def sort_key(obj):
            occ = obj.next_occurrence(start)
            return occ[0] if occ else None
        return sorted([e for e in self if sort_key(e)], key=sort_key)


class EventQuerySet(SortableQuerySet):
    def for_period(self, from_date=None, to_date=None):
        # TODO this is probably very inefficient. Investigate writing a postgres
        # function to handle recurring dates, or caching, or only working in 
        # occurrences rather than querying the events table?
        # worst case, store next_occurrence on the events table and update on
        # cron
        
        approx_qs = self
        
        # first winnow down as much as possible via queryset filtering
        if from_date:
            from_date = as_datetime(from_date)
            approx_qs = approx_qs.filter(
                Q(occurrence__end__gte=from_date) | \
                (Q(occurrence__repeat__isnull=False) & \
                 (Q(occurrence__repeat_until__gte=from_date) | \
                  Q(occurrence__repeat_until__isnull=True)))).distinct()
        
        if to_date:
            to_date = as_datetime(to_date, True)
            approx_qs = approx_qs.filter(
                Q(occurrence__start__lte=to_date)).distinct()
        
        # then work out actual results based on occurrences
        pks = []
        for event in approx_qs:
            occs = event.all_occurrences(start=from_date, end=to_date)
            if first_item(occs):
                pks.append(event.pk)
        
        # and then filter the queryset
        return self.filter(pk__in=pks)


class EventManager(models.Manager.from_queryset(EventQuerySet)):
    use_for_related_fields = True


class BaseEvent(models.Model):
    objects = EventManager()
    
    def all_occurrences(self, start=None, end=None, limit=None):
        return self.occurrence_set.all_occurrences(start, end, False, 
                                                   limit=limit)
    
    def next_occurrence(self, start=None):
        if not start:
            start = datetime.now()
        return first_item(self.all_occurrences(start=start))
    
    class Meta:
        abstract = True
    

class OccurrenceQuerySet(SortableQuerySet):
    def for_period(self, from_date=None, to_date=None):
        # TODO optimise as with EventQuerySet
        
        approx_qs = self
        
        # first winnow down as much as possible via queryset filtering
        if from_date:
            from_date = as_datetime(from_date)
            approx_qs = approx_qs.filter(
                Q(end__gte=from_date) | \
                (Q(repeat__isnull=False) & \
                 (Q(repeat_until__gte=from_date) | \
                  Q(repeat_until__isnull=True)))).distinct()
        
        if to_date:
            to_date = as_datetime(to_date, True)
            approx_qs = approx_qs.filter(Q(start__lte=to_date)).distinct()
        
        # then work out actual results based on occurrences
        pks = []
        for occurrence in approx_qs:
            occs = occurrence.all_occurrences(start=from_date, end=to_date)
            if first_item(occs):
                pks.append(occurrence.pk)
        
        # and then filter the queryset
        return self.filter(pk__in=pks)
    
    def all_occurrences(self, start=None, end=None, include_event=True, 
                        limit=None):
        """Return a generator yielding a (start, end) tuple for all occurrence
           dates in the queryset, taking repetition into account, up to a
           maximum limit if specified. """
         
        count = 0
        grouped = []
        for occ in self:
            gen = occ.all_occurrences(start, end)
            try:
                next_date = gen.next()
            except StopIteration:
                pass
            else:
                grouped.append([occ, gen, next_date])
        
        while limit is None or count < limit:
            # work out which generator will yield the earliest date (based on
            # start; end is ignored)
            next_group = None
            for group in grouped:
                if not next_group or group[2][0] < next_group[2][0]:
                    next_group = group
            
            if not next_group:
                return
            
            # yield the next (start, end) pair, with event if needed
            yield next_group[2] + ((occ.event, ) if include_event else ())
            count += 1
            
            # update the group, so we don't keep yielding the same date
            try:
                next_group[2] = next_group[1].next()
            except StopIteration:
                grouped.remove(next_group)


class OccurrenceManager(models.Manager.from_queryset(OccurrenceQuerySet)):
    use_for_related_fields = True


class BaseOccurrence(models.Model):
    REPEAT_MAX = 200
    
    REPEAT_CHOICES = (
        (rrule.DAILY, 'Daily'),
        (rrule.WEEKLY, 'Weekly'),
        (rrule.MONTHLY, 'Monthly'),
        (rrule.YEARLY, 'Yearly'),
    )
    
    start = models.DateTimeField(db_index=True)
    end = models.DateTimeField(db_index=True)
    
    repeat = models.PositiveSmallIntegerField(choices=REPEAT_CHOICES,
                                              null=True, blank=True)
    repeat_until = models.DateField(null=True, blank=True)
    
    def clean(self):
        if self.start and self.end and self.start >= self.end:
            msg = u"End must be after start"
            raise ValidationError(msg)
        
        if self.repeat_until and self.repeat is None:
            msg = u"Select a repeat interval, or remove the 'repeat until' date"
            raise ValidationError(msg)
        
        if self.repeat_until and self.repeat_until < self.start.date():
            msg = u"'Repeat until' cannot be before the first occurrence"
            raise ValidationError(msg)

    objects = OccurrenceManager()
    
    def next_occurrence(self, start=None):
        if not start:
            start = datetime.now()
        return first_item(self.all_occurrences(start=start))
    
    def all_occurrences(self, start=None, end=None):
        """Return a generator yielding a (start, end) tuple for all dates
           for this occurrence, taking repetition into account. 
           TODO handle start efficiently
           """
        
        start = start and as_datetime(start)
        end = end and as_datetime(end, True)
        
        if self.repeat is None: # might be 0
            if (not start or self.start >= start) and \
               (not end or self.start <= end):
                yield (self.start, self.end)
        else:
            delta = self.end - self.start
            until = self.repeat_until + timedelta(1) \
                            if self.repeat_until else None
            repeater = rrule.rrule(self.repeat, dtstart=self.start, 
                                   until=until, count=self.REPEAT_MAX)
            
            for occ_start in repeater:
                if (not start or occ_start >= start) and \
                   (not end or self.start <= end):
                    yield (occ_start, occ_start + delta)

    class Meta:
        ordering = ('start', 'end')
        abstract = True

    def __unicode__(self):
        return '%s' % (self.start)
