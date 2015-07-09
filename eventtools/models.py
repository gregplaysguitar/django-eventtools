# -*- coding: utf-8 -*-

from dateutil import rrule
from datetime import timedelta, date, datetime

from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property


class EventQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        from_date = kwargs.pop('from_date', None)
        to_date = kwargs.pop('to_date', None)
        qs = super(EventQuerySet, self).filter(*args, **kwargs)
        
        # TODO this is probably very inefficient. Investigate writing a postgres
        # function to handle recurring dates, or caching, or only working in 
        # occurrences rather than querying the events table?
        # worst case, store next_occurrence on the events table and update on
        # cron
        
        if from_date:
            if type(from_date) is date:
                from_date = datetime(*tuple(from_date.timetuple())[:3])
            qs = qs.filter(
                Q(occurrence__end__gte=from_date) | \
                (Q(occurrence__repeat__isnull=False) & \
                 (Q(occurrence__repeat_until__gte=from_date) | \
                  Q(occurrence__repeat_until__isnull=True)))).distinct()
        
        if to_date:
            if type(to_date) is date:
                args = tuple(to_date.timetuple())[:3] + (23, 59, 59)
                to_date = datetime(*args)
            qs = qs.filter(Q(occurrence__start__lte=to_date)).distinct()
        
        return qs
    
    def sort_by_next(self, start=None):
        """Sort the queryset by next_occurrence. Note that this method 
           necessarily returns a list, not a queryset. """  
         
        def sort_key(event):
            occ = event.next_occurrence(start)
            return occ[0] if occ else None
        return sorted([e for e in self if sort_key(e)], key=sort_key)


class EventManager(models.Manager.from_queryset(EventQuerySet)):
    use_for_related_fields = True


class BaseEvent(models.Model):
    objects = EventManager()
    
    def all_occurrences(self, start=None):
        return self.occurrence_set.all_occurrences(start, False)
    
    def next_occurrence(self, start=None):
        if not start:
            start = datetime.now()
        try:
            return self.all_occurrences(start=start).next()
        except StopIteration:
            return None
    
    class Meta:
        abstract = True
    

class OccurrenceQuerySet(models.QuerySet):
    def future(self):
        return self.all_occurrences(datetime.now())
    
    def all_occurrences(self, start=None, end=None, include_event=True):
        """Return a generator yielding a (start, end) tuple for all occurrence
           dates in the queryset, taking repetition into account. """
         
        grouped = []
        for occ in self:
            gen = occ.all_occurrences(start)
            try:
                next_date = gen.next()
            except StopIteration:
                pass
            else:
                grouped.append([occ, gen, next_date])
        
        while True:
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
        if self.start >= self.end:
            msg = u"End must be after start"
            raise ValidationError(msg)
        
        if self.repeat_until and self.repeat is None:
            msg = u"Select a repeat interval, or remove the 'repeat until' date"
            raise ValidationError(msg)
        
        if self.repeat_until and self.repeat_until < self.start.date():
            msg = u"'Repeat until' cannot be before the first occurrence"
            raise ValidationError(msg)

    objects = OccurrenceManager()
    
    def all_occurrences(self, start=None):
        """Return a generator yielding a (start, end) tuple for all dates
           for this occurrence, taking repetition into account. 
           TODO handle start efficiently
           """
        
        if self.repeat is None: # might be 0
            if not start or self.start >= start:
                yield (self.start, self.end)
        else:
            delta = self.end - self.start
            until = self.repeat_until + timedelta(1) \
                            if self.repeat_until else None
            repeater = rrule.rrule(self.repeat, dtstart=self.start, 
                                   until=until, count=self.REPEAT_MAX)
            
            for occ_start in repeater:
                if not start or occ_start >= start:
                    yield (occ_start, occ_start + delta)

    class Meta:
        ordering = ('start', 'end')
        abstract = True

    def __unicode__(self):
        return '%s' % (self.start)
