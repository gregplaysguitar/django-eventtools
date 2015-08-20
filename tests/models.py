from django.db import models

from eventtools.models import BaseEvent, BaseOccurrence


class Event(BaseEvent):
    title = models.CharField(max_length=100)

    def __unicode__(self):
        return self.title


class Occurrence(BaseOccurrence):
    event = models.ForeignKey(Event)

    @property
    def occurrence_data(self):
        return {
            'event': self.event,
        }
