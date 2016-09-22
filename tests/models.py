from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from eventtools.models import BaseEvent, BaseOccurrence


@python_2_unicode_compatible
class Event(BaseEvent):
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title


class Occurrence(BaseOccurrence):
    event = models.ForeignKey(Event)
